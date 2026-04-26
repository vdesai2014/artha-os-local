# Stage 08 — Wire Demo Services (Execution)

## Goal

Wire the imitation learning baseline policy and supporting services
into the runtime: add SHM types, replace `services.yaml`, activate
recorder sources, copy the project's frontend overlay, and rebuild
the frontend bundle.

## Do NOT re-narrate the WHY

The user has already heard, in Stage 07, that we are attaching the
IL baseline as a service, that recorder + provenance work over NATS,
and that NATS bridges frontend ↔ runtime. DO NOT re-explain those.

You may, and should, surface short progress markers as edits land
("SHM types added", "services.yaml swapped, IL inference wired",
"recorder sources activated", "frontend overlay copied", "frontend
rebuilt"). You MUST surface any failure immediately, in chat.

## Agent-only context (do not narrate to user)

The clone JSON at `/tmp/artha-grasp-clone.json` contains `id_remaps`,
but for `services.yaml` the IL run identity (project_id, run_id) is
read directly from `run.json` inside the local IL run directory —
those IDs are already remapped by the clone. The IL inference script
lives at `<il_run_dir>/inference.py` and looks for its checkpoint at
`checkpoints/best.pt` relative to its own directory.

Five edits land in this stage; do them in order so the supervisor has
a complete topology before later stages restart it.

## Allowed commands

Run, in order:

```bash
# 1. Add demo SHM types to core/types.py
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

# Clear stale SHM segments if struct sizes changed across runs.
rm -rf /tmp/iceoryx2

# 2. Replace services.yaml with the demo runtime (IL baseline). Backup
# the prior file as services.yaml.pre-demo.
python3 - <<'PY'
import json
from pathlib import Path

projects = sorted(Path("workspace").glob("grasp-pickup__*"))
if not projects:
    raise SystemExit("No workspace/grasp-pickup__* directory found — did clone complete?")
project_dir = projects[-1]

il_dirs = sorted(project_dir.glob("runs/**/imitation-learning__*"))
if not il_dirs:
    raise SystemExit("No imitation-learning run directory found in workspace")
il_dir = il_dirs[-1]

il_run_meta = json.loads((il_dir / "run.json").read_text())
project_id = il_run_meta.get("project_id", "")
il_run_id = il_run_meta.get("id", "")
if not project_id or not il_run_id:
    raise SystemExit(f"run.json missing project_id or id: {il_run_meta}")

Path("services.yaml.pre-demo").write_text(Path("services.yaml").read_text())
Path("services.yaml").write_text(f'''# Demo services for artha-os grasp-pickup onboarding (IL baseline).

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
    POLICY_NAME: imitation-learning-cnn-mlp
  ipc:
    publishes:
      sim_robot/desired: RobStrideCommand
    subscribes:
      inference/desired: RobStrideCommand

imitation_learning_inference:
  cmd: ["python3", "{il_dir}/inference.py"]
  env:
    SERVICE_NAME: imitation_learning_inference
    LOOP_RATE_HZ: "50"
    POLICY_NAME: imitation-learning-cnn-mlp
    SOURCE_PROJECT_ID: {project_id}
    SOURCE_RUN_ID: {il_run_id}
    SOURCE_CHECKPOINT: checkpoints/best.pt
  ipc:
    publishes:
      inference/desired: RobStrideCommand
    subscribes:
      sim_robot/actual: RobStrideState
      camera/gripper_policy: CameraFrame
      camera/overhead_policy: CameraFrame
''')

print(f"project_dir={project_dir}")
print(f"il_dir={il_dir}")
print(f"local_project_id={project_id}")
print(f"local_il_run_id={il_run_id}")
PY

# 3. Activate recorder sources for the demo (joint state, joint command,
# both policy cameras).
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

# 4. Copy the project's frontend Controls page overlay into the
# base frontend tree.
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

# 5. Rebuild the frontend bundle so the supervisor serves the updated
# Controls page.
cd frontend && npm run build && cd -
```

You may NOT run `artha up`, set provenance, or touch the runtime in
any other way. Those belong to Stage 10.

## Success criteria

- `core/types.py` contains `class RobStrideState`, `class
  RobStrideCommand`, and `class CameraFrame`.
- `services.yaml.pre-demo` exists (backup of the base config).
- `services.yaml` declares an `imitation_learning_inference` service
  whose `cmd` points at the IL run's `inference.py` and whose
  `SOURCE_RUN_ID` is set.
- `services/data_recorder/main.py` contains the marker comment
  "Active sim-demo source config inserted by onboarding".
- `frontend/src/features/controls/pages/ControlsPage.tsx` matches the
  project's overlay (different size or hash than the neutral
  scaffold).
- `frontend/dist/index.html` has been rebuilt (newer mtime).

If any step fails, surface in chat and triage before requesting the
continue token. Common failures: missing `run.json` in the IL run dir
(check the clone completed cleanly), the project's
`frontend/ControlsPage.tsx` not present (older project structure —
flag and ask), or `core/types.py` missing the `import ctypes` it
already depends on (rare; surface the traceback).

## Continue token

The user must type, EXACTLY, in their next message:

    continue

Vague confirmations DO NOT count.

## Next file

Once the token is received, open `onboarding/09-boot-bad.md`. Do NOT
open it before.
