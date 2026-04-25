# artha-os Guided Onboarding

This is the first-run script for a coding agent inside an `artha-os`
checkout. The goal is to give the user a working local runtime, then walk
them through the canonical grasp-pickup robot-learning demo.

Keep the user oriented. Before long installs or downloads, explain what is
about to happen, how long it may take, and what they should expect to see.
During onboarding, the agent is a guide first and installer second. Explain
the robot-learning infrastructure problems being solved as you work. Progress
is good, but silent command execution is a failed onboarding.

## 0. Explain The Tour

Tell the user:

- artha-os is an agent-first robot learning platform for local robots,
  datasets, runs, checkpoints, and cloud sharing.
- This walkthrough is the **grasp-pickup demo** — one application of the
  tool. The same primitives (typed SHM data plane, NATS control plane,
  local file-based store, agent-driven service wiring) generalize to other
  simulated robots and to real robot hardware.
- The base install brings up NATS, local_tool, the supervisor, and the
  frontend.
- The guided demo clones a MuJoCo grasp-pickup project from artha.bot,
  wires its sim/inference/frontend into the local runtime, and lets the
  user run an in-browser eval.
- Expect roughly 10-15 minutes for setup on a fresh machine, longer if
  Python, Node, Rust, or large checkpoint downloads are cold.

Ask for permission before continuing.

## 1. Install Dependencies

Run from the repo root.

```bash
python3 -m pip install --user -e .
python3 -m pip install --user mujoco torch torchvision einops
cd frontend && npm install && npm run build && cd -
```

Install `nats-server` if missing:

```bash
if ! command -v nats-server >/dev/null; then
  OS=$(uname -s | tr '[:upper:]' '[:lower:]')
  ARCH=$(uname -m | sed -e 's/x86_64/amd64/' -e 's/aarch64/arm64/')
  VER=$(python3 - <<'PY'
import json, urllib.request
print(json.load(urllib.request.urlopen("https://api.github.com/repos/nats-io/nats-server/releases/latest"))["tag_name"])
PY
)
  mkdir -p "$HOME/.local/bin"
  curl -fsSL "https://github.com/nats-io/nats-server/releases/download/${VER}/nats-server-${VER}-${OS}-${ARCH}.tar.gz" | tar -xz -C /tmp
  install -m755 "/tmp/nats-server-${VER}-${OS}-${ARCH}/nats-server" "$HOME/.local/bin/"
fi
nats-server --version
```

The video bridge is required — `video_bridge` is referenced
unconditionally in the demo `services.yaml` and serves the UI camera
streams. If Cargo is missing, ask the user for permission to install Rust
via rustup, then build.

```bash
if ! command -v cargo >/dev/null; then
  curl --proto '=https' --tlsv1.2 -fsSL https://sh.rustup.rs | sh -s -- -y --default-toolchain stable
  source "$HOME/.cargo/env"
fi
cd services/video_bridge && cargo build --release && cd -
```

If any dependency fails, read `docs/onboarding-steps.md` for fallback notes
and tell the user exactly what failed.

## 2. Prove The Base Runtime

Start the stock runtime and show that the agent can operate it.

```bash
artha up
artha status
```

Expected shape:

```text
nats          running
local_tool    running
supervisor    running
services:
  param_server  running
  bridge        running
```

Tell the user to open `http://127.0.0.1:8000`. Ask them to confirm the
frontend loads.

## 2.5 Post-Install Orientation

Before cloning the demo, pause and explain what the user now has.

Do not rush into the next command. The user may be new to robot learning,
so make the infrastructure problems concrete.

Explain:

- Robot-learning experiments rarely stay fixed. Users add cameras,
  footpedals, reward buttons, intervention controls, telemetry streams,
  and safety state.
- artha-os makes these additions mechanical: define the data shape, run a
  service, wire it into recording/control/UI, and restart the runtime.
- High-rate data such as images and joint state moves through typed SHM.
- Control-plane events such as eval start, intervention buttons, params,
  and service coordination move through NATS.
- The browser frontend is part of the experiment loop. It can subscribe
  to SHM through the bridge and publish commands, so data visualization
  and control UI can evolve with the experiment.
- `local_tool` stores projects, runs, manifests, episodes, files,
  checkpoints, and provenance in local robot-learning shapes.
- `push`, `pull`, and `clone` move code, data, and checkpoints between
  this machine, collaborators, and cloud GPU jobs.
