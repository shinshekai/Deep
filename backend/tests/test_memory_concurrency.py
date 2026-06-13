"""Concurrency regression tests for MemoryService write serialization.

These tests exercise the CRITICAL race fixed by routing all writes through
MemoryService._write_lock: a single shared aiosqlite connection multiplexed
across many concurrent coroutines. Before the fix, interleaving bare
execute()+commit() writes with a BEGIN IMMEDIATE transaction (e.g.
recall_facts' phase-2 update) on the same connection could raise
"cannot start a transaction within a transaction" or commit partial work.

The tests spawn many concurrent writers (and concurrent recalls) against a
single instance and assert that no exception is raised and every row is
persisted.
"""

import asyncio
import os
import tempfile

import pytest

from app.services.memory_service import MemoryService


@pytest.fixture
async def isolated_service():
    tmpdir = tempfile.mkdtemp()
    svc = MemoryService(db_path=os.path.join(tmpdir, "concurrency_test.db"))
    await svc.initialize()
    yield svc
    await svc.close()


class TestConcurrentWrites:
    async def test_many_concurrent_episode_writes_all_persist(self, isolated_service):
        """50 concurrent store_episode calls must all succeed and persist."""
        svc = isolated_service
        device_id = "concurrent-episodes"
        n = 50

        results = await asyncio.gather(
            *(
                svc.store_episode(
                    device_id=device_id,
                    query=f"q{i}",
                    answer=f"a{i}",
                    session_type="chat",
                )
                for i in range(n)
            )
        )

        assert len(results) == n
        assert len(set(results)) == n  # unique ids, no lost writes

        stats = await svc.get_stats(device_id)
        assert stats["episodes"] == n

    async def test_concurrent_fact_writes_all_persist(self, isolated_service):
        """Concurrent store_fact calls must all succeed and persist."""
        svc = isolated_service
        device_id = "concurrent-facts"
        n = 40

        results = await asyncio.gather(
            *(svc.store_fact(device_id, f"fact number {i} about topic") for i in range(n))
        )

        assert len(set(results)) == n
        stats = await svc.get_stats(device_id)
        assert stats["facts"] == n

    async def test_writes_interleaved_with_recalls_no_error(self, isolated_service):
        """Mix writes (store_episode/store_fact) with recalls on one connection.

        recall_facts performs a BEGIN IMMEDIATE phase-2 update; interleaving it
        with bare-commit writes is exactly the race that previously corrupted
        the connection. With write serialization, all operations complete
        cleanly.
        """
        svc = isolated_service
        device_id = "interleaved"

        # Seed a few facts so recalls have something to update.
        for i in range(5):
            await svc.store_fact(device_id, f"seed fact {i} about python")

        async def writer(i: int):
            await svc.store_episode(device_id, f"wq{i}", f"wa{i}")
            await svc.store_fact(device_id, f"runtime fact {i} about python")

        async def recaller():
            await svc.recall_facts(device_id, "python")
            await svc.recall_episodes(device_id, "wq")

        tasks = []
        for i in range(25):
            tasks.append(writer(i))
            tasks.append(recaller())

        # Must not raise (no "transaction within a transaction", no partial
        # commits invalidating the connection).
        await asyncio.gather(*tasks)

        stats = await svc.get_stats(device_id)
        assert stats["episodes"] == 25
        assert stats["facts"] == 5 + 25

    async def test_track_usage_no_deadlock_under_writes(self, isolated_service):
        """store_episode calls track_usage internally; ensure no deadlock.

        track_usage acquires _write_lock; store_episode holds it and uses the
        lock-free _track_usage_nolock helper. A regression that made
        track_usage re-acquire the lock from within store_episode would hang
        here, so we bound it with a timeout.
        """
        svc = isolated_service
        device_id = "deadlock-check"

        async def run():
            await asyncio.gather(
                *(svc.store_episode(device_id, f"q{i}", f"a{i}") for i in range(20))
            )

        # If a deadlock were reintroduced this would never return.
        await asyncio.wait_for(run(), timeout=30)

        stats = await svc.get_stats(device_id)
        assert stats["episodes"] == 20
