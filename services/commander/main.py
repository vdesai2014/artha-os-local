"""
Commander — state machine for robot command blending.

The commander is what sits between policy/sequence outputs and the robot's
desired SHM topic. It owns the "what am I doing right now" state: running a
pre-authored sequence, forwarding a live policy, returning home, or idle.
It blends commands (trickle + slew) so nothing jumps discontinuously on mode
changes.

This default is a *pattern*, not a prescription. It's generic enough to run
the sim-demo eval (policy_gate mode) and show how sequences compose, but
you'll fork it for your own robot's quirks — zeroing, polarity, teleop
sources, etc. The user's agent will modify this file to suit their needs.

Modes
-----
  idle          — no output; writer is quiet
  policy_gate   — forwards a policy topic straight through when enabled
                   (the sim-demo eval uses this)
  sequence      — running a pre-authored sequence of steps
  return_home   — trickling toward the home pose; auto-transitions to idle

Sequence step types
-------------------
  trickle       — glide to {pose}
  waypoint      — load {waypoint_file}, trickle to it, hold {hold}s
  trajectory    — load {trajectory_file}, follow timestamped positions
  policy        — gate to {topic}, optional recording, timeout-exits

NATS interface
--------------
  commander.enable / disable / toggle      — policy_gate on/off
  commander.set_policy {policy_name}       — updates published provenance
  commander.status                         — request/reply current state
  commander.run_sequence {name}            — load + run a sequence
  commander.stop_sequence                  — stop -> return_home
  commander.return_home                    — go home from any mode
  commander.emergency_stop                 — stop all output, back to idle
  commander.skip_to {step}                 — within a sequence, jump step

Hardware-specific bits you'd expect in a commander but aren't here
-------------------------------------------------------------------
  - Teleop leader-arm mapping — add your own mode that reads from a
    leader SHM topic and forwards 
  - Joint offsets / polarity — store/apply per your actuator setup.
  - Safety slew limits — tune `commander.slew_limit` via param_server.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path

from core.shm import ReaderManager, WriterGroup
import core.types as shm_types

from core.config import nats_connect, ParamClient


# ---------------------------------------------------------------------------
# Config — edit for your robot
# ---------------------------------------------------------------------------

NUM_JOINTS = 7
HOME_POSITIONS = [0.0] * NUM_JOINTS
STATE_TOPIC = "sim_robot/actual"            # where we read current joint state
COMMAND_TOPIC = "sim_robot/desired"         # where we write desired commands

# Default policy topic used by policy_gate mode and policy-type sequence steps.
# Overridable per-step or via env.
DEFAULT_POLICY_TOPIC = os.environ.get("POLICY_TOPIC", "inference/desired")

# Where sequence definitions live on disk. Missing dirs are fine — sequences
# that need them will fail gracefully at run time.
ARTHA_ROOT = Path(os.environ.get("ARTHA_ROOT", Path(__file__).resolve().parents[2]))
SEQ_DIR = ARTHA_ROOT / "config" / "sequences"
WAYPOINT_DIR = ARTHA_ROOT / "config" / "waypoints"
TRAJ_DIR = ARTHA_ROOT / "config" / "trajectories"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def trickle_step(
    current: list[float],
    target: list[float],
    max_step: float,
    threshold: float,
) -> tuple[list[float], bool]:
    """One trickle tick toward target. Returns (next, converged)."""
    out = list(current)
    converged = True
    for i in range(len(current)):
        diff = target[i] - current[i]
        if abs(diff) <= threshold or abs(diff) <= max_step:
            out[i] = target[i]
        else:
            out[i] = current[i] + (max_step if diff > 0 else -max_step)
            converged = False
    return out, converged


def expand_sequence(seq_def: dict) -> dict:
    """Flatten any `loop` step into N copies of its inner steps."""
    expanded = []
    for step in seq_def.get("steps", []):
        if step.get("type") == "loop":
            count = step.get("count", 1)
            inner = expand_sequence({"steps": step.get("steps", [])})
            for _ in range(count):
                expanded.extend(inner["steps"])
        else:
            expanded.append(step)
    return {**seq_def, "steps": expanded}


def load_json(directory: Path, name: str, ext: str = ".json") -> dict:
    path = directory / name if name.endswith(ext) else directory / f"{name}{ext}"
    if not path.exists():
        raise FileNotFoundError(f"Not found: {path}")
    return json.loads(path.read_text())


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    service_name = os.environ.get("SERVICE_NAME", "commander")
    loop_rate_hz = int(os.environ.get("LOOP_RATE_HZ", "100"))
    pid = os.getpid()
    start_time = time.time()

    # State
    mode = "idle"
    policy_gate_enabled = False
    policy_name = os.environ.get("POLICY_NAME")
    cmd_positions = [0.0] * NUM_JOINTS
    prev_cmd: list[float] | None = None

    # Sequence state
    seq_def: dict | None = None
    seq_step_idx = 0
    seq_sub = "idle"
    seq_trickle_target: list[float] = []
    seq_traj_data: dict | None = None
    seq_traj_idx = 0
    seq_traj_start_mono = 0.0
    seq_policy_topic = DEFAULT_POLICY_TOPIC
    seq_policy_start_mono = 0.0
    seq_hold_until = 0.0
    seq_recording = False

    nc = await nats_connect(service_name)

    # Tunables — live-updated via param_server
    trickle_rate = 0.3
    trickle_threshold = 0.05
    slew_limit = 3.0

    async def handle_param_update(key, val):
        nonlocal trickle_rate, trickle_threshold, slew_limit
        if key == "commander.trickle_rate":
            trickle_rate = float(val)
        elif key == "commander.trickle_threshold":
            trickle_threshold = float(val)
        elif key == "commander.slew_limit":
            slew_limit = float(val)
        print(f"[{service_name}] {key}={val}")

    params = ParamClient(nc, prefix="commander", on_change=handle_param_update)
    await params.init()
    trickle_rate = params.get("commander.trickle_rate", trickle_rate)
    trickle_threshold = params.get("commander.trickle_threshold", trickle_threshold)
    slew_limit = params.get("commander.slew_limit", slew_limit)

    # SHM I/O
    ipc_publishes = json.loads(os.environ.get("IPC_PUBLISHES", "{}"))
    shm_writers = WriterGroup.from_mapping(ipc_publishes, shm_types)
    for topic, _writer in shm_writers.items():
        print(f"[{service_name}] SHM writer: {topic}")

    ipc_subscribes = json.loads(os.environ.get("IPC_SUBSCRIBES", "{}"))
    readers = ReaderManager.from_mapping(ipc_subscribes, shm_types)

    tx_cmd = shm_types.RobStrideCommand() if hasattr(shm_types, "RobStrideCommand") else None
    # If user hasn't defined a command type yet, we can't actually write.
    # Fail fast at startup rather than silently go idle.
    if tx_cmd is None:
        raise RuntimeError(
            "[commander] core/types.py has no command struct (e.g. JointAction or "
            "RobStrideCommand). Define one and declare it in services.yaml ipc.publishes."
        )

    frame_count = 0

    def seed_from_robot():
        """Snap the command buffer to the current robot state to avoid a jump."""
        nonlocal cmd_positions, prev_cmd
        rs = readers.get(STATE_TOPIC)
        if rs is not None:
            cmd_positions = [rs.position[i] for i in range(NUM_JOINTS)]
            prev_cmd = list(cmd_positions)
            print(f"[{service_name}] Seeded from {STATE_TOPIC}: {[round(p, 3) for p in cmd_positions]}")
            return
        print(f"[{service_name}] WARNING: could not seed from {STATE_TOPIC}; using HOME")
        cmd_positions = list(HOME_POSITIONS)
        prev_cmd = list(cmd_positions)

    # Provenance announcements — keeps the provenance service in sync with
    # what mode/policy commander thinks it's running. See services/provenance.py
    async def publish_provenance_state():
        try:
            await nc.publish(
                "provenance.commander",
                json.dumps({
                    "mode": mode_for_provenance(),
                    "policy_name": policy_name,
                    "timestamp": time.time(),
                }).encode(),
            )
        except Exception:
            pass

    def mode_for_provenance() -> str:
        # Map internal modes onto what provenance/data_recorder expect.
        # "eval" = actively running a policy (gate on, or inside a policy step).
        if mode == "policy_gate" and policy_gate_enabled:
            return "eval"
        if mode == "sequence" and seq_sub == "policy":
            return "eval"
        return "idle" if mode == "idle" else mode

    # -----------------------------------------------------------------------
    # Sequence step runners
    # -----------------------------------------------------------------------

    async def start_recording(step: dict):
        nonlocal seq_recording
        try:
            payload = step.get("recording_overrides", {})
            await nc.publish("recorder.start", json.dumps(payload if isinstance(payload, dict) else {}).encode())
        except Exception:
            pass
        seq_recording = True
        print(f"[{service_name}] Recording started")

    async def stop_recording():
        nonlocal seq_recording
        if not seq_recording:
            return
        try:
            await nc.publish("recorder.stop", b"")
        except Exception:
            pass
        seq_recording = False
        print(f"[{service_name}] Recording stopped")

    async def begin_seq_step():
        nonlocal seq_sub, seq_trickle_target, seq_traj_data

        step = seq_def["steps"][seq_step_idx]

        if step["type"] == "trickle":
            seq_trickle_target = [float(x) for x in step["pose"]]
            seq_sub = "trickle"
            print(f"[{service_name}] Step {seq_step_idx}: trickle")

        elif step["type"] == "waypoint":
            try:
                wp = load_json(WAYPOINT_DIR, step["file"])
            except FileNotFoundError as e:
                print(f"[{service_name}] {e}, skipping")
                await advance_seq()
                return
            seq_trickle_target = [float(x) for x in wp["pose"]]
            seq_sub = "trickle_to_step"
            print(
                f"[{service_name}] Step {seq_step_idx}: waypoint "
                f"'{step['file']}' (hold={step.get('hold', 0)}s)"
            )

        elif step["type"] == "trajectory":
            try:
                seq_traj_data = load_json(TRAJ_DIR, step["file"])
            except FileNotFoundError as e:
                print(f"[{service_name}] {e}, skipping")
                await advance_seq()
                return
            seq_trickle_target = [float(x) for x in seq_traj_data["positions"][0]]
            seq_sub = "trickle_to_step"
            print(
                f"[{service_name}] Step {seq_step_idx}: trajectory "
                f"'{step['file']}' ({len(seq_traj_data['positions'])} pts)"
            )

        elif step["type"] == "policy":
            step_pose = step.get("pose")
            topic = step.get("topic", DEFAULT_POLICY_TOPIC)
            if not step_pose and topic in readers.topics():
                inf = readers.get(topic)
                if inf is not None:
                    step_pose = [inf.position[i] for i in range(NUM_JOINTS)]
            seq_trickle_target = (
                [float(x) for x in step_pose] if step_pose else list(cmd_positions)
            )
            seq_sub = "trickle_to_step"
            print(
                f"[{service_name}] Step {seq_step_idx}: policy "
                f"topic={topic}, record={step.get('record', False)}"
            )

    def enter_trajectory():
        nonlocal seq_sub, seq_traj_idx, seq_traj_start_mono
        seq_traj_idx = 0
        seq_traj_start_mono = time.monotonic()
        seq_sub = "trajectory"

    async def enter_policy(step: dict):
        nonlocal seq_sub, seq_policy_start_mono, seq_policy_topic
        seq_policy_start_mono = time.monotonic()
        seq_policy_topic = step.get("topic", DEFAULT_POLICY_TOPIC)
        seq_sub = "policy"
        if step.get("record", False):
            await start_recording(step)
        await publish_provenance_state()

    async def enter_hold(step: dict):
        nonlocal seq_sub, seq_hold_until
        hold_s = float(step.get("hold", 0))
        if hold_s > 0:
            seq_hold_until = time.monotonic() + hold_s
            seq_sub = "hold"
        else:
            await advance_seq()

    async def advance_seq():
        nonlocal seq_step_idx, mode, seq_def
        if seq_recording:
            await stop_recording()
        seq_step_idx += 1
        if seq_step_idx >= len(seq_def["steps"]):
            if seq_def.get("loop", False):
                seq_step_idx = 0
                print(f"[{service_name}] Sequence looping")
                await begin_seq_step()
            else:
                print(f"[{service_name}] Sequence complete -> return_home")
                seq_def = None
                mode = "return_home"
                await publish_provenance_state()
        else:
            await begin_seq_step()

    # -----------------------------------------------------------------------
    # NATS handlers
    # -----------------------------------------------------------------------

    async def do_emergency_stop(reason: str):
        nonlocal mode, seq_def, policy_gate_enabled
        prev_mode = mode
        mode = "idle"
        seq_def = None
        policy_gate_enabled = False
        if seq_recording:
            await stop_recording()
        await publish_provenance_state()
        print(f"[{service_name}] E-STOP ({reason}): {prev_mode} -> idle")

    async def on_enable(msg):
        nonlocal mode, policy_gate_enabled
        policy_gate_enabled = True
        if mode == "idle":
            seed_from_robot()
            mode = "policy_gate"
        await publish_provenance_state()
        print(f"[{service_name}] policy_gate enabled (mode={mode})")
        if msg.reply:
            await nc.publish(msg.reply, json.dumps({"enabled": True, "mode": mode}).encode())

    async def on_disable(msg):
        nonlocal mode, policy_gate_enabled
        policy_gate_enabled = False
        if mode == "policy_gate":
            mode = "idle"
        await publish_provenance_state()
        print(f"[{service_name}] policy_gate disabled (mode={mode})")
        if msg.reply:
            await nc.publish(msg.reply, json.dumps({"enabled": False, "mode": mode}).encode())

    async def on_toggle(msg):
        if policy_gate_enabled:
            await on_disable(msg)
        else:
            await on_enable(msg)

    async def on_status(msg):
        if msg.reply:
            await nc.publish(
                msg.reply,
                json.dumps({
                    "mode": mode,
                    "policy_gate_enabled": policy_gate_enabled,
                    "policy_name": policy_name,
                    "seq_name": seq_def.get("name") if seq_def else None,
                    "seq_step": seq_step_idx if seq_def else None,
                }).encode(),
            )

    async def on_set_policy(msg):
        nonlocal policy_name
        try:
            payload = json.loads(msg.data.decode()) if msg.data else {}
        except Exception:
            payload = {}
        next_policy = payload.get("policy_name")
        if next_policy != policy_name:
            policy_name = next_policy
            await publish_provenance_state()
        if msg.reply:
            await nc.publish(msg.reply, json.dumps({"policy_name": policy_name}).encode())

    async def on_run_sequence(msg):
        nonlocal mode, seq_def, seq_step_idx, seq_sub, seq_recording

        if mode != "idle":
            print(f"[{service_name}] run_sequence ignored: mode={mode}")
            return

        try:
            payload = json.loads(msg.data.decode()) if msg.data else {}
        except Exception:
            payload = {}

        seq_name = payload.get("name", "")
        if not seq_name:
            print(f"[{service_name}] run_sequence: no name")
            return

        try:
            raw = load_json(SEQ_DIR, seq_name)
            seq_def = expand_sequence(raw)
        except FileNotFoundError as e:
            print(f"[{service_name}] {e}")
            return

        if not seq_def.get("steps"):
            print(f"[{service_name}] Sequence '{seq_name}' has no steps")
            seq_def = None
            return

        for i, step in enumerate(seq_def["steps"]):
            if step.get("type") == "policy":
                topic = step.get("topic", DEFAULT_POLICY_TOPIC)
                if topic not in readers.topics():
                    print(f"[{service_name}] PREFLIGHT FAIL: step {i} topic '{topic}' not in SHM readers")
                    seq_def = None
                    return

        print(
            f"[{service_name}] Running '{seq_name}': "
            f"{len(seq_def['steps'])} steps, loop={seq_def.get('loop', False)}"
        )

        seed_from_robot()
        seq_step_idx = 0
        seq_sub = "idle"
        seq_recording = False
        mode = "sequence"
        await publish_provenance_state()

        try:
            await nc.publish("inference.reset", b"{}")
        except Exception:
            pass

        await begin_seq_step()

    async def on_stop_sequence(msg):
        nonlocal mode, seq_def
        if mode != "sequence":
            return
        if seq_recording:
            await stop_recording()
        seq_def = None
        mode = "return_home"
        await publish_provenance_state()
        print(f"[{service_name}] Sequence stopped -> return_home")

    async def on_return_home(msg):
        nonlocal mode, seq_def, policy_gate_enabled
        if mode == "idle":
            return
        if seq_recording:
            await stop_recording()
        seq_def = None
        policy_gate_enabled = False
        mode = "return_home"
        await publish_provenance_state()
        print(f"[{service_name}] -> return_home")

    async def on_emergency_stop(msg):
        await do_emergency_stop("NATS command")

    async def on_skip_to(msg):
        nonlocal seq_step_idx
        if mode != "sequence" or seq_def is None:
            return
        try:
            payload = json.loads(msg.data.decode()) if msg.data else {}
        except Exception:
            return
        target = payload.get("step")
        if target is not None and 0 <= target < len(seq_def["steps"]):
            if seq_recording:
                await stop_recording()
            seq_step_idx = target
            print(f"[{service_name}] Skip to step {target}")
            await begin_seq_step()

    await nc.subscribe("commander.enable", cb=on_enable)
    await nc.subscribe("commander.disable", cb=on_disable)
    await nc.subscribe("commander.toggle", cb=on_toggle)
    await nc.subscribe("commander.status", cb=on_status)
    await nc.subscribe("commander.set_policy", cb=on_set_policy)
    await nc.subscribe("commander.run_sequence", cb=on_run_sequence)
    await nc.subscribe("commander.stop_sequence", cb=on_stop_sequence)
    await nc.subscribe("commander.return_home", cb=on_return_home)
    await nc.subscribe("commander.emergency_stop", cb=on_emergency_stop)
    await nc.subscribe("commander.skip_to", cb=on_skip_to)

    await publish_provenance_state()
    print(
        f"[{service_name}] Started (pid={pid}), {loop_rate_hz}Hz, "
        f"trickle={trickle_rate}, slew={slew_limit}, policy={policy_name}"
    )

    loop_period = 1.0 / max(loop_rate_hz, 1)
    heartbeat_interval = 1.0
    last_heartbeat = 0.0
    next_wake = time.monotonic()

    # -----------------------------------------------------------------------
    # Main loop
    # -----------------------------------------------------------------------
    try:
        while True:
            next_wake += loop_period
            mono_now = time.monotonic()

            readers.poll()

            max_trickle = trickle_rate * loop_period
            should_write = False

            if mode == "idle":
                pass

            elif mode == "policy_gate":
                # Forward the latest policy command straight through when enabled.
                # If there's no current policy sample, hold the last command.
                if policy_gate_enabled:
                    inf = readers.get(DEFAULT_POLICY_TOPIC)
                    if inf is not None:
                        cmd_positions = [inf.position[i] for i in range(NUM_JOINTS)]
                        should_write = True

            elif mode == "sequence" and seq_def is not None:
                should_write = True

                if seq_sub in ("trickle", "trickle_to_step"):
                    cmd_positions, converged = trickle_step(
                        cmd_positions, seq_trickle_target, max_trickle, trickle_threshold,
                    )
                    if converged:
                        if seq_sub == "trickle":
                            await advance_seq()
                        else:
                            step = seq_def["steps"][seq_step_idx]
                            if step["type"] == "waypoint":
                                await enter_hold(step)
                            elif step["type"] == "trajectory":
                                enter_trajectory()
                            elif step["type"] == "policy":
                                await enter_policy(step)

                elif seq_sub == "trajectory":
                    elapsed = mono_now - seq_traj_start_mono
                    positions = seq_traj_data["positions"]
                    timestamps = seq_traj_data["timestamps"]
                    while (
                        seq_traj_idx < len(timestamps) - 1
                        and timestamps[seq_traj_idx + 1] <= elapsed
                    ):
                        seq_traj_idx += 1
                    if seq_traj_idx >= len(positions) - 1:
                        cmd_positions = [float(x) for x in positions[-1]]
                        print(f"[{service_name}] Step {seq_step_idx}: trajectory done ({elapsed:.1f}s)")
                        await advance_seq()
                    else:
                        t0 = timestamps[seq_traj_idx]
                        t1 = timestamps[seq_traj_idx + 1]
                        alpha = (elapsed - t0) / (t1 - t0) if t1 > t0 else 1.0
                        alpha = max(0.0, min(1.0, alpha))
                        p0 = positions[seq_traj_idx]
                        p1 = positions[seq_traj_idx + 1]
                        cmd_positions = [
                            p0[i] + alpha * (p1[i] - p0[i])
                            for i in range(NUM_JOINTS)
                        ]

                elif seq_sub == "policy":
                    inf = readers.get(seq_policy_topic)
                    if inf is not None:
                        cmd_positions = [inf.position[i] for i in range(NUM_JOINTS)]
                    timeout = seq_def["steps"][seq_step_idx].get("completion", {}).get("timeout", 30)
                    if (mono_now - seq_policy_start_mono) >= timeout:
                        print(f"[{service_name}] Step {seq_step_idx}: policy timeout ({timeout}s)")
                        await advance_seq()

                elif seq_sub == "hold":
                    if mono_now >= seq_hold_until:
                        print(f"[{service_name}] Step {seq_step_idx}: hold done")
                        await advance_seq()

            elif mode == "return_home":
                cmd_positions, converged = trickle_step(
                    cmd_positions, HOME_POSITIONS, max_trickle, trickle_threshold,
                )
                should_write = True
                if converged:
                    mode = "idle"
                    await publish_provenance_state()
                    print(f"[{service_name}] Home reached -> idle")

            if should_write:
                # Slew-limit per-tick to prevent discontinuous commands.
                max_slew = slew_limit * loop_period
                if prev_cmd is not None:
                    for i in range(NUM_JOINTS):
                        diff = cmd_positions[i] - prev_cmd[i]
                        if abs(diff) > max_slew:
                            cmd_positions[i] = prev_cmd[i] + (max_slew if diff > 0 else -max_slew)
                prev_cmd = list(cmd_positions)

                tx_cmd.timestamp = time.time()
                tx_cmd.frame_id = frame_count
                frame_count += 1
                for i in range(NUM_JOINTS):
                    tx_cmd.position[i] = cmd_positions[i]
                    tx_cmd.velocity[i] = 0.0
                    tx_cmd.torque[i] = 0.0
                writer = shm_writers.get(COMMAND_TOPIC)
                if writer is not None:
                    writer.write(tx_cmd)

            # Heartbeat
            now = time.time()
            if now - last_heartbeat >= heartbeat_interval:
                last_heartbeat = now
                stats = {
                    "mode": mode,
                    "policy_gate_enabled": policy_gate_enabled,
                    "policy_name": policy_name,
                    "output_frames": frame_count,
                    "readers": readers.connected_count(),
                }
                if seq_def is not None:
                    stats.update({
                        "seq_name": seq_def.get("name", ""),
                        "seq_step": seq_step_idx,
                        "seq_total": len(seq_def["steps"]),
                        "seq_sub": seq_sub,
                        "seq_recording": seq_recording,
                    })
                try:
                    await nc.publish(
                        f"service.{service_name}.heartbeat",
                        json.dumps({
                            "pid": pid,
                            "status": "running",
                            "uptime_s": round(now - start_time, 1),
                            "stats": stats,
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
        print(f"[{service_name}] Shutting down (mode={mode})...")
        shm_writers.close()
        readers.close()
        if nc and nc.is_connected:
            await nc.drain()
        print(f"[{service_name}] Done.")


if __name__ == "__main__":
    asyncio.run(main())
