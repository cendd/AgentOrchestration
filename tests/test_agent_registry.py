"""Tests for agent registry with disabled-entry filtering."""
import pytest
from src.agent.registry import AgentRegistry, AgentStatus


class TestAgentRegistry:
    def setup_method(self):
        self.registry = AgentRegistry()

    def test_register(self):
        agent_id = self.registry.register("test-agent", "python")
        assert agent_id is not None
        agent = self.registry.get(agent_id)
        assert agent["name"] == "test-agent"
        assert agent["status"] == "idle"

    def test_list_active_excludes_disabled(self):
        a1 = self.registry.register("active1", "python")
        a2 = self.registry.register("disabled1", "python")
        self.registry.disable(a2)
        active = self.registry.list_active()
        ids = [a["id"] for a in active]
        assert a1 in ids
        assert a2 not in ids

    def test_disable_and_enable(self):
        a_id = self.registry.register("test", "python")
        assert self.registry.disable(a_id) is True
        assert self.registry.get(a_id)["status"] == "disabled"
        assert self.registry.enable(a_id) is True
        assert self.registry.get(a_id)["status"] == "idle"

    def test_cannot_start_disabled(self):
        a_id = self.registry.register("test", "python")
        self.registry.disable(a_id)
        with pytest.raises(ValueError, match="disabled"):
            self.registry.start(a_id)

    def test_list_with_status_filter(self):
        a1 = self.registry.register("a1", "python")
        a2 = self.registry.register("a2", "python")
        self.registry.start(a1)
        running = self.registry.list(status=AgentStatus.RUNNING)
        assert len(running) == 1
        assert running[0]["id"] == a1
