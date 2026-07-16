"use client";

import { useState } from "react";
import { useGameStore } from "@/store/useGameStore";
import { useConfigQuery } from "@/hooks/useQueries";

/** HUD top bar: capital / burn(+budget) / sim day / agent picker / skills / mood. */
export function HUD() {
  const snapshot = useGameStore((s) => s.snapshot);
  const setSelectedAgentId = useGameStore((s) => s.setSelectedAgentId);
  const { data: cfg } = useConfigQuery();
  const mood = avgMood(snapshot.agents);
  const [open, setOpen] = useState(false);

  return (
    <div className="pixel-panel flex flex-wrap items-center gap-6 px-4 py-2 text-sm">
      <span>💰 ${snapshot.economy.capital.toLocaleString()}</span>
      <span>
        🔥 ${snapshot.economy.monthly_burn.toLocaleString()}/mo
        {cfg && cfg.monthly_budget > 0
          ? ` / $${cfg.monthly_budget.toLocaleString()}`
          : ""}
      </span>
      <span>📅 Day {Math.floor(snapshot.tick / 10) + 1}</span>
      <div className="relative">
        <button
          className="hover:text-cyan-300"
          title="Select an agent"
          onClick={() => setOpen((o) => !o)}
        >
          👥 {snapshot.agents.length}
        </button>
        {open && (
          <>
            <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
            <ul className="pixel-panel absolute left-0 top-full z-20 mt-1 max-h-72 w-56 overflow-y-auto p-2 text-xs">
              {snapshot.agents.length === 0 ? (
                <li className="italic text-gray-500">(no agents)</li>
              ) : (
                snapshot.agents.map((a) => (
                  <li key={a.agent_id}>
                    <button
                      className="block w-full py-1 text-left hover:text-cyan-300"
                      onClick={() => {
                        setSelectedAgentId(a.agent_id);
                        setOpen(false);
                      }}
                    >
                      {a.name} <span className="text-gray-500">({a.role})</span>
                    </button>
                  </li>
                ))
              )}
            </ul>
          </>
        )}
      </div>
      <span>🧠 {snapshot.skills.length}</span>
      <span>😊 Mood: {Math.round(mood * 100)}%</span>
    </div>
  );
}

function avgMood(agents: { mood: number }[]): number {
  if (agents.length === 0) return 0.78;
  const sum = agents.reduce((acc, a) => acc + (a.mood + 1) / 2, 0);
  return sum / agents.length;
}