- The important design choice is transparency: the system is small,
  file-based, API-driven, and inspectable by a coding agent. The agent can
  handle the operational muck while the user focuses on the research.

Then ask:

```text
Want me to continue into the grasp-pickup demo so you can see this loop end to end?
```

## 3. Clone The Grasp-Pickup Demo

**Narrate:** This is the cloud → local hop that makes the demo possible.
`artha clone` pulls the entire grasp-pickup project from artha.bot — code,
runs, manifests, episodes, and checkpoints — into the local store, with
fresh local IDs. Expect several minutes; the command prints a sync job
id and periodic file/byte progress while `local_tool` does the work in
the background.

Agent guardrails: use `artha clone`, not `/api/sync/plan` — plan is
structural and only `clone` output contains the authoritative execution
remaps. Sync is additive: clone never prunes files. If obsolete cloud
files need deletion later, use the cloud file-delete endpoints explicitly.

**Execute:**

```bash
artha clone proj_e5509f6a7a0443eb913be950c6a0fac9 --output /tmp/artha-grasp-clone.json
```

The file `/tmp/artha-grasp-clone.json` is the source of truth for the rest
of this session.

Now stop the stack before editing service definitions:

```bash
artha down
```

## 4. Add Demo SHM Types

**Narrate:** The artha-os data plane uses iceoryx2 shared memory with
typed ctypes structs — same memory layout in every service that touches
a topic, sub-millisecond latency. The demo needs three: a 7-DOF robot
state, a 7-DOF robot command, and a 921600-byte camera frame (sized for
up to 640×480×3 RGB). Adding a typed topic to artha-os is exactly this:
drop a struct in `core/types.py` and restart.

**Execute:**

```bash
python3 - <<'PY'
from pathlib import Path

p = Path("core/types.py")
s = p.read_text()
if "class RobStrideState" not in s:
    s += '''


NUM_JOINTS = 7


class RobStrideState(ctypes.Structure):
    _fields_ = [
        ("timestamp", ctypes.c_double),
        ("frame_id", ctypes.c_uint64),
        ("position", ctypes.c_double * NUM_JOINTS),
        ("velocity", ctypes.c_double * NUM_JOINTS),
        ("torque", ctypes.c_double * NUM_JOINTS),
        ("temperature", ctypes.c_double * NUM_JOINTS),
        ("enabled", ctypes.c_uint8 * NUM_JOINTS),
    ]


class RobStrideCommand(ctypes.Structure):
    _fields_ = [
        ("timestamp", ctypes.c_double),
        ("frame_id", ctypes.c_uint64),
        ("position", ctypes.c_double * NUM_JOINTS),
        ("velocity", ctypes.c_double * NUM_JOINTS),
        ("torque", ctypes.c_double * NUM_JOINTS),
    ]


class CameraFrame(ctypes.Structure):
    _fields_ = [
        ("timestamp", ctypes.c_double),
        ("frame_id", ctypes.c_uint64),
        ("width", ctypes.c_uint32),
        ("height", ctypes.c_uint32),
        ("channels", ctypes.c_uint32),
        ("_pad", ctypes.c_uint32),
        ("data", ctypes.c_uint8 * 921600),
    ]

    @classmethod
    def type_name(cls):
        return "camera_service::CameraFrame"
'''
    p.write_text(s)
PY
```

If you changed struct sizes after a previous run, clear old SHM segments:

```bash
rm -rf /tmp/iceoryx2
```

## 4.5 Orient On The Run Progression

Before wiring the demo runtime, briefly explain what was cloned. The
project is a research ladder — CNN+MLP behavior cloning, then chunked
CNN+MLP, then ACT-style transformer over chunks, then residual PPO on top
of ACT — with eval success roughly 0% → 31% → 68% → ~100%. The checkpoint
about to be loaded (`rl_best_eval.ckpt` from `act-ppo-dense-affine`) is
the top rung. Every rung is a first-class run in artha-os with its own
code, data, and provenance, so the user can inspect or branch from any
of them. Section 11 has the full table for the recap.

## 5. Wire Demo Services

**Narrate:** This replaces `services.yaml` with the demo runtime — sim,
data_recorder, video_bridge, bridge, eval_runner, provenance, commander,
and act_ppo_inference — each declared with its IPC publishes/subscribes
so the supervisor knows the full topology. We keep the prior file as
`services.yaml.pre-demo`.

**Execute:**

