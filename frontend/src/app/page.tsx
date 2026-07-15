"use client";

import { useEffect, useRef } from "react";
import { useGameState } from "@/hooks/useGameState";
import { HUD } from "@/components/HUD";
import { ControlBar } from "@/components/ControlBar";
import { LogFeed } from "@/components/LogFeed";
import { AgentPanel } from "@/components/AgentPanel";
import { TaskBoard } from "@/components/TaskBoard";

type GameHandle = { destroy: (remove?: boolean) => void };

export default function Page() {
  const containerRef = useRef<HTMLDivElement>(null);
  const gameRef = useRef<GameHandle | null>(null);
  const { snapshot, logs, selectedAgent, selectAgent } = useGameState();

  // 挂载 Phaser 游戏 - 动态 import 避免 SSR 时引入 phaser (window 未定义)
  useEffect(() => {
    let cancelled = false;
    void import("@/game").then(({ createGame }) => {
      if (cancelled || !containerRef.current) return;
      gameRef.current = createGame(containerRef.current) as unknown as GameHandle;
    });
    return () => {
      cancelled = true;
      gameRef.current?.destroy(true);
      gameRef.current = null;
    };
  }, []);

  return (
    <main className="relative h-screen w-full overflow-hidden">
      {/* Phaser 画布层 */}
      <div ref={containerRef} className="absolute inset-0" />

      {/* HUD 顶栏 */}
      <div className="absolute left-0 top-0 w-full">
        <HUD snapshot={snapshot} />
      </div>

      {/* 左侧任务看板 */}
      <div className="absolute left-2 top-16">
        <TaskBoard tasks={snapshot.tasks} />
      </div>

      {/* 侧边 Agent 面板 */}
      <div className="absolute right-2 top-16 w-80">
        <AgentPanel agent={selectedAgent} onClose={() => selectAgent(null)} />
      </div>

      {/* 日志底栏 */}
      <div className="absolute bottom-12 left-0 w-full">
        <LogFeed logs={logs} />
      </div>

      {/* 控制栏 */}
      <div className="absolute bottom-0 left-0 w-full">
        <ControlBar />
      </div>
    </main>
  );
}
