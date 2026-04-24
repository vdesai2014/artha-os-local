"""Supervisor daemon — reads services.yaml, manages service processes, and
maintains the portable runtime lease used by supervised children."""

from __future__ import annotations

import argparse
import asyncio
import ctypes
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import yaml

from core.config import nats_connect
from core.supervision import (
    DEFAULT_HEARTBEAT_INTERVAL_S,
    DEFAULT_LEASE_TIMEOUT_S,
    ENV_LEASE_TIMEOUT_S,
    ENV_SERVICES_PATH,
    ENV_RUNTIME_DIR,
    ENV_SERVICE_NAME,
    ENV_SESSION_ID,
    ensure_runtime_layout,
    generate_session_id,
    now_wall_time,
    supervisor_file,
    supervisor_payload,
    write_json_atomic,
)
import core.types as shm_types
from supervisor.platform import get_platform_adapter


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Artha-OS supervisor")
    parser.add_argument(
        "--services",
        default=os.environ.get("SERVICES_PATH", "services.yaml"),
        help="Path to services.yaml to boot",
    )
    parser.add_argument(
        "--runtime-dir",
        default=str(Path(".artha/run")),
        help="Portable runtime metadata directory",
    )
    parser.add_argument(
        "--lease-timeout",
        type=float,
        default=DEFAULT_LEASE_TIMEOUT_S,
        help="Seconds before a missing heartbeat is considered invalid",
    )
    parser.add_argument(
        "--heartbeat-interval",
        type=float,
        default=DEFAULT_HEARTBEAT_INTERVAL_S,
        help="Seconds between supervisor heartbeat updates",
    )
    return parser.parse_args()


def _parse_type_check_output(stdout: str) -> dict[str, dict]:
    types: dict[str, dict] = {}
    current_type = None
    for line in stdout.strip().splitlines():
        parts = line.split()
        if len(parts) == 4 and parts[0] == "TYPE" and parts[2] == "SIZE":
            current_type = parts[1]
            types[current_type] = {"size": int(parts[3]), "fields": {}}
        elif len(parts) == 6 and parts[0] == "FIELD" and parts[2] == "OFFSET" and parts[4] == "SIZE":
            if current_type is not None:
                types[current_type]["fields"][parts[1]] = {
                    "offset": int(parts[3]),
                    "size": int(parts[5]),
                }
    return types


def _check_ipc_types(services: dict) -> None:
    for name, svc in services.items():
        if not svc.get("type_check"):
            continue

        cmd = svc["cmd"][0]
        try:
            result = subprocess.run(
                [cmd, "--type-check"],
                capture_output=True,
                text=True,
                timeout=5,
            )
        except FileNotFoundError:
            raise RuntimeError(
                f"[supervisor] Type check for {name}: binary not found at '{cmd}'. "
                f"Build the service before boot."
            )

        if result.returncode != 0:
            raise RuntimeError(
                f"[supervisor] Type check for {name} exited {result.returncode}: "
                f"{result.stderr.strip()}"
            )

        rust_types = _parse_type_check_output(result.stdout)
        ipc = svc.get("ipc", {})
        all_type_names = set(ipc.get("publishes", {}).values()) | set(ipc.get("subscribes", {}).values())

        for type_name in all_type_names:
            py_cls = getattr(shm_types, type_name, None)
            if py_cls is None:
                raise RuntimeError(
                    f"[supervisor] {name}: type '{type_name}' declared in manifest "
                    f"but not found in core/types.py"
                )

            if type_name not in rust_types:
                raise RuntimeError(
                    f"[supervisor] {name}: Rust binary does not report type '{type_name}' "
                    f"(reported: {list(rust_types.keys())})"
                )

            rust_info = rust_types[type_name]
            py_size = ctypes.sizeof(py_cls)
            if rust_info["size"] != py_size:
                raise RuntimeError(
                    f"[supervisor] TYPE SIZE MISMATCH {name}/{type_name}: "
                    f"Rust={rust_info['size']} bytes, Python={py_size} bytes"
                )

            for field_name, _ in py_cls._fields_:
                py_offset = getattr(py_cls, field_name).offset
                py_field_size = getattr(py_cls, field_name).size
                rust_field = rust_info["fields"].get(field_name)

                if rust_field is None:
                    raise RuntimeError(
                        f"[supervisor] FIELD MISSING {type_name}.{field_name}: "
                        f"exists in Python but not reported by Rust binary"
                    )

                if rust_field["offset"] != py_offset or rust_field["size"] != py_field_size:
                    raise RuntimeError(
                        f"[supervisor] FIELD MISMATCH {type_name}.{field_name}: "
                        f"Rust(offset={rust_field['offset']}, size={rust_field['size']}) vs "
                        f"Python(offset={py_offset}, size={py_field_size})"
                    )

        print(f"[supervisor] Type check passed for {name}")


