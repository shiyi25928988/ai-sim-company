"""Org chart - roles / departments / reporting lines (see §四 report_to)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class OrgNode:
    agent_id: str
    role: str
    department: str
    reports_to: str | None = None
    reports: list[str] = field(default_factory=list)


class OrgChart:
    """Org chart tree."""

    def __init__(self) -> None:
        self._nodes: dict[str, OrgNode] = {}

    def add(self, agent_id: str, role: str, department: str, reports_to: str | None = None) -> OrgNode:
        node = OrgNode(agent_id=agent_id, role=role, department=department, reports_to=reports_to)
        self._nodes[agent_id] = node
        if reports_to and reports_to in self._nodes:
            self._nodes[reports_to].reports.append(agent_id)
        return node

    def remove(self, agent_id: str) -> None:
        node = self._nodes.pop(agent_id, None)
        if node and node.reports_to and node.reports_to in self._nodes:
            parent = self._nodes[node.reports_to]
            parent.reports = [r for r in parent.reports if r != agent_id]

    def get(self, agent_id: str) -> OrgNode | None:
        return self._nodes.get(agent_id)

    def by_department(self, department: str) -> list[OrgNode]:
        return [n for n in self._nodes.values() if n.department == department]

    def direct_reports(self, agent_id: str) -> list[str]:
        node = self._nodes.get(agent_id)
        return list(node.reports) if node else []