```bash
python3 - <<'PY'
import json
from pathlib import Path

clone = json.loads(Path("/tmp/artha-grasp-clone.json").read_text())
project_id = clone["id_remaps"]["projects"]["proj_e5509f6a7a0443eb913be950c6a0fac9"]
ppo_run_id = clone["id_remaps"]["runs"]["run_fabbe8144d5d474abea1ad7e6f15cd90"]

projects = sorted(Path("workspace").glob("grasp-pickup__*"))
if not projects:
    raise SystemExit("No workspace/grasp-pickup__* directory found")
project_dir = projects[-1]

ppo_dirs = sorted(project_dir.glob("runs/**/act-ppo-dense-affine__*"))
if not ppo_dirs:
    raise SystemExit("No act-ppo-dense-affine run directory found")
ppo_dir = ppo_dirs[-1]

Path("services.yaml.pre-demo").write_text(Path("services.yaml").read_text())
Path("services.yaml").write_text(f'''# Demo services for artha-os grasp-pickup onboarding.

param_server:
  cmd: ["python3", "services/param_server.py"]
  env:
    SERVICE_NAME: param_server
    PARAM_FILE_PATH: "config/params.json"

sim:
  cmd: ["python3", "{project_dir}/sim/main.py"]
  env:
    SERVICE_NAME: sim
    LOOP_RATE_HZ: "50"
    SIM_POLICY_CAMERA_WIDTH: "128"
    SIM_POLICY_CAMERA_HEIGHT: "128"
    SIM_UI_CAMERA_WIDTH: "512"
    SIM_UI_CAMERA_HEIGHT: "512"
  ipc:
    publishes:
      sim_robot/actual: RobStrideState
      camera/gripper_policy: CameraFrame
      camera/overhead_policy: CameraFrame
      camera/gripper_ui: CameraFrame
      camera/overhead_ui: CameraFrame
    subscribes:
      sim_robot/desired: RobStrideCommand

data_recorder:
  cmd: ["python3", "-m", "services.data_recorder"]
  env:
    SERVICE_NAME: data_recorder
    LOOP_RATE_HZ: "30"
  ipc:
    subscribes:
      sim_robot/actual: RobStrideState
      sim_robot/desired: RobStrideCommand
      camera/gripper_policy: CameraFrame
      camera/overhead_policy: CameraFrame

video_bridge:
  cmd: ["./services/video_bridge/target/release/video-bridge"]
  env:
    SERVICE_NAME: video_bridge
    VIDEO_BRIDGE_PORT: "9090"
    VIDEO_BRIDGE_FPS: "30"
    VIDEO_BRIDGE_QUALITY: "80"
  ipc:
    subscribes:
      camera/gripper_ui: CameraFrame
      camera/overhead_ui: CameraFrame

bridge:
  cmd: ["python3", "services/bridge.py"]
  env:
    SERVICE_NAME: bridge

eval_runner:
  cmd: ["python3", "{project_dir}/eval_runner.py"]
  env:
    SERVICE_NAME: eval_runner
    EVAL_TIMEOUT_S: "20"

provenance:
  cmd: ["python3", "services/provenance.py"]
  env:
    SERVICE_NAME: provenance

commander:
  cmd: ["python3", "-m", "services.commander"]
  env:
    SERVICE_NAME: commander
    LOOP_RATE_HZ: "100"
    POLICY_NAME: act_ppo
  ipc:
    publishes:
      sim_robot/desired: RobStrideCommand
    subscribes:
      inference/desired: RobStrideCommand

act_ppo_inference:
  cmd: ["python3", "{ppo_dir}/inference.py"]
  env:
    SERVICE_NAME: act_ppo_inference
    LOOP_RATE_HZ: "50"
    POLICY_NAME: act_ppo
    SOURCE_PROJECT_ID: {project_id}
    SOURCE_RUN_ID: {ppo_run_id}
    SOURCE_CHECKPOINT: rl_best_eval.ckpt
  ipc:
    publishes:
      inference/desired: RobStrideCommand
    subscribes:
      sim_robot/actual: RobStrideState
      camera/gripper_policy: CameraFrame
      camera/overhead_policy: CameraFrame
''')

print(f"project_dir={project_dir}")
print(f"ppo_dir={ppo_dir}")
print(f"local_project_id={project_id}")
print(f"local_ppo_run_id={ppo_run_id}")
PY
```

**Narrate the dataflow** — this is where the artha-os pattern becomes
concrete. Walk the user through what `services.yaml` actually wires up:

