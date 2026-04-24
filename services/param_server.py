"""Centralized parameter store.  Holds all tunable params in RAM, persists to
a JSON file on disk, and broadcasts changes over NATS so ParamClients in other
services update their local caches in real time."""

import os
import asyncio
import json
import signal
from pathlib import Path

file_path = os.environ.get("PARAM_FILE_PATH", "config/params.json")
PARAM_FILE = Path(file_path)
PARAM_FILE.parent.mkdir(parents=True, exist_ok=True)

class ParamServer:
    """In-memory param store backed by a JSON file.  A simple 1-second
    background loop coalesces rapid writes so the disk is never thrashed
    but dirty state is flushed promptly."""

    def __init__(self):
        self.nc = None
        self.params = {}
        self._dirty = False

    def _load_disk(self):
        """Read params from the JSON file into RAM, or initialize an empty
        file if none exists."""
        if PARAM_FILE.exists():
            with open(PARAM_FILE, "r") as f:
                self.params = json.load(f)
        else:
            self.params = {}
            self._save_disk()

    def _save_disk(self):
        """Flush the current param dict to disk and clear the dirty flag."""
        with open(PARAM_FILE, "w") as f:
            json.dump(self.params, f, indent=2)
        self._dirty = False
        print(f"[ParamServer] Flushed params to disk. (Keys: {len(self.params)})")

    async def _disk_sync_loop(self):
        """Flush dirty params to disk every 1 second.  All write coalescing
        happens naturally — on_set_param just sets _dirty = True and this
        loop batches everything since the last tick into one write."""
        while True:
            await asyncio.sleep(1.0)
            if self._dirty:
                self._save_disk()

    async def start(self):
        """Load params from disk, connect to NATS, register handlers for
        'param.get_all' (bulk fetch) and 'param.set' (single update), start
        the disk sync loop, and block forever.  On shutdown, flushes any
        remaining dirty state before closing NATS."""
        from core.config import nats_connect
        self._load_disk()
        self.nc = await nats_connect("param_server")

        asyncio.create_task(self._disk_sync_loop())

        async def on_get_all(msg):
            """Reply with the full param dict."""
            await msg.respond(json.dumps(self.params).encode())

        async def on_set_param(msg):
            """Update a single param in RAM, broadcast the change, mark dirty."""
            try:
                req = json.loads(msg.data.decode())
                key = req["key"]
                value = req["value"]

                self.params[key] = value
                self._dirty = True

                await self.nc.publish(f"param.updated.{key}", json.dumps(value).encode())
                await msg.respond(json.dumps({"success": True}).encode())

            except Exception as e:
                await msg.respond(json.dumps({"success": False, "error": str(e)}).encode())

        await self.nc.subscribe("param.get_all", cb=on_get_all)
        await self.nc.subscribe("param.set", cb=on_set_param)
        print("[ParamServer] Running. Listening for endocrine updates...")

        try:
            await asyncio.Future()
        finally:
            if self._dirty:
                self._save_disk()
            await self.nc.close()

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    task = loop.create_task(ParamServer().start())
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, task.cancel)
    try:
        loop.run_until_complete(task)
    except asyncio.CancelledError:
        pass