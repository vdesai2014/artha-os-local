# Stage 04 — Base Runtime (Execution)

## Goal

Bring up the artha-os base runtime and have the user confirm the
frontend loads in their browser.

## Do NOT re-narrate the WHY

The user has already heard, in Stage 03, the dependency order, why we
boot the base before cloning the demo, and what to expect on screen.
DO NOT re-explain those.

You may, and should, surface short progress markers as commands
complete ("nats up", "local_tool ready", "supervisor running",
"param_server and bridge running under the supervisor"). You MUST
surface any failure immediately, in chat, with the relevant log tail.

## Allowed commands

Run, in order:

```bash
artha up
artha status
```

If `artha up` fails because something is already running on a port
(NATS 4222 or frontend 8000), surface the failure to the user. Do
NOT silently use `--force`. Ask the user whether to kill what's
running and retry; only then run:

```bash
artha up --force
```

If a service is missing from `artha status`, triage with logs before
asking the user:

```bash
artha logs supervisor -n 80
artha logs nats -n 80
artha logs local_tool -n 80
```

You may NOT run `artha clone`, edit `services.yaml`, or any command
that touches project content. Those belong to later stages.

## Success criteria

- `artha status` shows `nats`, `local_tool`, and `supervisor` all
  running, with `param_server` and `bridge` running under the
  supervisor.
- The user has opened `http://127.0.0.1:8000` in their browser and
  confirmed the artha-os UI shell loads — empty of project content
  but live, with navigation tabs visible.

If either fails, surface in chat and triage before requesting the
continue token.

## Continue token

The user must type, EXACTLY, in their next message:

    continue

Vague confirmations DO NOT count. The user should type `continue`
ONLY after verifying the frontend loads in their browser.

## Next file

Once the token is received, open `onboarding/05-clone-demo.md`. Do
NOT open it before. Note: `05-clone-demo.md` does not yet exist in
this checkout — if the file is missing, tell the user the next stage
is not yet authored and stop. Do not improvise the next stage.
