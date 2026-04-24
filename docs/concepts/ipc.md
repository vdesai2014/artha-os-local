# IPC and memory movement

Artha-OS splits shared state across three tiers by update rate and by what it
takes to change it. Pick the right tier when you add new data.

| Tier | Rate | For | Changing requires |
|------|------|-----|-------------------|
| **SHM** (iceoryx2 blackboard) | > 1 Hz | camera frames, joint state, control commands | nothing — per-write |
| **param_server** | < 1 Hz | runtime-tunable constants: PD gains, FPS, safety slew, logging flags | nothing — NATS broadcast + disk persist |
| **services.yaml** | — | process topology, env vars, launch commands, infra wiring (CAN bus, device paths) | supervisor reload / service restart |

**Rule of thumb:** if it changes every frame, it's SHM. If a human tweaks it
while the robot runs, it's param_server. If changing it means restarting a
process, it belongs in `services.yaml`.

## SHM (core/shm.py, core/types.py)

Latest-value blackboard per topic. Writers copy a fixed-size struct in;
readers copy the latest value out. No queuing, no history — if you missed
frame N you skip to frame N+1. Matches the semantics of a control loop.

`core/types.py` defines the structs. Every topic is exactly one
`ctypes.Structure` subclass. Four invariants:

1. **Fixed size.** iceoryx2 pre-sizes the segment at create time. Resizing a
   struct invalidates it — restart every service that touches it *and* nuke
   `/tmp/iceoryx2`. Otherwise readers segfault.
2. **C layout.** `ctypes.Structure` with `_fields_` on the Python side, a
   `#[repr(C)]` companion on the Rust side. The supervisor boots
   `--type-check` against each Rust binary and refuses to start on
   mismatch.
3. **`timestamp: c_double` and `frame_id: c_uint64` first.** `ReaderManager`
   uses `frame_id` to detect staleness; structs without it are marked stale
   every poll.
4. **Variable-valid region inside fixed capacity.** A 640×480 `CameraFrame`
   holding a 320×240 image uses `width`/`height` fields to mark the valid
   slice. Never trust `len(data)` — the array is always capacity-sized.

See `core/types.py` for worked examples (`CameraFrame`, `JointState`,
`JointAction`) and the Rust-name-matching `type_name()` override.

## NATS

Control plane, RPC, and heartbeats. Not for high-rate data. Use NATS for:

- Commands (`commander.enable`, `sim.reset`, `recorder.start`)
- Request/reply (`provenance.get`, `param.get_all`)
- Service heartbeats (`service.<name>.heartbeat` — optional, for "functional"
  liveness; filesystem covers "process alive" — see `concepts/supervisor.md`)
- Param update broadcasts (`param.updated.<key>`)

NATS is assumed local and always-on. If it's down, the control plane dies
but SHM data keeps flowing — readers don't know and don't care.

## param_server

`services/param_server.py` owns an in-memory dict, persists to
`config/params.json`, and publishes `param.updated.<key>` on NATS when
anything changes. Services consume via `core.config.ParamClient` which
subscribes first (to avoid a race) and then fetches the snapshot — the
cache then supports synchronous `get()` inside tight loops.

If changing a value requires a process restart, it doesn't belong in the
param server. It belongs in `services.yaml`.
