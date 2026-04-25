# Stage 06 — Clone The Demo (Execution)

## Goal

Pull the grasp-pickup project from artha.bot via `artha clone`, save
the ID-remap output, then bring the runtime down so later stages can
edit `services.yaml` safely.

## Do NOT re-narrate the WHY

The user has already heard, in Stage 05, what `artha clone` pulls,
the artha.bot data model, the additive-not-git framing, and the
time/size expectations. DO NOT re-explain those.

You may, and should, surface short progress markers as the clone runs
("clone job started, id <job-id>", "X / Y files pulled, Z MB",
"checkpoint files downloading"). You MUST surface any error or stall
immediately, in chat. After clone completes, briefly tell the user
the clone is done and that you're now bringing the runtime down so
the next stage can edit `services.yaml` safely. Then run `artha down`.

## Agent-only context (do not narrate to user)

The clone produces `/tmp/artha-grasp-clone.json`, a JSON file
containing `id_remaps` — a mapping from cloud project / run /
manifest / episode / checkpoint IDs to fresh local IDs. Later stages
read this file to wire the right run and checkpoint into
`services.yaml`. Treat it as the session's source of truth. If `/tmp`
gets nuked between stages, you will have to re-clone.

## Allowed commands

Run, in order:

```bash
# Clone the grasp-pickup project from artha.bot. The stack must be UP
# for this — local_tool runs the sync job. Surface the sync-job id
# and periodic progress to the user.
artha clone proj_e5509f6a7a0443eb913be950c6a0fac9 --output /tmp/artha-grasp-clone.json
```

After clone completes successfully:

```bash
# Stop the stack so later stages can edit services.yaml safely.
artha down
```

You may NOT yet edit `services.yaml`, add SHM types, or run any
other command that touches the runtime. Those belong to later stages.

## Success criteria

- `/tmp/artha-grasp-clone.json` exists and is non-empty.
- A `workspace/grasp-pickup__*` directory exists in the repo root,
  containing `runs/`, `manifests/`, and `episodes/` subdirectories.
- `artha status` shows nats / local_tool / supervisor not running.

If clone fails or stalls, surface the failure with the relevant log
tail (`artha logs local_tool -n 80`) and ask the user how to proceed
before retrying or aborting.

## Continue token

The user must type, EXACTLY, in their next message:

    continue

Vague confirmations DO NOT count.

## Next file

Once the token is received, open `onboarding/07-wire-services.md`. Do
NOT open it before. Note: `07-wire-services.md` does not yet exist in
this checkout — if the file is missing, tell the user the next stage
is not yet authored and stop. Do not improvise the next stage.
