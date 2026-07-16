"use client";

import { HUD } from "@/components/HUD";
import { ControlBar } from "@/components/ControlBar";
import { LogFeed } from "@/components/LogFeed";
import { AgentPanel } from "@/components/AgentPanel";
import { TaskBoard } from "@/components/TaskBoard";

/** Main console: HUD / TaskBoard | log | AgentPanel / control bar (responsive CSS grid). */
export default function Page() {
  return (
    <main className="grid h-full grid-rows-[auto_1fr_auto] gap-2 p-2">
      <HUD />

      <div className="grid min-h-0 grid-cols-1 gap-2 md:grid-cols-[16rem_1fr] lg:grid-cols-[16rem_1fr_20rem]">
        <TaskBoard />
        <LogFeed />
        <AgentPanel />
      </div>

      <ControlBar />
    </main>
  );
}
