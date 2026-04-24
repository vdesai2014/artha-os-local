from __future__ import annotations

import json
import os
import tempfile
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlencode

import httpx
import websockets
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .deps import init_store
from .routes import episodes, manifests, projects, runs, sync


BRIDGE_HTTP_BASE = "http://127.0.0.1:9090"
BRIDGE_WS_BASE = "ws://127.0.0.1:8765/ws"


def _state_file_path(home: Path) -> Path:
    return home / ".artha" / "run" / "local_tool.json"


def _write_state_file(home: Path) -> Path | None:
    """Atomically write .artha/run/local_tool.json with pid/port/url/started_at.

    CLI reads this to discover local_tool's actual listening port.
    Env vars ARTHA_LOCAL_TOOL_HOST/PORT should be set by whoever launches
    uvicorn (typically `artha up`); otherwise falls back to 127.0.0.1:8000
    with a printed warning.
    """
    host = os.environ.get("ARTHA_LOCAL_TOOL_HOST", "127.0.0.1")
    port_raw = os.environ.get("ARTHA_LOCAL_TOOL_PORT")
    if port_raw is None:
        print(
            "[local_tool] WARNING: ARTHA_LOCAL_TOOL_PORT unset; state file "
            "will claim port 8000 (set this env var at launch to match your "
            "--port flag)"
        )
    try:
        port = int(port_raw) if port_raw else 8000
    except ValueError:
        print(f"[local_tool] WARNING: invalid ARTHA_LOCAL_TOOL_PORT={port_raw!r}; using 8000")
        port = 8000

    path = _state_file_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "pid": os.getpid(),
        "host": host,
        "port": port,
        "url": f"http://{host}:{port}",
        "started_at": time.time(),
    }
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True)
            fh.write("\n")
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
    return path


@asynccontextmanager
async def lifespan(app: FastAPI):
    ctx = init_store()
    print(f"[local_tool] home={ctx.home}")
    state_path = _write_state_file(ctx.home)
    if state_path is not None:
        print(f"[local_tool] state: {state_path}")
    try:
        yield
    finally:
        if state_path is not None:
            try:
                state_path.unlink(missing_ok=True)
            except OSError:
                pass


app = FastAPI(title="Artha Local Tool", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(projects.router, prefix="/api")
app.include_router(runs.router, prefix="/api")
app.include_router(manifests.router, prefix="/api")
app.include_router(episodes.router, prefix="/api")
app.include_router(sync.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "artha-local-tool"}


def _with_query(base: str, query_params) -> str:
    if not query_params:
        return base
    query = urlencode(list(query_params.multi_items()))
    return f"{base}?{query}" if query else base


@app.api_route("/video/{path:path}", methods=["GET", "HEAD"])
async def proxy_video(path: str, request: Request):
    upstream_url = _with_query(f"{BRIDGE_HTTP_BASE}/{path}", request.query_params)
    client = httpx.AsyncClient(timeout=None)
    upstream = await client.send(
        client.build_request(request.method, upstream_url, headers={
            key: value for key, value in request.headers.items()
            if key.lower() not in {"host", "content-length"}
        }),
        stream=True,
    )

    async def body_iter():
        try:
            async for chunk in upstream.aiter_bytes():
                yield chunk
        finally:
            await upstream.aclose()
            await client.aclose()

    headers = {
        key: value for key, value in upstream.headers.items()
        if key.lower() not in {"content-length", "transfer-encoding", "connection"}
    }
    return StreamingResponse(
        body_iter(),
        status_code=upstream.status_code,
        headers=headers,
        media_type=upstream.headers.get("content-type"),
    )


@app.websocket("/ws")
async def proxy_ws(websocket: WebSocket):
    await websocket.accept()
    upstream_url = BRIDGE_WS_BASE
    if websocket.query_params:
        upstream_url = _with_query(upstream_url, websocket.query_params)

    try:
        async with websockets.connect(upstream_url) as upstream:
            async def client_to_upstream():
                while True:
                    message = await websocket.receive_text()
                    await upstream.send(message)

            async def upstream_to_client():
                async for message in upstream:
                    if isinstance(message, bytes):
                        await websocket.send_bytes(message)
                    else:
                        await websocket.send_text(message)

            async with httpx.AsyncClient():
                import asyncio
                tasks = [
                    asyncio.create_task(client_to_upstream()),
                    asyncio.create_task(upstream_to_client()),
                ]
                done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
                for task in pending:
                    task.cancel()
                for task in done:
                    exc = task.exception()
                    if exc is not None:
                        raise exc
    except WebSocketDisconnect:
        return
    except Exception:
        await websocket.close()
        return


_frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _frontend_dist.is_dir():
    _frontend_dist_resolved = _frontend_dist.resolve()
    assets_dir = _frontend_dist / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{path:path}")
    async def spa_fallback(request: Request, path: str):
        candidate = (_frontend_dist_resolved / path).resolve()
        if _frontend_dist_resolved in candidate.parents and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_frontend_dist_resolved / "index.html")
