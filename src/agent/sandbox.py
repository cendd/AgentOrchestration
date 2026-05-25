"""Sandbox environment for agent execution with path verification."""
from __future__ import annotations
import os
import shutil
import tempfile
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from pathlib import Path

logger = logging.getLogger(__name__)


class ResourceLimitError(ValueError):
    """Raised when ResourceLimits contain invalid (zero/negative) values."""


class PathTraversalError(ValueError):
    """Raised when a path tries to escape the sandbox directory."""


@dataclass
class ResourceLimits:
    """Resource limits for sandbox execution."""
    cpu: float = 1.0
    memory_mb: int = 512
    disk_mb: int = 1024
    timeout_seconds: int = 300

    def __post_init__(self):
        errors = []
        if self.cpu <= 0:
            errors.append(f"cpu must be positive, got {self.cpu}")
        if self.memory_mb <= 0:
            errors.append(f"memory_mb must be positive, got {self.memory_mb}")
        if self.disk_mb <= 0:
            errors.append(f"disk_mb must be positive, got {self.disk_mb}")
        if self.timeout_seconds <= 0:
            errors.append(f"timeout_seconds must be positive, got {self.timeout_seconds}")
        if errors:
            raise ResourceLimitError("; ".join(errors))

    def to_dict(self) -> Dict:
        return {
            "cpu": self.cpu,
            "memory_mb": self.memory_mb,
            "disk_mb": self.disk_mb,
            "timeout_seconds": self.timeout_seconds,
        }


class AgentSandbox:
    def __init__(self, sandbox_dir: Optional[str] = None, limits: Optional[ResourceLimits] = None):
        self._limits = limits or ResourceLimits()
        self._sandbox_dir = os.path.abspath(sandbox_dir or tempfile.mkdtemp(prefix="agent_sandbox_"))
        self._tracked_paths: Set[str] = set()
        self._closed = False
        os.makedirs(self._sandbox_dir, exist_ok=True)

    @property
    def limits(self) -> ResourceLimits:
        return self._limits

    @property
    def sandbox_dir(self) -> str:
        return self._sandbox_dir

    def _verify_within_sandbox(self, abs_path: str) -> None:
        """Verify the resolved path is within the sandbox directory (prevents path traversal)."""
        resolved = os.path.realpath(abs_path)
        sandbox_real = os.path.realpath(self._sandbox_dir)
        if not resolved.startswith(sandbox_real + os.sep) and resolved != sandbox_real:
            raise PathTraversalError(
                f"Path '{abs_path}' resolves to '{resolved}' which is outside sandbox '{sandbox_real}'"
            )

    def track_path(self, path: str) -> None:
        abs_path = os.path.abspath(path)
        self._verify_within_sandbox(abs_path)
        self._tracked_paths.add(abs_path)

    def get_path(self, relative_path: str) -> Optional[str]:
        """Resolve a tracked path, verifying it exists and is within the sandbox."""
        abs_path = os.path.join(self._sandbox_dir, relative_path)
        abs_path = os.path.abspath(abs_path)
        self._verify_within_sandbox(abs_path)
        if abs_path not in self._tracked_paths:
            logger.warning("Path %s is not tracked", abs_path)
            return None
        if not os.path.exists(abs_path):
            logger.warning("Tracked path %s no longer exists", abs_path)
            return None
        return abs_path

    def write_file(self, relative_path: str, content: str) -> str:
        full_path = os.path.join(self._sandbox_dir, relative_path)
        full_path = os.path.abspath(full_path)
        self._verify_within_sandbox(full_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w") as f:
            f.write(content)
        self.track_path(full_path)
        return full_path

    def read_file(self, relative_path: str) -> Optional[str]:
        path = self.get_path(relative_path)
        if not path:
            return None
        with open(path) as r:
            return r.read()

    def cleanup(self) -> None:
        if self._closed:
            return
        self._closed = True
        if os.path.exists(self._sandbox_dir):
            shutil.rmtree(self._sandbox_dir, ignore_errors=True)
            logger.info("Cleaned up sandbox %s", self._sandbox_dir)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
