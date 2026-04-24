# Bridge

The bridge is the translator between the real-time OS and the frontend. The
browser can only speak WebSocket and HTTP — it cannot read iceoryx2 SHM or
publish to NATS. `services/bridge.py` bridges both.

## What it exposes

**`WS /ws`** — one WebSocket, four message types:

| type | direction | purpose |
|------|-----------|---------|
| `subscribe-topic` / `unsubscribe-topic` | client → bridge | stream any `core.types` SHM struct at a requested rate |
| `nats-publish` | client → bridge | fire-and-forget NATS publish |
| `nats-subscribe` / `nats-unsubscribe` | client → bridge | stream NATS subject payloads |
| `nats-request` | client ↔ bridge | request/reply with a client-chosen `req_id` |

Responses come back as `topic-data`, `nats-message`, and `nats-response`.
See `frontend/src/lib/useBridge.ts` for the canonical client.

**`HTTP /mjpeg/{topic}`** — MJPEG stream from a `CameraFrame` SHM topic.
Python + Pillow encoding; fine for low-rate tinkering, too slow for real
video. Use `video_bridge` for production cameras. See `concepts/cameras.md`.

## What it skips from /ws payloads

Large fields are dropped before the JSON encode:

- Any field named `data` or `_pad`
- Any array longer than 1000 elements

This keeps a `CameraFrame` from blowing up the browser when a careless
`subscribe-topic` lands on a camera topic. The browser reads camera
frames from `/mjpeg/*` or the video_bridge, not from `/ws`.

## Where it sits

`local_tool` proxies `/ws` and `/video/*` to the bridge and video_bridge
respectively, so the frontend only ever connects to one host:port.

```
browser ──HTTP/WS──▶ local_tool ──proxy──▶ bridge / video_bridge ──SHM/NATS──▶ services
```

## Why it's Python

Low-rate, structured, mostly text. JSON-serializing a `JointState` struct
and fanning it out to a few clients at 20 Hz is trivial. The part that
*is* performance-critical — video — lives in a separate Rust service.
