"use client";

import { useParams } from "next/navigation";
import { useAgentsQuery, useAgentSkillsQuery } from "@/hooks/useQueries";
import { Skeleton } from "@/components/Skeleton";

export default function AgentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: agents = [], isLoading } = useAgentsQuery();
  const agent = agents.find((a) => a.agent_id === id);
  const { data: skills = [] } = useAgentSkillsQuery(id);

  if (isLoading) {
    return (
      <main className="pixel-panel m-4 max-w-2xl space-y-3 p-4 text-sm">
        <Skeleton className="h-5 w-40" />
        <Skeleton className="h-3 w-32" />
        <Skeleton className="h-3 w-28" />
        <Skeleton className="h-3 w-36" />
      </main>
    );
  }
  if (!agent) return <main className="p-4 text-gray-500">Agent not found: {id}</main>;

  const recent = agent.recent ?? [];

  return (
    <main className="pixel-panel m-4 max-w-2xl space-y-3 p-4 text-sm">
      <h2 className="text-lg font-bold">{agent.name}</h2>
      <dl className="space-y-1">
        <div>Role: {agent.role}</div>
        <div>Department: {agent.department}</div>
        <div>Status: {agent.status}</div>
        <div>Energy: {Math.round(agent.energy)}%</div>
        <div>Mood: {Math.round((agent.mood + 1) * 50)}%</div>
      </dl>
      <div>
        <div className="mb-1 text-gray-400">Skills ({skills.length})</div>
        <ul className="list-inside list-disc text-xs">
          {skills.length === 0 ? (
            <li className="italic text-gray-500">(none)</li>
          ) : (
            skills.map((s) => (
              <li key={s.id}>
                {s.name} <span className="text-gray-600">[{s.level}]</span>
              </li>
            ))
          )}
        </ul>
      </div>
      <div>
        <div className="mb-1 text-gray-400">Recent Thoughts/Actions</div>
        <ul className="space-y-1 text-xs">
          {recent.length === 0 ? (
            <li className="italic text-gray-500">(none)</li>
          ) : (
            recent.map((r, i) => (
              <li key={i} className="border-l-2 border-gray-700 pl-2">
                <span className="text-gray-600">[{r.type}]</span>{" "}
                <span className="text-gray-300">{r.content.slice(0, 80)}</span>
              </li>
            ))
          )}
        </ul>
      </div>
    </main>
  );
}
