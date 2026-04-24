"""artha nats {pub,req} — raw NATS for emergency / debugging use."""

from __future__ import annotations

import asyncio
import json

from cli.common import find_repo_root, nats_url, die


async def _pub(url: str, subject: str, payload: str) -> None:
    import nats
    nc = await nats.connect(url, max_reconnect_attempts=1, connect_timeout=2.0)
    try:
        await nc.publish(subject, payload.encode())
        await nc.flush(timeout=1.0)
    finally:
        await nc.drain()


async def _req(url: str, subject: str, payload: str, timeout: float) -> bytes:
    import nats
    nc = await nats.connect(url, max_reconnect_attempts=1, connect_timeout=2.0)
    try:
        resp = await nc.request(subject, payload.encode(), timeout=timeout)
        return resp.data or b""
    finally:
        await nc.drain()


def _validate_json(s: str) -> str:
    try:
        json.loads(s)
    except ValueError as exc:
        die(f"--payload must be valid JSON: {exc}")
    return s


def run(args) -> int:
    root = find_repo_root()
    url = nats_url(root)
    payload = _validate_json(args.payload)

    if args.nats_cmd == "pub":
        try:
            asyncio.run(_pub(url, args.subject, payload))
        except Exception as exc:
            die(f"publish failed: {exc}")
        print(f"published to {args.subject}")
        return 0

    if args.nats_cmd == "req":
        try:
            data = asyncio.run(_req(url, args.subject, payload, args.timeout))
        except Exception as exc:
            die(f"request failed: {exc}")
        # Try to pretty-print JSON if it parses
        try:
            print(json.dumps(json.loads(data.decode()), indent=2, default=str))
        except (ValueError, UnicodeDecodeError):
            print(data.decode(errors="replace"))
        return 0

    die(f"unknown nats subcommand: {args.nats_cmd}")
    return 1
