"""Deployment utilities with graceful queue pause for schema migrations."""

import time
import logging
from typing import Callable, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class QueuePauseError(RuntimeError):
    """Raised when queue pause/unpause operations fail."""


@dataclass
class QueueState:
    paused: bool = False
    drain_timeout: int = 30
    paused_at: Optional[float] = None
    queued_during_pause: int = 0


class GracefulQueueManager:
    """Manages graceful queue pause before schema changes."""

    def __init__(self, drain_callback: Optional[Callable] = None):
        self._state = QueueState()
        self._drain_callback = drain_callback

    def pause(self, drain_timeout: int = 30) -> bool:
        """Pause the queue gracefully, waiting for in-flight tasks to drain."""
        if self._state.paused:
            logger.warning("Queue is already paused")
            return False

        self._state.paused = True
        self._state.paused_at = time.time()
        self._state.drain_timeout = drain_timeout

        # Drain in-flight tasks
        if self._drain_callback:
            try:
                self._drain_callback(timeout=drain_timeout)
            except Exception as e:
                self._state.paused = False
                raise QueuePauseError(f"Failed to drain queue: {e}") from e

        logger.info("Queue paused gracefully (timeout=%ds)", drain_timeout)
        return True

    def resume(self) -> bool:
        """Resume the queue after schema changes."""
        if not self._state.paused:
            logger.warning("Queue is not paused")
            return False

        self._state.paused = False
        duration = time.time() - (self._state.paused_at or time.time())
        queued = self._state.queued_during_pause

        logger.info("Queue resumed after %.1fs (%d tasks queued during pause)", duration, queued)
        self._state.paused_at = None
        self._state.queued_during_pause = 0
        return True

    @property
    def is_paused(self) -> bool:
        return self._state.paused

    def enqueue_during_pause(self, count: int = 1) -> None:
        if self._state.paused:
            self._state.queued_during_pause += count

    def state_summary(self) -> dict:
        return {
            "paused": self._state.paused,
            "paused_at": self._state.paused_at,
            "drain_timeout": self._state.drain_timeout,
            "queued_during_pause": self._state.queued_during_pause,
        }


def pause_queue_before_schema_change(queue_mgr: GracefulQueueManager, schema_change_fn: Callable) -> bool:
    """Context manager pattern: pause queue -> apply schema -> resume queue."""
    try:
        queue_mgr.pause()
        schema_change_fn()
        queue_mgr.resume()
        return True
    except Exception as e:
        logger.error("Schema change failed during queue pause: %s", e)
        try:
            queue_mgr.resume()
        except Exception:
            pass
        raise
