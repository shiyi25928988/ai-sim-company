"""Task management - CEO/HR create tasks, engineers claim and complete them (see §三 task decomposition and assignment).

Tasks are persisted to a Redis hash (aisim:tasks). Claim model: a task may specify an assignee_role,
and any Agent of that role may claim it; the first Agent to complete wins ownership.
"""

from __future__ import annotations

import logging
import re

from aisim.comm.message_bus import MessageBus
from aisim.shared import channels
from aisim.shared.models import Task, TaskStatus

logger = logging.getLogger(__name__)


def _task_id(title: str, tick: int) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:24] or "task"
    return f"task-{tick}-{slug}"


def _to_dict(task: Task) -> dict:
    d = task.__dict__.copy()
    d["status"] = task.status.value
    return d


def _from_dict(data: dict) -> Task:
    return Task(
        id=data["id"],
        title=data.get("title", ""),
        description=data.get("description", ""),
        status=TaskStatus(data.get("status", "pending")),
        assignee=data.get("assignee", ""),
        assignee_role=data.get("assignee_role", ""),
        project=data.get("project", ""),
        priority=data.get("priority", "normal"),
        created_by=data.get("created_by", ""),
        created_tick=int(data.get("created_tick", 0)),
        completed_tick=int(data.get("completed_tick", 0)),
        completed_by=data.get("completed_by", ""),
        result=data.get("result", ""),
    )


class TaskManager:
    """Redis task pool."""

    def __init__(self, bus: MessageBus) -> None:
        self.bus = bus

    async def create(
        self,
        title: str,
        description: str = "",
        assignee_role: str = "",
        assignee: str = "",
        project: str = "",
        priority: str = "normal",
        created_by: str = "",
        tick: int = 0,
    ) -> Task:
        task = Task(
            id=_task_id(title, tick),
            title=title,
            description=description,
            status=TaskStatus.PENDING,
            assignee=assignee,
            assignee_role=assignee_role,
            project=project,
            priority=priority,
            created_by=created_by,
            created_tick=tick,
        )
        await self.bus.hset_json(channels.KEY_TASKS, task.id, _to_dict(task))
        logger.info("新任务: %s (派给 %s) by %s", title, assignee_role or assignee, created_by)
        return task

    async def complete(self, task_id: str, agent_id: str, result: str, tick: int) -> Task | None:
        task = await self.get(task_id)
        if task is None:
            logger.warning("complete: 任务不存在 %s", task_id)
            return None
        if task.status == TaskStatus.DONE:
            logger.info("任务已被 %s 完成: %s", task.completed_by, task_id)
            return task
        if task.assignee == "":
            task.assignee = agent_id  # claim
        task.status = TaskStatus.DONE
        task.result = result
        task.completed_by = agent_id
        task.completed_tick = tick
        await self.bus.hset_json(channels.KEY_TASKS, task.id, _to_dict(task))
        logger.info("任务完成: %s by %s", task.title, agent_id)
        return task

    async def get(self, task_id: str) -> Task | None:
        data = await self.bus.hget_json(channels.KEY_TASKS, task_id)
        return _from_dict(data) if data else None

    async def list(self) -> list[Task]:
        data = await self.bus.hgetall_json(channels.KEY_TASKS)
        tasks = [_from_dict(v) for v in data.values()]
        tasks.sort(key=lambda t: t.created_tick)
        return tasks

    async def list_dicts(self) -> list[dict]:
        return [_to_dict(t) for t in await self.list()]

    @staticmethod
    def to_dict(task: Task) -> dict:
        return _to_dict(task)

    async def pending_for(self, agent_id: str, role: str) -> list[Task]:
        """Tasks currently actionable for an Agent: those assigned to it (pending/in_progress) +
        those assigned to its role and unclaimed (pending)."""
        tasks = await self.list()
        out = []
        for t in tasks:
            if t.status == TaskStatus.DONE:
                continue
            if t.assignee == agent_id and t.status in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS):
                out.append(t)
            elif t.assignee == "" and t.assignee_role == role and t.status == TaskStatus.PENDING:
                out.append(t)
        return out

    async def remove(self, task_id: str) -> None:
        await self.bus.hdel(channels.KEY_TASKS, task_id)
