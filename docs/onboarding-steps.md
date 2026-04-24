# Machine Setup Reference — artha-os

For the guided first-run product tour, start at `../onboard.md`. This file
is the lower-level dependency and fallback reference for agents debugging a
fresh machine.

You are a coding agent on a fresh machine. Read this top-to-bottom, run the
steps, and hand off to the user.

Target: Linux or macOS (POSIX). Windows is not supported.

## 0. Orient

artha-os is a modular robotics runtime. Services talk over iceoryx2 SHM
(hot path: joint state, camera frames, commands) and NATS (control plane).
A supervisor reads `services.yaml` and launches each service under a
wrapper process with lease-based fail-fast restarts.

Read these before doing anything else — they're short, they're the
source of truth for how the system thinks:

- `docs/concepts/ipc.md` — three-tier memory movement (SHM / param_server / services.yaml)
- `docs/concepts/supervisor.md` — lease + heartbeat + restart semantics
- `docs/concepts/local-tool.md` — STORE vs SYNC; the stable dual-consumer contract
- `docs/concepts/sync.md` — push/pull/clone, not git
- `docs/concepts/cameras.md` — Rust writer + SHM reader + video_bridge for browser

## 1. Get the code

```bash
git clone <artha-os-url> ~/artha-os
cd ~/artha-os
```

## 2. Install the NATS binary (non-snap, non-brew)

All services connect to NATS on `localhost:4222`. Install the static
binary to `~/.local/bin`:

```bash
OS=$(uname -s | tr '[:upper:]' '[:lower:]')
ARCH=$(uname -m | sed -e 's/x86_64/amd64/' -e 's/aarch64/arm64/')
VER=$(curl -fsSL https://api.github.com/repos/nats-io/nats-server/releases/latest \
      | python3 -c 'import json,sys;print(json.load(sys.stdin)["tag_name"])')
mkdir -p "$HOME/.local/bin"
curl -fsSL "https://github.com/nats-io/nats-server/releases/download/${VER}/nats-server-${VER}-${OS}-${ARCH}.tar.gz" \
  | tar -xz -C /tmp
install -m755 "/tmp/nats-server-${VER}-${OS}-${ARCH}/nats-server" "$HOME/.local/bin/"
nats-server --version
```

**Do not use a snap-packaged nats-server** — snap confinement blocks reads
from arbitrary paths, and `config/nats.conf` will fail with "permission
denied" even though the file is world-readable.

## 3. Install Python 3.12 + Node 20+

Use whatever is installed or available — don't insist on any one package
manager.

- macOS: `brew install python@3.12 node` (or from python.org / nodejs.org)
- Linux: `sudo apt-get install -y python3.12 python3.12-venv python3-pip nodejs npm`

Verify:

```bash
python3 --version    # expect 3.12+
node --version       # expect v20+
```

## 4. Install Python packages

```bash
# Core OS dependencies
python3 -m pip install --user \
  iceoryx2 nats-py aiohttp websockets httpx fastapi uvicorn pydantic \
  pyarrow numpy pillow av pyyaml blake3

# local_tool is a package, install in-place
python3 -m pip install --user -e local_tool

# Sim-demo additions (only if onboarding the grasp-pickup project — step 7)
python3 -m pip install --user mujoco torch einops torchvision
```

**Gotcha:** if the user has a system `/usr/bin/uvicorn` shim, it may point
at a Python that doesn't have `typing_extensions`. Always launch uvicorn
via `python3 -m uvicorn ...`, not the bare `uvicorn` command.

## 5. (Optional) Build Rust services

The camera writer and video_bridge are Rust. Needed only if the user has
real cameras or wants MJPEG streams in the frontend.

```bash
command -v cargo >/dev/null || \
  { curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y; \
    . "$HOME/.cargo/env"; }

cd services/video_bridge && cargo build --release && cd -
cd services/camera       && cargo build --release && cd -
```

Video bridge links against libturbojpeg. If the build fails:
- macOS: `brew install jpeg-turbo`
- Linux: `sudo apt-get install -y libturbojpeg0-dev`

## 6. (Optional) Install frontend deps

```bash
cd frontend && npm install && cd -
```

The frontend is served statically out of `frontend/dist/` by `local_tool`
once built (`cd frontend && npm run build`). For dev: `npm run dev` on
port 5173.

## 7. (Optional) Clone a demo project

artha-os ships without a workspace — users bring their own robot. To pull
the public **grasp-pickup** sim demo (project
`proj_e5509f6a7a0443eb913be950c6a0fac9`, ~743 MB with checkpoints):

```bash
# Start local_tool (ARTHA_HOME points at the repo root)
ARTHA_HOME=$(pwd) python3 -m uvicorn local_tool.server.app:app \
  --host 127.0.0.1 --port 8000 &
sleep 2
curl -sS http://127.0.0.1:8000/api/health   # expect {"status":"ok",...}

# Clone via the HTTP API (no auth required for public projects).
# Expect ~10 minutes on a decent connection; there is currently no
# progress feedback — the request just blocks until done.
curl -sS -X POST http://127.0.0.1:8000/api/sync/execute \
  -H 'Content-Type: application/json' \
  -d '{
    "operation": "clone",
    "entity_type": "project",
    "entity_id": "proj_e5509f6a7a0443eb913be950c6a0fac9"
  }' > /tmp/clone-result.json

# Grab the id_remaps — THIS is the authoritative remap, not /sync/plan's.
python3 -c "import json; print(json.dumps(json.load(open('/tmp/clone-result.json'))['id_remaps'], indent=2))"
```