```text
Data plane — iceoryx2 shared memory, typed structs, sub-ms latency:

  sim ──▶ inference ──▶ commander ──▶ sim    (50Hz state+cams → 50Hz chunks → 100Hz commands)
  sim ──▶ data_recorder                       (30Hz episodes: state, cmd, policy cameras)
  sim ──▶ video_bridge ──HTTP/WS──▶ browser   (UI camera streams)

Control plane — NATS pub/sub, event-based:

  frontend ◀──▶ bridge ◀──▶ eval_runner, param_server, commander
  (eval start/stop, params, intervention buttons, service health)
```

The split — typed SHM for high-rate data, NATS for events — is the
artha-os pattern. iceoryx2's shared-memory transport keeps the inference
loop tight; NATS makes any service or the browser an event source or
sink with two lines of code. Another sim, another robot, or a new UI all
plug into the same two planes; adding a service is a `services.yaml`
entry plus a Python or Rust process.

## 6. Enable Demo Recording Sources

**Narrate:** The recorder ships as a no-op. We're activating four
sources: 7-DOF joint positions from `sim_robot/actual`, 7-DOF commanded
positions from `sim_robot/desired`, and the two 128×128 policy cameras.
These get written into the manifest as columns
(`observation.joint_positions`, `action`) and videos
(`observation.images.gripper`, `observation.images.overhead`).

The shapes here — 7 joints, 128×128 cameras — are grasp-pickup specific.
Your own project would define different sources matching its typed
topics.

**Execute:**

```bash
python3 - <<'PY'
from pathlib import Path

p = Path("services/data_recorder/main.py")
s = p.read_text()
marker = "# Active sim-demo source config inserted by onboarding"
if marker not in s:
    active = '''# Active sim-demo source config inserted by onboarding
NUM_JOINTS = 7


def _joint_positions(state):
    return [float(state.position[i]) for i in range(NUM_JOINTS)]


def _command_positions(cmd):
    return [float(cmd.position[i]) for i in range(NUM_JOINTS)]


def _camera_rgb(frame):
    n = int(frame.height) * int(frame.width) * 3
    return (
        np.ctypeslib.as_array(frame.data)[:n]
        .reshape(frame.height, frame.width, 3)
        .copy()
    )


SOURCES = [
    Source(
        topic="sim_robot/actual",
        type_name="RobStrideState",
        extract=_joint_positions,
        feature="observation.joint_positions",
        schema={"dtype": "float32", "shape": [NUM_JOINTS]},
        kind="column",
    ),
    Source(
        topic="sim_robot/desired",
        type_name="RobStrideCommand",
        extract=_command_positions,
        feature="action",
        schema={"dtype": "float32", "shape": [NUM_JOINTS]},
        kind="column",
    ),
    Source(
        topic="camera/gripper_policy",
        type_name="CameraFrame",
        extract=_camera_rgb,
        feature="observation.images.gripper",
        schema={"dtype": "video", "shape": [128, 128, 3]},
        kind="video",
    ),
    Source(
        topic="camera/overhead_policy",
        type_name="CameraFrame",
        extract=_camera_rgb,
        feature="observation.images.overhead",
        schema={"dtype": "video", "shape": [128, 128, 3]},
        kind="video",
    ),
]
'''
    s = s.replace("SOURCES: list[Source] = []", active)
    p.write_text(s)
PY
```

Known limitation: `data_recorder` should eventually anchor on the slowest
source and only append when all sources advance. For this demo, keep the
recorder at 30 Hz so the policy camera streams remain the effective anchor.

## 7. Apply The Project Frontend Overlay

**Narrate:** The demo project ships a task-specific Controls page that
renders the UI camera streams plus the eval start/stop button. We swap
it into `frontend/src/features/controls/pages/ControlsPage.tsx` and
rebuild. Frontend overlays are how an artha-os project bundles its own
UI without forking the base frontend.

**Execute:**

```bash
python3 - <<'PY'
from pathlib import Path

project_dir = sorted(Path("workspace").glob("grasp-pickup__*"))[-1]
src = project_dir / "frontend" / "ControlsPage.tsx"
dst = Path("frontend/src/features/controls/pages/ControlsPage.tsx")
if not src.exists():
    raise SystemExit(f"missing project controls page: {src}")
dst.write_text(src.read_text())
print(f"copied {src} -> {dst}")
PY

cd frontend && npm run build && cd -
```

## 8. Boot The Demo Runtime

