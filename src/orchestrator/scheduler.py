"""Task Scheduler — Priority-based task queuing and dispatch."""

import asyncio
import heapq
import time
import logging
from typing import Any, Dict, Optional, List
from uuid import uuid4

logger = logging.getLogger(__name__)

# Default retention window (seconds) — tasks older than this are dropped on catch-up
DEFAULT_RETENTION_WINDOW = 86400  # 24 hours


class RetentionPolicy:
    """Enforces catch-up retention window for scheduler recovery."""

    def __init__(self, retention_window: int = DEFAULT_RETENTION_WINDOW):
        if retention_window < 60:
            raise ValueError("retention_window must be >= 60 seconds")
        self.retention_window = retention_window

    def is_within_window(self, enqueued_at: float) -> bool:
        """Check if a task is within the retention window."""
        return (time.time() - enqueued_at) <= self.retention_window

    def filter_within_window(self, tasks: List[Dict]) -> List[Dict]:
        """Filter tasks, keeping only those within the retention window."""
        results = []
        dropped = 0
        for task in tasks:
            enqueued = task.get("enqueued_at", 0)
            if self.is_within_window(enqueued):
                results.append(task)
            else:
                dropped += 1
                logger.warning(
                    "Dropping stale task %s (enqueued %.1fs ago, window=%ds)",
                    task.get("id", "?"), time.time() - enqueued, self.retention_window,
                )
        if dropped:
            logger.info("Catch-up: dropped %d stale tasks, kept %d", dropped, len(results))
        return results

    def __repr__(self) -> str:
        return f"RetentionPolicy(window={self.retention_window}s)"


class PreconditionError(Exception):
    """Raised when a scheduler state transition violates preconditions."""


class PriorityQueue:
    def __init__(self):
        self._queue = []
        self._counter = 0

    def push(self, item: Any, priority: int = 0) -> None:
        heapq.heappush(self._queue, (-priority, self._counter, item))
        self._counter += 1

    def pop(self) -> Optional[Any]:
        if self._queue:
            return heapq.heappop(self._queue)[2]
        return None

    def peek(self) -> Optional[Any]:
        if self._queue:
            return self._queue[0][2]
        return None

    def __len__(self) -> int:
        return len(self._queue)


class TaskScheduler:
    def __init__(self, retention_window: int = DEFAULT_RETENTION_WINDOW):
        self._queues: Dict[str, PriorityQueue] = {}
        self._scheduled: Dict[str, float] = {}
        self._in_flight: Dict[str, Dict] = {}
        self._completed: Dict[str, Dict] = {}
        self._max_retries = 3
        self._retention = RetentionPolicy(retention_window)
        self._catchup_mode = False

    def enqueue(self, task: Dict, queue: str = "default", priority: int = 0) -> str:
        """Enqueue a task with optional catch-up retention check."""
        if self._catchup_mode and "enqueued_at" in task:
            enqueued = task.get("enqueued_at", time.time())
            if not self._retention.is_within_window(enqueued):
                raise PreconditionError(
                    f"Catch-up rejected task outside retention window "
                    f"(enqueued {time.time() - enqueued:.0f}s ago, window={self._retention.retention_window}s)"
                )

        task_id = str(uuid4())
        task["id"] = task_id
        task["enqueued_at"] = task.get("enqueued_at", time.time())
        task["retries"] = 0

        if queue not in self._queues:
            self._queues[queue] = PriorityQueue()
        self._queues[queue].push(task, priority)

        return task_id

    async def dequeue(self, queue: str = "default", timeout: float = 5.0) -> Optional[Dict]:
        if queue not in self._queues or len(self._queues[queue]) == 0:
            await asyncio.sleep(timeout / 10)
            if queue not in self._queues or len(self._queues[queue]) == 0:
                return None

        task = self._queues[queue].pop()
        if task:
            self._in_flight[task["id"]] = task
            task["dequeued_at"] = time.time()
        return task

    def complete(self, task_id: str) -> bool:
        if task_id not in self._in_flight:
            return False
        task = self._in_flight.pop(task_id)
        task["completed_at"] = time.time()
        self._completed[task_id] = task
        return True

    def fail(self, task_id: str) -> bool:
        if task_id not in self._in_flight:
            return False
        task = self._in_flight.pop(task_id)
        task["retries"] += 1

        if task["retries"] < self._max_retries:
            task["enqueued_at"] = time.time()
            self._queues["default"].push(task, 0)
        return True

    def enter_catchup_mode(self) -> int:
        """Enter catch-up mode. Returns count of tasks surviving retention check."""
        self._catchup_mode = True
        total = 0
        dropped = 0
        for queue_name, pq in self._queues.items():
            surviving = []
            while len(pq) > 0:
                total += 1
                task = pq.pop()
                if self._retention.is_within_window(task.get("enqueued_at", 0)):
                    surviving.append(task)
                else:
                    dropped += 1
                    logger.warning(
                        "Catch-up drop task %s — outside retention window",
                        task.get("id", "?"),
                    )
            for task in surviving:
                pq.push(task, 0 if "retries" not in task else task["retries"])
        if dropped:
            logger.info("Catch-up mode: dropped %d/%d stale tasks", dropped, total)
        return total - dropped

    def exit_catchup_mode(self) -> None:
        self._catchup_mode = False

    def catchup_backlog(self) -> int:
        """Return number of pending tasks (catch-up safe)."""
        total = 0
        for pq in self._queues.values():
            total += len(pq)
        return total

    def status(self) -> Dict:
        return {
            "queues": {k: len(v) for k, v in self._queues.items()},
            "in_flight": len(self._in_flight),
            "completed": len(self._completed),
            "completed_ids": list(self._completed.keys()),
            "catchup_mode": self._catchup_mode,
            "retention_window": self._retention.retention_window,
        }

    def get_audit_log(self) -> List[Dict]:
        """Return bounded audit metadata without exposing private runtime data."""
        return [
            {"id": tid, "completed_at": task.get("completed_at", 0),
             "enqueued_at": task.get("enqueued_at", 0),
             "type": task.get("type", "?"), "retries": task.get("retries", 0)}
            for tid, task in list(self._completed.items())[-50:]
        ]
