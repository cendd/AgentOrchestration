"""Tests for graceful queue pause deployment."""
import pytest
import time
from src.common.deploy import GracefulQueueManager, QueuePauseError


class TestGracefulQueueManager:
    def test_pause_and_resume(self):
        mgr = GracefulQueueManager()
        assert mgr.pause() is True
        assert mgr.is_paused is True
        assert mgr.resume() is True
        assert mgr.is_paused is False

    def test_double_pause_returns_false(self):
        mgr = GracefulQueueManager()
        mgr.pause()
        assert mgr.pause() is False

    def test_resume_without_pause_returns_false(self):
        mgr = GracefulQueueManager()
        assert mgr.resume() is False

    def test_drain_callback_called(self):
        drain_called = [False]

        def drain(**kwargs):
            drain_called[0] = True

        mgr = GracefulQueueManager(drain_callback=drain)
        mgr.pause()
        assert drain_called[0] is True

    def test_enqueue_during_pause_tracked(self):
        mgr = GracefulQueueManager()
        mgr.pause()
        mgr.enqueue_during_pause(5)
        mgr.enqueue_during_pause(3)
        summary = mgr.state_summary()
        assert summary["queued_during_pause"] == 8

    def test_state_summary(self):
        mgr = GracefulQueueManager()
        mgr.pause(drain_timeout=60)
        summary = mgr.state_summary()
        assert summary["paused"] is True
        assert summary["drain_timeout"] == 60
        assert summary["paused_at"] is not None