**Known friction** (see `to-do.md`):
- `/api/sync/plan` and `/api/sync/execute` each regenerate fresh IDs;
  only /execute's `id_remaps` is authoritative.
- Clone has no progress feedback over HTTP.
- Clone is not idempotent — re-running creates a second copy. Clean
  up with `rm -rf workspace/grasp-pickup__*` before retrying.

## 8. Wire the demo (if you cloned in step 7)

After clone, you have `workspace/grasp-pickup__<new-short>/` with files
but artha-os doesn't know what services to run. You need to:

### 8a. Add SHM types

`core/types.py` ships empty. The sim + inference services want
`RobStrideState`, `RobStrideCommand`, and `CameraFrame`. Append these
to `core/types.py` — use the worked examples in the existing docstring
as the template, with:

```python
class RobStrideState(ctypes.Structure):
    _fields_ = [
        ("timestamp", ctypes.c_double),
        ("frame_id", ctypes.c_uint64),
        ("position", ctypes.c_double * 7),
        ("velocity", ctypes.c_double * 7),
        ("torque", ctypes.c_double * 7),
        ("temperature", ctypes.c_double * 7),
        ("enabled", ctypes.c_uint8 * 7),
    ]

class RobStrideCommand(ctypes.Structure):
    _fields_ = [
        ("timestamp", ctypes.c_double),
        ("frame_id", ctypes.c_uint64),
        ("position", ctypes.c_double * 7),
        ("velocity", ctypes.c_double * 7),
        ("torque", ctypes.c_double * 7),
    ]

class CameraFrame(ctypes.Structure):
    _fields_ = [
        ("timestamp", ctypes.c_double),
        ("frame_id", ctypes.c_uint64),
        ("width", ctypes.c_uint32),
        ("height", ctypes.c_uint32),
        ("channels", ctypes.c_uint32),
        ("_pad", ctypes.c_uint32),
        ("data", ctypes.c_uint8 * 921600),
    ]

    @classmethod
    def type_name(cls):
        return "camera_service::CameraFrame"
```

### 8b. Add demo services to `services.yaml`

The stock `services.yaml` enables only `param_server` + `bridge`. Add
the sim-demo services using the id_remaps captured in step 7 — rewrite
every occurrence of the old project short-id in paths, and the full
`SOURCE_PROJECT_ID` / `SOURCE_RUN_ID` env vars. See the commented-out
blocks in `services.yaml` for `provenance`, `commander`, `data_recorder`,
and `video_bridge`; uncomment those, then append `sim`, `eval_runner`,
and `act_ppo_inference` entries (ask the user for the exact shape if
it's not obvious from the cloned project's file layout).

### 8c. Overlay the project's controls page onto the frontend

Demo projects ship their own `ControlsPage.tsx` because the OS's
`frontend/src/features/controls/pages/ControlsPage.tsx` is a neutral
placeholder. Copy the project's version over the neutral scaffold:

```bash
cp workspace/grasp-pickup__<new-short>/frontend/ControlsPage.tsx \
   frontend/src/features/controls/pages/ControlsPage.tsx
```

**Convention (current):** if a project has a `frontend/` directory at its
root, the agent is expected to copy each file into the matching location
under the OS repo's `frontend/src/`. Today this is a manual copy; a
future CLI verb (`artha apply-overlay <project>`) will automate it. The
neutral scaffold is preserved at `docs/templates/ControlsPage.tsx` so
reverting after a project unmount is trivial.

Two sources of truth result from this pattern (project copy is canonical,
frontend copy is a derived artifact). Re-copy when the project's controls
page updates.

### 8d. Populate `data_recorder` SOURCES (optional)

`services/data_recorder/main.py` ships with `SOURCES = []` so recording
is a no-op. The file contains a commented example block for the grasp
demo; uncomment it if you want eval runs to save episodes.

## 9. Boot the stack

Three long-lived processes, typically in their own terminals:

```bash
# Terminal 1 — NATS broker
nats-server -c config/nats.conf

# Terminal 2 — local_tool HTTP server (hosts /api/* and proxies /ws + /video)
ARTHA_HOME=$(pwd) python3 -m uvicorn local_tool.server.app:app \
  --host 127.0.0.1 --port 8000

# Terminal 3 — supervisor (reads services.yaml, launches each service)
python3 -m supervisor.main --services services.yaml
```

## 10. Hand off

Tell the user:

- "artha-os bootstrapped at `<path>`."
- If a demo was cloned: "Demo project `grasp-pickup` cloned and wired; new
  project ID `<...>`. services.yaml has N services; types added to
  core/types.py."
- Report `curl http://127.0.0.1:8000/api/health` output.
- Ask what they want to do next.
