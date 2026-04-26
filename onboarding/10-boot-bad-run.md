# Stage 10 — Run The IL Baseline (Execution)

## Goal

Boot the demo runtime with the IL inference wired in, register
provenance over NATS so eval episodes get tagged to the IL training
run, then hand the user to the browser to run a manual eval.

## Do NOT re-narrate the WHY

The user has already heard, in Stage 09, what the IL policy is,
why it fails, and what they need to do in the browser. DO NOT
re-explain any of those.

You may, and should, surface short progress markers as the runtime
comes up ("supervisor up", "IL inference loaded checkpoint",
"provenance set"). You MUST surface any failure immediately, in
chat.

## Agent-only context (do not narrate to user)

`artha provenance set` is the user-facing CLI for the same NATS
provenance flow you described in Stage 07 — it publishes the
manifest metadata onto the bus where the recorder picks it up. The
local `project_id` and IL `run_id` come from
`<il_run_dir>/run.json`, already remapped by clone (same source you
used to build `services.yaml` in Stage 08).

`artha up --force` is required here because `services.yaml` changed
in Stage 08; the running base services need to come down so the
demo topology can come up cleanly.

## Allowed commands

Run, in order:

```bash
# 1. Boot the demo runtime with the new services.yaml.
artha up --force
artha status

# 2. Pull the IL run identity from local run.json (already remapped
# by clone) into shell vars so the next command can use them.
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

# 3. Register IL eval provenance over NATS.
artha provenance set \
  --manifest-name eval-imitation-learning-grasp-pickup \
  --manifest-type eval \
  --policy-name imitation-learning-cnn-mlp \
  --source-project-id "$ARTHA_PROJECT_ID" \
  --source-run-id "$ARTHA_IL_RUN_ID" \
  --source-checkpoint checkpoints/best.pt \
  --fps 30

# 4. Verify provenance is set.
artha provenance get
```

If `artha status` shows a service down (e.g.,
`imitation_learning_inference` fails to load the checkpoint, or
`video_bridge` can't bind its port), triage before continuing:

```bash
artha logs imitation_learning_inference -n 80
artha logs supervisor -n 80
artha logs video_bridge -n 80
```

You may NOT swap policies, edit `services.yaml`, or run a swapped
eval. The policy swap belongs to Stage 11/12.

## Hand off to the user

Once `artha status` is clean and `artha provenance get` shows the
IL eval manifest, surface this checklist to the user (do NOT
re-narrate the WHY — they heard it in Stage 09; this is just the
action list):

1. Open `http://127.0.0.1:8000`.
2. Go to the **Controls** page.
3. Click **start-eval**. The robot will start moving.
4. Watch it struggle — drift, oscillate, never quite close the
   gripper.
5. When the robot is clearly stuck, click **STOP**. Don't wait it
   out.
6. Go to the **Datasets** page. Find the new episode from this eval.
7. Click `Run` in the bottom-right of the episode card to see the
   lineage link back to the imitation-learning training run.
8. Thumbs-down the eval to mark it as a failure.
9. Come back to chat and type `continue` when done.

Wait for the literal `continue` token. Do NOT proceed to Stage 11
before the user has explicitly typed it.

## Success criteria

- `artha status` shows the demo runtime services running:
  `imitation_learning_inference`, `commander`, `data_recorder`,
  `video_bridge`, `eval_runner`, plus the base components.
- `artha provenance get` returns an eval manifest with
  `policy-name: imitation-learning-cnn-mlp`, the local IL
  `source-run-id`, and `source-checkpoint: checkpoints/best.pt`.
- After the user finishes, they have reported in chat that the IL
  eval ran and failed as expected, and that they saw the new
  episode + `Run` lineage link on the Datasets page.

If any of the above is wrong, surface in chat and triage before
requesting the continue token.

## Continue token

The user must type, EXACTLY, in their next message:

    continue

Vague confirmations DO NOT count. The user should type `continue`
ONLY after they have completed the browser eval flow and seen the
Datasets page lineage.

## Next file

Once the token is received, open `onboarding/11-swap-good.md`. Do
NOT open it before.
