"""TaskManager unit tests - uses FakeBus (no Redis)."""

from __future__ import annotations

import pytest

from aisim.company.task_manager import TaskManager
from aisim.shared.models import TaskStatus

pytestmark = pytest.mark.asyncio


class FakeBus:
    def __init__(self) -> None:
        self.data: dict[str, dict] = {}

    async def hset_json(self, name, key, value):
        self.data.setdefault(name, {})[key] = value

    async def hget_json(self, name, key):
        return self.data.get(name, {}).get(key)

    async def hgetall_json(self, name):
        return dict(self.data.get(name, {}))

    async def hdel(self, name, *keys):
        for k in keys:
            self.data.get(name, {}).pop(k, None)


async def test_create_and_list():
    tm = TaskManager(FakeBus())  # type: ignore[arg-type]
    t = await tm.create(
        title="搭 API", description="写接口", assignee_role="senior-engineer",
        created_by="ceo-alex", tick=1,
    )
    assert t.status == TaskStatus.PENDING
    assert t.assignee_role == "senior-engineer"
    tasks = await tm.list()
    assert len(tasks) == 1 and tasks[0].title == "搭 API"
    # list_dicts (for snapshot) must be serializable - regression: status must be enum or .value crashes
    dicts = await tm.list_dicts()
    assert dicts[0]["status"] == "pending"
    assert dicts[0]["id"] == t.id


async def test_complete_claims_and_marks_done():
    tm = TaskManager(FakeBus())  # type: ignore[arg-type]
    t = await tm.create(title="写测试", assignee_role="senior-engineer", tick=1)
    done = await tm.complete(t.id, "eng-jordan", "写好 10 个用例", tick=2)
    assert done.status == TaskStatus.DONE
    assert done.assignee == "eng-jordan"
    assert done.result == "写好 10 个用例"
    # second agent completes again: first one wins (idempotent)
    again = await tm.complete(t.id, "eng-sam", "x", tick=3)
    assert again.completed_by == "eng-jordan"


async def test_pending_for_role_and_assignee():
    tm = TaskManager(FakeBus())  # type: ignore[arg-type]
    t1 = await tm.create(title="A", assignee_role="senior-engineer", tick=1)
    t2 = await tm.create(title="B", assignee="eng-jordan", tick=1)
    t3 = await tm.create(title="C", assignee_role="designer", tick=1)
    await tm.complete(t2.id, "eng-jordan", "done", tick=2)

    pend = await tm.pending_for("eng-jordan", "senior-engineer")
    ids = {t.id for t in pend}
    assert t1.id in ids          # role matches and unclaimed
    assert t2.id not in ids      # already completed
    assert t3.id not in ids      # role does not match
