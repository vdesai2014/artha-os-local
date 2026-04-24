"""artha logs <name> [-f] — tail logs/<name>.out and logs/<name>.err."""

from __future__ import annotations

import subprocess
import sys

from cli.common import find_repo_root, die


def run(args) -> int:
    root = find_repo_root()
    log_dir = root / "logs"
    out = log_dir / f"{args.name}.out"
    err = log_dir / f"{args.name}.err"
    existing = [p for p in (out, err) if p.exists()]
    if not existing:
        die(
            f"no logs found for {args.name!r} under {log_dir}. "
            "Has it ever run? (`artha status`)"
        )
    cmd = ["tail", f"-n{args.lines}"]
    if args.follow:
        cmd.append("-f")
    cmd.extend(str(p) for p in existing)
    try:
        proc = subprocess.run(cmd)
        return proc.returncode
    except KeyboardInterrupt:
        return 0
