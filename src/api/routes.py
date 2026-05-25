"""API route definitions with workspace-aware agent listing."""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Optional

from src.agent import AgentRegistry, AgentStatus

router = APIRouter()
registry = AgentRegistry()


@router.get("/agents")
async def list_agents(
    status: Optional[str] = None,
    group: Optional[str] = None,
    workspace: Optional[str] = Query(None, description="Filter agents by workspace ID"),
):
    status_filter = AgentStatus(status) if status else None
    agents = registry.list(status=status_filter, group=group)

    if workspace:
        agents = [a for a in agents if a.get("workspace") == workspace]

    return {"agents": agents, "workspace_filter": workspace}


@router.get("/agents/workspaces")
async def list_workspaces():
    """List all distinct workspaces from registered agents."""
    all_agents = registry.list()
    workspaces = sorted(set(
        a.get("workspace", "default") for a in all_agents
    ))
    return {"workspaces": workspaces}


@router.post("/agents")
async def register_agent(name: str, agent_type: str, config: Optional[Dict] = None, workspace: Optional[str] = "default"):
    agent_id = registry.register(name, agent_type, config, workspace=workspace)
    return {"agent_id": agent_id, "status": "registered", "workspace": workspace}


@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str):
    agent = registry.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.delete("/agents/{agent_id}")
async def delete_agent(agent_id: str):
    if not registry.delete(agent_id):
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"status": "deleted"}


@router.post("/agents/{agent_id}/start")
async def start_agent(agent_id: str):
    try:
        result = registry.start(agent_id)
        return {"status": "started", "agent_id": agent_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/agents/{agent_id}/stop")
async def stop_agent(agent_id: str):
    try:
        result = registry.stop(agent_id)
        return {"status": "stopped", "agent_id": agent_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/agents/{agent_id}/logs")
async def get_agent_logs(agent_id: str, lines: int = 100):
    logs = registry.get_logs(agent_id, lines)
    if logs is None:
        raise HTTPException(status_code=404, detail="Agent not found or no logs available")
    return {"agent_id": agent_id, "logs": logs}
