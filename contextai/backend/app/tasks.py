"""Background task queue for non-blocking file indexing.

Uses asyncio.Queue with a single worker coroutine. Tasks are fire-and-forget
with status tracking via an in-memory dict keyed by task ID.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Coroutine

logger = logging.getLogger("contextai.tasks")


class TaskQueue:
    """Single-worker async task queue with status tracking."""

    def __init__(self):
        self._queue: asyncio.Queue = asyncio.Queue()
        self._results: dict[str, dict] = {}
        self._worker_task: asyncio.Task | None = None

    async def start(self):
        """Start the background worker. Call once at app startup."""
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._worker())
            logger.info("Task queue worker started")

    async def stop(self):
        """Cancel the worker gracefully."""
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            logger.info("Task queue worker stopped")

    async def _worker(self):
        """Process tasks sequentially from the queue."""
        while True:
            task_id, coro = await self._queue.get()
            self._results[task_id]["status"] = "running"
            self._results[task_id]["started_at"] = datetime.now(timezone.utc).isoformat()
            try:
                result = await coro
                self._results[task_id].update({
                    "status": "done",
                    "result": result,
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                })
                logger.info("task_completed", extra={"task_id": task_id})
            except Exception as e:
                self._results[task_id].update({
                    "status": "error",
                    "error": str(e),
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                })
                logger.error(f"Task {task_id} failed: {e}")
            finally:
                self._queue.task_done()

    async def enqueue(self, task_id: str, coro: Coroutine) -> str:
        """Add a coroutine to the queue. Returns the task ID."""
        self._results[task_id] = {
            "status": "pending",
            "enqueued_at": datetime.now(timezone.utc).isoformat(),
        }
        await self._queue.put((task_id, coro))
        logger.info(f"Task enqueued: {task_id}")
        return task_id

    def get_status(self, task_id: str) -> dict | None:
        """Get the current status of a task."""
        return self._results.get(task_id)

    def list_tasks(self, limit: int = 20) -> list[dict]:
        """List recent tasks with their statuses."""
        items = [
            {"task_id": tid, **info}
            for tid, info in self._results.items()
        ]
        return sorted(items, key=lambda x: x.get("enqueued_at", ""), reverse=True)[:limit]

    @property
    def pending_count(self) -> int:
        return self._queue.qsize()


# Global singleton
task_queue = TaskQueue()
