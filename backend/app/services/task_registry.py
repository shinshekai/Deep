"""TaskRegistry — track asyncio.create_task calls for lifecycle observability."""

import asyncio
import logging
from typing import Any, Coroutine

logger = logging.getLogger(__name__)


class TaskRegistry:
    def __init__(self, name: str = "default"):
        self.name = name
        self._tasks: set[asyncio.Task] = set()
        self._failed_count = 0

    def spawn(self, coro: Coroutine[Any, Any, Any], *, name: str | None = None) -> asyncio.Task:
        task = asyncio.create_task(coro, name=name)
        self._tasks.add(task)
        task.add_done_callback(self._on_done)
        return task

    def _on_done(self, task: asyncio.Task) -> None:
        self._tasks.discard(task)
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            self._failed_count += 1
            logger.error(
                f"task_registry[{self.name}] task_failed: {task.get_name()} exc={exc!r}",
                exc_info=exc,
            )

    @property
    def pending_count(self) -> int:
        return len(self._tasks)

    @property
    def failed_count(self) -> int:
        return self._failed_count

    async def cancel_all(self, timeout: float = 5.0) -> int:
        if not self._tasks:
            return 0
        for t in self._tasks:
            t.cancel()
        cancelled = 0
        try:
            await asyncio.wait_for(
                asyncio.gather(*self._tasks, return_exceptions=True),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            logger.warning(f"task_registry[{self.name}] cancel_all timed out after {timeout}s")
        cancelled = sum(1 for t in self._tasks if t.cancelled() or t.done())
        return cancelled


_global_registry = TaskRegistry(name="global")
