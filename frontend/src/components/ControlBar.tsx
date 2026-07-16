"use client";

import { useState } from "react";
import { API_URL } from "@/lib/config";

async function control(action: string, speed?: number): Promise<void> {
  try {
    await fetch(`${API_URL}/api/simulation/control`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, speed }),
    });
  } catch {
    // stay silent when the backend is down
  }
}

/** Bottom bar controls: play/pause / speed (1x/10x/60x) / snapshot / open office. */
export function ControlBar({ onOpenOffice }: { onOpenOffice: () => void }) {
  const [speed, setSpeed] = useState(1);
  const [playing, setPlaying] = useState(true);

  const changeSpeed = (s: number) => {
    setSpeed(s);
    void control("speed", s);
  };

  const togglePlay = () => {
    const next = !playing;
    setPlaying(next);
    void control(next ? "play" : "pause");
  };

  const step = () => {
    setPlaying(false); // stepping implies paused
    void control("step");
  };

  return (
    <div className="pixel-panel flex items-center justify-center gap-4 px-4 py-1 text-sm">
      <button onClick={togglePlay} className="hover:text-cyan-300">
        {playing ? "⏸ Pause" : "▶ Play"}
      </button>
      <button onClick={step} className="hover:text-cyan-300">
        ⏭ Step
      </button>
      {[1, 10, 60].map((s) => (
        <button
          key={s}
          onClick={() => changeSpeed(s)}
          className={speed === s ? "text-cyan-300" : "hover:text-cyan-300"}
        >
          {s}x
        </button>
      ))}
      <button className="hover:text-cyan-300" onClick={() => void control("play")}>
        📸 Snapshot
      </button>
      <button className="hover:text-cyan-300" onClick={onOpenOffice}>
        🏢 Show Office
      </button>
    </div>
  );
}
