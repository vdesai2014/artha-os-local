from __future__ import annotations

from pathlib import Path
from subprocess import Popen
from typing import Protocol


class PlatformAdapter(Protocol):
    def launch_process(
        self,
        cmd: list[str],
        *,
        env: dict[str, str],
        stdout,
        stderr,
    ) -> Popen: ...

    def process_start_ticks(self, pid: int) -> int | None: ...

    def terminate_process_tree(self, pid: int, *, grace_period_s: float = 2.0) -> None: ...

    def pid_is_alive(self, pid: int) -> bool: ...

    def reap_runtime_processes(self, runtime_dir: Path) -> None: ...

    def cleanup_ipc_artifacts(self) -> None: ...
