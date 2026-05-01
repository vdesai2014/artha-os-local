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
# 1. Preflight — confirm the user actually completed the IL eval before
# any destructive change. The user typed `continue`, but verify the
# manifest has at least one episode. If it doesn't, do NOT proceed —
# stop, ask the user to confirm they completed the in-browser tour.
python3 - <<'PY'
import json, urllib.request
m = next(
    (m for m in json.loads(urllib.request.urlopen("http://127.0.0.1:8000/api/manifests?type=eval").read())["manifests"]
     if m["name"] == "eval-imitation-learning-grasp-pickup"),
    None,
)
if m is None:
    raise SystemExit("FAIL: eval-imitation-learning-grasp-pickup manifest not found — did the user complete the IL eval?")
ep_count = m.get("episode_count", 0)
print(f"OK: manifest_id={m['id']} episode_count={ep_count}")
if ep_count == 0:
    raise SystemExit("FAIL: manifest has 0 episodes — the user may not have completed the IL eval. Stop and confirm with the user before swapping policies.")
PY

# 2. Link the IL eval manifest as an output of the IL run. The IL
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

# Associate the manifest with the run via the bidirectional junction
# endpoint. Server-side dedup makes this idempotent — repeating is a
# no-op.
req = urllib.request.Request(
    f"{API}/runs/{run_id}/manifests",
    method="POST",
    data=json.dumps({"manifest_id": manifest["id"]}).encode(),
    headers={"Content-Type": "application/json"},
)
urllib.request.urlopen(req).read()

# Verify the link landed via the bidirectional GET.
linked = json.loads(urllib.request.urlopen(f"{API}/runs/{run_id}/manifests").read())["manifests"]
assert any(m["name"] == "eval-imitation-learning-grasp-pickup" for m in linked), \
    "FAIL: IL eval manifest NOT in IL run's manifests after POST"
print(f"OK: linked manifest {manifest['id']} to IL run {run_id}; verified via GET")
PY

# 3. Rewrite services.yaml — swap IL inference for ACT+PPO. Same
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

# Verify the yaml shape after rewrite.
python3 -c "
import yaml
d = yaml.safe_load(open('services.yaml'))
assert 'act_ppo_inference' in d, 'FAIL: act_ppo_inference missing from services.yaml'
assert 'imitation_learning_inference' not in d, 'FAIL: imitation_learning_inference still present'
print('OK: services.yaml has act_ppo_inference, IL service removed')
"

# 4. Restart with the new topology.
artha up --force
artha status --json

# 5. Register ACT+PPO eval provenance over NATS.
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

# Verify provenance landed and matches what we expect.
artha provenance get | python3 -c "
import json, sys
p = json.load(sys.stdin)
assert p.get('manifest_name') == 'eval-act-ppo-grasp-pickup', f'manifest_name={p.get(\"manifest_name\")!r}'
assert p.get('policy_name') == 'act-ppo-dense-affine', f'policy_name={p.get(\"policy_name\")!r}'
assert p.get('source_checkpoint') == 'checkpoints/rl_best_eval.ckpt', f'source_checkpoint={p.get(\"source_checkpoint\")!r}'
print('OK: provenance set for ACT+PPO')
"

# 6. Verify ACT+PPO inference is producing commands on the bus.
artha peek inference/desired --timeout 3
```

If any verification above fails, triage before continuing. Common
failure modes:

- **`act_ppo_inference` not running** — checkpoint load failed. Check
  `artha logs act_ppo_inference -n 80`. The script hardcodes
  `SCRIPT_DIR/checkpoints/rl_best_eval.ckpt`; verify the file exists
  in the deeply-nested ACT+PPO run dir.
- **`artha peek inference/desired` times out** — inference up but not
  publishing. Check whether sim is publishing state
  (`artha peek sim_robot/actual`). If sim is fine but inference is
  silent, check `artha logs act_ppo_inference -n 80` and
  `artha logs commander -n 80`.
- **Provenance mismatch** — re-run the `artha provenance set` block
  with the right values.
- **Stale SHM after services.yaml swap** — clear and restart:
  `rm -rf /tmp/iceoryx2 && artha down && artha up --force`.

If you can't get past a failure after triage, surface to the user and
offer to file feedback (see "Filing feedback (any stage)" in
`onboard.md`).

## Success criteria

Each maps to a probe you've actually run inline above.

- **Preflight passed** — IL eval manifest exists with `episode_count
  ≥ 1` (Step 1 print statement).
- **IL run linked** — bidirectional GET on
  `/api/runs/{IL_run_id}/manifests` includes
  `eval-imitation-learning-grasp-pickup` (Step 2 inline assertion).
- **services.yaml swapped** — `act_ppo_inference` present,
  `imitation_learning_inference` absent (Step 3 yaml verifier).
- **Process state** — `artha status --json` shows
  `act_ppo_inference` and the rest running (Step 4).
- **Provenance set** — `artha provenance get` matches
  `eval-act-ppo-grasp-pickup` / `act-ppo-dense-affine` /
  `checkpoints/rl_best_eval.ckpt` (Step 5 inline assertion).
- **Inference live on the bus** — `artha peek inference/desired`
  returns a `RobStrideCommand` snapshot within 3s (Step 6).

If any criterion fails, surface in chat and triage. Do NOT auto-flow
to Stage 04 with a broken runtime.

## Next file

Once all success criteria are met, immediately open
`onboarding/04-witness-progression.md` and start narrating from
there. There is no continue token — auto-flow.
