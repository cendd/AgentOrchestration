"""Agent Registry module with disabled-entry filtering."""

import logging
from typing import Dict, List, Optional, Any
from enum import Enum
from uuid import uuid4

logger = logging.getLogger(__name__)


class AgentStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"
    DISABLED = "disabled"


class AgentRegistry:
    def __init__(self):
        self._agents: Dict[str, Dict] = {}

    def register(self, name: str, agent_type: str, config: Optional[Dict] = None, workspace: str = "default") -> str:
        agent_id = str(uuid4())
        self._agents[agent_id] = {
            "id": agent_id,
            "name": name,
            "type": agent_type,
            "config": config or {},
            "status": AgentStatus.IDLE.value,
            "workspace": workspace,
        }
        return agent_id

    def get(self, agent_id: str) -> Optional[Dict]:
        return self._agents.get(agent_id)

    def list(self, status: Optional[AgentStatus] = None, group: Optional[str] = None) -> List[Dict]:
        agents = list(self._agents.values())

        if status:
            agents = [a for a in agents if a.get("status") == status.value]

        if group:
            agents = [a for a in agents if a.get("group") == group]

        return agents

    def list_active(self) -> List[Dict]:
        """List only active (non-disabled) agents — avoids leaking disabled entries."""
        return [a for a in self._agents.values() if a.get("status") != AgentStatus.DISABLED.value]

    def delete(self, agent_id: str) -> bool:
        if agent_id not in self._agents:
            return False
        del self._agents[agent_id]
        return True

    def disable(self, agent_id: str) -> bool:
        agent = self._agents.get(agent_id)
        if not agent:
            return False
        agent["status"] = AgentStatus.DISABLED.value
        logger.info("Disabled agent %s", agent_id)
        return True

    def enable(self, agent_id: str) -> bool:
        agent = self._agents.get(agent_id)
        if not agent:
            return False
        if agent.get("status") == AgentStatus.DISABLED.value:
            agent["status"] = AgentStatus.IDLE.value
            logger.info("Enabled agent %s", agent_id)
        return True

    def start(self, agent_id: str) -> bool:
        agent = self._agents.get(agent_id)
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")
        if agent.get("status") == AgentStatus.DISABLED.value:
            raise ValueError(f"Cannot start disabled agent {agent_id}")
        agent["status"] = AgentStatus.RUNNING.value
        return True

    def stop(self, agent_id: str) -> bool:
        agent = self._agents.get(agent_id)
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")
        agent["status"] = AgentStatus.STOPPED.value
        return True

    def get_logs(self, agent_id: str, lines: int = 100) -> Optional[List[str]]:
        agent = self._agents.get(agent_id)
        if not agent:
            return None
        return agent.get("logs", [])[-lines:]
