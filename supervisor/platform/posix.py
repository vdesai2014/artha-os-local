from __future__ import annotations

import os
import shutil
import signal
import subprocess
import time
from pathlib import Path

from core.supervision import read_json_file, services_dir, supervisor_file


class PosixPlatformAdapter:
    _EXPECTED_CMDLINE_SNIPPETS = (
        "supervisor.main",
        "supervisor.wrapper",
    )

    def launch_process(
        self,
        cmd: list[str],
        *,
        env: dict[str, str],
        stdout,
        stderr,
    ) -> subprocess.Popen:
        return subprocess.Popen(
            cmd,
            env=env,
            stdout=stdout,
            stderr=stderr,
            preexec_fn=os.setsid,
        )

    def process_start_ticks(self, pid: int) -> int | None:
        stat_path = Path(f"/proc/{pid}/stat")
        try:
            raw = stat_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        except OSError:
            return None

        try:
            return int(raw.rsplit(")", 1)[1].split()[19])
        except (IndexError, ValueError):
            return None

    def process_cmdline(self, pid: int) -> str | None:
        cmdline_path = Path(f"/proc/{pid}/cmdline")
        try:
            raw = cmdline_path.read_bytes()
        except FileNotFoundError:
            return None
        except OSError:
            return None
        if not raw:
            return None
        return raw.replace(b"\x00", b" ").decode("utf-8", errors="replace").strip()

    def _matches_expected_process(
        self,
        pid: int,
        *,
        expected_start_ticks: int | None,
    ) -> bool:
        if pid <= 1 or pid == os.getpid():
            return False
        if expected_start_ticks is None:
            return False
        live_start_ticks = self.process_start_ticks(pid)
        if live_start_ticks != expected_start_ticks:
            return False
        cmdline = self.process_cmdline(pid)
        if not cmdline:
            return False
        return any(snippet in cmdline for snippet in self._EXPECTED_CMDLINE_SNIPPETS)

    def terminate_process_tree(self, pid: int, *, grace_period_s: float = 2.0) -> None:
        if pid <= 1 or pid == os.getpid():
            return
        try:
            pgid = os.getpgid(pid)
        except ProcessLookupError:
            return
        except OSError:
            return
        if pgid <= 1:
            return

        try:
            os.killpg(pgid, signal.SIGTERM)
        except ProcessLookupError:
            return
        except OSError:
            return

        try:
            os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            pass
        except OSError:
            pass

        if grace_period_s > 0:
            deadline = time.monotonic() + grace_period_s
            while time.monotonic() < deadline:
                if not self.pid_is_alive(pid):
                    return
                time.sleep(0.1)

        if self.pid_is_alive(pid):
            try:
                os.killpg(pgid, signal.SIGKILL)
            except ProcessLookupError:
                return
            except OSError:
                return

    def pid_is_alive(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    def reap_runtime_processes(self, runtime_dir: Path) -> None:
        paths = [supervisor_file(runtime_dir)]
        svc_dir = services_dir(runtime_dir)
        if svc_dir.exists():
            paths.extend(sorted(svc_dir.glob("*.json")))

        seen: set[int] = set()
        for path in paths:
            data = read_json_file(path)
            if not data:
                continue
            for key, start_key in (
                ("wrapper_pid", "wrapper_pid_start_ticks"),
                ("child_pid", "child_pid_start_ticks"),
                ("pid", "pid_start_ticks"),
            ):
                pid = data.get(key)
                start_ticks = data.get(start_key)
                if not isinstance(pid, int) or pid <= 0 or pid in seen:
                    continue
                if not isinstance(start_ticks, int):
                    continue
                if not self._matches_expected_process(pid, expected_start_ticks=start_ticks):
                    continue
                seen.add(pid)
                self.terminate_process_tree(pid, grace_period_s=0.5)

    def cleanup_ipc_artifacts(self) -> None:
        dev_shm = Path("/dev/shm")
        if dev_shm.exists():
            for path in dev_shm.glob("iox2_*"):
                path.unlink(missing_ok=True)

        tmp_dir = Path("/tmp")
        for path in tmp_dir.glob("iox2_*"):
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            else:
                path.unlink(missing_ok=True)

        for path in tmp_dir.glob("*.shm_state"):
            path.unlink(missing_ok=True)

        iceoryx_tmp = tmp_dir / "iceoryx2"
        if iceoryx_tmp.exists():
            shutil.rmtree(iceoryx_tmp, ignore_errors=True)
