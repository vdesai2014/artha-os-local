# Stage 02 — Install (Execution)

## Goal

Run the install commands the user already approved in Stage 01.

## Do NOT re-narrate the WHY

The user has already heard the plan and approved it via the
`continue: install-run` token. DO NOT re-explain what is being
installed or why — that work is done.

You may, and should, surface short progress markers as commands run
("starting pip install — this'll take a few minutes", "frontend bundle
built", "video_bridge compiled"). You MUST surface any error
immediately, in chat, before continuing to the next command.

## Allowed commands

Run, in order:

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

# Rust install (ONLY if user explicitly approved in Stage 01)
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

Once the token is received, open `onboarding/03-base-runtime.md`. Do
NOT open it before. Note: `03-base-runtime.md` does not yet exist in
this checkout — if the file is missing, tell the user the next stage
is not yet authored and stop. Do not improvise the next stage.
