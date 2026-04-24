"""artha restart — ask the supervisor to restart one service via NATS."""

from __future__ import annotations

import asyncio
import json

from cli.common import find_repo_root, nats_url, die, green, red


async def _restart(url: str, service: str) -> dict:
    import nats
    nc = await nats.connect(url, max_reconnect_attempts=1, connect_timeout=2.0)
    try:
        resp = await nc.request("cmd.restart-service", json.dumps({"name": service}).encode(), timeout=5.0)
        return json.loads(resp.data.decode()) if resp.data else {}
    finally:
        await nc.drain()


def run(args) -> int:
    root = find_repo_root()
    url = nats_url(root)
    try:
        result = asyncio.run(_restart(url, args.service))
    except Exception as exc:
        die(f"NATS request failed: {exc}")
    if not result.get("success"):
        print(red(f"restart failed: {result.get('error', 'unknown')}"))
        return 1
    print(green(f"restarted {args.service}"))
    return 0
