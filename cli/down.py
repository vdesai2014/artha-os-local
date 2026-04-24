"""artha down — stop supervisor, then local_tool, then nats (reverse order)."""

from __future__ import annotations

import os
import signal
import time
from pathlib import Path

from cli.common import (
    bold,
    dim,
    find_repo_root,
    green,
    read_local_tool_state,
    runtime_dir,
    yellow,
)
from core.supervision import load_supervisor_state
from supervisor.platform import get_platform_adapter


def _wait_dead(platform, pid: int, timeout_s: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if not platform.pid_is_alive(pid):
            return True
        time.sleep(0.1)
    return False


def _stop_supervisor(root: Path, platform) -> str:
    sv = load_supervisor_state(runtime_dir(root))
    if not sv or not isinstance(sv.get("pid"), int):
        return yellow("not running")
    pid = sv["pid"]
    if not platform.pid_is_alive(pid):
        return yellow("already dead")
    # Supervisor terminates cleanly via its SIGTERM handler, which in turn
    # brings wrappers down via the lease expiring. terminate_process_tree
    # handles both.
    platform.terminate_process_tree(pid, grace_period_s=4.0)
    if _wait_dead(platform, pid, timeout_s=2.0):
        return green("stopped")
    return yellow("signal sent (still shutting down)")


def _stop_local_tool(root: Path, platform) -> str:
    lt = read_local_tool_state(root)
    if not lt or not isinstance(lt.get("pid"), int):
        return yellow("not running")
    pid = lt["pid"]
    if not platform.pid_is_alive(pid):
        return yellow("already dead")
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError as exc:
        return yellow(f"kill failed: {exc}")
    if _wait_dead(platform, pid):
        return green("stopped")
    # Escalate
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        pass
    return green("stopped") if _wait_dead(platform, pid, 2.0) else yellow("still alive after SIGKILL")


def _stop_nats(root: Path, platform) -> str:
    pid_file = root / ".artha" / "run" / "nats.pid"
    if not pid_file.exists():
        return yellow("no pid file (not started by artha?)")
    try:
        pid = int(pid_file.read_text().strip())
    except ValueError:
        return yellow("unreadable pid file")
    if not platform.pid_is_alive(pid):
        pid_file.unlink(missing_ok=True)
        return yellow("already dead")
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError as exc:
        return yellow(f"kill failed: {exc}")
    if _wait_dead(platform, pid):
        pid_file.unlink(missing_ok=True)
        return green("stopped")
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        pass
    pid_file.unlink(missing_ok=True)
    return green("stopped")


def run(args) -> int:
    root = find_repo_root()
    platform = get_platform_adapter()

    print(bold("[1/3] supervisor") + "  " + _stop_supervisor(root, platform))
    print(bold("[2/3] local_tool") + "  " + _stop_local_tool(root, platform))
    print(bold("[3/3] nats") + "        " + _stop_nats(root, platform))
    print()
    print(green("stack down.") + dim("  `artha status` will show what, if anything, remains"))
    return 0
