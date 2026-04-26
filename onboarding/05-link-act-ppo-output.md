# Stage 05 — Link The ACT+PPO Eval Output (Execution)

## Goal

Attach the ACT+PPO eval manifest as an output of the ACT+PPO run.
The eval just happened in Stage 04 while the runtime was up, so
the manifest exists in `local_tool`. We attach it now so that if
the user later pushes the project to artha.bot, the success eval
shows up as an output of the ACT+PPO run on the cloud project
page.

## No re-narration

The user just finished the ACT+PPO eval; this stage is a small
REST-API bookkeeping step, not user-facing. Surface a short
progress marker ("ACT+PPO eval manifest linked to ACT+PPO run")
and any failure. Do NOT re-explain why.

## Auto-flow note

This stage does NOT require a `continue` token. As soon as the
success criterion is met, immediately open
`onboarding/06-close-loop.md` and start narrating from there.

## Allowed commands

```bash
# Link the ACT+PPO eval manifest as an output of the ACT+PPO run.
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
print(f"Linked manifest {manifest['id']} as output of ACT+PPO run {run_id}")
PY
```

You may NOT touch the runtime, edit `services.yaml`, run any
`artha` CLI command, or do anything else here. This stage is one
focused REST patch.

## Success criteria

- The ACT+PPO run now has an output link to the
  `eval-act-ppo-grasp-pickup` manifest (the link script's print
  statement above confirms `Linked manifest <id> as output of
  ACT+PPO run <id>`).

If the link fails (e.g., manifest not found because the user
didn't actually complete the ACT+PPO eval), surface in chat and
ask the user to confirm the eval finished. Do NOT auto-flow with
a missing manifest.

## Next file

Once the success criterion is met, immediately open
`onboarding/06-close-loop.md` and start narrating from there.
There is no continue token — auto-flow.
