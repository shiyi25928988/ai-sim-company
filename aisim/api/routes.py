"""REST routes - Agent / state / simulation control / LLM / Skill (see §三)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from aisim.api.state import hub

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


def _parse_skill_content(text: str) -> dict:
    """Parse a skill definition from JSON / YAML / Markdown-with-frontmatter.

    Markdown frontmatter (--- ... ---) holds the metadata; the body becomes prompt_injection.
    """
    import json
    import re

    import yaml

    text = (text or "").strip()
    if not text:
        return {}
    if text.startswith("---"):
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.DOTALL)
        if m:
            meta = yaml.safe_load(m.group(1)) or {}
            if not isinstance(meta, dict):
                meta = {}
            body = m.group(2).strip()
            if body:
                meta["prompt_injection"] = body
            return meta
    try:
        d = json.loads(text)
        return d if isinstance(d, dict) else {}
    except json.JSONDecodeError:
        pass
    try:
        d = yaml.safe_load(text)
        return d if isinstance(d, dict) else {}
    except yaml.YAMLError:
        pass
    return {}


# ═══ Request models ═══


class CreateAgentRequest(BaseModel):
    name: str
    role: str  # e.g. ceo/hr-director/senior-engineer/junior-engineer/designer/product-manager/marketer/data-analyst/qa-engineer
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
    agents = await hub.agent_manager.list()
    for a in agents:
        a["recent"] = hub.agent_runner.recent_memory(a.get("agent_id", ""), 5)
    return agents


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
    state["recent"] = hub.agent_runner.recent_memory(agent_id, 5)
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
    import shutil

    claude_path = shutil.which("claude")
    return {
        "provider": hub.config.llm.provider,
        "default_model": hub.config.llm.default_model,
        "routing": hub.config.llm.routing,
        "daily_budget": hub.config.llm.daily_budget,
        "usage_today": hub.llm_gateway.usage_today,
        "claude_code": {
            "installed": claude_path is not None,
            "enabled": hub.config.llm.claude_code_enabled,
            "path": claude_path,
        },
    }


class ClaudeCodeConfigRequest(BaseModel):
    claude_code_enabled: bool


@router.post("/llm/config")
async def update_llm_config(req: ClaudeCodeConfigRequest) -> dict:
    """Update the Claude Code enable flag (writes company.yaml + updates config in place)."""
    import yaml
    from pathlib import Path

    cfg_path = Path("config/company.yaml")
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    existing: dict = {}
    if cfg_path.exists():
        existing = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    existing.setdefault("llm", {})["claude_code_enabled"] = req.claude_code_enabled
    cfg_path.write_text(
        yaml.safe_dump(existing, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )
    hub.config.llm.claude_code_enabled = req.claude_code_enabled
    return {"claude_code_enabled": req.claude_code_enabled}


# ═══ Skill pool ═══


@router.get("/skills")
async def list_skills() -> list[dict]:
    return await hub.skill_pool.list_dicts()


class SkillRequest(BaseModel):
    name: str
    description: str = ""
    prompt_injection: str = ""  # injected into the agent's system prompt
    category: str = "technical"  # technical / management / creative / operations
    level: str = "company"  # company / department / role / personal
    scope: list[str] = []  # who inherits: department name / role / agent_id (by level)


@router.post("/skills")
async def create_skill(req: SkillRequest) -> dict:
    """Upload a user skill (published immediately, inheritable by agents)."""
    return await hub.create_skill(
        name=req.name,
        description=req.description,
        prompt_injection=req.prompt_injection,
        category=req.category,
        level=req.level,
        scope=req.scope,
    )


@router.delete("/skills/{skill_id}")
async def delete_skill(skill_id: str) -> dict:
    return await hub.delete_skill(skill_id)


class SkillUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    prompt_injection: str | None = None
    category: str | None = None
    level: str | None = None
    scope: list[str] | None = None


@router.put("/skills/{skill_id}")
async def update_skill(skill_id: str, req: SkillUpdateRequest) -> dict:
    """Update editable fields on a skill."""
    s = await hub.update_skill(skill_id, **req.model_dump(exclude_none=True))
    if s is None:
        raise HTTPException(status_code=404, detail=f"skill not found: {skill_id}")
    return s


@router.post("/skills/upload")
async def upload_skill(file: UploadFile = File(...)) -> dict:
    """Upload a skill package (.zip).

    SKILL.md (or skill.md / skill.json / skill.yaml) is the skill definition: frontmatter is
    metadata, body is prompt_injection. prompt.md (if present) overrides prompt_injection.
    .py files are saved to workspace_dir/skills/{name}/ so agents can read/run them.
    """
    import io
    import json
    import re
    import zipfile
    from pathlib import Path

    import yaml

    data = await file.read()
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="not a valid zip file")
    meta: dict = {}
    prompt: str | None = None
    py_files: list[tuple[str, bytes]] = []
    md_files: list[tuple[str, bytes]] = []
    with zf:
        for n in zf.namelist():
            base = n.split("/")[-1]
            if not base:
                continue
            low = base.lower()
            if low == "skill.md":
                meta = _parse_skill_content(zf.read(n).decode("utf-8")) or meta
            elif low == "skill.json":
                meta = json.loads(zf.read(n).decode("utf-8"))
            elif low in ("skill.yaml", "skill.yml"):
                meta = yaml.safe_load(zf.read(n).decode("utf-8")) or {}
            elif low == "prompt.md":
                prompt = zf.read(n).decode("utf-8")
            elif low.endswith(".py"):
                py_files.append((n, zf.read(n)))
            elif low.endswith(".md"):
                md_files.append((n, zf.read(n)))
    if not meta:
        raise HTTPException(status_code=400, detail="SKILL.md / skill.json / skill.yaml not found in zip")
    if prompt:
        meta["prompt_injection"] = prompt

    created = await hub.create_skill(
        name=meta.get("name", "Unnamed"),
        description=meta.get("description", ""),
        prompt_injection=meta.get("prompt_injection", ""),
        category=meta.get("category", "technical"),
        level=meta.get("level", "company"),
        scope=meta.get("scope", []) or [],
    )

    if py_files or md_files:
        slug = re.sub(r"[^a-z0-9]+", "-", (meta.get("name") or "skill").lower()).strip("-")[:24] or "skill"
        base_dir = (Path(hub.config.company.workspace_dir) / "skills" / slug).resolve()

        def _save(files: list[tuple[str, bytes]]) -> list[str]:
            saved: list[str] = []
            for path, content in files:
                fname = Path(path).name
                target = (base_dir / fname).resolve()
                if str(target).startswith(str(base_dir)):
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(content)
                    saved.append(fname)
            return saved

        created["python_files"] = _save(py_files)
        created["markdown_files"] = _save(md_files)

    return created


class SkillImportRequest(BaseModel):
    content: str  # JSON or YAML text


@router.post("/skills/import")
async def import_skill(req: SkillImportRequest) -> dict:
    """Import a skill from pasted JSON / YAML / Markdown (frontmatter)."""
    meta = _parse_skill_content(req.content)
    if not meta:
        raise HTTPException(status_code=400, detail="no skill definition found (JSON/YAML/Markdown)")
    return await hub.create_skill(
        name=meta.get("name", "Unnamed"),
        description=meta.get("description", ""),
        prompt_injection=meta.get("prompt_injection", ""),
        category=meta.get("category", "technical"),
        level=meta.get("level", "company"),
        scope=meta.get("scope", []) or [],
    )


class SkillInstallUrlRequest(BaseModel):
    url: str


@router.post("/skills/install-url")
async def install_skill_from_url(req: SkillInstallUrlRequest) -> dict:
    """Download a skill from a URL (.json/.yaml/.zip) and install it."""
    import io
    import json
    import zipfile

    import httpx
    import yaml

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            r = await client.get(req.url)
            r.raise_for_status()
            data = r.content
    except httpx.HTTPError as e:
        raise HTTPException(status_code=400, detail=f"download failed: {e}")
    meta: dict = {}
    url_lower = req.url.lower()
    if zipfile.is_zipfile(io.BytesIO(data)) or url_lower.endswith(".zip"):
        try:
            zf = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile:
            raise HTTPException(status_code=400, detail="not a valid zip")
        prompt: str | None = None
        with zf:
            for n in zf.namelist():
                base = n.split("/")[-1]
                if base == "skill.json":
                    meta = json.loads(zf.read(n).decode("utf-8"))
                elif base in ("skill.yaml", "skill.yml"):
                    meta = yaml.safe_load(zf.read(n).decode("utf-8")) or {}
                elif base == "skill.md":
                    meta = _parse_skill_content(zf.read(n).decode("utf-8"))
                elif base == "prompt.md":
                    prompt = zf.read(n).decode("utf-8")
        if prompt:
            meta["prompt_injection"] = prompt
    else:
        text = data.decode("utf-8", errors="replace")
        meta = _parse_skill_content(text)
        if not meta:
            raise HTTPException(status_code=400, detail="content is not valid JSON/YAML/Markdown/zip")
    if not isinstance(meta, dict) or not meta:
        raise HTTPException(status_code=400, detail="no skill definition found")
    return await hub.create_skill(
        name=meta.get("name", "Unnamed"),
        description=meta.get("description", ""),
        prompt_injection=meta.get("prompt_injection", ""),
        category=meta.get("category", "technical"),
        level=meta.get("level", "company"),
        scope=meta.get("scope", []) or [],
    )


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


# ═══ Config (business setup) ═══


class ConfigRequest(BaseModel):
    name: str
    business_description: str = ""
    initial_capital: int = 500_000
    monthly_budget: int = 0  # 0 = unlimited
    workspace_dir: str = "data/workspace"


@router.get("/config")
async def get_config() -> dict:
    """Current business config (does not expose the LLM API key)."""
    c = hub.config.company
    return {
        "name": c.name,
        "business_description": c.business_description,
        "initial_capital": c.initial_capital,
        "monthly_budget": c.monthly_budget,
        "workspace_dir": c.workspace_dir,
    }


@router.post("/config")
async def update_config(req: ConfigRequest) -> dict:
    """Update business config (writes config/company.yaml, merged) and hot-reload the Hub."""
    import yaml
    from pathlib import Path

    from aisim.shared.config import load_config

    cfg_path = Path("config/company.yaml")
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    existing: dict = {}
    if cfg_path.exists():
        existing = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    existing["company"] = {
        "name": req.name,
        "business_description": req.business_description,
        "initial_capital": req.initial_capital,
        "monthly_budget": req.monthly_budget,
        "workspace_dir": req.workspace_dir,
    }
    cfg_path.write_text(
        yaml.safe_dump(existing, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )
    new_config = load_config(str(cfg_path))
    return await hub.apply_config(new_config)


# ═══ Workspace files ═══


@router.get("/files")
async def list_files(path: str = "", scope: str = "shared") -> list[dict]:
    return await hub.list_workspace(path, scope)


@router.get("/files/content")
async def read_file(path: str, scope: str = "shared") -> dict:
    content = await hub.read_workspace(path, scope)
    if content is None:
        raise HTTPException(status_code=404, detail=f"file not found: {path}")
    return {"path": path, "content": content}


# ═══ MCP (Model Context Protocol) ═══


class McpServerRequest(BaseModel):
    name: str
    transport: str = "stdio"  # stdio | sse
    command: str | None = None
    args: list[str] = []
    url: str | None = None
    env: dict | None = None


@router.get("/mcp")
async def list_mcp() -> dict:
    return {"servers": hub.mcp_manager.servers_status()}


@router.post("/mcp")
async def add_mcp_server(req: McpServerRequest) -> dict:
    """Add an MCP server (writes company.yaml, configures, connects)."""
    import yaml
    from pathlib import Path

    logger.info("Adding MCP server '%s' (transport=%s)", req.name, req.transport)
    cfg_path = Path("config/company.yaml")
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    existing: dict = {}
    if cfg_path.exists():
        existing = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    servers = existing.setdefault("llm", {}).setdefault("mcp_servers", [])
    servers[:] = [s for s in servers if s.get("name") != req.name]
    servers.append({k: v for k, v in req.model_dump().items() if v is not None})
    cfg_path.write_text(
        yaml.safe_dump(existing, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )
    logger.info("MCP config written to %s (%d servers total)", cfg_path, len(servers))
    hub.config.llm.mcp_servers = servers
    hub.mcp_manager.configure(servers)
    logger.info("MCP manager configured, connecting '%s'...", req.name)
    await hub.mcp_manager.connect(req.name)
    logger.info("MCP add '%s' done", req.name)
    return {"servers": hub.mcp_manager.servers_status()}


@router.delete("/mcp/{name}")
async def delete_mcp_server(name: str) -> dict:
    import yaml
    from pathlib import Path

    await hub.mcp_manager.disconnect(name)
    cfg_path = Path("config/company.yaml")
    if cfg_path.exists():
        existing = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        servers = existing.get("llm", {}).get("mcp_servers", [])
        servers[:] = [s for s in servers if s.get("name") != name]
        cfg_path.write_text(
            yaml.safe_dump(existing, default_flow_style=False, allow_unicode=True),
            encoding="utf-8",
        )
        hub.config.llm.mcp_servers = servers
        hub.mcp_manager.configure(servers)
    return {"servers": hub.mcp_manager.servers_status()}


@router.post("/mcp/{name}/connect")
async def connect_mcp_server(name: str) -> dict:
    hub.mcp_manager.configure(hub.config.llm.mcp_servers)
    ok = await hub.mcp_manager.connect(name)
    return {"name": name, "connected": ok, "servers": hub.mcp_manager.servers_status()}
