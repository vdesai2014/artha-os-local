"""Shared ctypes structs for iceoryx2 blackboard IPC.

Define one Structure subclass per SHM topic type. The bridge and supervisor
resolve types by class name (dynamic getattr), so adding a new struct here is
all that's needed to make it streamable to the frontend and type-checkable
against a Rust companion.

Invariants every struct must respect
------------------------------------
1. Fixed size. iceoryx2 blackboard segments are pre-sized at create time.
   Changing a struct's size invalidates the segment — you must restart all
   services that use it AND nuke /tmp/iceoryx2 or services will segfault.

2. C layout. ctypes.Structure with `_fields_ = [...]` is the right shape.
   The Rust side uses `#[repr(C)]`. Match field order, types, and padding
   exactly. See the Rust `print_type_layout()` helper + the supervisor's
   `_check_ipc_types` for the enforcement path.

3. `timestamp: c_double` and `frame_id: c_uint64` as the first two fields.
   ReaderManager uses `frame_id` to detect staleness — structs without it
   will be marked stale on every poll. `timestamp` is convention for wall
   time at write.

4. Large arrays are fixed-capacity. If a frame is smaller than capacity, use
   a `width` / `height` / `length` field to mark the valid region. Readers
   slice with that, not with `len(data)`.

Naming a Rust companion
-----------------------
iceoryx2 matches blackboard entries by key + type name. Python defaults to
the class name (`CameraFrame`); Rust registers as the crate-qualified name
(`camera_service::CameraFrame`). If they differ, override on the Python
side with:

    @classmethod
    def type_name(cls):
        return "camera_service::CameraFrame"

Sample types (copy, rename, fill in)
------------------------------------
# Camera frame: fixed-capacity RGB buffer, actual size marked by width/height.
#
# class CameraFrame(ctypes.Structure):
#     _fields_ = [
#         ("timestamp", ctypes.c_double),
#         ("frame_id",  ctypes.c_uint64),
#         ("width",     ctypes.c_uint32),
#         ("height",    ctypes.c_uint32),
#         ("channels",  ctypes.c_uint32),
#         ("_pad",      ctypes.c_uint32),          # align `data` to 8 bytes
#         ("data",      ctypes.c_uint8 * 921600),  # 640 * 480 * 3 max
#     ]

# Joint state: N actuators, physical readings published each control tick.
#
# NUM_JOINTS = 7
# class JointState(ctypes.Structure):
#     _fields_ = [
#         ("timestamp",   ctypes.c_double),
#         ("frame_id",    ctypes.c_uint64),
#         ("position",    ctypes.c_double * NUM_JOINTS),
#         ("velocity",    ctypes.c_double * NUM_JOINTS),
#         ("torque",      ctypes.c_double * NUM_JOINTS),
#         ("temperature", ctypes.c_double * NUM_JOINTS),
#         ("enabled",     ctypes.c_uint8  * NUM_JOINTS),
#     ]

# Joint action: commanded targets for the same N actuators.
#
# class JointAction(ctypes.Structure):
#     _fields_ = [
#         ("timestamp", ctypes.c_double),
#         ("frame_id",  ctypes.c_uint64),
#         ("position",  ctypes.c_double * NUM_JOINTS),
#         ("velocity",  ctypes.c_double * NUM_JOINTS),
#         ("torque",    ctypes.c_double * NUM_JOINTS),
#     ]
"""

import ctypes  # noqa: F401  — re-exported for user struct definitions below
