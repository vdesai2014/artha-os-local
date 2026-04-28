# Stage 03 — Swap To The Better Policy (Execution)

## Goal

Attach the IL eval manifest as an output of the IL run, then swap
inference to the ACT+PPO checkpoint, register the new eval
provenance, and restart the runtime. After this stage, the user
will re-run the eval manually (no tour) and see the better policy
succeed.

## No re-narration

The user already knows the demo is a research progression from
CNN+MLP to ACT+PPO (Stage 02), and just watched the IL baseline
fail in the in-browser tour. DO NOT re-explain why we're
swapping.

You may, and should, surface short progress markers as steps land:

- "linked IL eval manifest as output of IL run"
- "services.yaml updated for ACT+PPO"
- "supervisor restarted"
- "ACT+PPO inference loaded checkpoint"
- "ACT+PPO eval provenance registered"

Surface any failure immediately, in chat.

## Auto-flow note

This stage does NOT require a `continue` token. As soon as the
success criteria are met, immediately open
`onboarding/04-witness-progression.md` and start narrating from
there.

## Agent-only context (do not narrate to user)

The ACT+PPO run is deeply nested in the project's parent-child run
chain: `runs/imitation-learning__*/runs/il-action-chunking__*/runs/
act-reference__*/runs/act-ppo-dense-affine__*`. The recursive glob
`runs/**/act-ppo-dense-affine__*` resolves it correctly from the
project root. The ACT+PPO inference script hardcodes its checkpoint
to `SCRIPT_DIR/checkpoints/rl_best_eval.ckpt`; `SOURCE_CHECKPOINT`
is provenance metadata only.

## Allowed commands

Run, in order:

```bash
# 1. Link the IL eval manifest as an output of the IL run. The IL
# eval already happened in Stage 02 while the runtime was up, so
# the manifest exists in local_tool. We attach it now so the eval
# travels with the IL run on cloud push.
python3 - <<'PY'
import json, urllib.request
from pathlib import Path

API = "http://127.0.0.1:8000/api"

# Find the IL eval manifest by name.
manifests = json.loads(urllib.request.urlopen(f"{API}/manifests?type=eval").read())["manifests"]
manifest = next(m for m in manifests if m["name"] == "eval-imitation-learning-grasp-pickup")

# Find the IL run id from local run.json (already remapped by clone).
project_dir = sorted(Path("workspace").glob("grasp-pickup__*"))[-1]
il_dir = sorted(project_dir.glob("runs/**/imitation-learning__*"))[-1]
run_id = json.loads((il_dir / "run.json").read_text())["id"]

# Read current links; skip if already linked (idempotent).
run = json.loads(urllib.request.urlopen(f"{API}/runs/{run_id}").read())
links = run.get("links") or []
if not any(L.get("target_id") == manifest["id"] for L in links):
    links.append({
        "type": "output",
        "target_type": "manifest",
        "target_id": manifest["id"],
        "label": manifest["name"],
    })
    req = urllib.request.Request(
        f"{API}/runs/{run_id}",
        method="PATCH",
        data=json.dumps({"links": links}).encode(),
        headers={"Content-Type": "application/json"},
    )
    urllib.request.urlopen(req).read()
print(f"Linked manifest {manifest['id']} as output of IL run {run_id}")
PY

# 2. Rewrite services.yaml — swap IL inference for ACT+PPO. Same
# topology as Stage 01 otherwise; only the inference service and
# commander POLICY_NAME change.
python3 - <<'PY'
import json
from pathlib import Path

projects = sorted(Path("workspace").glob("grasp-pickup__*"))
if not projects:
    raise SystemExit("No workspace/grasp-pickup__* directory found")
project_dir = projects[-1]

ppo_dirs = sorted(project_dir.glob("runs/**/act-ppo-dense-affine__*"))
if not ppo_dirs:
    raise SystemExit("No act-ppo-dense-affine run directory found in project")
ppo_dir = ppo_dirs[-1]

ppo_run_meta = json.loads((ppo_dir / "run.json").read_text())
project_id = ppo_run_meta.get("project_id", "")
ppo_run_id = ppo_run_meta.get("id", "")
if not project_id or not ppo_run_id:
    raise SystemExit(f"run.json missing project_id or id: {ppo_run_meta}")

Path("services.yaml").write_text(f'''# Demo services for artha-os grasp-pickup onboarding (ACT+PPO).

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
    POLICY_NAME: act-ppo-dense-affine
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
    POLICY_NAME: act-ppo-dense-affine
    SOURCE_PROJECT_ID: {project_id}
    SOURCE_RUN_ID: {ppo_run_id}
    SOURCE_CHECKPOINT: checkpoints/rl_best_eval.ckpt
  ipc:
    publishes:
      inference/desired: RobStrideCommand
    subscribes:
      sim_robot/actual: RobStrideState
      camera/gripper_policy: CameraFrame
      camera/overhead_policy: CameraFrame
''')
PY

# 3. Restart with the new topology.
artha up --force
artha status

# 4. Register ACT+PPO eval provenance over NATS.
eval "$(python3 - <<'PY'
import json
from pathlib import Path
projects = sorted(Path("workspace").glob("grasp-pickup__*"))
project_dir = projects[-1]
ppo_dirs = sorted(project_dir.glob("runs/**/act-ppo-dense-affine__*"))
ppo_dir = ppo_dirs[-1]
meta = json.loads((ppo_dir / "run.json").read_text())
print(f"export ARTHA_PROJECT_ID={meta['project_id']}")
print(f"export ARTHA_PPO_RUN_ID={meta['id']}")
PY
)"

artha provenance set \
  --manifest-name eval-act-ppo-grasp-pickup \
  --manifest-type eval \
  --policy-name act-ppo-dense-affine \
  --source-project-id "$ARTHA_PROJECT_ID" \
  --source-run-id "$ARTHA_PPO_RUN_ID" \
  --source-checkpoint checkpoints/rl_best_eval.ckpt \
  --fps 30

artha provenance get
```

If `artha status` shows a service down, triage:

```bash
artha logs act_ppo_inference -n 80
artha logs supervisor -n 80
artha logs commander -n 80
```

## Success criteria

- The IL run now has an output link to the
  `eval-imitation-learning-grasp-pickup` manifest (the link
  script's print statement above confirms `Linked manifest <id>
  as output of IL run <id>`).
- `services.yaml` declares `act_ppo_inference` (no longer
  `imitation_learning_inference`) pointing at the deeply-nested
  ACT+PPO run dir's `inference.py`.
- `artha status` shows `act_ppo_inference` running.
- `artha provenance get` returns the
  `eval-act-ppo-grasp-pickup` manifest with the local ACT+PPO
  `source-run-id`.

If any criterion fails, surface in chat and triage. Do NOT auto-flow
to Stage 04 with a broken runtime.

## Next file

Once all success criteria are met, immediately open
`onboarding/04-witness-progression.md` and start narrating from
there. There is no continue token — auto-flow.
