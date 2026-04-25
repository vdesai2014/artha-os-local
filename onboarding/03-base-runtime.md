# Stage 03 — Base Runtime Plan (Narration Only)

## Goal

Walk the user through what is about to happen when we bring up the
base artha-os runtime, so they understand what each component does
and what they should expect to see in their browser.

This stage is conversation ONLY. The actual `artha up` happens in
Stage 04. Do NOT skip ahead.

## Required narration

Explain the following in your own words, in chat, with concrete
examples (do not paraphrase, do not just recite):

- **What `artha up` does, in dependency order.** It brings up four
  things, with readiness gates between them so a downstream component
  doesn't start before an upstream one is healthy:

  1. **NATS** — the control-plane bus we installed in Stage 02. `up`
     waits for the TCP port (default 4222) to open before declaring
     it ready.
  2. **local_tool** — the file-based store API. Holds projects, runs,
     manifests, episodes, checkpoints, and provenance — everything
     the `artha` CLI and the frontend read and write. It serves a
     small HTTP API; `up` waits for its `/health` endpoint to return
     200 before continuing.
  3. **supervisor** — the process supervisor that reads
     `services.yaml` to know which user services to start. At base
     runtime, `services.yaml` declares only `param_server` and
     `bridge` — enough to make the frontend functional, no
     project-specific services yet.
  4. **frontend** — already built into a static bundle in Stage 02;
     served by the supervisor over HTTP at `http://127.0.0.1:8000`.

- **Why we boot the base runtime BEFORE cloning the demo.** Two
  reasons. First, it confirms the install actually works end-to-end
  — much cheaper to find an env problem here than after cloning a
  multi-gigabyte demo project. Second, the base runtime is the
  canvas: every project (this demo or any future robot the user
  brings) plugs into the same base, so seeing the empty base first
  makes clear what's "artha-os" vs. what's "this particular project".

- **What the user should see.** After `artha up` completes,
  `artha status` will show `nats`, `local_tool`, and `supervisor`
  running, plus `param_server` and `bridge` services running under
  the supervisor. The user opens `http://127.0.0.1:8000` and sees the
  artha-os UI shell — empty of project content but live, with the
  navigation tabs visible. Tell them you'll wait for them to confirm
  the page loads.

- **Common things that can go wrong.** Port 4222 (NATS) or 8000
  (frontend) may be occupied by another process from a prior run or
  unrelated app. If `artha up` fails on a port, the next stage will
  tell us which and we can clean it up. Also: a stale supervisor or
  local_tool process from an earlier session can block startup —
  `artha up --force` resolves that, but we'll start with plain
  `artha up` first to keep things safe.

## Allowed commands

**NONE.** This stage is conversation only. The actual boot happens
in Stage 04.

If you find yourself wanting to run `artha up`, `artha status`, or
any other command: STOP. You are in the wrong stage. The execution
stage opens only after the user supplies the continue token.

## Success criteria

- You have explained the four-component dependency order (NATS →
  local_tool → supervisor → frontend) in your own words.
- You have explained why we boot the base runtime before cloning
  the demo.
- You have set expectations: `artha status` should show all green,
  and the user will need to open `http://127.0.0.1:8000` to confirm
  the frontend loads.
- You have flagged the common failure modes (port conflicts, stale
  processes) so the user isn't surprised if we hit one.
- The user is ready to proceed.

## Continue token

The user must type, EXACTLY, in their next message:

    continue

Vague confirmations DO NOT count.

## Next file

Once the token is received, open `onboarding/04-base-runtime-run.md`.
Do NOT open it before. Note: `04-base-runtime-run.md` does not yet
exist in this checkout — if the file is missing, tell the user the
next stage is not yet authored and stop. Do not improvise the next
stage.
