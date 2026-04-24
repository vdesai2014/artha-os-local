"""
iceoryx2 shared memory interface — blackboard pattern.

Provides BlackboardWriter and BlackboardReader wrappers for latest-value
shared memory communication between services.

Pattern: single-entry blackboard per topic. Writer creates the blackboard
and updates via update_with_copy(). Reader opens existing blackboard and
reads via entry.get().decode_as().
"""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
import time
from typing import Optional, Type, TypeVar

import iceoryx2 as iox2

T = TypeVar("T")

# Single entry per blackboard — convention preserved from earlier revs.
KEY = ctypes.c_ulong(0)

# Consecutive write failures before raising (fail-fast).
# A dead writer is a zombie — crash so the supervisor can restart cleanly.
WRITE_FAIL_LIMIT = 3

# ---------------------------------------------------------------------------
# Singleton node — one iceoryx2 Node per process, shared by all readers/writers.
# Each Node registers in /tmp/iceoryx2/nodes/; creating one per topic pollutes
# the namespace and confuses iceoryx2's dead-node GC.
# ---------------------------------------------------------------------------

_GLOBAL_NODE = None


def _get_node():
    global _GLOBAL_NODE
    if _GLOBAL_NODE is None:
        iox2.set_log_level_from_env_or(iox2.LogLevel.Warn)
        _GLOBAL_NODE = iox2.NodeBuilder.new().create(iox2.ServiceType.Ipc)
    return _GLOBAL_NODE


def _is_already_exists_error(exc: Exception) -> bool:
    """Best-effort classifier for iceoryx2 create collisions.

    The Python bindings expose BlackboardCreateError, but not a rich enough API
    here to reliably pattern-match variants directly. Keep the recovery path
    narrow: only treat explicit AlreadyExists-style failures as reopenable.
    """
    msg = str(exc)
    return "AlreadyExists" in msg or "already exists" in msg.lower()


class BlackboardWriter:
    """Writes latest value to a named blackboard entry."""

    def __init__(self, topic: str, state_type: Type[T], initial: Optional[T] = None):
        self._closed = True  # set early so __del__ is safe if __init__ fails
        self._topic = topic
        self._consecutive_failures = 0
        self._node = _get_node()
        if initial is None:
            initial = state_type()
        self._service = self._create_or_reopen(topic, initial)
        self._writer = self._service.writer_builder().create()
        self._entry = self._writer.entry(KEY, state_type)
        self._closed = False

    def _create_or_reopen(self, topic: str, initial):
        """Create blackboard service, recovering from stale segments left by crashed processes.

        Strategy:
        1. Try create() — fast path for clean startup
        2. On AlreadyExists: cleanup_dead_nodes() and retry create()
        3. On second AlreadyExists: open the stale service and get a writer from it
           (works when readers like the bridge hold the segment alive but the writer is dead)
        """
        builder = lambda: (
            self._node.service_builder(iox2.ServiceName.new(topic))
            .blackboard_creator(ctypes.c_ulong)
            .add(KEY, initial)
        )
        try:
            return builder().create()
        except iox2.BlackboardCreateError as e:
            if not _is_already_exists_error(e):
                raise RuntimeError(
                    f"[SHM] {topic}: blackboard create failed: {e}"
                ) from e

        print(f"[SHM] {topic}: AlreadyExists, cleaning dead nodes")
        self._node.cleanup_dead_nodes(iox2.ServiceType.Ipc, self._node.config)
        try:
            return builder().create()
        except iox2.BlackboardCreateError as e:
            if not _is_already_exists_error(e):
                raise RuntimeError(
                    f"[SHM] {topic}: create after cleanup failed: {e}"
                ) from e

        # Stale service held alive by readers — open and take over the writer slot
        print(f"[SHM] {topic}: reopening stale service as writer")
        try:
            return (
                self._node.service_builder(iox2.ServiceName.new(topic))
                .blackboard_opener(ctypes.c_ulong)
                .open()
            )
        except Exception as e:
            raise RuntimeError(
                f"[SHM] {topic}: stale blackboard reopen failed: {e}"
            ) from e

    def write(self, state: T) -> bool:
        """Update the blackboard entry with a new value.

        Raises RuntimeError after WRITE_FAIL_LIMIT consecutive failures.
        This crashes the service so the supervisor can restart it cleanly
        rather than leaving a zombie publisher that silently drops data.
        """
        if self._closed:
            raise RuntimeError(f"[SHM] Write on closed topic {self._topic}")
        try:
            self._entry.update_with_copy(state)
            self._consecutive_failures = 0
            return True
        except Exception as e:
            self._consecutive_failures += 1
            if self._consecutive_failures >= WRITE_FAIL_LIMIT:
                raise RuntimeError(
                    f"[SHM] {self._topic}: {self._consecutive_failures} consecutive "
                    f"write failures — segment is dead, crashing for supervisor restart"
                ) from e
            print(f"[SHM] Write error on {self._topic} "
                  f"({self._consecutive_failures}/{WRITE_FAIL_LIMIT}): {e}")
            return False

    def close(self) -> None:
        self._closed = True
        self._entry = None
        self._writer = None
        self._service = None
        # Don't close self._node — it's the shared singleton

    def __del__(self):
        if not self._closed:
            self.close()


