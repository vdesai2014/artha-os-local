"""WebSocket + HTTP bridge for the frontend.

WebSocket /ws:
  - subscribe-topic / unsubscribe-topic for SHM streaming
  - nats-publish for fire-and-forget NATS commands
  - nats-subscribe / nats-unsubscribe for NATS subject streaming
  - nats-request for NATS request/reply
  - topic-data / nats-message / nats-response messages sent back to the client

HTTP /mjpeg/{topic}:
  MJPEG camera stream from SHM CameraFrame topics.
"""

import asyncio
import io
import json

import numpy as np
from aiohttp import web
import aiohttp

from core.shm import ReaderManager
import core.types as shm_types

PORT = 8765
LARGE_FIELD_SKIP = {"data", "_pad"}
LARGE_ARRAY_THRESHOLD = 1000


def serialize_struct(data):
    if data is None:
        return None
    result = {}
    for field_name, _ in data._fields_:
        if field_name in LARGE_FIELD_SKIP:
            continue
        val = getattr(data, field_name)
        if hasattr(val, "__len__") and not isinstance(val, (str, bytes)):
            if len(val) > LARGE_ARRAY_THRESHOLD:
                continue
            val = list(val)
        result[field_name] = val
    return result


async def ws_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    print("[bridge] WS client connected")

    nc = request.app.get("nats")
    subscriptions: dict[str, asyncio.Task] = {}
    nats_subscriptions: dict[str, object] = {}

    async def poll_and_send(topic: str, struct_cls, rate_hz: float):
        readers = ReaderManager({topic: struct_cls})
        last_frame_id = 0
        sleep_time = 1.0 / max(rate_hz, 1)
        try:
            while True:
                readers.poll()
                data = readers.get(topic)
                if data and data.frame_id != last_frame_id:
                    last_frame_id = data.frame_id
                    values = serialize_struct(data)
                    try:
                        await ws.send_json({
                            "type": "topic-data",
                            "topic": topic,
                            "timestamp": data.timestamp,
                            "frame_id": data.frame_id,
                            "values": values,
                        })
                    except Exception:
                        break
                await asyncio.sleep(sleep_time)
        except asyncio.CancelledError:
            pass
        finally:
            readers.close()

    async def ensure_nats_subscription(subject: str):
        if subject in nats_subscriptions or not (nc and nc.is_connected):
            return

        async def on_msg(msg):
            try:
                payload = json.loads(msg.data.decode()) if msg.data else None
            except Exception:
                payload = msg.data.decode(errors="ignore") if msg.data else None
            try:
                await ws.send_json({
                    "type": "nats-message",
                    "subject": msg.subject,
                    "payload": payload,
                })
            except Exception:
                pass

        nats_subscriptions[subject] = await nc.subscribe(subject, cb=on_msg)
        print(f"[bridge] NATS subscribed: {subject}")

    async def drop_nats_subscription(subject: str):
        sub = nats_subscriptions.pop(subject, None)
        if sub is None:
            return
        try:
            await sub.unsubscribe()
        except Exception:
            pass
        print(f"[bridge] NATS unsubscribed: {subject}")

    try:
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                try:
                    req = json.loads(msg.data)
                except Exception:
                    continue

                msg_type = req.get("type")

                if msg_type == "subscribe-topic":
                    topic = req.get("topic", "")
                    type_name = req.get("type_name", "")
                    rate_hz = req.get("rate_hz", 30)
                    struct_cls = getattr(shm_types, type_name, None)
                    if not struct_cls:
                        await ws.send_json({"type": "error", "message": f"Unknown type: {type_name}"})
                        continue
                    old = subscriptions.pop(topic, None)
                    if old:
                        old.cancel()
                    task = asyncio.create_task(poll_and_send(topic, struct_cls, rate_hz))
                    subscriptions[topic] = task
                    print(f"[bridge] Subscribed: {topic} ({type_name}) @ {rate_hz}Hz")

                elif msg_type == "unsubscribe-topic":
                    topic = req.get("topic", "")
                    old = subscriptions.pop(topic, None)
                    if old:
                        old.cancel()
                        print(f"[bridge] Unsubscribed: {topic}")

                elif msg_type == "nats-publish":
                    subject = req.get("subject", "")
                    payload = req.get("payload", {})
                    if subject and nc and nc.is_connected:
                        try:
                            await nc.publish(subject, json.dumps(payload).encode())
                        except Exception as e:
                            print(f"[bridge] NATS publish error: {e}")

                elif msg_type == "nats-subscribe":
                    subject = req.get("subject", "")
                    if subject:
                        await ensure_nats_subscription(subject)

                elif msg_type == "nats-unsubscribe":
                    subject = req.get("subject", "")
                    if subject:
                        await drop_nats_subscription(subject)

                elif msg_type == "nats-request":
                    subject = req.get("subject", "")
                    payload = req.get("payload", {})
                    req_id = req.get("req_id")
                    if subject and req_id and nc and nc.is_connected:
                        try:
                            resp = await nc.request(subject, json.dumps(payload).encode(), timeout=2.0)
                            try:
                                body = json.loads(resp.data.decode()) if resp.data else None
                            except Exception:
                                body = resp.data.decode(errors="ignore") if resp.data else None
                            await ws.send_json({"type": "nats-response", "req_id": req_id, "payload": body})
                        except Exception as e:
                            await ws.send_json({"type": "nats-response", "req_id": req_id, "error": str(e)})

            elif msg.type == aiohttp.WSMsgType.ERROR:
                break
    except Exception:
        pass
    finally:
        for task in subscriptions.values():
            task.cancel()
        subscriptions.clear()
        for subject in list(nats_subscriptions.keys()):
            await drop_nats_subscription(subject)
        print("[bridge] WS client disconnected")

    return ws


