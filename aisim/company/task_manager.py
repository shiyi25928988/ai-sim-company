"""任务管理 - CEO/HR 创建任务，工程师认领并完成 (见 §三 任务分解与分配)。

Task 落盘到 Redis hash (aisim:tasks)。认领模型: 任务可指定 assignee_role，
该角色的任一 Agent 可认领；第一个 complete 的 Agent 赢得归属。
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
    """Redis 任务池。"""

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
            task.assignee = agent_id  # 认领
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
        """某 Agent 当前可做的任务: 已派给它的 (pending/in_progress) +
        派给它角色且未认领的 (pending)。"""
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
