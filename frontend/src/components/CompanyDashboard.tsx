"use client";

import { useGameStore } from "@/store/useGameStore";
import { useLlmConfigQuery, useConfigQuery } from "@/hooks/useQueries";

const ROLE_LABELS: Record<string, string> = {
  ceo: "CEO",
  "hr-director": "HR Director",
  "product-manager": "Product Manager",
  "senior-engineer": "Senior Engineer",
  "junior-engineer": "Junior Engineer",
  designer: "Designer",
};

const TASK_STATUS_COLOR: Record<string, string> = {
  pending: "text-yellow-300",
  in_progress: "text-cyan-300",
  done: "text-green-400",
  blocked: "text-red-400",
};

/** Company dashboard: cash flow / LLM usage / team / project board. */
export function CompanyDashboard() {
  const snapshot = useGameStore((s) => s.snapshot);
  const { data: llm } = useLlmConfigQuery();
  const { data: cfg } = useConfigQuery();

  const agents = snapshot.agents;
  const tasks = snapshot.tasks;
  const eco = snapshot.economy;

  const tasksByStatus = {
    pending: tasks.filter((t) => t.status === "pending"),
    in_progress: tasks.filter((t) => t.status === "in_progress"),
    done: tasks.filter((t) => t.status === "done"),
    blocked: tasks.filter((t) => t.status === "blocked"),
  };

  const avgMood = agents.length
    ? agents.reduce((a, x) => a + (x.mood + 1) / 2, 0) / agents.length
    : 0;
  const avgEnergy = agents.length
    ? agents.reduce((a, x) => a + x.energy, 0) / agents.length
    : 0;

  const budget = cfg?.monthly_budget ?? 0;
  const burnPct = budget > 0 ? Math.min(100, (eco.monthly_burn / budget) * 100) : 0;
  const llmPct =
    llm && llm.daily_budget > 0
      ? Math.min(100, (llm.usage_today / llm.daily_budget) * 100)
      : 0;

  return (
    <div className="space-y-3 p-4 text-sm">
      <h2 className="text-base font-bold">{snapshot.company || "Company"} Dashboard</h2>

      {/* Top row: economy + LLM */}
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        <section className="pixel-panel p-3">
          <h3 className="mb-2 font-bold">Cash Flow</h3>
          <div className="space-y-1 text-xs">
            <div>💰 Capital: ${eco.capital.toLocaleString()}</div>
            <div>🔥 Monthly burn: ${eco.monthly_burn.toLocaleString()}/mo</div>
            <div>📈 Revenue: ${eco.revenue.toLocaleString()}</div>
            {budget > 0 && (
              <div>
                Budget: ${budget.toLocaleString()} ({burnPct.toFixed(0)}% used)
                <div className="mt-1 h-2 w-full bg-gray-700">
                  <div className="h-2 bg-cyan-400" style={{ width: `${burnPct}%` }} />
                </div>
              </div>
            )}
            {eco.bankrupt && <div className="text-red-400">⚠️ Bankrupt</div>}
          </div>
        </section>
        <section className="pixel-panel p-3">
          <h3 className="mb-2 font-bold">LLM Usage</h3>
          <div className="space-y-1 text-xs">
            <div>Used: {llm?.usage_today.toLocaleString() ?? 0} tokens</div>
            <div>Budget: {llm?.daily_budget.toLocaleString() ?? 0} tokens</div>
            <div>
              {llmPct.toFixed(0)}% used
              <div className="mt-1 h-2 w-full bg-gray-700">
                <div className="h-2 bg-purple-400" style={{ width: `${llmPct}%` }} />
              </div>
            </div>
            <div className="text-gray-400">{llm?.default_model ?? "-"}</div>
          </div>
        </section>
      </div>

      {/* Team */}
      <section className="pixel-panel p-3">
        <h3 className="mb-2 font-bold">Team ({agents.length})</h3>
        {agents.length === 0 ? (
          <p className="text-xs italic text-gray-500">(no agents)</p>
        ) : (
          <>
            <div className="grid grid-cols-2 gap-2 text-xs md:grid-cols-3">
              {agents.map((a) => (
                <div key={a.agent_id} className="border-l-2 border-cyan-700 pl-2">
                  <div className="font-bold">{a.name}</div>
                  <div className="text-gray-500">
                    {ROLE_LABELS[a.role] ?? a.role} · {a.department}
                  </div>
                  <div className="text-gray-500">
                    {a.status} · E{Math.round(a.energy)}% · M
                    {Math.round(((a.mood + 1) / 2) * 100)}%
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-2 text-xs text-gray-400">
              Avg mood: {Math.round(avgMood * 100)}% · Avg energy: {Math.round(avgEnergy)}%
            </div>
          </>
        )}
      </section>

      {/* Project board */}
      <section className="pixel-panel p-3">
        <h3 className="mb-2 font-bold">Project Board ({tasks.length} tasks)</h3>
        {tasks.length === 0 ? (
          <p className="text-xs italic text-gray-500">(no tasks)</p>
        ) : (
          <div className="grid grid-cols-2 gap-3 text-xs md:grid-cols-4">
            {(["pending", "in_progress", "done", "blocked"] as const).map((st) => (
              <div key={st}>
                <div className={`mb-1 ${TASK_STATUS_COLOR[st]}`}>
                  {st} ({tasksByStatus[st].length})
                </div>
                <ul className="space-y-1">
                  {tasksByStatus[st].map((t) => (
                    <li key={t.id} className="border-l-2 border-gray-600 pl-1">
                      <div>{t.title}</div>
                      <div className="text-gray-500">
                        {"->"} {t.assignee || t.assignee_role || "-"}
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
