"use client";

import { useEffect, useRef, useState } from "react";
import { useGameState } from "@/hooks/useGameState";
import { HUD } from "@/components/HUD";
import { ControlBar } from "@/components/ControlBar";
import { LogFeed } from "@/components/LogFeed";
import { AgentPanel } from "@/components/AgentPanel";
import { TaskBoard } from "@/components/TaskBoard";

// Subset of the Phaser.Game interface (avoids statically importing phaser; declares only what we use)
type GameHandle = {
  destroy: (remove?: boolean) => void;
  loop: { sleep: () => void; wake: () => void };
};

export default function Page() {
  const containerRef = useRef<HTMLDivElement>(null);
  const gameRef = useRef<GameHandle | null>(null);
  const gameStarted = useRef(false);
  // Office overlay is collapsed by default: the main view shows only data panels;
  // click the button to pop up the canvas.
  const [officeOpen, setOfficeOpen] = useState(false);
  const { snapshot, logs, selectedAgent, selectAgent } = useGameState();

  // Lazy load: create the Phaser instance only when the overlay is first opened.
  // While collapsed by default no canvas is rendered (saves CPU); gameBridge.snapshot
  // is kept up to date by useGameState, and the first OfficeScene reconciles existing
  // agents without losing state.
  useEffect(() => {
    if (!officeOpen || gameStarted.current || !containerRef.current) return;
    gameStarted.current = true;
    let cancelled = false;
    void import("@/game").then(({ createGame }) => {
      if (cancelled || !containerRef.current) return;
      gameRef.current = createGame(containerRef.current) as unknown as GameHandle;
    });
    return () => {
      cancelled = true;
    };
  }, [officeOpen]);

  // Pause the Phaser render loop while the overlay is collapsed; resume on open
  // (avoids running the canvas in the background).
  useEffect(() => {
    const game = gameRef.current;
    if (!game) return;
    if (officeOpen) game.loop.wake();
    else game.loop.sleep();
  }, [officeOpen]);

  // Destroy the Phaser instance on unmount.
  useEffect(() => {
    return () => {
      gameRef.current?.destroy(true);
      gameRef.current = null;
    };
  }, []);

  return (
    <main className="relative h-screen w-full overflow-hidden bg-[#0f0f1a]">
      {/* HUD top bar */}
      <div className="absolute left-0 top-0 w-full">
        <HUD snapshot={snapshot} />
      </div>

      {/* Left task board */}
      <div className="absolute left-2 top-16">
        <TaskBoard tasks={snapshot.tasks} />
      </div>

      {/* Side agent panel */}
      <div className="absolute right-2 top-16 w-80">
        <AgentPanel agent={selectedAgent} onClose={() => selectAgent(null)} />
      </div>

      {/* Bottom log bar */}
      <div className="absolute bottom-12 left-0 w-full">
        <LogFeed logs={logs} />
      </div>

      {/* Control bar */}
      <div className="absolute bottom-0 left-0 w-full">
        <ControlBar onOpenOffice={() => setOfficeOpen(true)} />
      </div>

      {/* Office overlay: collapsed by default, popped up via "Show Office", closed with ✕.
          containerRef stays in the DOM and keeps its size; only opacity + pointer-events
          toggle visibility, so Phaser FIT doesn't break on a zero-size parent (display:none). */}
      <div
        className={`fixed inset-0 z-50 flex items-center justify-center bg-black/70 transition-opacity duration-200 ${
          officeOpen ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
      >
        <div className="relative">
          {/* Phaser canvas mount point */}
          <div
            ref={containerRef}
            className="h-[640px] w-[960px] max-h-[85vh] max-w-[95vw]"
          />
          <button
            onClick={() => setOfficeOpen(false)}
            className="pixel-panel absolute -right-3 -top-3 flex h-8 w-8 items-center justify-center rounded text-sm hover:text-cyan-300"
            aria-label="Close office"
          >
            ✕
          </button>
        </div>
      </div>
    </main>
  );
}
