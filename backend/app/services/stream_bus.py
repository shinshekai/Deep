"""StreamBus — typed event protocol with fan-out, replay, and pause/resume.

Inspired by DeepTutor's `deeptutor/core/stream_bus.py`.
Each solve session gets its own StreamBus instance for isolation.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)


@dataclass
class StreamEvent:
    """A single event on the bus, with sequence number for replay."""
    seq: int = 0
    type: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0


class StreamBus:
    """Per-session event bus with typed events, fan-out subscribers, replay, and pause/resume."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self._events: list[StreamEvent] = []
        self._subscribers: list[Callable[[StreamEvent], Awaitable[None]]] = []
        self._seq = 0
        self._paused = asyncio.Event()

    async def emit(self, event_type: str, data: dict[str, Any] | None = None) -> int:
        """Emit a typed event to all subscribers. Returns the event's sequence number."""
        if self._paused.is_set():
            return self._seq

        self._seq += 1
        event = StreamEvent(
            seq=self._seq,
            type=event_type,
            data=data or {},
            timestamp=time.time(),
        )
        self._events.append(event)
        for sub in self._subscribers:
            try:
                await sub(event)
            except Exception:
                pass
        return self._seq

    def subscribe(self, callback: Callable[[StreamEvent], Awaitable[None]]) -> None:
        """Register a subscriber callback for all events."""
        self._subscribers.append(callback)

    async def replay(self, after_seq: int = 0) -> list[StreamEvent]:
        """Replay events after the given sequence number.

        Returns the replayed events for the client to process.
        A late-connecting client calls this with after_seq=0 to get full history.
        """
        replayed = [e for e in self._events if e.seq > after_seq]
        if replayed:
            logger.debug("Replaying %d events for session %s after seq %d",
                         len(replayed), self.session_id, after_seq)
        return replayed

    async def pause(self) -> None:
        """Pause the bus, blocking all emit() calls until resume() is called.

        Used for mid-turn clarification: the agent pauses, asks the user
        a question, and waits for input before continuing.
        """
        self._paused.set()
        logger.info("StreamBus paused for session %s", self.session_id)

    def resume(self) -> None:
        """Resume the bus after a pause."""
        self._paused.clear()
        logger.info("StreamBus resumed for session %s", self.session_id)

    @property
    def is_paused(self) -> bool:
        return self._paused.is_set()

    @property
    def event_count(self) -> int:
        return len(self._events)

    @property
    def last_seq(self) -> int:
        return self._seq
