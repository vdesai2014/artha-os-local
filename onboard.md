# artha-os Guided Onboarding

This is the first-run script for a coding agent inside an `artha-os`
checkout. The goal is to give the user a working local runtime, then walk
them through the canonical grasp-pickup robot-learning demo.

Keep the user oriented. Before long installs or downloads, explain what is
about to happen, how long it may take, and what they should expect to see.

## 0. Explain The Tour

Tell the user:

- artha-os is an agent-first robot learning platform for local robots,
  datasets, runs, checkpoints, and cloud sharing.
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

Build the video bridge if Rust/Cargo is available. If Cargo is missing, ask
the user before installing Rust.

```bash
if command -v cargo >/dev/null; then
  cd services/video_bridge && cargo build --release && cd -
else
  echo "cargo missing; video_bridge build skipped"
fi
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

## 3. Clone The Grasp-Pickup Demo

Explain that the next step downloads the public demo project and checkpoints
from artha.bot. It may take several minutes and the sync endpoint currently
has no progress stream.

Use `/api/sync/execute`, not `/api/sync/plan`, because execute remaps are
the authoritative local IDs.

```bash
python3 - <<'PY'
import json
import httpx

body = {
    "operation": "clone",
    "entity_type": "project",
    "entity_id": "proj_e5509f6a7a0443eb913be950c6a0fac9",
}
resp = httpx.post("http://127.0.0.1:8000/api/sync/execute", json=body, timeout=1800.0)
resp.raise_for_status()
result = resp.json()
with open("/tmp/artha-grasp-clone.json", "w") as f:
    json.dump(result, f, indent=2)
print(json.dumps(result.get("id_remaps", {}), indent=2))
PY
```

Save the output mentally and on disk. The file
`/tmp/artha-grasp-clone.json` is the source of truth for the rest of this
session.

Now stop the stack before editing service definitions:

```bash
artha down
```

## 4. Add Demo SHM Types

The demo needs robot state, robot command, and camera frame structs.

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

## 5. Wire Demo Services

This replaces `services.yaml` with the demo runtime and keeps a backup.

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

If `video_bridge` was not built, either build it now or temporarily remove
the `video_bridge` service before booting.

## 6. Enable Demo Recording Sources

The recorder ships as a no-op. For the demo, activate the sim sources.

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

The demo ships a task-specific controls page.

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

```bash
artha up --force
artha status
```

If anything is down:

```bash
artha logs supervisor -n 80
artha logs sim -n 80
artha logs act_ppo_inference -n 80
artha logs video_bridge -n 80
```

Fix missing dependencies, bad paths, or unbuilt binaries before continuing.

## 9. Set Eval Provenance

Make the eval data land under the ACT+PPO checkpoint context.

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

Tell the user:

- Open `http://127.0.0.1:8000`.
- Go to the Controls page.
- Click the eval/start control.
- The robot should attempt the block pickup in sim.
- If it succeeds, the eval stops and a new episode should appear in the
  Datasets page.

If the user reports success or failure, patch the episode reward when the
episode ID is visible.

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
