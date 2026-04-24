"""artha — CLI for the artha-os runtime.

Dispatch-only. Each subcommand lives in its own module to keep things
grep-friendly. See AGENTS.md + docs/operations/ for context.
"""

from __future__ import annotations

import argparse
import sys


def _add_status(sp) -> None:
    p = sp.add_parser("status", help="aggregate liveness for nats/local_tool/supervisor/services")
    p.add_argument("--json", action="store_true", help="machine-readable output")


def _add_up(sp) -> None:
    p = sp.add_parser("up", help="start nats + local_tool + supervisor in order")
    p.add_argument("--force", action="store_true", help="kill anything already running and restart")


def _add_down(sp) -> None:
    sp.add_parser("down", help="stop supervisor + local_tool + nats")


def _add_restart(sp) -> None:
    p = sp.add_parser("restart", help="restart one supervised service via NATS")
    p.add_argument("service", help="service name")


def _add_logs(sp) -> None:
    p = sp.add_parser("logs", help="tail logs/<name>.out and .err")
    p.add_argument("name", help="service name OR 'nats'/'local_tool'/'supervisor'")
    p.add_argument("-f", "--follow", action="store_true")
    p.add_argument("-n", "--lines", type=int, default=40)


def _add_peek(sp) -> None:
    p = sp.add_parser("peek", help="grab latest snapshot of an SHM topic via the bridge")
    p.add_argument("topic")
    p.add_argument("--type", dest="type_name", help="struct class in core.types (inferred from services.yaml if omitted)")
    p.add_argument("--timeout", type=float, default=3.0)


def _add_camera(sp) -> None:
    p = sp.add_parser("camera", help="save a single frame from a camera topic via video_bridge")
    p.add_argument("topic")
    p.add_argument("--save", help="output path (default /tmp/<topic-sanitized>.png)")
    p.add_argument("--timeout", type=float, default=5.0)


def _add_push(sp) -> None:
    p = sp.add_parser("push", help="push local entity to cloud")
    p.add_argument("entity_type", choices=("project", "run", "manifest"))
    p.add_argument("entity_id")
    p.add_argument("--include-links", action="store_true")
    p.add_argument("--include-descendants", action="store_true")


def _add_pull(sp) -> None:
    p = sp.add_parser("pull", help="pull cloud entity into local store")
    p.add_argument("entity_type", choices=("project", "run", "manifest"))
    p.add_argument("entity_id")
    p.add_argument("--include-links", action="store_true")
    p.add_argument("--include-descendants", action="store_true")


def _add_clone(sp) -> None:
    p = sp.add_parser("clone", help="clone a cloud project with fresh local IDs")
    p.add_argument("project_id")


def _add_provenance(sp) -> None:
    p = sp.add_parser("provenance", help="read/write the provenance override")
    sub = p.add_subparsers(dest="prov_cmd", required=True)

    p_set = sub.add_parser("set", help="set one or more override fields")
    p_set.add_argument("--manifest-id", dest="manifest_id")
    p_set.add_argument("--manifest-name", dest="manifest_name")
    p_set.add_argument("--manifest-type", dest="manifest_type")
    p_set.add_argument("--task", dest="task")
    p_set.add_argument("--task-description", dest="task_description")
    p_set.add_argument("--policy-name", dest="policy_name")
    p_set.add_argument("--source-project-id", dest="source_project_id")
    p_set.add_argument("--source-run-id", dest="source_run_id")
    p_set.add_argument("--source-checkpoint", dest="source_checkpoint")
    p_set.add_argument("--fps", type=int, dest="fps")
    p_set.add_argument("--updated-by", dest="updated_by", default="cli")

    sub.add_parser("get", help="print the current resolved provenance context")
    sub.add_parser("clear", help="clear all override fields")


def _add_nats(sp) -> None:
    p = sp.add_parser("nats", help="raw NATS operations")
    sub = p.add_subparsers(dest="nats_cmd", required=True)

    p_pub = sub.add_parser("pub", help="publish a message")
    p_pub.add_argument("subject")
    p_pub.add_argument("--payload", default="{}", help="JSON payload (default {})")

    p_req = sub.add_parser("req", help="request/reply")
    p_req.add_argument("subject")
    p_req.add_argument("--payload", default="{}", help="JSON payload (default {})")
    p_req.add_argument("--timeout", type=float, default=2.0)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="artha", description="CLI for artha-os")
    sp = parser.add_subparsers(dest="cmd", required=True)
    _add_status(sp)
    _add_up(sp)
    _add_down(sp)
    _add_restart(sp)
    _add_logs(sp)
    _add_peek(sp)
    _add_camera(sp)
    _add_push(sp)
    _add_pull(sp)
    _add_clone(sp)
    _add_provenance(sp)
    _add_nats(sp)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # Lazy-import so each subcommand only pulls in what it needs.
    if args.cmd == "status":
        from cli.status import run
    elif args.cmd == "up":
        from cli.up import run
    elif args.cmd == "down":
        from cli.down import run
    elif args.cmd == "restart":
        from cli.restart import run
    elif args.cmd == "logs":
        from cli.logs import run
    elif args.cmd == "peek":
        from cli.peek import run
    elif args.cmd == "camera":
        from cli.camera import run
    elif args.cmd in ("push", "pull", "clone"):
        from cli.sync_cmd import run
    elif args.cmd == "provenance":
        from cli.provenance import run
    elif args.cmd == "nats":
        from cli.nats_cmd import run
    else:  # pragma: no cover — argparse should prevent this
        parser.error(f"unknown command: {args.cmd}")

    return run(args) or 0


if __name__ == "__main__":
    sys.exit(main())
