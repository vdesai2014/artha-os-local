"""artha push / pull / clone — wrappers over POST /api/sync/execute."""

from __future__ import annotations

import json

import httpx

from cli.common import find_repo_root, local_tool_url, die, dim


def _post_execute(url: str, body: dict, timeout: float = 1800.0) -> dict:
    """One long-blocking call. Sync has no progress-over-HTTP today (see to-do)."""
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


def run(args) -> int:
    root = find_repo_root()
    url = local_tool_url(root)

    op = args.cmd  # "push" | "pull" | "clone"
    if op == "clone":
        body = {
            "operation": "clone",
            "entity_type": "project",
            "entity_id": args.project_id,
        }
        print(dim(f"cloning {args.project_id} — no progress feedback over HTTP today, this may take minutes"))
    else:
        body = {
            "operation": op,
            "entity_type": args.entity_type,
            "entity_id": args.entity_id,
            "include_links": bool(args.include_links),
            "include_descendants": bool(args.include_descendants),
        }
        print(dim(f"{op}ing {args.entity_type} {args.entity_id} — may take minutes for large entities"))

    result = _post_execute(url, body)

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
