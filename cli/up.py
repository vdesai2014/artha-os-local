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
    runtime_dir,
    red,
)
from core.supervision import load_supervisor_state
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
    if _tcp_open("localhost", port):
        blockers.append(f"nats-server (port {port})")
    # local_tool state file + pid alive
    st = read_local_tool_state(root)
    if st and isinstance(st.get("pid"), int) and platform.pid_is_alive(st["pid"]):
        blockers.append(f"local_tool (pid {st['pid']})")
    # supervisor state file + pid alive
    sv = load_supervisor_state(runtime_dir(root))
    if sv and isinstance(sv.get("pid"), int) and platform.pid_is_alive(sv["pid"]):
        blockers.append(f"supervisor (pid {sv['pid']})")
    return blockers


def _ensure_dirs(root: Path) -> None:
    (root / "logs").mkdir(exist_ok=True)
    (root / ".artha" / "run").mkdir(parents=True, exist_ok=True)


def _start_nats(root: Path) -> subprocess.Popen:
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
            pid_path.parent.mkdir(parents=True, exist_ok=True)
            pid_path.write_text(f"{proc.pid}\n")
        else:
            raise SystemExit(red(f"nats-server exited immediately. tail:\n{tail}"))
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
    if sv and isinstance(sv.get("pid"), int) and platform.pid_is_alive(sv["pid"]):
        print(dim(f"  kill supervisor pid {sv['pid']}"))
        platform.terminate_process_tree(sv["pid"], grace_period_s=3.0)
    # local_tool
    lt = read_local_tool_state(root)
    if lt and isinstance(lt.get("pid"), int) and platform.pid_is_alive(lt["pid"]):
        print(dim(f"  kill local_tool pid {lt['pid']}"))
        try:
            os.kill(lt["pid"], signal.SIGTERM)
        except OSError:
            pass
    # nats — from pid file
    nats_pid_path = root / ".artha" / "run" / "nats.pid"
    if nats_pid_path.exists():
        try:
            pid = int(nats_pid_path.read_text().strip())
            if platform.pid_is_alive(pid):
                print(dim(f"  kill nats pid {pid}"))
                os.kill(pid, signal.SIGTERM)
        except (OSError, ValueError):
            pass
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
    _start_nats(root)
    _poll(lambda: _tcp_open("localhost", nats_port), READINESS_TIMEOUT_S, f"nats :{nats_port}")
    print(" " + green("ready"))

    # 2. local_tool
    print(bold("[2/3] local_tool") + f"  starting (port {lt_port})...", end="", flush=True)
    _start_local_tool(root, lt_host, lt_port)

    def _health_ok() -> bool:
        try:
            r = httpx.get(f"http://{lt_host}:{lt_port}/api/health", timeout=0.5)
            return r.status_code == 200
        except httpx.RequestError:
            return False

    _poll(_health_ok, READINESS_TIMEOUT_S, f"local_tool :{lt_port}")
    print(" " + green("ready") + dim(f"  http://{lt_host}:{lt_port}"))

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
