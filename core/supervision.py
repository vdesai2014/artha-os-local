from __future__ import annotations

import json
import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any


DEFAULT_RUNTIME_DIR = Path(".artha/run")
DEFAULT_HEARTBEAT_INTERVAL_S = 1.0
DEFAULT_LEASE_TIMEOUT_S = 3.0
DEFAULT_SERVICE_HEARTBEAT_INTERVAL_S = 2.0
DEFAULT_SERVICE_STALE_AFTER_S = 5.0

ENV_RUNTIME_DIR = "ARTHA_RUNTIME_DIR"
ENV_SESSION_ID = "ARTHA_SESSION_ID"
ENV_SERVICE_NAME = "ARTHA_SERVICE_NAME"
ENV_LEASE_TIMEOUT_S = "ARTHA_SUPERVISOR_LEASE_TIMEOUT_S"
ENV_SERVICES_PATH = "ARTHA_SERVICES_PATH"


def default_runtime_dir() -> Path:
    return DEFAULT_RUNTIME_DIR


def runtime_dir_from_env() -> Path:
    raw = os.environ.get(ENV_RUNTIME_DIR)
    if raw:
        return Path(raw).resolve()
    return default_runtime_dir().resolve()


def services_dir(runtime_dir: Path) -> Path:
    return runtime_dir / "services"


def supervisor_file(runtime_dir: Path) -> Path:
    return runtime_dir / "supervisor.json"


def service_file(runtime_dir: Path, service_name: str) -> Path:
    return services_dir(runtime_dir) / f"{service_name}.json"


def ensure_runtime_layout(runtime_dir: Path) -> None:
    runtime_dir.mkdir(parents=True, exist_ok=True)
    services_dir(runtime_dir).mkdir(parents=True, exist_ok=True)


def generate_session_id() -> str:
    return uuid.uuid4().hex


def now_wall_time() -> float:
    return time.time()


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True)
            fh.write("\n")
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def read_json_file(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return data


def supervisor_payload(
    *,
    session_id: str,
    pid: int,
    pid_start_ticks: int | None,
    services_path: str,
    started_at: float,
    heartbeat_at: float,
) -> dict[str, Any]:
    return {
        "session_id": session_id,
        "pid": pid,
        "pid_start_ticks": pid_start_ticks,
        "started_at": started_at,
        "heartbeat_at": heartbeat_at,
        "services_path": services_path,
    }


def service_payload(
    *,
    service: str,
    session_id: str,
    wrapper_pid: int,
    wrapper_pid_start_ticks: int | None,
    child_pid: int | None,
    child_pid_start_ticks: int | None,
    started_at: float,
    heartbeat_at: float,
    cmd: list[str],
    status: str,
) -> dict[str, Any]:
    return {
        "service": service,
        "session_id": session_id,
        "wrapper_pid": wrapper_pid,
        "wrapper_pid_start_ticks": wrapper_pid_start_ticks,
        "child_pid": child_pid,
        "child_pid_start_ticks": child_pid_start_ticks,
        "started_at": started_at,
        "heartbeat_at": heartbeat_at,
        "cmd": cmd,
        "status": status,
    }


def lease_is_valid(
    supervisor_state: dict[str, Any] | None,
    *,
    expected_session_id: str,
    stale_after_s: float,
    now: float | None = None,
) -> bool:
    if supervisor_state is None:
        return False
    if supervisor_state.get("session_id") != expected_session_id:
        return False
    heartbeat_at = supervisor_state.get("heartbeat_at")
    if not isinstance(heartbeat_at, (int, float)):
        return False
    if now is None:
        now = now_wall_time()
    return (now - float(heartbeat_at)) <= stale_after_s


def load_supervisor_state(runtime_dir: Path) -> dict[str, Any] | None:
    return read_json_file(supervisor_file(runtime_dir))


def load_service_state(runtime_dir: Path, service_name: str) -> dict[str, Any] | None:
    return read_json_file(service_file(runtime_dir, service_name))


def _probe_process(
    platform,
    pid: int | None,
    expected_start_ticks: int | None,
) -> tuple[bool, str | None]:
    """Is this pid the process we expect? Catches pid reuse."""
    if pid is None or pid <= 0:
        return False, "no pid"
    if not platform.pid_is_alive(pid):
        return False, "pid dead"
    if expected_start_ticks is None:
        return True, None  # caller didn't record ticks; trust pid_is_alive
    live_ticks = platform.process_start_ticks(pid)
    if live_ticks is None:
        return False, "pid gone"
    if live_ticks != expected_start_ticks:
        return False, "pid reused"
    return True, None


def probe_supervisor(
    runtime_dir: Path,
    platform,
    *,
    stale_after_s: float = DEFAULT_LEASE_TIMEOUT_S,
    now: float | None = None,
) -> dict[str, Any]:
    """Return structured liveness info for the supervisor.

    Shape: {alive: bool, reason: str | None, payload: dict | None, hb_age_s: float | None}
    """
    payload = load_supervisor_state(runtime_dir)
    if payload is None:
        return {"alive": False, "reason": "no state file", "payload": None, "hb_age_s": None}
    now = now_wall_time() if now is None else now
    hb = payload.get("heartbeat_at")
    hb_age_s = None if not isinstance(hb, (int, float)) else now - float(hb)
    if hb_age_s is None:
        return {"alive": False, "reason": "no heartbeat", "payload": payload, "hb_age_s": None}
    if hb_age_s > stale_after_s:
        return {"alive": False, "reason": "stale heartbeat", "payload": payload, "hb_age_s": hb_age_s}
    alive, reason = _probe_process(platform, payload.get("pid"), payload.get("pid_start_ticks"))
    if not alive:
        return {"alive": False, "reason": reason, "payload": payload, "hb_age_s": hb_age_s}
    return {"alive": True, "reason": None, "payload": payload, "hb_age_s": hb_age_s}


def probe_service(
    runtime_dir: Path,
    service_name: str,
    platform,
    *,
    stale_after_s: float = DEFAULT_SERVICE_STALE_AFTER_S,
    now: float | None = None,
) -> dict[str, Any]:
    """Return structured liveness info for one service.

    Shape: {alive: bool, reason: str | None, payload: dict | None, hb_age_s: float | None}
    """
    payload = load_service_state(runtime_dir, service_name)
    if payload is None:
        return {"alive": False, "reason": "no state file", "payload": None, "hb_age_s": None}
    now = now_wall_time() if now is None else now
    hb = payload.get("heartbeat_at")
    hb_age_s = None if not isinstance(hb, (int, float)) else now - float(hb)
    if hb_age_s is None:
        return {"alive": False, "reason": "no heartbeat", "payload": payload, "hb_age_s": None}
    if hb_age_s > stale_after_s:
        return {"alive": False, "reason": "stale heartbeat", "payload": payload, "hb_age_s": hb_age_s}
    alive, reason = _probe_process(
        platform,
        payload.get("child_pid"),
        payload.get("child_pid_start_ticks"),
    )
    if not alive:
        return {"alive": False, "reason": reason, "payload": payload, "hb_age_s": hb_age_s}
    return {"alive": True, "reason": None, "payload": payload, "hb_age_s": hb_age_s}