class BlackboardReader:
    """Reads latest value from a named blackboard entry."""

    def __init__(self, topic: str, state_type: Type[T]):
        self._closed = True  # set early so __del__ is safe if __init__ fails
        self._topic = topic
        self._state_type = state_type
        self._node = _get_node()
        self._service = (
            self._node.service_builder(iox2.ServiceName.new(topic))
            .blackboard_opener(ctypes.c_ulong)
            .open()
        )
        self._reader = self._service.reader_builder().create()
        self._entry = self._reader.entry(KEY, state_type)
        self._closed = False

    def read(self) -> Optional[T]:
        """Returns decoded struct with latest value, or None on error."""
        if self._closed:
            return None
        try:
            return self._entry.get().decode_as(self._state_type)
        except Exception:
            return None

    def close(self) -> None:
        self._closed = True
        self._entry = None
        self._reader = None
        self._service = None
        # Don't close self._node — it's the shared singleton

    def __del__(self):
        if not self._closed:
            self.close()


@dataclass
class ReaderState:
    state_type: Type[T]
    reader: Optional[BlackboardReader] = None
    latest: Optional[T] = None
    last_frame_id: Optional[int] = None
    last_good_read_at: float = 0.0
    consecutive_failures: int = 0
    next_retry_at: float = 0.0
    status: str = "disconnected"


class ReaderManager:
    """Owns reader open/retry/staleness logic for one or more SHM topics."""

    def __init__(
        self,
        topic_types: dict[str, Type],
        *,
        retry_delay_s: float = 1.0,
        stale_after_s: float = 2.0,
        max_failures: int = 3,
    ):
        self._retry_delay_s = retry_delay_s
        self._stale_after_s = stale_after_s
        self._max_failures = max_failures
        self._topics = {
            topic: ReaderState(state_type=state_type)
            for topic, state_type in topic_types.items()
        }

    @classmethod
    def from_mapping(
        cls,
        topic_type_names: dict[str, str],
        types_module,
        **kwargs,
    ) -> "ReaderManager":
        topic_types = {
            topic: getattr(types_module, type_name)
            for topic, type_name in topic_type_names.items()
        }
        return cls(topic_types, **kwargs)

    def poll(self) -> None:
        now = time.monotonic()
        for topic, state in self._topics.items():
            if state.reader is None:
                if now < state.next_retry_at:
                    continue
                try:
                    state.reader = BlackboardReader(topic, state.state_type)
                    state.consecutive_failures = 0
                    state.last_good_read_at = now
                    state.status = "connected"
                except Exception:
                    state.next_retry_at = now + self._retry_delay_s
                    state.status = "waiting"
                continue

            sample = state.reader.read()
            if sample is None:
                state.consecutive_failures += 1
                state.status = "read_error"
                if state.consecutive_failures >= self._max_failures:
                    self._disconnect(topic, state, now)
                continue

            state.latest = sample
            state.consecutive_failures = 0
            frame_id = getattr(sample, "frame_id", None)
            if frame_id != state.last_frame_id:
                state.last_frame_id = frame_id
                state.last_good_read_at = now
                state.status = "healthy"
            elif now - state.last_good_read_at > self._stale_after_s:
                state.status = "stale"
                self._disconnect(topic, state, now)

    def get(self, topic: str):
        state = self._topics.get(topic)
        if state is None:
            return None
        return state.latest

    def status(self, topic: str) -> str:
        state = self._topics.get(topic)
        if state is None:
            return "unknown"
        return state.status

    def topics(self) -> tuple[str, ...]:
        return tuple(self._topics.keys())

    def connected_count(self) -> int:
        return sum(1 for state in self._topics.values() if state.reader is not None)

    def pending_count(self) -> int:
        return sum(1 for state in self._topics.values() if state.reader is None)

    def close(self) -> None:
        for topic, state in self._topics.items():
            self._disconnect(topic, state, time.monotonic(), schedule_retry=False)

    def _disconnect(
        self,
        topic: str,
        state: ReaderState,
        now: float,
        *,
        schedule_retry: bool = True,
    ) -> None:
        if state.reader is not None:
            try:
                state.reader.close()
            except Exception:
                pass
        state.reader = None
        if schedule_retry:
            state.next_retry_at = now + self._retry_delay_s
            if state.status not in {"stale", "read_error"}:
                state.status = "waiting"
        else:
            state.status = "closed"


class WriterGroup:
    """Thin helper for creating and closing groups of BlackboardWriters."""

    def __init__(self, writers: dict[str, BlackboardWriter]):
        self._writers = writers

    @classmethod
    def from_mapping(
        cls,
        topic_type_names: dict[str, str],
        types_module,
    ) -> "WriterGroup":
        writers = {}
        for topic, type_name in topic_type_names.items():
            writers[topic] = BlackboardWriter(topic, getattr(types_module, type_name))
        return cls(writers)

    def get(self, topic: str) -> Optional[BlackboardWriter]:
        return self._writers.get(topic)

    def items(self):
        return self._writers.items()

    def values(self):
        return self._writers.values()

    def __contains__(self, topic: str) -> bool:
        return topic in self._writers

    def __getitem__(self, topic: str) -> BlackboardWriter:
        return self._writers[topic]

    def close(self) -> None:
        for writer in self._writers.values():
            writer.close()
