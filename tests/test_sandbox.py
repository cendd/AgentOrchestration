"""Tests for sandbox with ResourceLimits validation."""
import pytest
from src.agent.sandbox import AgentSandbox, ResourceLimits, ResourceLimitError


class TestResourceLimits:
    def test_default_limits(self):
        limits = ResourceLimits()
        assert limits.cpu == 1.0
        assert limits.memory_mb == 512

    def test_positive_valid(self):
        limits = ResourceLimits(cpu=2.0, memory_mb=1024)
        assert limits.cpu == 2.0

    def test_zero_cpu_raises(self):
        with pytest.raises(ResourceLimitError, match="cpu must be positive"):
            ResourceLimits(cpu=0)

    def test_negative_memory_raises(self):
        with pytest.raises(ResourceLimitError, match="memory_mb must be positive"):
            ResourceLimits(memory_mb=-1)

    def test_zero_disk_raises(self):
        with pytest.raises(ResourceLimitError, match="disk_mb must be positive"):
            ResourceLimits(disk_mb=0)

    def test_zero_timeout_raises(self):
        with pytest.raises(ResourceLimitError, match="timeout_seconds must be positive"):
            ResourceLimits(timeout_seconds=0)

    def test_all_invalid_reports_all_errors(self):
        with pytest.raises(ResourceLimitError) as exc:
            ResourceLimits(cpu=0, memory_mb=-1, disk_mb=0, timeout_seconds=0)
        msg = str(exc.value)
        assert "cpu" in msg and "memory_mb" in msg and "disk_mb" in msg and "timeout_seconds" in msg


class TestAgentSandbox:
    def test_create_sandbox(self):
        with AgentSandbox(limits=ResourceLimits()) as sb:
            assert sb.sandbox_dir is not None
            assert sb.limits.cpu == 1.0

    def test_write_and_read_file(self):
        with AgentSandbox() as sb:
            sb.write_file("test.txt", "hello")
            assert sb.read_file("test.txt") == "hello"

    def test_get_untracked_path_returns_none(self):
        with AgentSandbox() as sb:
            result = sb.get_path("nonexistent.txt")
            assert result is None

    def test_tracked_path_access(self):
        with AgentSandbox() as sb:
            path = sb.write_file("data.txt", "content")
            result = sb.get_path("data.txt")
            assert result is not None
            assert os.path.exists(result)

    def test_resource_limit_injected(self):
        limits = ResourceLimits(cpu=4.0, memory_mb=2048)
        with AgentSandbox(limits=limits) as sb:
            assert sb.limits.cpu == 4.0
            assert sb.limits.memory_mb == 2048
