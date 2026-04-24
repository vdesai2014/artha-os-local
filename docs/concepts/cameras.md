# Cameras

Camera data has the tightest budget in the system: 30 fps of image bytes
arriving from hardware, plus inference policies that want the freshest
frame with no deserialization overhead. The answer: **Rust for the
writer, SHM for in-process readers, a dedicated Rust service for the
browser.**

## The writer (`services/camera/`)

`camera-service` is a Rust binary that:

- Opens a V4L2 device (`CAMERA_DEVICE`, default `/dev/video0`)
- Prefers MJPEG format, falls back to YUYV; forces 640×480 @ 30fps
- Decodes MJPEG via `turbojpeg` (~800µs/frame, SIMD) or converts YUYV→RGB
  in a tight loop
- Writes `CameraFrame` to an iceoryx2 blackboard

**Why Rust, not Python:** MJPEG decode + YUYV conversion + tight V4L2
buffer cycling at 30 fps. Python with OpenCV gets you there, but at ~3×
CPU and with GC-induced frame drops. For a control loop that needs the
next frame *now*, that's not workable.

For simulated cameras, the sim service writes the struct directly — no
V4L2, same iceoryx2 path.

## In-process readers (inference, sim, recorder)

Policies and recorders open a `BlackboardReader` on the camera topic and
read the latest value:

```python
from core.shm import BlackboardReader
import core.types as shm_types

reader = BlackboardReader("camera/gripper_policy", shm_types.CameraFrame)
frame = reader.read()
n = frame.width * frame.height * 3
img = (
    np.ctypeslib.as_array(frame.data)[:n]
    .reshape(frame.height, frame.width, 3)
    .copy()  # copy out before the writer lands the next frame
)
```

**What "low latency SHM" really means:** no socket, no serialization, no
framing protocol. The reader lands on the same physical page as the
writer — in the same process you'd call it zero-copy; across processes
there's one memcpy-equivalent from the SHM page into the reader's own
buffer. Either way, ~100× faster than the bridge path. That's what makes
30 fps in / 50 Hz inference viable on modest hardware.

You *must* copy before looping. The writer can land the next frame at
any moment and the struct array aliases the SHM page.

## The browser path (`services/video_bridge/`)

`video_bridge` is a second Rust binary. It reads the same SHM topics and
serves MJPEG over HTTP (one endpoint per topic from `IPC_SUBSCRIBES`):

- One blackboard reader per subscribed `CameraFrame` topic
- HTTP `GET /<topic>` → `multipart/x-mixed-replace; boundary=frame`
- JPEG encode via `turbojpeg` at configurable quality; rate-limited fps
- `local_tool` proxies `/video/<topic>` → `video_bridge` so the browser
  hits one host

**Why a separate Rust service, not `bridge.py`:** JPEG-encoding several
streams at 30 fps saturates a Python core. Rust holds its own on a
Jetson.

## The Rust type-name gotcha

iceoryx2 matches blackboard entries by name. Rust writers register the
crate-qualified name (`camera_service::CameraFrame`); Python defaults to
the bare class name (`CameraFrame`). Override on the Python side:

```python
class CameraFrame(ctypes.Structure):
    _fields_ = [...]

    @classmethod
    def type_name(cls):
        return "camera_service::CameraFrame"
```

The supervisor's `--type-check` catches layout mismatches at boot, but
*not* name mismatches — if the override is wrong, `BlackboardReader`
just fails with "not found." Test the roundtrip end-to-end.

## Adding a new camera

1. **Struct.** If 640×480 RGB is fine, reuse `CameraFrame`. If not,
   define a new `ctypes.Structure` in `core/types.py` with a
   fixed-capacity buffer at the new max resolution. Size changes to an
   *existing* struct require nuking `/tmp/iceoryx2` — see
   `concepts/ipc.md`.

2. **Writer.** Run another `camera-service` instance with its own
   `CAMERA_DEVICE` and a topic under `ipc.publishes` in `services.yaml`.
   For a sim camera, the sim service writes directly.

3. **Subscribers.** Declare the topic under `ipc.subscribes` for every
   service that wants the frames — `video_bridge` (for the browser),
   policy services, `data_recorder`, etc.

4. **Resolution is a struct-level constraint.** Multiple cameras at the
   same resolution share one type. Cameras at different resolutions need
   different types (or a single type sized to the largest; waste the
   bytes).

5. **Don't write from Python unless you're simulating.** For real
   hardware at real framerates, use the Rust writer.
