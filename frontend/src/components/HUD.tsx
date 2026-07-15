"use client";

import type { GameSnapshot } from "@/types/game";

/** HUD 顶栏: 资金 / 仿真日(Tick) / 团队情绪 / 倍速。 */
export function HUD({ snapshot }: { snapshot: GameSnapshot }) {
  const mood = avgMood(snapshot.agents);
  return (
    <div className="pixel-panel flex items-center gap-6 px-4 py-2 text-sm">
      <span>💰 ${snapshot.economy.capital.toLocaleString()}</span>
      <span>💸 ${snapshot.economy.monthly_burn.toLocaleString()}/月</span>
      <span>📅 Day {Math.floor(snapshot.tick / 10) + 1}</span>
      <span>👥 {snapshot.agents.length}</span>
      <span>🧠 {snapshot.skills.length}</span>
      <span>😊 Mood: {Math.round(mood * 100)}%</span>
      <span className="text-gray-400">{snapshot.company}</span>
    </div>
  );
}

function avgMood(agents: { mood: number }[]): number {
  if (agents.length === 0) return 0.78;
  const sum = agents.reduce((acc, a) => acc + (a.mood + 1) / 2, 0);
  return sum / agents.length;
}
