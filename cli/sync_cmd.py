"""artha push / pull / clone — CLI wrappers over the local sync engine."""

from __future__ import annotations

import json
import time
from pathlib import Path

import httpx

from cli.common import find_repo_root, local_tool_url, die, dim


def _progress(line: str) -> None:
    print(dim(line), flush=True)


def _post_execute(url: str, body: dict, timeout: float = 1800.0) -> dict:
    """One long-blocking call. Sync has no progress stream today (see to-do)."""
    try:
        resp = httpx.post(f"{url}/api/sync/execute", json=body, timeout=timeout)
    except httpx.RequestError as exc:
        die(f"local_tool unreachable at {url}: {exc}")
    if resp.status_code >= 400:
        try:
            detail = resp.json().get("detail", resp.text)
        except ValueError:
            detail = resp.text
        die(f"sync failed ({resp.status_code}): {detail}")
    return resp.json()


def _post_job(url: str, body: dict) -> dict | None:
    try:
        resp = httpx.post(f"{url}/api/sync/jobs", json=body, timeout=10.0)
    except httpx.RequestError as exc:
        die(f"local_tool unreachable at {url}: {exc}")
    if resp.status_code == 404:
        return None
    if resp.status_code >= 400:
        try:
            detail = resp.json().get("detail", resp.text)
        except ValueError:
            detail = resp.text
        die(f"sync job failed to start ({resp.status_code}): {detail}")
    return resp.json()


def _get_job(url: str, job_id: str) -> dict:
    try:
        resp = httpx.get(f"{url}/api/sync/jobs/{job_id}", timeout=10.0)
    except httpx.RequestError as exc:
        die(f"local_tool unreachable at {url}: {exc}")
    if resp.status_code >= 400:
        try:
            detail = resp.json().get("detail", resp.text)
        except ValueError:
            detail = resp.text
        die(f"sync job poll failed ({resp.status_code}): {detail}")
    return resp.json()


def _fmt_bytes(value: int | float | None) -> str:
    n = float(value or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f}{unit}" if unit != "B" else f"{int(n)}B"
        n /= 1024
    return f"{n:.1f}GB"


def _job_line(job: dict) -> str:
    plan = job.get("plan") or {}
    summary = plan.get("summary") or {}
    execute = job.get("execute") or {}
    counters = execute.get("counters") or {}
    events = execute.get("events") or []
    latest = events[-1] if events else {}
    file_total = int(summary.get("file_actions") or 0)
    file_done = int(counters.get("files_done") or 0)
    byte_total = int(summary.get("file_bytes") or 0)
    byte_done = int(counters.get("bytes_done") or 0)
    msg = latest.get("message") or job.get("status")
    if file_total:
        return f"{job.get('status')} files {file_done}/{file_total} {_fmt_bytes(byte_done)}/{_fmt_bytes(byte_total)} — {msg}"
    return f"{job.get('status')} — {msg}"


def _wait_job(url: str, job_id: str, *, quiet: bool = False) -> dict:
    last_line = None
    while True:
        job = _get_job(url, job_id)
        line = _job_line(job)
        if not quiet and line != last_line:
            _progress(line)
            last_line = line
        status = job.get("status")
        if status == "succeeded":
            return job.get("result") or {"success": True, "progress": {"job_id": job_id}}
        if status == "failed":
            die(f"sync job failed: {job.get('error') or 'unknown error'}")
        time.sleep(1.0)


def run(args) -> int:
    root = find_repo_root()
    url = local_tool_url(root)
    quiet = bool(getattr(args, "json", False))

    op = args.cmd  # "push" | "pull" | "clone"
    if op == "clone":
        body = {
            "operation": "clone",
            "entity_type": "project",
            "entity_id": args.project_id,
        }
        if not quiet:
            _progress(f"cloning {args.project_id}")
    else:
        body = {
            "operation": op,
            "entity_type": args.entity_type,
            "entity_id": args.entity_id,
            "include_manifests": bool(args.include_manifests),
            "include_descendants": bool(args.include_descendants),
        }
        if not quiet:
            _progress(f"{op}ing {args.entity_type} {args.entity_id}")

    job = _post_job(url, body)
    if job is None:
        if not quiet:
            _progress("sync jobs endpoint unavailable; falling back to blocking execute")
        result = _post_execute(url, body)
    else:
        if not quiet:
            _progress(f"sync job {job['job_id']}")
        result = _wait_job(url, job["job_id"], quiet=quiet)

    if getattr(args, "output", None):
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, indent=2, default=str) + "\n", encoding="utf-8")
        if not quiet:
            _progress(f"wrote sync result: {output_path}")

    if getattr(args, "json", False):
        print(json.dumps(result, indent=2, default=str))
        return 0

    # Condensed summary. Full dump available via `--json`? keep simple for v1.
    summary_keys = ("success", "created", "patched", "uploaded", "copied", "id_remaps", "warnings")
    for k in summary_keys:
        if k in result and result[k]:
            print(f"{k}: {json.dumps(result[k], indent=2, default=str)}")
    errors = result.get("errors") or []
    if errors:
        print(f"errors: {json.dumps(errors, indent=2, default=str)}")
        return 1
    return 0
