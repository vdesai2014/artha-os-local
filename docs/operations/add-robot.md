# Adding a new robot

Wiring a new robot is the biggest single integration. It touches types,
multiple services, the commander, the data recorder, the frontend.
Take it in layers; verify each layer alone before wiring it into the
next.

> **Agent rule for robot work.** You do not run coupon tests. You do
> not press buttons that move the robot. You write the test procedure,
> stage the exact commands the user should run, explain what to watch
> for, then wait for the user to execute. Every hardware-moving action
> is user-initiated, every single time, no matter how trivial. If the
> user says "just run it," confirm once more before proceeding. This is
> non-negotiable even late in a session when the pattern feels familiar.

## Target architecture

```
    +---------------+       +--------------+       +---------------+       +------+
    |   teleop /    |       |              |       |               |       |      |
    |   policy /    |------>|  commander   |------>|   safety      |------>| HAL  |
    |   sequences   |       |   (blend)    |       | (limits/slew) |       |      |
    +---------------+       +--------------+       +---------------+       +--+---+
                                                                              |
                                                                              v
                                                                       physical robot
                                                                              |
                                                                              v
                              +-------------+       +---------------+       +---+
                              | data_       |<------|               |<------|   |
                              | recorder    |       |   HAL telem   |       |   |
                              +-------------+       +-------+-------+       +---+
                                                            |
                                                            v
                                                     commander reads
                                                     robot/actual for
                                                     return-home, seeding
```

Topics (adapt names for your robot):

