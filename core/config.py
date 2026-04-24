"""Shared NATS helpers used by all services and the supervisor.

Provides nats_connect() for resilient connections and ParamClient for
reading tunable parameters from the param_server with zero-latency
local-RAM caching."""

import asyncio
import json
import nats


async def nats_connect(name="node"):
    """Connect to the local NATS server with infinite reconnect attempts.
    Logs disconnect/reconnect/error events using the caller-supplied name
    so you can tell which service lost connectivity in the logs."""
    async def disconnected_cb():
        print(f"[{name}] NATS disconnected")

    async def reconnected_cb():
        print(f"[{name}] NATS reconnected")

    async def error_cb(e):
        print(f"[{name}] NATS error: {e}")

    return await nats.connect(
        "nats://localhost:4222",
        max_reconnect_attempts=-1,
        reconnect_time_wait=1,
        disconnected_cb=disconnected_cb,
        reconnected_cb=reconnected_cb,
        error_cb=error_cb,
    )


class ParamClient:
    """Client-side cache for parameters stored in the param_server.  On init(),
    fetches the full param set via NATS request/reply, then subscribes to live
    updates so the local cache stays current.  get() is a synchronous dict
    lookup — safe to call inside tight control loops with no async overhead."""

    def __init__(self, nc, prefix="", on_change=None):
        self.nc = nc
        self.prefix = prefix
        self.cache = {}
        self.on_change = on_change

    async def init(self):
        """Subscribe to live param updates FIRST, then fetch the full snapshot.
        This ordering closes the race window where an update published between
        the snapshot response and the subscribe call would be permanently missed.
        Any duplicate updates from the overlap are harmless — the snapshot is
        applied as a base and live updates override it."""
        # 1. Subscribe FIRST so we never miss an update
        async def on_update(msg):
            key = msg.subject.replace("param.updated.", "")
            val = json.loads(msg.data.decode())
            self.cache[key] = val
            print(f"[{self.prefix}] Live update applied: {key} = {val}")
            if self.on_change:
                await self.on_change(key, val)

        subscribe_subject = f"param.updated.{self.prefix}.>" if self.prefix else "param.updated.>"
        await self.nc.subscribe(subscribe_subject, cb=on_update)

        # 2. THEN fetch snapshot — live updates that snuck in during the fetch
        #    are preserved (snapshot is base, live updates override)
        try:
            resp = await self.nc.request("param.get_all", b"", timeout=2.0)
            all_params = json.loads(resp.data.decode())

            if self.prefix:
                snapshot = {k: v for k, v in all_params.items() if k.startswith(self.prefix)}
            else:
                snapshot = all_params

            snapshot.update(self.cache)
            self.cache = snapshot

        except Exception as e:
            print(f"[ParamClient] Failed to fetch initial params: {e}")
            # cache keeps whatever live updates arrived during the attempt

    def get(self, key, default=None):
        """Return a cached parameter value, or default if not present.
        Pure dict lookup — zero network overhead, safe at 100Hz+."""
        return self.cache.get(key, default)
