import asyncio
import json
import logging
import os
import tempfile
import time
from collections.abc import Awaitable, Callable
from pathlib import Path

logger = logging.getLogger(__name__)


class TaskWAL:
    def __init__(self, wal_path: Path = Path("data/persistence/task_wal.json")):
        self.wal_path = Path(wal_path)
        self._entries: list[dict] = []
        self._lock = asyncio.Lock()
        self._loaded = False

    async def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        if self.wal_path.exists():
            try:
                with open(self.wal_path, encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    self._entries = data
                else:
                    self._entries = []
            except (OSError, json.JSONDecodeError) as e:
                logger.error(f"Failed to load task WAL {self.wal_path}: {e}")
                self._entries = []
        self._loaded = True

    async def _flush(self) -> None:
        self.wal_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            dir=str(self.wal_path.parent),
            prefix=".task_wal_",
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._entries, f, indent=2)
            os.replace(tmp_path, self.wal_path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    async def record_start(self, task_name: str, task_id: str, payload: dict) -> None:
        async with self._lock:
            await self._ensure_loaded()
            self._entries.append(
                {
                    "task_id": task_id,
                    "task_name": task_name,
                    "payload": payload,
                    "started_at": time.time(),
                    "status": "running",
                }
            )
            await self._flush()

    async def record_complete(self, task_id: str, status: str, result: dict | None = None) -> None:
        async with self._lock:
            await self._ensure_loaded()
            for entry in self._entries:
                if entry.get("task_id") == task_id:
                    entry["completed_at"] = time.time()
                    entry["status"] = status
                    if result is not None:
                        entry["result"] = result
                    break
            await self._flush()

    async def list_pending(self) -> list[dict]:
        async with self._lock:
            await self._ensure_loaded()
            return [e for e in self._entries if e.get("status") == "running"]

    async def list_completed(self, since_seconds: int = 3600) -> list[dict]:
        async with self._lock:
            await self._ensure_loaded()
            cutoff = time.time() - since_seconds
            return [
                e
                for e in self._entries
                if e.get("status") != "running" and (e.get("completed_at") or 0) >= cutoff
            ]

    async def replay_pending(self, handler: Callable[[dict], Awaitable[None]]) -> int:
        async with self._lock:
            await self._ensure_loaded()
            pending = [e for e in self._entries if e.get("status") == "running"]
        if not pending:
            return 0
        count = 0
        for entry in pending:
            try:
                await handler(entry)
            except Exception as e:
                logger.error(f"Replay handler failed for {entry.get('task_id')}: {e}")
                continue
            async with self._lock:
                for e in self._entries:
                    if e.get("task_id") == entry.get("task_id") and e.get("status") == "running":
                        e["status"] = "replayed"
                        e["replayed_at"] = time.time()
                        break
                await self._flush()
            count += 1
        return count