- `robot/raw_desired`   — commander → safety (what the policy wants)
- `robot/desired`       — safety → HAL (what's safe to execute)
- `robot/actual`        — HAL → everyone (telemetry)

## Step 1: Define the joint struct

Edit `core/types.py`. Pick N (joint count) and a command shape. Match
what your actuators actually accept (position? velocity? torque?
combinations?).

```python
NUM_JOINTS = 6  # your robot's joint count

class MyRobotState(ctypes.Structure):
    _fields_ = [
        ("timestamp",   ctypes.c_double),
        ("frame_id",    ctypes.c_uint64),
        ("position",    ctypes.c_double * NUM_JOINTS),
        ("velocity",    ctypes.c_double * NUM_JOINTS),
        ("torque",      ctypes.c_double * NUM_JOINTS),
        ("temperature", ctypes.c_double * NUM_JOINTS),
        ("fault",       ctypes.c_uint8  * NUM_JOINTS),
    ]

class MyRobotCommand(ctypes.Structure):
    _fields_ = [
        ("timestamp", ctypes.c_double),
        ("frame_id",  ctypes.c_uint64),
        ("position",  ctypes.c_double * NUM_JOINTS),
        ("velocity",  ctypes.c_double * NUM_JOINTS),
        ("torque",    ctypes.c_double * NUM_JOINTS),
    ]
```

Invariants: `timestamp` + `frame_id` must be the first two fields
(`ReaderManager` uses `frame_id` for staleness detection).

## Step 2: HAL service

The HAL owns the physical interface — CAN, Dynamixel SDK, serial,
Modbus, whatever your actuators speak. It:

- **Reads** raw telemetry at the bus rate, scales/offsets it into your
  joint convention, publishes `robot/actual`.
- **Writes** commands to the bus on new frames from `robot/desired`.

Follow `docs/operations/add-service.md` for the skeleton. Your
`main.py` opens the bus, builds `BlackboardWriter("robot/actual",
MyRobotState)` and `BlackboardReader("robot/desired", MyRobotCommand)`,
and ticks at whatever the bus comfortably handles (typically 250 Hz
for CAN, 50–200 Hz for Dynamixel).

**Stage a HAL validation plan for the user to run** before wiring the
HAL into anything else. Broadly, what you and the user want to see
yourselves convinced of:

- Telemetry matches reality. A `BlackboardReader` on `robot/actual`
  shows frames advancing; positions align with a physically-measured
  pose the user reports.
- Commands actually drive joints as expected, starting with the lowest
  possible stakes (small joint, low torque, safe starting position).
- Failure modes are tame. Power-cycling the robot mid-run either
  reconnects cleanly or dies cleanly so the supervisor can restart it;
  there's no zombie state that leaves motors energized.

Write the exact commands (standalone run line with env vars, the
snippet that publishes a test command, the reader line the user runs
in another terminal) and hand them to the user. Don't improvise the
procedure mid-session — discuss it with the user, agree on what's
being checked, then let them execute.

## Step 3: Safety layer

*Strongly recommended.* A service that sits between commander and HAL
and enforces invariants the policy / teleoperator shouldn't be
trusted with.

- Subscribes `robot/raw_desired`, publishes `robot/desired`.
- Also subscribes `robot/actual` so it can slew-limit relative to
  reality, not the last command.
- Enforces (at minimum): per-joint position limits, per-joint velocity
  limits (slew rate), temperature-based torque derating. Consider:
  self-collision envelope, cartesian workspace box, e-stop NATS
  subject.

A safety service typically has no internal state beyond the last
safe command and a few cached limits. Keep it simple — it's the
layer you'll want to convince yourself is correct.

**Stage a safety-layer validation plan** for the user to run. Broadly,
what you want evidence of:

- The output is *always* within spec, no matter how hostile the input.
  Intentionally bad `robot/raw_desired` commands (out-of-range, NaN,
  discontinuous jumps) should clamp cleanly.
- No glitches in normal conditions — the output under a realistic
  command stream looks continuous.
- The layer behaves the same on startup, after a restart, and after
  the HAL reconnects.

Route the safety output to a dummy reader (not the real HAL) during
this phase so there's no path to the physical robot while you're
probing it. Write the test commands for the user to execute; they run
the procedure and report back.

## Step 4: Wire commander

Edit `services/commander/main.py`:

- Change `STATE_TOPIC` to `"robot/actual"`, `COMMAND_TOPIC` to
  `"robot/raw_desired"` (so safety sits between commander and HAL).
- Update `NUM_JOINTS` and `HOME_POSITIONS` for your robot.
- Update `tx_cmd` to be an instance of your `MyRobotCommand`.
- Update `services.yaml` commander entry: `publishes
  robot/raw_desired: MyRobotCommand`, `subscribes robot/actual:
  MyRobotState`.

The commander's sequence runner, slew-limit, trickle, and policy_gate
mode all work unchanged — they operate on joint-array semantics.

If your robot has a specific teleop rig, add a `teleop` mode to the
state machine that reads from a leader topic (see the rev4 commander
example in git history for a reference shape).

## Step 5: Wire data_recorder

Edit `services/data_recorder/main.py` — add a `Source` entry to
`SOURCES` for each signal you want to record:

```python
Source(
    topic="robot/actual",
    type_name="MyRobotState",
    extract=lambda s: [float(s.position[i]) for i in range(NUM_JOINTS)],
    feature="observation.joint_positions",
    schema={"dtype": "float32", "shape": [NUM_JOINTS]},
    kind="column",
),
# + one per camera, one for action (robot/desired or robot/raw_desired,
# whichever you're training on), any other sensors.
```

Matching `services.yaml` subscribes for the recorder.

Preserve slow-sensor anchoring when you customize the recorder. Record only
when every source in `SOURCES` has advanced its `frame_id` since the previous
recorded sample, or explicitly document the resampling policy in that robot's
recorder code. In practice, the slowest camera/sensor should set the episode
step cadence; faster joint/action streams can be sampled at that cadence.

## Step 6: Controls page

Either:
- Edit `frontend/src/features/controls/pages/ControlsPage.tsx` in place
  — rebind `useTopic("robot/actual", "MyRobotState", 20)`, update
  joint count, video URLs, command buttons.
- Or ship a project-specific `frontend/ControlsPage.tsx` and let the
  agent overlay it at onboarding time (see `docs/onboarding-steps.md`
  §8c).

See `docs/operations/modify-frontend.md` for the hook surface.

## Multi-machine setup

iceoryx2 is shared-memory; SHM doesn't cross machines. If your HAL
runs on an onboard SBC but your policy inference lives on a desktop
GPU, you have two options:

1. **Run artha-os on each machine, bridge over NATS.** NATS spans
   hosts. Replicate `robot/actual` from the SBC to the desktop by
   having a small bridge service on each side that subscribes to
   local SHM and publishes its contents as NATS JSON (at a lower
   rate for bandwidth), and vice-versa for commands. The cloud
   manifest/run graph ties the two machines' data together.
2. **Single machine, remote bus access.** If latency permits, run
   everything on the desktop and have the HAL talk to the SBC via
   CAN-over-ethernet or similar.

Option 1 is more common for mobile robots. Start simple — just pair
a single pair of topics (state + command) before building a full
bitstream relay.

## Common first-boot issues

- Supervisor crash-loops the HAL because the bus isn't up → check
  power, cables, permissions on `/dev/ttyUSB*` or CAN interface.
- Joint positions look like noise → units/sign/offset mismatch in
  your scaling. Tape-measure a known pose, work backward.
- Joints twitch on startup → your HAL is writing before `robot/desired`
  has been seeded. Have the HAL hold the current actual position until
  it sees a fresh command (`frame_id` increment).
- Safety layer rejects everything → slew limit is too tight for your
  control rate, or the "safe starting" position is outside the valid
  range.
