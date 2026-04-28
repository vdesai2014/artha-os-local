# Stage 01 — Prepare (Execution)

## Goal

Do all the agent-driven prep in one pass: install dependencies,
boot the base runtime, clone the demo project from artha.bot, wire
the imitation-learning baseline as a service, boot the demo
runtime, and register the IL eval provenance.

This stage runs many commands in sequence. ~20–30 minutes total on
a fresh machine.

## No re-narration

The user already heard, in Stage 00, why we install, what the demo
arc is, and where the agent fits. DO NOT re-explain those.

You may, and should, surface short progress markers as steps
complete: "install done", "base runtime up", "clone running — X
files / Y MB", "demo wiring in place", "demo runtime up",
"provenance set". You MUST surface any failure immediately, in
chat, with the relevant log tail.

## Auto-flow note

This stage does NOT require a `continue` token. As soon as the
success criteria are met, immediately open
`onboarding/02-meet-the-demo.md` and start narrating from there.

## Allowed commands

Run the following blocks in order.

### Step 1 — Install dependencies

```bash
# Python + ML — try `--user` first; fall back to a project-local
# venv only if the install fails specifically with
# `error: externally-managed-environment` (PEP 668). Do NOT switch
# to venv for unrelated failures (network, dep conflicts).

# Path A — standard --user install
python3 -m pip install --user -e .
python3 -m pip install --user mujoco torch torchvision einops

# Path B — fallback to .venv/ if Path A errored with PEP 668. After
# this path, future shells need `source .venv/bin/activate` to find
# the `artha` CLI on PATH.
#
#   python3 -m venv .venv
#   source .venv/bin/activate
#   python3 -m pip install -e .
#   python3 -m pip install mujoco torch torchvision einops

# Frontend
cd frontend && npm install && npm run build && cd -

# NATS server (only if missing)
if ! command -v nats-server >/dev/null; then
  OS=$(uname -s | tr '[:upper:]' '[:lower:]')
  ARCH=$(uname -m | sed -e 's/x86_64/amd64/' -e 's/aarch64/arm64/')
  VER=$(python3 -c "import json,urllib.request; print(json.load(urllib.request.urlopen('https://api.github.com/repos/nats-io/nats-server/releases/latest'))['tag_name'])")
  mkdir -p "$HOME/.local/bin"
  curl -fsSL "https://github.com/nats-io/nats-server/releases/download/${VER}/nats-server-${VER}-${OS}-${ARCH}.tar.gz" | tar -xz -C /tmp
  install -m755 "/tmp/nats-server-${VER}-${OS}-${ARCH}/nats-server" "$HOME/.local/bin/"
fi
nats-server --version

# Rust install (ONLY with explicit user permission — rustup is a
# ~250MB unbounded download).
if ! command -v cargo >/dev/null; then
  curl --proto '=https' --tlsv1.2 -fsSL https://sh.rustup.rs | sh -s -- -y --default-toolchain stable
  source "$HOME/.cargo/env"
fi

# video_bridge
cd services/video_bridge && cargo build --release && cd -
```

### Step 2 — Boot the base runtime and verify

```bash
artha up
artha status
```

If a port is occupied (4222 or 8000), ask the user before using
`--force`. If `artha status` shows a service down, triage with
`artha logs <name> -n 80` before continuing.

### Step 3 — Clone the demo project from artha.bot

This pulls ~10–15 minutes of assets — code, runs, manifests,
episodes, checkpoints. Surface the sync-job id and periodic file/
byte progress to the user.

```bash
artha clone proj_541fcc9a31b844579dcb91175d8b6c17 --output /tmp/artha-grasp-clone.json
```

### Step 4 — Stop the runtime so we can edit services.yaml safely

```bash
artha down
```

### Step 5 — Add the demo SHM types to core/types.py

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

# Clear stale SHM segments if struct sizes changed across runs.
rm -rf /tmp/iceoryx2
```

### Step 6 — Replace services.yaml with the IL-baseline demo runtime

```bash
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
PY
```

### Step 7 — Activate recorder sources

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

### Step 8 — Apply the project's frontend overlay

```bash
python3 - <<'PY'
from pathlib import Path
project_dir = sorted(Path("workspace").glob("grasp-pickup__*"))[-1]
src = project_dir / "frontend" / "ControlsPage.tsx"
dst = Path("frontend/src/features/controls/pages/ControlsPage.tsx")
if not src.exists():
    raise SystemExit(f"missing project controls page: {src}")
dst.write_text(src.read_text())
PY

cd frontend && npm run build && cd -
```

### Step 9 — Boot the demo runtime

```bash
artha up --force
artha status
```

If `imitation_learning_inference` or any service is down, triage:

```bash
artha logs imitation_learning_inference -n 80
artha logs supervisor -n 80
artha logs video_bridge -n 80
```

### Step 10 — Register IL eval provenance over NATS

```bash
eval "$(python3 - <<'PY'
import json
from pathlib import Path
projects = sorted(Path("workspace").glob("grasp-pickup__*"))
project_dir = projects[-1]
il_dirs = sorted(project_dir.glob("runs/**/imitation-learning__*"))
il_dir = il_dirs[-1]
meta = json.loads((il_dir / "run.json").read_text())
print(f"export ARTHA_PROJECT_ID={meta['project_id']}")
print(f"export ARTHA_IL_RUN_ID={meta['id']}")
PY
)"

artha provenance set \
  --manifest-name eval-imitation-learning-grasp-pickup \
  --manifest-type eval \
  --policy-name imitation-learning-cnn-mlp \
  --source-project-id "$ARTHA_PROJECT_ID" \
  --source-run-id "$ARTHA_IL_RUN_ID" \
  --source-checkpoint checkpoints/best.pt \
  --fps 30

artha provenance get
```

## Success criteria

- `which artha` resolves; `frontend/dist/index.html` exists;
  `nats-server --version` prints 2.x; the `video-bridge` release
  binary exists.
- `/tmp/artha-grasp-clone.json` exists; `workspace/grasp-pickup__*/`
  exists and contains `runs/` with the trained policies (e.g.,
  `runs/imitation-learning__*` plus the deeper rungs nested
  inside it).
- `core/types.py` has `RobStrideState`, `RobStrideCommand`,
  `CameraFrame`.
- `services.yaml.pre-demo` exists; `services.yaml` declares
  `imitation_learning_inference` with `cmd` pointing at the IL run
  dir's `inference.py`.
- `services/data_recorder/main.py` has the sim-demo source config
  marker.
- `artha status` shows the demo runtime services running:
  `imitation_learning_inference`, `commander`, `data_recorder`,
  `video_bridge`, `eval_runner`, plus the base components.
- `artha provenance get` returns the IL eval manifest.

If any criterion fails, surface in chat and triage. Do NOT auto-flow
to Stage 02 with a broken runtime.

## Next file

Once all success criteria are met, immediately open
`onboarding/02-meet-the-demo.md` and start narrating from there.
There is no continue token — auto-flow.
