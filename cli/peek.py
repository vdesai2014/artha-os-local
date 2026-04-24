"""artha peek <topic> — one-shot snapshot of an SHM topic via bridge WS."""

from __future__ import annotations

import asyncio
import json

from cli.common import find_repo_root, bridge_ws_url, load_services_yaml, die


def _infer_type_name(services: dict, topic: str) -> str | None:
    """Scan services.yaml for this topic in anyone's publishes or subscribes."""
    for svc in services.values():
        ipc = svc.get("ipc") or {}
        for section in ("publishes", "subscribes"):
            mapping = ipc.get(section) or {}
            if topic in mapping:
                return mapping[topic]
    return None


async def _peek(url: str, topic: str, type_name: str, timeout: float) -> dict:
    import websockets
    async with websockets.connect(url) as ws:
        await ws.send(json.dumps({
            "type": "subscribe-topic",
            "topic": topic,
            "type_name": type_name,
            "rate_hz": 30,
        }))
        try:
            while True:
                msg = await asyncio.wait_for(ws.recv(), timeout=timeout)
                data = json.loads(msg)
                if data.get("type") == "topic-data" and data.get("topic") == topic:
                    # Unsubscribe so bridge cleans up the reader task
                    try:
                        await ws.send(json.dumps({"type": "unsubscribe-topic", "topic": topic}))
                    except Exception:
                        pass
                    return data
                if data.get("type") == "error":
                    raise RuntimeError(data.get("message", "unknown bridge error"))
        except asyncio.TimeoutError:
            raise RuntimeError(
                f"no frame within {timeout}s — is '{topic}' being published?"
            )


def run(args) -> int:
    root = find_repo_root()
    type_name = args.type_name

    if type_name is None:
        services = load_services_yaml(root)
        type_name = _infer_type_name(services, args.topic)
        if type_name is None:
            die(
                f"could not infer type for topic '{args.topic}' from services.yaml. "
                f"Pass --type <StructName>."
            )

    url = bridge_ws_url()
    try:
        data = asyncio.run(_peek(url, args.topic, type_name, args.timeout))
    except ConnectionError as exc:
        die(f"bridge unreachable at {url}: {exc}")
    except Exception as exc:
        die(f"peek failed: {exc}")

    print(json.dumps({
        "topic": data.get("topic"),
        "type_name": type_name,
        "frame_id": data.get("frame_id"),
        "timestamp": data.get("timestamp"),
        "values": data.get("values"),
    }, indent=2, default=str))
    return 0
