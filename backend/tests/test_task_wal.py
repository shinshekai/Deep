import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.services.task_wal import TaskWAL


@pytest.fixture
def wal_path(tmp_path) -> Path:
    return tmp_path / "task_wal.json"


@pytest.fixture
def wal(wal_path) -> TaskWAL:
    return TaskWAL(wal_path=wal_path)


@pytest.mark.asyncio
async def test_record_start_and_complete(wal: TaskWAL, wal_path: Path):
    await wal.record_start("task_a", "id_1", {"k": "v1"})
    await wal.record_start("task_b", "id_2", {"k": "v2"})
    await wal.record_complete("id_1", "completed", {"ok": True})

    pending = await wal.list_pending()
    assert len(pending) == 1
    assert pending[0]["task_id"] == "id_2"
    assert pending[0]["task_name"] == "task_b"
    assert pending[0]["status"] == "running"

    completed = await wal.list_completed()
    assert len(completed) == 1
    assert completed[0]["task_id"] == "id_1"
    assert completed[0]["status"] == "completed"
    assert completed[0]["result"] == {"ok": True}

    on_disk = json.loads(wal_path.read_text(encoding="utf-8"))
    assert len(on_disk) == 2
    statuses = {e["task_id"]: e["status"] for e in on_disk}
    assert statuses == {"id_1": "completed", "id_2": "running"}


@pytest.mark.asyncio
async def test_replay_pending(wal: TaskWAL):
    await wal.record_start("orphan_a", "orph_1", {"foo": 1})
    await wal.record_start("orphan_b", "orph_2", {"bar": 2})

    pending_before = await wal.list_pending()
    assert len(pending_before) == 2

    handler = AsyncMock()
    count = await wal.replay_pending(handler)
    assert count == 2
    assert handler.await_count == 2

    pending_after = await wal.list_pending()
    assert pending_after == []

    handler_ids = {call.args[0]["task_id"] for call in handler.await_args_list}
    assert handler_ids == {"orph_1", "orph_2"}

    async def fetch_all():
        async with wal._lock:
            await wal._ensure_loaded()
            return list(wal._entries)

    entries = await fetch_all()
    assert {e["task_id"]: e["status"] for e in entries} == {
        "orph_1": "replayed",
        "orph_2": "replayed",
    }


@pytest.mark.asyncio
async def test_concurrent_writes(wal: TaskWAL, wal_path: Path):
    async def _write(i: int) -> None:
        await wal.record_start(f"task_{i}", f"id_{i}", {"index": i})

    await asyncio.gather(*[_write(i) for i in range(5)])

    pending = await wal.list_pending()
    assert len(pending) == 5
    seen = {entry["task_id"] for entry in pending}
    assert seen == {f"id_{i}" for i in range(5)}

    on_disk = json.loads(wal_path.read_text(encoding="utf-8"))
    assert len(on_disk) == 5
    assert {e["task_id"] for e in on_disk} == {f"id_{i}" for i in range(5)}
    assert all(e["status"] == "running" for e in on_disk)