class Supervisor:
    def __init__(
        self,
        *,
        services_path: Path,
        runtime_dir: Path,
        lease_timeout_s: float,
        heartbeat_interval_s: float,
    ):
        self.services_path = services_path.resolve()
        self.runtime_dir = runtime_dir.resolve()
        self.lease_timeout_s = lease_timeout_s
        self.heartbeat_interval_s = heartbeat_interval_s
        self.session_id = generate_session_id()
        self.platform = get_platform_adapter()
        self.nc = None
        self.services: dict = {}
        self.processes: dict[str, object] = {}
        self.log_files: dict[str, tuple[object, object]] = {}
        self.shutdown_event = asyncio.Event()
        self.crash_counts: dict[str, int] = {}
        self.last_start_time: dict[str, float] = {}
        self.restart_tasks: dict[str, asyncio.Task] = {}
        self.started_at = now_wall_time()

    def _write_supervisor_state(self) -> None:
        write_json_atomic(
            supervisor_file(self.runtime_dir),
            supervisor_payload(
                session_id=self.session_id,
                pid=os.getpid(),
                pid_start_ticks=self.platform.process_start_ticks(os.getpid()),
                services_path=str(self.services_path),
                started_at=self.started_at,
                heartbeat_at=now_wall_time(),
            ),
        )

    def _reload_services(self) -> None:
        with self.services_path.open("r", encoding="utf-8") as fh:
            self.services = yaml.safe_load(fh) or {}
        self._write_supervisor_state()
        print(f"[supervisor] Services reloaded: {self.services_path}")

    def _close_log_files(self, name: str) -> None:
        fds = self.log_files.pop(name, None)
        if fds:
            for fh in fds:
                try:
                    fh.close()
                except Exception:
                    pass

    def _service_command(self, name: str) -> list[str]:
        svc = self.services[name]
        cmd = list(svc["cmd"])
        if cmd[0] in ("python", "python3"):
            cmd[0] = sys.executable
        return [
            sys.executable,
            "-m",
            "supervisor.wrapper",
            "--service-name",
            name,
            "--runtime-dir",
            str(self.runtime_dir),
            "--session-id",
            self.session_id,
            "--lease-timeout",
            str(self.lease_timeout_s),
            "--",
            *cmd,
        ]

    def _service_env(self, name: str) -> dict[str, str]:
        svc = self.services[name]
        env = os.environ.copy()
        repo_root = str(Path(__file__).resolve().parent.parent)
        existing_pythonpath = env.get("PYTHONPATH")
        env["PYTHONPATH"] = (
            f"{repo_root}{os.pathsep}{existing_pythonpath}"
            if existing_pythonpath
            else repo_root
        )
        env["PYTHONUNBUFFERED"] = "1"
        env[ENV_RUNTIME_DIR] = str(self.runtime_dir)
        env[ENV_SESSION_ID] = self.session_id
        env[ENV_SERVICE_NAME] = name
        env[ENV_LEASE_TIMEOUT_S] = str(self.lease_timeout_s)
        env[ENV_SERVICES_PATH] = str(self.services_path)

        for key, value in svc.get("env", {}).items():
            env[key] = str(value)

        if "ipc" in svc:
            env["IPC_PUBLISHES"] = json.dumps(svc["ipc"].get("publishes", {}))
            env["IPC_SUBSCRIBES"] = json.dumps(svc["ipc"].get("subscribes", {}))

        return env

    def _start_service(self, name: str) -> None:
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        self._close_log_files(name)
        out_file = (log_dir / f"{name}.out").open("a", encoding="utf-8")
        err_file = (log_dir / f"{name}.err").open("a", encoding="utf-8")
        self.log_files[name] = (out_file, err_file)

        proc = self.platform.launch_process(
            self._service_command(name),
            env=self._service_env(name),
            stdout=out_file,
            stderr=err_file,
        )
        self.processes[name] = proc
        self.last_start_time[name] = time.time()
        print(f"[supervisor] Booted {name} wrapper (PID: {proc.pid})")

    def _stop_service(self, name: str) -> None:
        proc = self.processes.pop(name, None)
        if proc and proc.poll() is None:
            self.platform.terminate_process_tree(proc.pid, grace_period_s=2.0)
            print(f"[supervisor] Stopped {name}")
        self._close_log_files(name)

    def _cancel_restart_task(self, name: str) -> None:
        task = self.restart_tasks.pop(name, None)
        if task is not None:
            task.cancel()

    def _schedule_restart(self, name: str, delay: float) -> None:
        if self.shutdown_event.is_set():
            return
        existing = self.restart_tasks.get(name)
        if existing is not None and not existing.done():
            return
        self.restart_tasks[name] = asyncio.create_task(self._delayed_restart(name, delay))

    async def _delayed_restart(self, name: str, delay: float) -> None:
        try:
            await asyncio.sleep(delay)
            if self.shutdown_event.is_set():
                return
            if name in self.processes:
                return
            self._reload_services()
            self._start_service(name)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            print(f"[supervisor] Restart failed for {name}: {exc}")
            if not self.shutdown_event.is_set():
                backoff = min(30.0, max(1.0, delay * 2))
                self._schedule_restart(name, backoff)
        finally:
            task = self.restart_tasks.get(name)
            if task is asyncio.current_task():
                self.restart_tasks.pop(name, None)

    async def _handle_get_services(self, msg) -> None:
        payload = []
        for name in self.services:
            proc = self.processes.get(name)
            is_alive = proc is not None and proc.poll() is None
            payload.append(
                {
                    "name": name,
                    "status": "running" if is_alive else "stopped",
                    "pid": proc.pid if is_alive else None,
                }
            )
        await msg.respond(json.dumps({"services": payload}).encode())

    async def _handle_restart_service(self, msg) -> None:
        req = json.loads(msg.data.decode())
        target = req.get("name")
        self._reload_services()
        if target not in self.services:
            await msg.respond(json.dumps({"success": False, "error": "Unknown service"}).encode())
            return
        self.crash_counts.pop(target, None)
        self._cancel_restart_task(target)
        self._stop_service(target)
        self._start_service(target)
        await msg.respond(json.dumps({"success": True}).encode())

    async def start(self) -> None:
        ensure_runtime_layout(self.runtime_dir)
        self.platform.reap_runtime_processes(self.runtime_dir)
        self.platform.cleanup_ipc_artifacts()
        self._reload_services()
        _check_ipc_types(self.services)
        self.nc = await nats_connect("supervisor")

        await self.nc.subscribe("cmd.get-services", cb=self._handle_get_services)
        await self.nc.subscribe("cmd.restart-service", cb=self._handle_restart_service)

        for name in self.services:
            self._start_service(name)

        try:
            while not self.shutdown_event.is_set():
                self._write_supervisor_state()
                for name, proc in list(self.processes.items()):
                    if proc.poll() is None:
                        continue

                    uptime = time.time() - self.last_start_time.get(name, time.time())
                    if uptime > 5.0:
                        self.crash_counts[name] = 1
                    else:
                        self.crash_counts[name] = self.crash_counts.get(name, 0) + 1
                    backoff = min(30.0, 2.0 ** (self.crash_counts[name] - 1))
                    print(
                        f"[supervisor] WARNING: {name} crashed "
                        f"(uptime={uptime:.1f}s), restarting in {backoff}s"
                    )
                    del self.processes[name]
                    self._schedule_restart(name, backoff)

                await asyncio.sleep(self.heartbeat_interval_s)
        except asyncio.CancelledError:
            pass
        finally:
            try:
                supervisor_file(self.runtime_dir).unlink(missing_ok=True)
            except Exception:
                pass

            for name in list(self.restart_tasks.keys()):
                self._cancel_restart_task(name)
            for name in reversed(list(self.processes.keys())):
                try:
                    self._stop_service(name)
                except Exception as exc:
                    print(f"[supervisor] Error stopping {name}: {exc}")
            if self.nc is not None:
                await self.nc.drain()


def main() -> None:
    args = parse_args()
    sup = Supervisor(
        services_path=Path(args.services),
        runtime_dir=Path(args.runtime_dir),
        lease_timeout_s=args.lease_timeout,
        heartbeat_interval_s=args.heartbeat_interval,
    )
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, sup.shutdown_event.set)
        except NotImplementedError:
            pass
    loop.run_until_complete(sup.start())


if __name__ == "__main__":
    main()
