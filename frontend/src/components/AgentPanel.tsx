"use client";

import { useEffect, useState } from "react";
import { API_URL } from "@/lib/config";
import type { AgentState, Skill } from "@/types/game";

/** 侧边 Agent 详情面板: 名字/角色/状态 + 继承的 Skills。 */
export function AgentPanel({
  agent,
  onClose,
}: {
  agent: AgentState | null;
  onClose: () => void;
}) {
  const [skills, setSkills] = useState<Skill[]>([]);

  useEffect(() => {
    if (!agent) {
      setSkills([]);
      return;
    }
    fetch(`${API_URL}/api/agents/${agent.agent_id}/skills`)
      .then((r) => r.json())
      .then((s: Skill[]) => setSkills(s))
      .catch(() => setSkills([]));
  }, [agent]);

  if (!agent) return null;
  return (
    <div className="pixel-panel max-h-[78vh] w-80 overflow-y-auto p-3 text-sm">
      <div className="mb-2 flex items-center justify-between">
        <strong>{agent.name}</strong>
        <button onClick={onClose} className="text-gray-400 hover:text-white">
          ✕
        </button>
      </div>
      <dl className="space-y-1">
        <div>角色: {agent.role}</div>
        <div>部门: {agent.department}</div>
        <div>状态: {agent.status}</div>
        <div>能量: {Math.round(agent.energy)}%</div>
      </dl>
      <div className="mt-3 text-gray-400">
        <div className="mb-1">Skills ({skills.length})</div>
        <ul className="list-inside list-disc text-xs">
          {skills.length === 0 ? (
            <li className="italic">(无)</li>
          ) : (
            skills.map((s) => (
              <li key={s.id}>
                {s.name} <span className="text-gray-600">[{s.level}]</span>
              </li>
            ))
          )}
        </ul>
      </div>
      <div className="mt-3 text-gray-400">
        <div className="mb-1">近期思考/动作</div>
        <ul className="space-y-1 text-xs">
          {agent.recent.length === 0 ? (
            <li className="italic text-gray-500">(无)</li>
          ) : (
            agent.recent.map((r, i) => (
              <li key={i} className="border-l-2 border-gray-700 pl-2">
                <span className="text-gray-600">[{r.type}]</span>{" "}
                <span className="text-gray-300">{r.content.slice(0, 60)}</span>
              </li>
            ))
          )}
        </ul>
      </div>
    </div>
  );
}
