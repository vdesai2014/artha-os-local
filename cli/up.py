"""artha up — start nats + local_tool + supervisor in order, with readiness gates."""

from __future__ import annotations

import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx

from cli.common import (
    bold,
    dim,
    find_repo_root,
    green,
    local_tool_url,
    nats_url,
    parse_nats_conf,
    read_local_tool_state,
    read_nats_state,
    runtime_dir,
    red,
    state_pid_matches,
)
from core.supervision import load_supervisor_state, write_json_atomic
from supervisor.platform import get_platform_adapter


READINESS_TIMEOUT_S = 15.0
POLL_INTERVAL_S = 0.2


def _tcp_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.3):
            return True
    except OSError:
        return False


def _poll(predicate, timeout_s: float, label: str) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(POLL_INTERVAL_S)
    raise SystemExit(red(f"timed out waiting for {label} to become ready"))


def _already_running(root: Path, platform) -> list[str]:
    """Return list of component names that look alive already."""
    blockers: list[str] = []
    # NATS
    conf = parse_nats_conf(root / "config" / "nats.conf")
    port = conf.get("port", 4222)
    # WARNING: TCP-open is only a port-level check. A foreign NATS process
    # can occupy this port; state-file validation below is what decides
    # whether artha is allowed to kill it.
    if _tcp_open("localhost", port):
        blockers.append(f"nats-server (port {port})")
    # local_tool state file + pid alive
    st = read_local_tool_state(root)
    alive, _reason = state_pid_matches(platform, st)
    if alive:
        blockers.append(f"local_tool (pid {st['pid']})")
    # supervisor state file + pid alive
    sv = load_supervisor_state(runtime_dir(root))
    alive, _reason = state_pid_matches(platform, sv)
    if alive:
        blockers.append(f"supervisor (pid {sv['pid']})")
    return blockers


def _ensure_dirs(root: Path) -> None:
    (root / "logs").mkdir(exist_ok=True)
    (root / ".artha" / "run").mkdir(parents=True, exist_ok=True)


def _write_nats_state(root: Path, proc: subprocess.Popen, *, port: int, cmd: list[str], platform) -> None:
    run_dir = root / ".artha" / "run"
    payload = {
        "pid": proc.pid,
        "pid_start_ticks": platform.process_start_ticks(proc.pid),
        "host": "localhost",
        "port": port,
        "url": f"nats://localhost:{port}",
        "cmd": cmd,
        "started_at": time.time(),
    }
    write_json_atomic(run_dir / "nats.json", payload)
    # Legacy pid file retained so older docs/tools still have a simple path.
    (run_dir / "nats.pid").write_text(f"{proc.pid}\n", encoding="utf-8")


def _start_nats(root: Path, platform) -> subprocess.Popen:
    conf_path = root / "config" / "nats.conf"
    pid_path = root / ".artha" / "run" / "nats.pid"
    conf = parse_nats_conf(conf_path)
    port = conf.get("port", 4222)
    log_out = (root / "logs" / "nats.out").open("a", encoding="utf-8")
    log_err = (root / "logs" / "nats.err").open("a", encoding="utf-8")
    if not shutil.which("nats-server"):
        raise SystemExit(red("nats-server not found on PATH — see docs/onboarding-steps.md §2"))

    # Prefer -c <conf> for full fidelity. Some snap-packaged builds can't
    # read paths outside ~/snap (config AND pidfile both fail), in which
    # case we retry with bare CLI flags and Python writes the pid file
    # ourselves so `artha down` still knows what to kill.
    try_conf = [
        "nats-server", "-c", str(conf_path), "-P", str(pid_path),
    ]
    try_flags = ["nats-server", "--port", str(port)]

    proc = subprocess.Popen(try_conf, stdout=log_out, stderr=log_err, start_new_session=True)
    # Give it a moment; if it died quickly with a config-read error, retry.
    time.sleep(0.3)
    if proc.poll() is not None:
        tail = (root / "logs" / "nats.err").read_text(errors="replace")[-500:]
        confined = "permission denied" in tail or "open config file" in tail
        if confined:
            print(dim("  (nats config/pidfile unreadable — likely snap-confined; retrying with bare flags)"))
            proc = subprocess.Popen(try_flags, stdout=log_out, stderr=log_err, start_new_session=True)
        else:
            raise SystemExit(red(f"nats-server exited immediately. tail:\n{tail}"))
    _write_nats_state(root, proc, port=port, cmd=try_flags if proc.args == try_flags else try_conf, platform=platform)
    return proc


def _start_local_tool(root: Path, host: str, port: int) -> subprocess.Popen:
    env = os.environ.copy()
    env["ARTHA_HOME"] = str(root)
    env["ARTHA_LOCAL_TOOL_HOST"] = host
    env["ARTHA_LOCAL_TOOL_PORT"] = str(port)
    env["PYTHONUNBUFFERED"] = "1"
    repo_root_str = str(root)
    env["PYTHONPATH"] = f"{repo_root_str}{os.pathsep}{env.get('PYTHONPATH', '')}"
    log_out = (root / "logs" / "local_tool.out").open("a", encoding="utf-8")
    log_err = (root / "logs" / "local_tool.err").open("a", encoding="utf-8")
    return subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "local_tool.server.app:app",
         "--host", host, "--port", str(port)],
        cwd=str(root),
        env=env,
        stdout=log_out,
        stderr=log_err,
        start_new_session=True,
    )


