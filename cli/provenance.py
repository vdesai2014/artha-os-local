"""artha provenance {set,get,clear} — NATS wrappers over provenance.override.*."""

from __future__ import annotations

import asyncio
import json

from cli.common import find_repo_root, nats_url, die


async def _req(url: str, subject: str, payload: dict, timeout: float = 2.0) -> dict:
    import nats
    nc = await nats.connect(url, max_reconnect_attempts=1, connect_timeout=2.0)
    try:
        resp = await nc.request(subject, json.dumps(payload).encode(), timeout=timeout)
        return json.loads(resp.data.decode()) if resp.data else {}
    finally:
        await nc.drain()


def _build_set_payload(args) -> dict:
    """Include only flags the user actually passed."""
    fields = (
        "manifest_id",
        "manifest_name",
        "manifest_type",
        "task",
        "task_description",
        "policy_name",
        "source_project_id",
        "source_run_id",
        "source_checkpoint",
        "fps",
        "updated_by",
    )
    payload: dict = {}
    for f in fields:
        v = getattr(args, f, None)
        if v is not None:
            payload[f] = v
    return payload


def run(args) -> int:
    root = find_repo_root()
    url = nats_url(root)

    if args.prov_cmd == "set":
        payload = _build_set_payload(args)
        if not payload or set(payload.keys()) == {"updated_by"}:
            die("nothing to set — pass at least one --manifest-name / --manifest-type / ... flag")
        try:
            ctx = asyncio.run(_req(url, "provenance.override.set", payload))
        except Exception as exc:
            die(f"NATS request failed: {exc}")
        print(json.dumps(ctx, indent=2, default=str))
        return 0

    if args.prov_cmd == "get":
        try:
            ctx = asyncio.run(_req(url, "provenance.get", {}))
        except Exception as exc:
            die(f"NATS request failed: {exc}")
        print(json.dumps(ctx, indent=2, default=str))
        return 0

    if args.prov_cmd == "clear":
        try:
            ctx = asyncio.run(_req(url, "provenance.override.clear", {}))
        except Exception as exc:
            die(f"NATS request failed: {exc}")
        print(json.dumps(ctx, indent=2, default=str))
        return 0

    die(f"unknown provenance subcommand: {args.prov_cmd}")
    return 1
