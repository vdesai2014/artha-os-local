# Stage 01 — Install Dependencies

## Goal

Install all dependencies needed to bring up the artha-os base runtime:
Python + ML libs, the frontend (Node), NATS, and the Rust video_bridge.

## Required narration

Explain the following in your own words, in chat, with concrete examples
(do not paraphrase, do not just recite):

- **What we are installing, and why each piece.** This is not a generic
  ML toolchain install — it is the install footprint for the data plane
  / control plane / cloud round-trip architecture from Stage 00:

  - **Python + ML libs** (`pip install -e .` plus `mujoco torch
    torchvision einops`). Editable install drops the `artha` CLI on
    the user's PATH; the ML libs are for the inference service and the
    MuJoCo demo simulation.
  - **NATS server.** The control-plane bus. Every event in the runtime
    — eval start/stop, parameter changes, intervention buttons,
    service health — rides NATS. With NATS up, any new service or even
    the browser can become an event source or sink in a couple of
    lines of code.
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

- **What success looks like, in their words you can verify.** All four
  installs complete; `which artha` resolves to a CLI on the PATH;
  `frontend/dist/index.html` exists; `nats-server --version` prints a
  2.x version; the `video-bridge` release binary exists.

## Allowed commands

After narration is complete and you have answered any questions, you
may run:

```bash
# Python + ML
python3 -m pip install --user -e .
python3 -m pip install --user mujoco torch torchvision einops

# Frontend
cd frontend && npm install && npm run build && cd -

# NATS server (only if missing)
if ! command -v nats-server >/dev/null; then
  OS=$(uname -s | tr '[:upper:]' '[:lower:]')
  ARCH=$(uname -m | sed -e 's/x86_64/amd64/' -e 's/aarch64/arm64/')
  VER=$(python3 -c "import json,urllib.request; print(json.load(urllib.request.urlopen('https://api.github.com/repos/nats-io/nats-server/releases/latest'))['tag_name'])")
  mkdir -p "$HOME/.local/bin"
  curl -fsSL "https://github.com/nats-io/nats-server/releases/download/${VER}/nats-server-${VER}-${OS}-${ARCH}.tar.gz" | tar -xz -C /tmp
  install -m755 "/tmp/nats-server-${VER}-${OS}-${ARCH}/nats-server" "$HOME/.local/bin/"
fi
nats-server --version

# Rust install (ONLY with explicit user permission)
if ! command -v cargo >/dev/null; then
  curl --proto '=https' --tlsv1.2 -fsSL https://sh.rustup.rs | sh -s -- -y --default-toolchain stable
  source "$HOME/.cargo/env"
fi

# video_bridge
cd services/video_bridge && cargo build --release && cd -
```

You may NOT run `artha up`, `artha clone`, or any other command that
starts services or contacts artha.bot. Those belong to later stages.

## Success criteria

- `which artha` returns a path.
- `frontend/dist/index.html` exists.
- `nats-server --version` prints a 2.x version.
- `services/video_bridge/target/release/video-bridge` exists.

If any of these fail, surface the failure to the user in chat and
diagnose before requesting the continue token. Common real-world
failures: torch CUDA mismatch, mujoco EGL/GL setup, ports 4222/8000
already in use from another stack.

## Continue token

The user must type, EXACTLY, in their next message:

    continue: boot-base

Vague confirmations DO NOT count.

## Next file

Once the token is received, open `onboarding/02-base-runtime.md`. Do NOT
open it before. Note: `02-base-runtime.md` does not yet exist in this
checkout — if the file is missing, tell the user the next stage is not
yet authored and stop. Do not improvise the next stage.
