# Adding a service

A *service* is any long-lived process the supervisor manages. It's the
unit of "a thing that runs." Adding one is the most common extension
point — if you're building a new sensor reader, a custom recorder, an
analytics loop, a driver for a new piece of hardware — it's a service.

## When a new service is the right answer

- The work is long-lived (runs as long as the supervisor is up)
- It reads or writes SHM, or responds to NATS commands
- It has its own process lifecycle (can crash independently)

If it's a one-off script or a library call, don't make it a service.

## Minimum viable service (Python)

Conventions every service follows:

```python
from __future__ import annotations
import asyncio, json, os, time
from core.config import nats_connect

SERVICE_NAME = os.environ.get("SERVICE_NAME", "my_service")
LOOP_RATE_HZ = int(os.environ.get("LOOP_RATE_HZ", "50"))

async def main():
    pid = os.getpid()
    start_time = time.time()
    nc = await nats_connect(SERVICE_NAME)

    # Subscribe to any commands you handle
    async def on_some_command(msg):
        ...
    await nc.subscribe(f"{SERVICE_NAME}.command", cb=on_some_command)

    loop_period = 1.0 / max(LOOP_RATE_HZ, 1)
    last_heartbeat = 0.0
    next_wake = time.monotonic()

    try:
        while True:
            next_wake += loop_period
            # ... your tick work here ...

            now = time.time()
            if now - last_heartbeat >= 1.0:
                last_heartbeat = now
                await nc.publish(
                    f"service.{SERVICE_NAME}.heartbeat",
                    json.dumps({
                        "pid": pid,
                        "status": "running",
                        "uptime_s": round(now - start_time, 1),
                        "stats": {...},
                        "timestamp": now,
                    }).encode(),
                )

            sleep_time = next_wake - time.monotonic()
            if sleep_time < -loop_period:
                next_wake = time.monotonic()
                sleep_time = 0
            await asyncio.sleep(max(0, sleep_time))
    except asyncio.CancelledError:
        pass
    finally:
        if nc and nc.is_connected:
            await nc.drain()

if __name__ == "__main__":
    asyncio.run(main())
```

This gives you: clean shutdown, NATS connectivity, filesystem-visible
heartbeats (via the wrapper), and a predictable tick.

## services.yaml entry

```yaml
my_service:
  cmd: ["python3", "services/my_service/main.py"]
  env:
    SERVICE_NAME: my_service
    LOOP_RATE_HZ: "50"
  ipc:
    publishes:
      my_topic/state: MyStructName        # type must exist in core/types.py
    subscribes:
      upstream_topic: SomeOtherStruct
```

Keys:
- `cmd`: argv. `python` / `python3` gets rewritten to the active
  interpreter.
- `env`: anything your service reads from `os.environ`. `ARTHA_*` +
  `IPC_PUBLISHES` + `IPC_SUBSCRIBES` are injected automatically.
- `ipc.publishes` / `ipc.subscribes`: SHM topics + their ctypes struct
  names. Drives the env vars your service parses; also a declaration
  the supervisor can type-check against a Rust binary if
  `type_check: true` is set.

## Recorder timing rule

If the service feeds `data_recorder`, make its SHM cadence explicit in the
service docs or `services.yaml` comments. The recorder should anchor on the
slowest sensor: append a sample only after every recorded source has advanced
its `frame_id` since the previous append. Do not make `LOOP_RATE_HZ` faster
than the slowest recorded source unless the recorder code for that robot
intentionally resamples and marks the policy for doing so.

## SHM types (if your service needs new ones)

If your service uses a struct shape that doesn't exist yet, add it to
`core/types.py` before starting. See `docs/concepts/ipc.md` for the
invariants (fixed size, `timestamp` + `frame_id` as first two fields,
Rust type_name override if you have a Rust companion).

Changing an existing struct's size means restarting every service that
uses it and `rm -rf /tmp/iceoryx2` — or readers segfault.

## Logging

Supervisor routes stdout to `logs/<service>.out` and stderr to
`logs/<service>.err` (appended, not rotated). Just `print()` or
`logging`; you don't configure file paths yourself.

## Restart workflow

Edit your service code. Then either:

```python
# In-repo, via NATS — lets supervisor handle the bounce
await nc.request("cmd.restart-service", json.dumps({"name": "my_service"}).encode())
```

Or via CLI once it lands: `artha restart my_service`.

The supervisor re-reads `services.yaml` on every restart, so changing
the `env` or `cmd` is applied on the next spawn — no supervisor restart
needed unless you're adding/removing services (the supervisor only
reads the full service list at boot).

## Rust services

Almost identical. You compile a binary (`cargo build --release`), point
`cmd` at it, and optionally add `type_check: true` so the supervisor
verifies your `#[repr(C)]` struct sizes match `core/types.py` before
boot. See `services/video_bridge/` and `services/camera/` for worked
examples.

## Coupon test before wiring into the full system

Run your service standalone with the env it'll see from the supervisor
before adding it to `services.yaml`:

```bash
SERVICE_NAME=my_service LOOP_RATE_HZ=50 \
  IPC_PUBLISHES='{"my_topic/state": "MyStructName"}' \
  IPC_SUBSCRIBES='{}' \
  python3 services/my_service/main.py
```

Watch for: NATS connect succeeds, heartbeat logs appear, SHM topics
open without crashing, your tick work runs at the expected rate. Fix
issues here before the supervisor starts crash-looping it.