def _start_supervisor(root: Path) -> subprocess.Popen:
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    repo_root_str = str(root)
    env["PYTHONPATH"] = f"{repo_root_str}{os.pathsep}{env.get('PYTHONPATH', '')}"
    log_out = (root / "logs" / "supervisor.out").open("a", encoding="utf-8")
    log_err = (root / "logs" / "supervisor.err").open("a", encoding="utf-8")
    return subprocess.Popen(
        [sys.executable, "-m", "supervisor.main", "--services", "services.yaml"],
        cwd=str(root),
        env=env,
        stdout=log_out,
        stderr=log_err,
        start_new_session=True,
    )


def _kill_from_state(root: Path, platform) -> None:
    """Kill anything `up` would conflict with. Used by --force."""
    # supervisor
    sv = load_supervisor_state(runtime_dir(root))
    alive, reason = state_pid_matches(platform, sv)
    if alive:
        print(dim(f"  kill supervisor pid {sv['pid']}"))
        platform.terminate_process_tree(sv["pid"], grace_period_s=3.0)
    elif sv and reason == "pid reused":
        print(dim(f"  skip supervisor stale pid {sv.get('pid')} (pid reused)"))
    # local_tool
    lt = read_local_tool_state(root)
    alive, reason = state_pid_matches(platform, lt)
    if alive:
        print(dim(f"  kill local_tool pid {lt['pid']}"))
        try:
            os.kill(lt["pid"], signal.SIGTERM)
        except OSError:
            pass
    elif lt and reason == "pid reused":
        print(dim(f"  skip local_tool stale pid {lt.get('pid')} (pid reused)"))
    # nats — from pid file
    nats_state = read_nats_state(root)
    alive, reason = state_pid_matches(platform, nats_state)
    if alive:
        try:
            pid = nats_state["pid"]
            print(dim(f"  kill nats pid {pid}"))
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    elif nats_state and reason == "pid reused":
        print(dim(f"  skip nats stale pid {nats_state.get('pid')} (pid reused)"))
    time.sleep(1.0)


def run(args) -> int:
    root = find_repo_root()
    platform = get_platform_adapter()
    _ensure_dirs(root)

    blockers = _already_running(root, platform)
    if blockers:
        if not args.force:
            print(red("already running: " + ", ".join(blockers)))
            print(dim("  use `artha down` first, or `artha up --force` to kill and restart"))
            return 1
        print(dim("--force: killing existing components"))
        _kill_from_state(root, platform)

    conf = parse_nats_conf(root / "config" / "nats.conf")
    nats_port = conf.get("port", 4222)
    lt_host = os.environ.get("ARTHA_LOCAL_TOOL_HOST", "127.0.0.1")
    lt_port = int(os.environ.get("ARTHA_LOCAL_TOOL_PORT", "8000"))

    # 1. NATS
    print(bold("[1/3] nats") + f"        starting (port {nats_port})...", end="", flush=True)
    _start_nats(root, platform)
    _poll(lambda: _tcp_open("localhost", nats_port), READINESS_TIMEOUT_S, f"nats :{nats_port}")
    print(" " + green("ready"))

    # 2. local_tool
    print(bold("[2/3] local_tool") + f"  starting (port {lt_port})...", end="", flush=True)
    _start_local_tool(root, lt_host, lt_port)

    def _health_ok() -> bool:
        try:
            r = httpx.get(f"http://{lt_host}:{lt_port}/api/health", timeout=0.5)
            if r.status_code != 200:
                return False
            payload = r.json()
            # WARNING: this also protects against an old/foreign local_tool
            # already listening on the same port after uvicorn bind failure.
            return payload.get("service") == "artha-local-tool" and payload.get("home") == str(root)
        except httpx.RequestError:
            return False
        except ValueError:
            return False

    _poll(_health_ok, READINESS_TIMEOUT_S, f"local_tool :{lt_port}")
    print(" " + green("ready") + dim(f"  http://{lt_host}:{lt_port}"))
    if not (root / "frontend" / "dist" / "index.html").exists():
        print(dim("  warning: frontend/dist missing; :8000 will serve backend only. Run `cd frontend && npm install && npm run build`, then restart."))

    # 3. supervisor
    print(bold("[3/3] supervisor") + "  starting...", end="", flush=True)
    _start_supervisor(root)

    def _supervisor_fresh() -> bool:
        state = load_supervisor_state(runtime_dir(root))
        if not state:
            return False
        hb = state.get("heartbeat_at")
        if not isinstance(hb, (int, float)):
            return False
        return (time.time() - hb) <= 3.0

    _poll(_supervisor_fresh, READINESS_TIMEOUT_S, "supervisor heartbeat")
    print(" " + green("ready"))
    print()
    print(green("stack up.") + dim(f"  `artha status` for details"))
    return 0
