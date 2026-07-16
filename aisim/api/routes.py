"""REST routes - Agent / state / simulation control / LLM / Skill (see §三)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from aisim.api.state import hub

router = APIRouter(prefix="/api")


# ═══ Request models ═══


class CreateAgentRequest(BaseModel):
    name: str
    role: str  # ceo/cto/hr-director/senior-engineer/junior-engineer/designer
    department: str = "General"
    salary: int = 0
    personality: dict = {}
    report_to: str | None = None


class SimulationControlRequest(BaseModel):
    action: str  # play | pause | step | speed
    speed: float | None = None


class MeetingRequest(BaseModel):
    topic: str
    participants: list[str]  # list of agent_ids
    caller: str | None = None  # host agent_id (defaults to CEO)


# ═══ Health / state ═══


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "backend": hub.agent_manager.mode, "started": hub._started}


@router.get("/state")
async def state_snapshot() -> dict:
    return await hub.snapshot()


# ═══ Agent ═══


@router.get("/agents")
async def list_agents() -> list[dict]:
    return await hub.agent_manager.list()


@router.post("/agents")
async def create_agent(req: CreateAgentRequest) -> dict:
    return await hub.create_agent(
        name=req.name,
        role=req.role,
        department=req.department,
        salary=req.salary,
        personality=req.personality,
        report_to=req.report_to,
    )


@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str) -> dict:
    state = await hub.agent_manager.get(agent_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"agent not found: {agent_id}")
    return state


@router.delete("/agents/{agent_id}")
async def delete_agent(agent_id: str) -> dict:
    await hub.remove_agent(agent_id)
    return {"removed": agent_id}


# ═══ Simulation control ═══


@router.post("/simulation/control")
async def simulation_control(req: SimulationControlRequest) -> dict:
    if req.action == "play":
        await hub.clock.start()
    elif req.action == "pause":
        await hub.clock.stop()
    elif req.action == "step":
        await hub.clock.stop()  # pause before stepping to avoid conflicting with the clock tick
        await hub.step()
    elif req.action == "speed":
        if req.speed is None:
            raise HTTPException(status_code=400, detail="speed 需要提供 speed 值")
        hub.clock.set_speed(req.speed)
    else:
        raise HTTPException(status_code=400, detail=f"unknown action: {req.action}")
    return {
        "action": req.action,
        "speed": req.speed,
        "tick": hub.clock.tick,
        "running": hub.clock.running,
    }


# ═══ LLM gateway ═══


@router.get("/llm/config")
async def llm_config() -> dict:
    """Return the LLM routing config (does not expose the API Key)."""
    return {
        "provider": hub.config.llm.provider,
        "default_model": hub.config.llm.default_model,
        "routing": hub.config.llm.routing,
        "daily_budget": hub.config.llm.daily_budget,
        "usage_today": hub.llm_gateway.usage_today,
    }


# ═══ Skill pool ═══


@router.get("/skills")
async def list_skills() -> list[dict]:
    return await hub.skill_pool.list_dicts()


@router.get("/agents/{agent_id}/skills")
async def agent_skills(agent_id: str) -> list[dict]:
    """The Skills currently in effect for an Agent (inherited company/department/role/personal)."""
    state = await hub.agent_manager.get(agent_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"agent not found: {agent_id}")
    skills = await hub.skill_pool.get_effective_skills(
        agent_id, state["role"], state["department"]
    )
    return [hub.skill_pool.to_dict(s) for s in skills]


# ═══ Tasks ═══


@router.get("/tasks")
async def list_tasks() -> list[dict]:
    return await hub.task_manager.list_dicts()


# ═══ Meeting ═══


@router.post("/meetings")
async def create_meeting(req: MeetingRequest) -> dict:
    """Manually convene an LLM-hosted meeting and return the minutes."""
    caller = req.caller or hub.config.ceo.agent_id
    minutes = await hub.call_meeting(caller, req.topic, req.participants)
    return {"topic": req.topic, "participants": req.participants, "minutes": minutes[:1000]}