**Narrate:** The supervisor brings up everything declared in
`services.yaml` in dependency order. After this, sim is publishing state
and camera frames at 50Hz, `act_ppo_inference` is loading the checkpoint
and beginning to predict, `video_bridge` is serving UI camera frames over
HTTP/WebSocket, and the recorder is idling on the eval-start signal.

**Execute:**

```bash
artha up --force
artha status
```

If anything is down, triage via logs before asking the user — most
failures are bad paths, missing deps, or stale SHM:

```bash
artha logs supervisor -n 80
artha logs sim -n 80
artha logs act_ppo_inference -n 80
artha logs video_bridge -n 80
```

## 9. Set Eval Provenance

**Narrate:** Provenance ties this eval to the specific run and checkpoint
that produced it. Episodes the recorder writes from this point on land
under that manifest, joinable to the source run, queryable in
`local_tool`, and pushable back to artha.bot with full lineage intact.
Without this step the episodes still get recorded — they just float free
of their source.

**Execute** — first print the local IDs from the clone output:

```bash
python3 - <<'PY'
import json
from pathlib import Path

clone = json.loads(Path("/tmp/artha-grasp-clone.json").read_text())
print(clone["id_remaps"]["projects"]["proj_e5509f6a7a0443eb913be950c6a0fac9"])
print(clone["id_remaps"]["runs"]["run_fabbe8144d5d474abea1ad7e6f15cd90"])
PY
```

Use the printed IDs:

```bash
artha provenance set \
  --manifest-name eval-act-ppo-grasp-pickup \
  --manifest-type eval \
  --policy-name act_ppo \
  --source-project-id <LOCAL_PROJECT_ID> \
  --source-run-id <LOCAL_ACT_PPO_RUN_ID> \
  --source-checkpoint rl_best_eval.ckpt \
  --fps 30
```

Check it:

```bash
artha provenance get
```

## 10. Hand The User To The Browser

**Narrate:** This is the moment the runtime works end-to-end. Walk the
user through it instead of dropping a URL — they don't yet know where
to click or what they're about to see.

Tell the user:

- Open `http://127.0.0.1:8000`. The frontend is already serving it.
- Go to the **Controls** page. They'll see two live camera streams
  (gripper view and overhead view), served by `video_bridge` over the
  WebSocket, plus an **eval/start** button.
- Tell them where to click and narrate what's about to happen: when they
  hit eval/start, a NATS event flips `eval_runner` into running mode;
  `act_ppo_inference` begins predicting 50-step action chunks at 50Hz
  off the policy cameras and joint state; `commander` relays each chunk
  to `sim_robot/desired` at 100Hz; sim executes the commands and steps
  physics; the recorder writes a new episode at 30Hz. They'll watch the
  arm in the overhead view reach for the block, close the gripper, and
  lift.
- Once the episode ends (success or 20s timeout), tell them to flip to
  the **Datasets** page — a new episode will be there under
  `eval-act-ppo-grasp-pickup`, with the joint columns, command columns,
  and recorded videos all queryable. That page going live is the payoff
  for the data plane and the provenance step earlier.

If the user reports success or failure, patch the episode reward when
the episode ID is visible — that turns the eval result into a structured,
queryable record that's joinable to other runs and pushable back to
artha.bot.

## 11. Explain The Demo Story

Use the cloned project README and run READMEs for details. The short arc:

| Run | Idea | Eval |
| --- | --- | --- |
| `synthetic-data` | Offline MuJoCo grasp episodes from Jacobian perturbations | produces the training manifest |
| `imitation-learning` | Single-step CNN+MLP behavior cloning | 0 / 20 = 0% |
| `il-action-chunking` | CNN+MLP predicts 50-action chunks | 20 / 63 = 31.75% |
| `act-reference` | ACT-style temporal policy | 43 / 63 = 68.25% |
| `act-ppo-dense-affine` | Residual PPO over ACT chunks | best 63 / 63 = 100%; latest logged 62 / 63 = 98.41% |

The product point: the agent can clone a real robot-learning project, wire
its services and UI into the runtime, load a checkpoint, run an eval, record
data, and preserve provenance without making the user perform the plumbing.

## 12. Close The Loop

After the first eval, explain the cloud path:

- With an artha.bot token, the user can push generated episodes or new runs.
- Cloud storage lets them collaborate, move datasets to a GPU machine,
  train there, and pull checkpoints back to local.
- The first useful next step is one of: create a new experiment, generate
  more synthetic data, inspect the technical docs, or wire their own robot.

Ask what they want to do next.
