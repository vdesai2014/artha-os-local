"""Shared helpers for the artha CLI."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import yaml


DEFAULT_NATS_URL = "nats://localhost:4222"
DEFAULT_LOCAL_TOOL_URL = "http://127.0.0.1:8000"
DEFAULT_BRIDGE_WS_URL = "ws://127.0.0.1:8765/ws"
DEFAULT_VIDEO_BRIDGE_URL = "http://127.0.0.1:9090"


# ---------------------------------------------------------------------------
# Repo root + state-file discovery
# ---------------------------------------------------------------------------

def find_repo_root(start: Path | None = None) -> Path:
    """Walk up from start (or cwd) looking for services.yaml + core/.

    Matches the convention used by `workspace/*/runs/*/inference.py` so
    the CLI works from anywhere inside the repo.
    """
    current = (start or Path.cwd()).resolve()
    for _ in range(16):
        if (current / "services.yaml").exists() and (current / "core").is_dir():
            return current
        if current.parent == current:
            break
        current = current.parent
    raise SystemExit(
        "error: not inside an artha-os repo (no services.yaml + core/ found "
        "walking up from cwd). cd to the repo root."
    )


def runtime_dir(root: Path) -> Path:
    return root / ".artha" / "run"


def load_services_yaml(root: Path) -> dict:
    path = root / "services.yaml"
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text()) or {}


# ---------------------------------------------------------------------------
# NATS URL resolution — env → config/nats.conf → default
# ---------------------------------------------------------------------------

def parse_nats_conf(path: Path) -> dict:
    """Minimal HJSON-ish parse of nats.conf — we only need top-level `port`
    and optional `websocket { port }`."""
    if not path.exists():
        return {}
    text = path.read_text()
    out: dict = {}
    m = re.search(r"^\s*port\s*[:=]\s*(\d+)", text, re.MULTILINE)
    if m:
        out["port"] = int(m.group(1))
    m = re.search(r"websocket\s*\{[^}]*?port\s*[:=]\s*(\d+)", text, re.DOTALL)
    if m:
        out["websocket_port"] = int(m.group(1))
    return out


def nats_url(root: Path) -> str:
    env = os.environ.get("ARTHA_NATS_URL")
    if env:
        return env
    conf = parse_nats_conf(root / "config" / "nats.conf")
    port = conf.get("port")
    if port:
        return f"nats://localhost:{port}"
    return DEFAULT_NATS_URL


# ---------------------------------------------------------------------------
# local_tool URL resolution — state file → env → default
# ---------------------------------------------------------------------------

def read_local_tool_state(root: Path) -> dict | None:
    """Returns {pid, port, host, url, started_at} or None if no state file."""
    import json
    path = runtime_dir(root) / "local_tool.json"
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            return data
    except (FileNotFoundError, ValueError, OSError):
        pass
    return None


def local_tool_url(root: Path) -> str:
    state = read_local_tool_state(root)
    if state and state.get("url"):
        return state["url"]
    env = os.environ.get("ARTHA_LOCAL_TOOL_URL")
    if env:
        return env
    return DEFAULT_LOCAL_TOOL_URL


# ---------------------------------------------------------------------------
# Bridge + video_bridge — no state files yet, hard-coded for now
# ---------------------------------------------------------------------------

def bridge_ws_url() -> str:
    return os.environ.get("ARTHA_BRIDGE_WS_URL", DEFAULT_BRIDGE_WS_URL)


def video_bridge_url() -> str:
    return os.environ.get("ARTHA_VIDEO_BRIDGE_URL", DEFAULT_VIDEO_BRIDGE_URL)


# ---------------------------------------------------------------------------
# Pretty printing
# ---------------------------------------------------------------------------

_USE_COLOR = sys.stdout.isatty() and "NO_COLOR" not in os.environ


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _USE_COLOR else text


def green(text: str) -> str:
    return _c("32", text)


def yellow(text: str) -> str:
    return _c("33", text)


def red(text: str) -> str:
    return _c("31", text)


def dim(text: str) -> str:
    return _c("2", text)


def bold(text: str) -> str:
    return _c("1", text)


def die(msg: str, code: int = 1) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)
