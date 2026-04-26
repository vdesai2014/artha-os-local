# Stage 12 — Swap To ACT+PPO (Execution)

## Goal

Swap `imitation_learning_inference` for `act_ppo_inference` in
`services.yaml`, register a new eval provenance manifest for the
ACT+PPO checkpoint, restart the runtime, and hand the user back to
the browser for the success eval.

## Do NOT re-narrate the WHY

The user has already heard, in Stage 11, what ACT+PPO is, why it
works where IL didn't, and the swap mechanic. DO NOT re-explain
those.

You may, and should, surface short progress markers as the swap
lands ("services.yaml updated", "act_ppo run identified",
"provenance set", "supervisor up", "act_ppo inference loaded
checkpoint"). You MUST surface any failure immediately, in chat.

## Agent-only context (do not narrate to user)

The ACT+PPO run is deeply nested in the project's parent-child run
chain: `runs/imitation-learning__*/runs/il-action-chunking__*/runs/
act-reference__*/runs/act-ppo-dense-affine__*`. The recursive glob
`runs/**/act-ppo-dense-affine__*` resolves it correctly from the
project root.

The ACT+PPO inference script hardcodes its checkpoint paths to
`SCRIPT_DIR/checkpoints/rl_best_eval.ckpt` (and `bc_init.ckpt` for
the BC initialization). The `SOURCE_CHECKPOINT` env var is provenance
metadata only, not used for loading.

## Allowed commands

Run, in order:

```bash
# 1. Rewrite services.yaml to swap IL inference for ACT+PPO. Same
# topology as Stage 08 otherwise — only the inference service (and
# commander POLICY_NAME) change.
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

print(f"ppo_dir={ppo_dir}")
print(f"local_project_id={project_id}")
print(f"local_ppo_run_id={ppo_run_id}")
PY

# 2. Restart the runtime with the new topology.
artha up --force
artha status

# 3. Pull project_id and PPO run_id into shell vars from local run.json
# (already remapped by clone), then register the ACT+PPO eval provenance
# over NATS. New manifest name so it's distinct from Stage 10's IL
# eval manifest.
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

# 4. Verify provenance is set.
artha provenance get
```

If `artha status` shows a service down (e.g., `act_ppo_inference`
fails to load `rl_best_eval.ckpt`, or commander/recorder lose their
SHM links), triage before continuing:

```bash
artha logs act_ppo_inference -n 80
artha logs supervisor -n 80
artha logs commander -n 80
```

You may NOT chain further swaps; this is the final policy run for
the demo.

## Hand off to the user

Once `artha status` is clean and `artha provenance get` shows the
new ACT+PPO eval manifest, surface this checklist (do NOT re-narrate
the WHY — they heard it in Stage 11):

1. Switch back to the browser tab at `http://127.0.0.1:8000` (still
   up from Stage 10's runtime; refresh if the websocket dropped
   during the restart).
2. Go to the **Controls** page.
3. Click **start-eval**. The robot will reach for the block.
4. Watch it close the gripper at the right moment and lift the
   block.
5. The eval auto-ends on success (or 20s timeout — but it should
   succeed).
6. Go to the **Datasets** page. There are now TWO episodes — the
   failed IL eval from Stage 10 and this new ACT+PPO success eval.
7. Click `Run` on the new episode to confirm lineage links back to
   the `act-ppo-dense-affine` training run (different run, different
   manifest from the IL eval).
8. Thumbs-up the eval (contrast with the thumbs-down on the IL one).
9. Come back to chat and type `continue` when done.

Wait for the literal `continue` token. Do NOT proceed to Stage 13
before the user has explicitly typed it.

## Success criteria

- `services.yaml` declares `act_ppo_inference` with `cmd` pointing
  at the deeply-nested ACT+PPO run dir's `inference.py` and
  `SOURCE_RUN_ID` set to the local ACT+PPO run id.
- `services.yaml` does NOT contain `imitation_learning_inference`
  anymore.
- `artha status` shows `act_ppo_inference` running.
- `artha provenance get` returns an eval manifest with
  `manifest-name: eval-act-ppo-grasp-pickup`,
  `policy-name: act-ppo-dense-affine`, and the local ACT+PPO
  `source-run-id`.
- After the user finishes, they have reported in chat that the
  ACT+PPO eval ran successfully and that they saw both episodes
  (IL + ACT+PPO) on the Datasets page with distinct lineage.

If any of the above is wrong, surface in chat and triage before
requesting the continue token.

## Continue token

The user must type, EXACTLY, in their next message:

    continue

Vague confirmations DO NOT count. The user should type `continue`
ONLY after they have completed the success eval and seen both
episodes on the Datasets page.

## Next file

Once the token is received, open `onboarding/13-close-loop.md`. Do
NOT open it before.
