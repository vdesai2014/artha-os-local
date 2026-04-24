from __future__ import annotations

import argparse
import os
import signal
import sys
import time
from pathlib import Path

from core.supervision import (
    DEFAULT_LEASE_TIMEOUT_S,
    DEFAULT_SERVICE_HEARTBEAT_INTERVAL_S,
    ensure_runtime_layout,
    lease_is_valid,
    load_supervisor_state,
    now_wall_time,
    service_file,
    service_payload,
    write_json_atomic,
)
from supervisor.platform import get_platform_adapter


LEASE_POLL_INTERVAL_S = 0.5


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Supervised child wrapper")
    parser.add_argument("--service-name", required=True)
    parser.add_argument("--runtime-dir", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--lease-timeout", type=float, default=DEFAULT_LEASE_TIMEOUT_S)
    parser.add_argument(
        "--heartbeat-interval",
        type=float,
        default=DEFAULT_SERVICE_HEARTBEAT_INTERVAL_S,
        help="Seconds between service json heartbeat updates",
    )
    parser.add_argument("cmd", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.cmd and args.cmd[0] == "--":
        args.cmd = args.cmd[1:]
    if not args.cmd:
        parser.error("missing child command")
    return args


def main() -> int:
    args = parse_args()
    runtime_dir = Path(args.runtime_dir).resolve()
    ensure_runtime_layout(runtime_dir)
    platform = get_platform_adapter()
    started_at = now_wall_time()

    child = None
    stopping = False
    current_status = "starting"
    current_child_pid: int | None = None
    current_child_ticks: int | None = None

    def write_status(status: str, child_pid: int | None) -> None:
        nonlocal current_status, current_child_pid, current_child_ticks
        current_status = status
        current_child_pid = child_pid
        current_child_ticks = (
            platform.process_start_ticks(child_pid) if child_pid is not None else None
        )
        write_json_atomic(
            service_file(runtime_dir, args.service_name),
            service_payload(
                service=args.service_name,
                session_id=args.session_id,
                wrapper_pid=os.getpid(),
                wrapper_pid_start_ticks=platform.process_start_ticks(os.getpid()),
                child_pid=child_pid,
                child_pid_start_ticks=current_child_ticks,
                started_at=started_at,
                heartbeat_at=now_wall_time(),
                cmd=list(args.cmd),
                status=status,
            ),
        )

    def write_heartbeat() -> None:
        """Re-write the service json with a fresh heartbeat_at, preserving status."""
        write_json_atomic(
            service_file(runtime_dir, args.service_name),
            service_payload(
                service=args.service_name,
                session_id=args.session_id,
                wrapper_pid=os.getpid(),
                wrapper_pid_start_ticks=platform.process_start_ticks(os.getpid()),
                child_pid=current_child_pid,
                child_pid_start_ticks=current_child_ticks,
                started_at=started_at,
                heartbeat_at=now_wall_time(),
                cmd=list(args.cmd),
                status=current_status,
            ),
        )

    def stop_child() -> None:
        nonlocal stopping
        if stopping:
            return
        stopping = True
        if child is not None and child.poll() is None:
            platform.terminate_process_tree(child.pid, grace_period_s=1.5)

    def on_signal(signum, _frame):
        stop_child()
        signal_name = signal.Signals(signum).name
        write_status(f"stopping:{signal_name}", child.pid if child is not None else None)
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)

    child_env = os.environ.copy()
    write_status("starting", None)
    child = platform.launch_process(args.cmd, env=child_env, stdout=sys.stdout, stderr=sys.stderr)
    write_status("running", child.pid)

    next_heartbeat_at = time.monotonic() + args.heartbeat_interval

    try:
        while True:
            rc = child.poll()
            if rc is not None:
                write_status(f"exited:{rc}", child.pid)
                return rc

            supervisor_state = load_supervisor_state(runtime_dir)
            if not lease_is_valid(
                supervisor_state,
                expected_session_id=args.session_id,
                stale_after_s=args.lease_timeout,
            ):
                write_status("lease_invalid", child.pid)
                stop_child()
                return 75

            # Filesystem liveness heartbeat for the CLI's status command.
            # Lease check runs every LEASE_POLL_INTERVAL_S; the heartbeat
            # rewrite is throttled to its own (slower) cadence.
            now_mono = time.monotonic()
            if now_mono >= next_heartbeat_at:
                write_heartbeat()
                next_heartbeat_at = now_mono + args.heartbeat_interval

            time.sleep(LEASE_POLL_INTERVAL_S)
    finally:
        if child is not None and child.poll() is None:
            stop_child()
        # Clean up the service state file so `artha status` doesn't report
        # a stale heartbeat after a clean shutdown. The supervisor writes
        # a fresh one on restart, so there's no lost-state risk.
        try:
            service_file(runtime_dir, args.service_name).unlink(missing_ok=True)
        except OSError:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
