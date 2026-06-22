"""Unit tests for stream_bus.py — event protocol with replay and pause/resume."""
import asyncio

import pytest

from app.services.stream_bus import StreamBus, StreamEvent


class TestStreamBus:
    @pytest.mark.asyncio
    async def test_emit_and_subscribe(self):
        bus = StreamBus("test-session")
        received = []

        async def handler(event: StreamEvent):
            received.append(event)

        bus.subscribe(handler)
        seq = await bus.emit("agent_step", {"content": "hello"})

        assert seq == 1
        assert len(received) == 1
        assert received[0].type == "agent_step"
        assert received[0].data["content"] == "hello"

    @pytest.mark.asyncio
    async def test_replay_after_seq(self):
        bus = StreamBus("test-session")

        await bus.emit("step_1", {"n": 1})
        await bus.emit("step_2", {"n": 2})
        await bus.emit("step_3", {"n": 3})

        replayed = await bus.replay(after_seq=1)
        assert len(replayed) == 2
        assert replayed[0].data["n"] == 2
        assert replayed[1].data["n"] == 3

    @pytest.mark.asyncio
    async def test_replay_full_history(self):
        bus = StreamBus("test-session")

        await bus.emit("step_1", {})
        await bus.emit("step_2", {})

        replayed = await bus.replay(after_seq=0)
        assert len(replayed) == 2

    @pytest.mark.asyncio
    async def test_pause_resume(self):
        bus = StreamBus("test-session")
        received = []

        async def handler(event: StreamEvent):
            received.append(event)

        bus.subscribe(handler)
        await bus.pause()
        assert bus.is_paused

        await bus.emit("should_not_arrive", {})
        assert len(received) == 0

        bus.resume()
        assert not bus.is_paused

        await bus.emit("should_arrive", {})
        assert len(received) == 1
        assert received[0].type == "should_arrive"

    @pytest.mark.asyncio
    async def test_multiple_subscribers(self):
        bus = StreamBus("test-session")
        r1 = []
        r2 = []

        async def h1(e):
            r1.append(e)

        async def h2(e):
            r2.append(e)

        bus.subscribe(h1)
        bus.subscribe(h2)
        await bus.emit("shared", {})

        assert len(r1) == 1
        assert len(r2) == 1

    @pytest.mark.asyncio
    async def test_subscriber_error_isolation(self):
        bus = StreamBus("test-session")
        received = []

        async def failing_handler(event: StreamEvent):
            raise RuntimeError("boom")

        async def good_handler(event: StreamEvent):
            received.append(event)

        bus.subscribe(failing_handler)
        bus.subscribe(good_handler)
        await bus.emit("test", {})

        assert len(received) == 1  # Good handler still received

    @pytest.mark.asyncio
    async def test_event_count(self):
        bus = StreamBus("test-session")
        assert bus.event_count == 0
        assert bus.last_seq == 0

        await bus.emit("test", {})
        assert bus.event_count == 1
        assert bus.last_seq == 1
