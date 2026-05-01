# Stage 05 — Link The ACT+PPO Eval Output (Execution)

## Goal

Attach the ACT+PPO eval manifest as an output of the ACT+PPO run.
The eval just happened in Stage 04 while the runtime was up, so
the manifest exists in `local_tool`. We attach it now so that if
the user later pushes the project to artha.bot, the success eval
shows up as an output of the ACT+PPO run on the cloud project
page.

## No re-narration

The user just finished the ACT+PPO eval and saw two episodes on
the Datasets page. This stage is a small REST-API bookkeeping
step that closes the same lineage loop the agent did in Stage 03
for the IL run — only this time for ACT+PPO. Surface a one-line
progress marker ("ACT+PPO eval manifest linked as output of
ACT+PPO run") and any failure. Do NOT re-explain why or
re-introduce the lineage concept; the user already saw it on the
Datasets page.

## Auto-flow note

This stage does NOT require a `continue` token. As soon as the
success criterion is met, immediately open
`onboarding/06-close-loop.md` and start narrating from there.

## Allowed commands

```bash
# 1. Preflight — confirm the user actually completed the ACT+PPO eval.
# The user typed `continue`, but verify the manifest has at least one
# episode before claiming the link succeeds. If 0 episodes, do NOT
# proceed — surface to the user and ask them to confirm.
python3 - <<'PY'
import json, urllib.request
m = next(
    (m for m in json.loads(urllib.request.urlopen("http://127.0.0.1:8000/api/manifests?type=eval").read())["manifests"]
     if m["name"] == "eval-act-ppo-grasp-pickup"),
    None,
)
if m is None:
    raise SystemExit("FAIL: eval-act-ppo-grasp-pickup manifest not found — did the user complete the ACT+PPO eval?")
ep_count = m.get("episode_count", 0)
print(f"OK: manifest_id={m['id']} episode_count={ep_count}")
if ep_count == 0:
    raise SystemExit("FAIL: manifest has 0 episodes — the user may not have completed the ACT+PPO eval. Stop and confirm with the user.")
PY

# 2. Link the ACT+PPO eval manifest as an output of the ACT+PPO run,
# then verify the link landed via the bidirectional GET.
python3 - <<'PY'
import json, urllib.request
from pathlib import Path

API = "http://127.0.0.1:8000/api"

# Find the ACT+PPO eval manifest by name.
manifests = json.loads(urllib.request.urlopen(f"{API}/manifests?type=eval").read())["manifests"]
manifest = next(m for m in manifests if m["name"] == "eval-act-ppo-grasp-pickup")

# Find the ACT+PPO run id from local run.json. The run is deeply
# nested under the parent-child run chain, but its id is already
# remapped by clone.
project_dir = sorted(Path("workspace").glob("grasp-pickup__*"))[-1]
ppo_dir = sorted(project_dir.glob("runs/**/act-ppo-dense-affine__*"))[-1]
run_id = json.loads((ppo_dir / "run.json").read_text())["id"]

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
assert any(m["name"] == "eval-act-ppo-grasp-pickup" for m in linked), \
    "FAIL: ACT+PPO eval manifest NOT in ACT+PPO run's manifests after POST"
print(f"OK: linked manifest {manifest['id']} to ACT+PPO run {run_id}; verified via GET")
PY
```

You may NOT touch the runtime, edit `services.yaml`, run any
`artha` CLI command, or do anything else here. This stage is one
focused REST patch.

## Success criteria

- **Preflight passed** — `eval-act-ppo-grasp-pickup` manifest exists
  with `episode_count ≥ 1` (Step 1 print statement).
- **Link landed** — bidirectional GET on
  `/api/runs/{ACT_PPO_run_id}/manifests` includes
  `eval-act-ppo-grasp-pickup` (Step 2 inline assertion).

If the preflight fails, the user likely didn't complete the eval —
surface in chat and ask them to confirm before retrying. If the
link itself fails (POST returned but GET doesn't show the manifest),
something's wrong with the junction store — check
`artha logs local_tool -n 80`. Do NOT auto-flow with an unverified
link.

## Next file

Once the success criterion is met, immediately open
`onboarding/06-close-loop.md` and start narrating from there.
There is no continue token — auto-flow.