async def mjpeg_handler(request):
    from PIL import Image

    topic = request.match_info["topic"]
    response = web.StreamResponse()
    response.content_type = "multipart/x-mixed-replace; boundary=frame"
    response.headers["Cache-Control"] = "no-cache"
    response.headers["Access-Control-Allow-Origin"] = "*"
    await response.prepare(request)

    readers = ReaderManager({topic: shm_types.CameraFrame})
    last_frame_id = 0

    try:
        while True:
            readers.poll()
            frame = readers.get(topic)
            if frame and frame.frame_id != last_frame_id:
                last_frame_id = frame.frame_id
                n_bytes = int(frame.height) * int(frame.width) * 3
                rgb = np.ctypeslib.as_array(frame.data)[:n_bytes].reshape(frame.height, frame.width, 3)
                img = Image.fromarray(rgb)
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=75)
                jpeg = buf.getvalue()

                await response.write(
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    b"Content-Length: " + str(len(jpeg)).encode() + b"\r\n"
                    b"\r\n" + jpeg + b"\r\n"
                )
            await asyncio.sleep(1 / 30)
    except (asyncio.CancelledError, ConnectionResetError, ConnectionAbortedError):
        pass
    finally:
        readers.close()

    return response


async def on_startup(app):
    try:
        import nats as nats_lib
        nc = await nats_lib.connect(
            "nats://localhost:4222",
            max_reconnect_attempts=-1,
            reconnect_time_wait=2,
        )
        app["nats"] = nc
        print("[bridge] NATS connected")
    except Exception as e:
        app["nats"] = None
        print(f"[bridge] NATS unavailable ({e}) — commands disabled")


async def on_shutdown(app):
    nc = app.get("nats")
    if nc and nc.is_connected:
        await nc.drain()


async def run_bridge():
    app = web.Application()
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    app.router.add_get("/ws", ws_handler)
    app.router.add_get("/mjpeg/{topic:.+}", mjpeg_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=PORT)

    print(f"[bridge] Starting on port {PORT}")
    await site.start()

    try:
        await asyncio.Future()
    except asyncio.CancelledError:
        pass
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(run_bridge())
