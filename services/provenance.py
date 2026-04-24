from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import datetime, timezone

from core.config import nats_connect


def utc_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def merge_patch(base: dict, patch: dict) -> dict:
    out = dict(base)
    for key, value in patch.items():
        if value is None:
            out.pop(key, None)
        else:
            out[key] = value
    return out


def default_manifest_type(mode: str | None) -> str:
    if mode == "eval":
        return "eval"
    if mode == "intervention":
        return "intervention"
    return "teleop"


def default_task(mode: str | None) -> str | None:
    if mode in {"teleop", "eval", "intervention"}:
        return mode
    return None


def default_task_description(mode: str | None) -> str | None:
    if mode == "teleop":
        return "Human teleoperation recording"
    if mode == "eval":
        return "Policy evaluation rollout"
    if mode == "intervention":
        return "Human intervention during policy execution"
    return None


def default_manifest_name(mode: str | None, policy_name: str | None) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    if mode == "eval":
        return f"eval-{policy_name or 'unknown'}-{stamp}"
    if mode == "intervention":
        return f"intvn-{policy_name or 'unknown'}-{stamp}"
    return f"teleop-{stamp}"


async def main():
    service_name = os.environ.get("SERVICE_NAME", "provenance")
    pid = os.getpid()
    start_time = time.time()
    nc = await nats_connect(service_name)

    commander_state: dict = {"mode": "idle", "policy_name": None, "timestamp": 0.0}
    inference_state: dict[str, dict] = {}
    override_state: dict = {}
    last_context: dict | None = None

    def resolve_context() -> dict:
        mode = commander_state.get("mode")
        policy_name = override_state.get("policy_name", commander_state.get("policy_name"))
        inference = inference_state.get(policy_name or "", {}) if policy_name else {}
        manifest_type = override_state.get("manifest_type") or default_manifest_type(mode)
        context = {
            "manifest_name": override_state.get("manifest_name") or default_manifest_name(mode, policy_name),
            "manifest_type": manifest_type,
            "task": override_state.get("task") if "task" in override_state else default_task(mode),
            "task_description": (
                override_state.get("task_description")
                if "task_description" in override_state
                else default_task_description(mode)
            ),
            "source_project_id": override_state.get("source_project_id") if "source_project_id" in override_state else inference.get("source_project_id"),
            "source_run_id": override_state.get("source_run_id") if "source_run_id" in override_state else inference.get("source_run_id"),
            "source_checkpoint": override_state.get("source_checkpoint") if "source_checkpoint" in override_state else inference.get("source_checkpoint"),
            "policy_name": policy_name,
            "timestamp": utc_iso_now(),
        }
        return context

    async def publish_context() -> None:
        nonlocal last_context
        context = resolve_context()
        last_context = context
        await nc.publish("provenance.context", json.dumps(context).encode())

    async def on_commander(msg):
        nonlocal commander_state
        try:
            commander_state = json.loads(msg.data.decode()) if msg.data else commander_state
        except Exception:
            return
        await publish_context()

    async def on_inference(msg):
        try:
            payload = json.loads(msg.data.decode()) if msg.data else {}
        except Exception:
            return
        policy_name = payload.get("policy_name")
        if not policy_name:
            return
        inference_state[policy_name] = payload
        if commander_state.get("policy_name") == policy_name:
            await publish_context()

    async def on_override_set(msg):
        nonlocal override_state
        try:
            payload = json.loads(msg.data.decode()) if msg.data else {}
        except Exception:
            payload = {}
        override_state = merge_patch(override_state, payload)
        await publish_context()
        if msg.reply:
            await nc.publish(msg.reply, json.dumps(resolve_context()).encode())

    async def on_override_clear(msg):
        nonlocal override_state
        override_state = {}
        await publish_context()
        if msg.reply:
            await nc.publish(msg.reply, json.dumps(resolve_context()).encode())

    async def on_get(msg):
        if msg.reply:
            await nc.publish(msg.reply, json.dumps(resolve_context()).encode())

    await nc.subscribe("provenance.commander", cb=on_commander)
    await nc.subscribe("provenance.inference.*", cb=on_inference)
    await nc.subscribe("provenance.override.set", cb=on_override_set)
    await nc.subscribe("provenance.override.clear", cb=on_override_clear)
    await nc.subscribe("provenance.get", cb=on_get)

    await publish_context()

    heartbeat_interval = 1.0
    last_heartbeat = 0.0
    try:
        while True:
            now = time.time()
            if now - last_heartbeat >= heartbeat_interval:
                last_heartbeat = now
                heartbeat = {
                    "pid": pid,
                    "status": "running",
                    "uptime_s": round(now - start_time, 1),
                    "stats": {
                        "commander": commander_state,
                        "override": override_state,
                        "context": resolve_context(),
                        "inference_policies": sorted(inference_state.keys()),
                    },
                    "timestamp": now,
                }
                try:
                    await nc.publish(f"service.{service_name}.heartbeat", json.dumps(heartbeat).encode())
                except Exception:
                    pass
            await asyncio.sleep(0.1)
    except asyncio.CancelledError:
        pass
    finally:
        if nc and nc.is_connected:
            await nc.drain()


if __name__ == "__main__":
    asyncio.run(main())
