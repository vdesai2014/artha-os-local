"""
Data recorder — buffers SHM sources during recording, writes an episode on stop.

Shape:
  - Subscribes to provenance for the current manifest / task / policy context.
  - On `recorder.start`: snapshots context, resolves/creates the manifest, and
    starts appending to per-source buffers at LOOP_RATE_HZ.
  - On `recorder.stop`: flushes buffers to disk as one episode (parquet for
    scalar/vector columns, mp4 for video), attaches it to the manifest via
    `local_tool.store.manifests.add_manifest_episodes`.
  - On `recorder.discard`: drops the buffers silently.

SOURCES — what to record
========================
Define one entry per feature you want in the episode. This file ships with
SOURCES = [] so the recorder is a no-op by default; populate for your robot
(or your demo project — see the commented example below).

Each source:
  topic        — SHM topic name
  type_name    — ctypes.Structure class name in core/types.py
  extract      — fn(struct) -> scalar / list[float] / ndarray (H,W,3 uint8)
  feature      — LeRobot-style feature key (becomes a parquet column or video)
  schema       — {"dtype": "float32"|"video", "shape": [...]}
  kind         — "column" (parquet) or "video" (mp4)

---------------------------------------------------------------------------
KNOWN ISSUE: sources are not coupled to the slowest writer.

The loop ticks at LOOP_RATE_HZ and appends the latest-cached value of each
source every tick. If a source is slower than the loop (e.g. camera at 30 Hz,
loop at 30 Hz but actually drifting, or obs at 50 Hz with camera at 30 Hz),
the same frame gets duplicated into the buffer — silently desynchronizing
columns from video.

Fix (owed): tick at the slowest source's rate, and only append when every
source has advanced its frame_id since the last record. See to-do.md.
---------------------------------------------------------------------------
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import av
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from core.config import nats_connect
from core.shm import ReaderManager
import core.types as shm_types
from local_tool.ids import generate_id
from local_tool.io import StoreError
from local_tool.models import RecordingContext
from local_tool.store.episodes import create_episode, refresh_episode_metadata
from local_tool.store.manifests import add_manifest_episodes
from local_tool.store.projects import StoreCtx, ensure_store_roots
from local_tool.store.recording import ensure_manifest_for_recording


# ---------------------------------------------------------------------------
# USER CONFIG — SOURCES
# ---------------------------------------------------------------------------

@dataclass
class Source:
    topic: str
    type_name: str
    extract: Callable[[Any], Any]
    feature: str
    schema: dict
    kind: str  # "column" or "video"


# No sources by default — the recorder starts, heartbeats, and no-ops.
# Populate this list for your robot, or uncomment the sim-demo example below.
SOURCES: list[Source] = []


# --- Example configuration for the sim-demo onboarding project --------------
# NUM_JOINTS = 7
#
# def _joint_positions(state):
#     return [float(state.position[i]) for i in range(NUM_JOINTS)]
#
# def _camera_rgb(frame):
#     n = int(frame.height) * int(frame.width) * 3
#     return (
#         np.ctypeslib.as_array(frame.data)[:n]
#         .reshape(frame.height, frame.width, 3)
#         .copy()
#     )
#
# SOURCES = [
#     Source(
#         topic="sim_robot/actual",
#         type_name="RobStrideState",
#         extract=_joint_positions,
#         feature="observation.joint_positions",
#         schema={"dtype": "float32", "shape": [NUM_JOINTS]},
#         kind="column",
#     ),
#     Source(
#         topic="sim_robot/desired",
#         type_name="RobStrideCommand",
#         extract=_joint_positions,
#         feature="action",
#         schema={"dtype": "float32", "shape": [NUM_JOINTS]},
#         kind="column",
#     ),
#     Source(
#         topic="camera/gripper_policy",
#         type_name="CameraFrame",
#         extract=_camera_rgb,
#         feature="observation.images.gripper",
#         schema={"dtype": "video", "shape": [480, 640, 3]},
#         kind="video",
#     ),
#     Source(
#         topic="camera/overhead_policy",
#         type_name="CameraFrame",
#         extract=_camera_rgb,
#         feature="observation.images.overhead",
#         schema={"dtype": "video", "shape": [480, 640, 3]},
#         kind="video",
#     ),
# ]


# ---------------------------------------------------------------------------
# Flush: episode creation + disk writes
# ---------------------------------------------------------------------------

def _video_filename(feature: str) -> str:
    # observation.images.gripper -> gripper.mp4
    stem = feature.split(".")[-1]
    return f"{stem}.mp4"


def flush_to_disk(
    ctx: StoreCtx,
    episode_id: str,
    resolved_context: RecordingContext,
    timestamps: list[int],
    buffers: dict[str, list],
    sources: list[Source],
):
    # Features dict: pass schemas through verbatim; video schemas may need
    # their shape refined from the first recorded frame.
    features: dict[str, dict] = {}
    for src in sources:
        schema = dict(src.schema)
        if src.kind == "video" and buffers.get(src.feature):
            first = buffers[src.feature][0]
            schema = {"dtype": "video", "shape": [first.shape[0], first.shape[1], 3]}
        features[src.feature] = schema

    episode = create_episode(
        ctx,
        episode_id=episode_id,
        length=len(timestamps),
        task=resolved_context.task,
        task_description=resolved_context.task_description,
        features=features,
        collection_mode=resolved_context.manifest_type,
        source_project_id=resolved_context.source_project_id,
        source_run_id=resolved_context.source_run_id,
        source_checkpoint=resolved_context.source_checkpoint,
        policy_name=resolved_context.policy_name,
    )

    ep_dir = ctx.home / "workspace" / "episodes" / episode_id
    vid_dir = ep_dir / "videos"

    # --- Parquet for column sources ----------------------------------------
    columns: dict[str, pa.Array] = {
        "step": pa.array(range(len(timestamps)), type=pa.int64()),
        "timestamp": pa.array(timestamps, type=pa.int64()),
    }
    for src in sources:
        if src.kind != "column":
            continue
        columns[src.feature] = pa.array(
            buffers[src.feature],
            type=pa.list_(pa.float32()),
        )
    if len(columns) > 2:  # something to write beyond step/timestamp
        pq.write_table(pa.table(columns), str(ep_dir / "data.parquet"))

    # --- MP4 per video source -----------------------------------------------
    fps = int(resolved_context.fps or 30)
    for src in sources:
        if src.kind != "video":
            continue
        frames = buffers.get(src.feature) or []
        if not frames:
            continue
        vid_dir.mkdir(parents=True, exist_ok=True)
        h, w = frames[0].shape[:2]
        container = av.open(str(vid_dir / _video_filename(src.feature)), mode="w")
        stream = container.add_stream("libx264", rate=fps)
        stream.width = w
        stream.height = h
        stream.pix_fmt = "yuv420p"
        for img in frames:
            frame = av.VideoFrame.from_ndarray(img, format="rgb24")
            for pkt in stream.encode(frame):
                container.mux(pkt)
        for pkt in stream.encode():
            container.mux(pkt)
        container.close()

    refreshed = refresh_episode_metadata(ctx, episode.id)
    add_manifest_episodes(ctx, resolved_context.manifest_id or "", [episode.id])
    return refreshed


async def request_provenance(nc) -> RecordingContext:
    resp = await nc.request("provenance.get", b"", timeout=2.0)
    raw = json.loads(resp.data.decode()) if resp.data else {}
    return RecordingContext.model_validate(raw)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    service_name = os.environ.get("SERVICE_NAME", "data_recorder")
    loop_rate_hz = int(os.environ.get("LOOP_RATE_HZ", "30"))
    pid = os.getpid()
    start_time = time.time()

    home = Path(os.environ.get("ARTHA_HOME", Path(__file__).resolve().parents[2])).resolve()
    ctx = StoreCtx(home=home)
    ensure_store_roots(ctx)

    mode = "idle"
    episode_id: str | None = None
    episode_count = 0
    timestamps: list[int] = []
    buffers: dict[str, list] = {src.feature: [] for src in SOURCES}
    current_context = RecordingContext()
    snap_context: RecordingContext | None = None

    # Per-source cached latest value + last-seen frame_id.
    last_frame_ids: dict[str, int] = {src.topic: 0 for src in SOURCES}
    cached: dict[str, Any] = {src.topic: None for src in SOURCES}

    nc = await nats_connect(service_name)

    async def on_context(msg):
        nonlocal current_context
        try:
            raw = json.loads(msg.data.decode()) if msg.data else {}
            current_context = RecordingContext.model_validate(raw)
        except Exception:
            return

    await nc.subscribe("provenance.context", cb=on_context)
    try:
        current_context = await request_provenance(nc)
    except Exception:
        current_context = RecordingContext()

    # Build readers from SOURCES (canonical) and fall back to manifest IPC if
    # SOURCES is empty, so the service still starts cleanly.
    if SOURCES:
        topic_types = {src.topic: getattr(shm_types, src.type_name) for src in SOURCES}
        readers = ReaderManager(topic_types)
    else:
        ipc_subscribes = json.loads(os.environ.get("IPC_SUBSCRIBES", "{}"))
        readers = ReaderManager.from_mapping(ipc_subscribes, shm_types)
        print(f"[{service_name}] WARNING: SOURCES is empty; recording will produce empty episodes.")

    def clear_buffers():
        nonlocal timestamps, buffers
        timestamps = []
        buffers = {src.feature: [] for src in SOURCES}

    async def on_start(_msg):
        nonlocal mode, episode_id, snap_context
        if mode != "idle":
            print(f"[{service_name}] recorder.start ignored: mode={mode}")
            return

        try:
            requested = await request_provenance(nc)
            requested = requested.model_copy(update={"updated_by": requested.updated_by or "runtime"})
            resolved = ensure_manifest_for_recording(ctx, requested)
        except (StoreError, Exception) as exc:
            print(f"[{service_name}] recorder.start rejected: {exc}")
            return

        clear_buffers()
        episode_id = generate_id("ep")
        snap_context = resolved
        mode = "recording"
        print(
            f"[{service_name}] recording started ep={episode_id} "
            f"manifest={resolved.manifest_name} ({resolved.manifest_id})"
        )

    async def on_stop(_msg):
        nonlocal mode, episode_id, snap_context, episode_count
        if mode != "recording":
            print(f"[{service_name}] recorder.stop ignored: mode={mode}")
            return
        if snap_context is None or episode_id is None:
            mode = "idle"
            return
        if not timestamps:
            print(f"[{service_name}] recorder.stop with empty buffer; discarding")
            clear_buffers()
            episode_id = None
            snap_context = None
            mode = "idle"
            return

        mode = "flushing"
        loop = asyncio.get_running_loop()
        resolved_context = snap_context
        resolved_episode_id = episode_id
        try:
            # Copy buffers so flush doesn't race with any concurrent clear.
            ts_copy = list(timestamps)
            buf_copy = {k: list(v) for k, v in buffers.items()}
            episode = await loop.run_in_executor(
                None,
                flush_to_disk,
                ctx,
                resolved_episode_id,
                resolved_context,
                ts_copy,
                buf_copy,
                SOURCES,
            )
            episode_count += 1
            await nc.publish(
                "recorder.episode_saved",
                json.dumps({
                    "episode_id": episode.id,
                    "manifest_id": resolved_context.manifest_id,
                    "manifest_name": resolved_context.manifest_name,
                    "manifest_type": resolved_context.manifest_type,
                    "length": episode.length,
                }).encode(),
            )
        except Exception as exc:
            print(f"[{service_name}] flush failed: {exc}")
        finally:
            clear_buffers()
            episode_id = None
            snap_context = None
            mode = "idle"

    async def on_discard(_msg):
        nonlocal mode, episode_id, snap_context
        if mode != "recording":
            print(f"[{service_name}] recorder.discard ignored: mode={mode}")
            return
        clear_buffers()
        episode_id = None
        snap_context = None
        mode = "idle"
        print(f"[{service_name}] recording discarded")

    await nc.subscribe("recorder.start", cb=on_start)
    await nc.subscribe("recorder.stop", cb=on_stop)
    await nc.subscribe("recorder.discard", cb=on_discard)

    print(f"[{service_name}] Started (pid={pid}), {loop_rate_hz}Hz, sources={len(SOURCES)}")

    loop_period = 1.0 / max(loop_rate_hz, 1)
    heartbeat_interval = 1.0
    last_heartbeat = 0.0
    next_wake = time.monotonic()

    try:
        while True:
            next_wake += loop_period
            readers.poll()

            # Pull latest from each source into its cache. See "KNOWN ISSUE"
            # in the module docstring — this caches regardless of frame_id,
            # which means repeat writes when a source is slower than the loop.
            for src in SOURCES:
                sample = readers.get(src.topic)
                if sample is None:
                    continue
                if sample.frame_id != last_frame_ids[src.topic]:
                    last_frame_ids[src.topic] = sample.frame_id
                    try:
                        cached[src.topic] = src.extract(sample)
                    except Exception as exc:
                        print(f"[{service_name}] extract failed for {src.topic}: {exc}")

            # Append if recording. All sources must have at least one sample
            # cached; otherwise we'd pad with None.
            if mode == "recording" and SOURCES and all(cached[src.topic] is not None for src in SOURCES):
                timestamps.append(time.time_ns())
                for src in SOURCES:
                    value = cached[src.topic]
                    if src.kind == "video":
                        # Copy — the SHM segment can be overwritten by the writer.
                        buffers[src.feature].append(np.array(value, copy=True))
                    else:
                        buffers[src.feature].append(list(value) if isinstance(value, list) else value)

            now = time.time()
            if now - last_heartbeat >= heartbeat_interval:
                last_heartbeat = now
                try:
                    await nc.publish(
                        f"service.{service_name}.heartbeat",
                        json.dumps({
                            "pid": pid,
                            "status": "running",
                            "uptime_s": round(now - start_time, 1),
                            "stats": {
                                "mode": mode,
                                "episode_id": episode_id,
                                "episode_count": episode_count,
                                "frames_buffered": len(timestamps),
                                "sources": len(SOURCES),
                                "readers": readers.connected_count(),
                                "context": current_context.model_dump(mode="json"),
                                "session": snap_context.model_dump(mode="json") if snap_context else None,
                            },
                            "timestamp": now,
                        }).encode(),
                    )
                except Exception:
                    pass

            sleep_time = next_wake - time.monotonic()
            if sleep_time < -loop_period:
                next_wake = time.monotonic()
                sleep_time = 0
            await asyncio.sleep(max(0, sleep_time))

    except asyncio.CancelledError:
        pass
    finally:
        readers.close()
        if nc and nc.is_connected:
            await nc.drain()


if __name__ == "__main__":
    asyncio.run(main())
