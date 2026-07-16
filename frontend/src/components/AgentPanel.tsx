"use client";

import { useGameStore } from "@/store/useGameStore";
import { useAgentSkillsQuery } from "@/hooks/useQueries";
import { Skeleton } from "@/components/Skeleton";

/** Side agent detail panel: name/role/status + inherited skills. */
export function AgentPanel() {
  const selectedAgentId = useGameStore((s) => s.selectedAgentId);
  const snapshot = useGameStore((s) => s.snapshot);
  const setSelectedAgentId = useGameStore((s) => s.setSelectedAgentId);
  const agent = snapshot.agents.find((a) => a.agent_id === selectedAgentId) ?? null;

  const { data: skills = [], isLoading: skillsLoading } = useAgentSkillsQuery(
    agent?.agent_id ?? null,
  );

  if (!agent) {
    return (
      <div className="pixel-panel h-full p-3 text-xs text-gray-500">
        Select an agent (click 👥 in the HUD) to see details.
      </div>
    );
  }

  return (
    <div className="pixel-panel h-full overflow-y-auto p-3 text-sm">
      <div className="mb-2 flex items-center justify-between">
        <strong>{agent.name}</strong>
        <button
          onClick={() => setSelectedAgentId(null)}
          className="text-gray-400 hover:text-white"
          aria-label="Close agent panel"
        >
          ✕
        </button>
      </div>
      <dl className="space-y-1">
        <div>Role: {agent.role}</div>
        <div>Department: {agent.department}</div>
        <div>Status: {agent.status}</div>
        <div>Energy: {Math.round(agent.energy)}%</div>
      </dl>
      <div className="mt-3 text-gray-400">
        <div className="mb-1">Skills ({skills.length})</div>
        {skillsLoading ? (
          <div className="space-y-1">
            <Skeleton className="h-3 w-24" />
            <Skeleton className="h-3 w-32" />
          </div>
        ) : (
          <ul className="list-inside list-disc text-xs">
            {skills.length === 0 ? (
              <li className="italic">(none)</li>
            ) : (
              skills.map((s) => (
                <li key={s.id}>
                  {s.name} <span className="text-gray-600">[{s.level}]</span>
                </li>
              ))
            )}
          </ul>
        )}
      </div>
      <div className="mt-3 text-gray-400">
        <div className="mb-1">Recent Thoughts/Actions</div>
        <ul className="space-y-1 text-xs">
          {agent.recent.length === 0 ? (
            <li className="italic text-gray-500">(none)</li>
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
