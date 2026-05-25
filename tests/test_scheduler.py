import pytest
import time
from src.orchestrator.scheduler import TaskScheduler, RetentionPolicy, PreconditionError, DEFAULT_RETENTION_WINDOW


class TestRetentionPolicy:
    def test_within_window(self):
        policy = RetentionPolicy(3600)
        assert policy.is_within_window(time.time() - 10)

    def test_outside_window(self):
        policy = RetentionPolicy(60)
        assert not policy.is_within_window(time.time() - 120)

    def test_filter_drops_stale(self):
        policy = RetentionPolicy(60)
        fresh = {"id": "a", "enqueued_at": time.time() - 10}
        stale = {"id": "b", "enqueued_at": time.time() - 120}
        result = policy.filter_within_window([fresh, stale])
        assert len(result) == 1
        assert result[0]["id"] == "a"

    def test_invalid_window(self):
        with pytest.raises(ValueError):
            RetentionPolicy(10)


class TestTaskScheduler:
    def setup_method(self):
        self.scheduler = TaskScheduler()

    def test_enqueue_task(self):
        task_id = self.scheduler.enqueue({"type": "test", "payload": {}})
        assert task_id is not None

    def test_dequeue_task(self):
        self.scheduler.enqueue({"type": "test", "payload": {"data": 1}})
        import asyncio
        task = asyncio.run(self.scheduler.dequeue())
        assert task is not None
        assert task["type"] == "test"

    def test_enqueue_multiple_priorities(self):
        self.scheduler.enqueue({"type": "low"}, priority=1)
        self.scheduler.enqueue({"type": "high"}, priority=10)
        import asyncio
        task = asyncio.run(self.scheduler.dequeue())
        assert task["type"] == "high"

    def test_complete_task(self):
        self.scheduler.enqueue({"type": "test"})
        import asyncio
        task = asyncio.run(self.scheduler.dequeue())
        assert self.scheduler.complete(task["id"])

    def test_fail_task_with_retry(self):
        self.scheduler.enqueue({"type": "test"})
        import asyncio
        task = asyncio.run(self.scheduler.dequeue())
        assert self.scheduler.fail(task["id"])
        assert len(self.scheduler._in_flight) == 0

    def test_catchup_rejects_stale(self):
        sched = TaskScheduler(retention_window=60)
        stale_task = {"type": "recover", "enqueued_at": time.time() - 300}
        sched._catchup_mode = True
        with pytest.raises(PreconditionError):
            sched.enqueue(stale_task)

    def test_catchup_accepts_fresh(self):
        sched = TaskScheduler(retention_window=3600)
        fresh_task = {"type": "recover", "enqueued_at": time.time() - 10}
        sched._catchup_mode = True
        task_id = sched.enqueue(fresh_task)
        assert task_id is not None

    def test_enter_catchup_drops_stale(self):
        sched = TaskScheduler(retention_window=60)
        sched._queues["default"] = type("MockPQ", (), {
            "_queue": [], "_counter": 0,
            "push": lambda self, i, p: self._queue.append(i),
            "pop": lambda self: self._queue.pop(0) if self._queue else None,
            "__len__": lambda self: len(self._queue)
        })()
        sched._queues["default"]._queue = [
            {"id": "stale", "enqueued_at": time.time() - 300}
        ]
        sched._queues["default"]._counter = 1
        surviving = sched.enter_catchup_mode()
        assert sched._catchup_mode
        assert sched.catchup_backlog() == 0

    def test_status_includes_catchup(self):
        status = self.scheduler.status()
        assert "catchup_mode" in status
        assert "retention_window" in status
        assert status["retention_window"] == DEFAULT_RETENTION_WINDOW

    def test_audit_log_bounded(self):
        self.scheduler.enqueue({"type": "auditable"})
        import asyncio
        task = asyncio.run(self.scheduler.dequeue())
        self.scheduler.complete(task["id"])
        logs = self.scheduler.get_audit_log()
        assert len(logs) == 1
        assert logs[0]["type"] == "auditable"
        # No private runtime data
        assert "payload" not in logs[0]
