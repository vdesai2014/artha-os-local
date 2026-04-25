# Stage 01 — Install Plan (Narration Only)

## Goal

Walk the user through what is about to be installed and why, so they
have informed buy-in before any package manager runs.

This stage is conversation ONLY. The actual installation lives in
Stage 02, gated by a separate continue token. Do NOT skip ahead.

## Required narration

Explain the following in your own words, in chat, with concrete examples
(do not paraphrase, do not just recite):

- **What we are about to install, and why each piece.** This is not a
  generic ML toolchain install — it is the install footprint for the
  data plane / control plane / cloud round-trip architecture from
  Stage 00:

  - **Python + ML libs** (`pip install -e .` plus `mujoco torch
    torchvision einops`). Editable install drops the `artha` CLI on
    the user's PATH; the ML libs are for the inference service and
    the MuJoCo demo simulation.
  - **NATS server.** The control-plane bus. Every event in the runtime
    — eval start/stop, parameter changes, intervention buttons,
    service health — rides NATS. With NATS up, any new service or
    even the browser can become an event source or sink in a couple
    of lines of code.
  - **Frontend** (`npm install` + `npm run build`). The browser UI
    that subscribes to camera frames and publishes user commands. It
    is part of the experiment loop, not a separate dashboard. We
    compile a static bundle here that the supervisor will serve.
  - **Rust video_bridge** (`cargo build --release`). The bridge from
    high-rate iceoryx2 shared-memory cameras to the browser at
    sub-millisecond latency. Without it the user cannot see the live
    camera streams.

- **Time and scale.** This is the longest stage on a fresh machine —
  10–15 minutes typical, longer on cold pip/npm/cargo caches. PyTorch
  and torchvision wheels alone are several hundred megabytes.

- **The Rust ask.** If `cargo` is not on PATH, you MUST ask the user
  for permission before installing Rust via rustup. Do not silently
  install Rust — rustup is an unbounded download (~250MB) and the user
  may want to opt out. video_bridge is required for the demo, so if
  they decline Rust, flag explicitly that the demo cannot proceed.

- **What success will look like.** All four installs complete; `which
  artha` resolves to a CLI on the PATH; `frontend/dist/index.html`
  exists; `nats-server --version` prints a 2.x version; the
  `video-bridge` release binary exists.

## Allowed commands

**NONE.** This stage is conversation only. There are no commands here
to run. The actual installation happens in Stage 02.

If you find yourself wanting to run `pip`, `npm`, `cargo`, or anything
else: STOP. You are in the wrong stage. The next stage exists for
that, and only opens after the user supplies the continue token.

## Success criteria

- You have explained all four install pieces (Python+ML, NATS,
  frontend, video_bridge) in your own words, with concrete examples.
- You have set expectations on time (10–15 min on a fresh machine,
  longer on cold caches).
- If `cargo` is missing, you have asked the user for permission to
  install Rust via rustup.
- The user has indicated they want to proceed with the install as
  described.

## Continue token

The user must type, EXACTLY, in their next message:

    continue: install-run

Vague confirmations ("yes", "sounds good", "go", "yee") DO NOT count.

## Next file

Once the token is received, open `onboarding/02-install-run.md`. Do NOT
open it before. That file is where the install commands live.
