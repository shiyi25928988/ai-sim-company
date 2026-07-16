"use client";

import { useState } from "react";
import { API_URL } from "@/lib/config";
import { useGameStore } from "@/store/useGameStore";
import { useToastStore } from "@/store/useToastStore";
import { MeetingDialog } from "@/components/MeetingDialog";
import type { GameSnapshot } from "@/types/game";

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

/** Bottom bar controls: play/pause / speed / meeting / refresh snapshot. */
export function ControlBar() {
  const [speed, setSpeed] = useState(1);
  const [playing, setPlaying] = useState(true);
  const [meetingOpen, setMeetingOpen] = useState(false);
  const toast = useToastStore((s) => s.push);

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

  const refresh = async () => {
    try {
      const r = await fetch(`${API_URL}/api/state`);
      const s = (await r.json()) as GameSnapshot;
      useGameStore.getState().setSnapshot(s);
      toast("State refreshed", "info");
    } catch {
      toast("Failed to refresh state", "error");
    }
  };

  return (
    <>
      <div className="pixel-panel flex items-center justify-center gap-4 px-4 py-1 text-sm">
        <button
          onClick={togglePlay}
          className="hover:text-cyan-300"
          aria-label={playing ? "Pause" : "Play"}
        >
          {playing ? "⏸ Pause" : "▶ Play"}
        </button>
        <button onClick={step} className="hover:text-cyan-300" aria-label="Step">
          ⏭ Step
        </button>
        {[1, 10, 60].map((s) => (
          <button
            key={s}
            onClick={() => changeSpeed(s)}
            className={speed === s ? "text-cyan-300" : "hover:text-cyan-300"}
            aria-label={`${s}x speed`}
          >
            {s}x
          </button>
        ))}
        <button
          className="hover:text-cyan-300"
          onClick={() => setMeetingOpen(true)}
          aria-label="Convene meeting"
        >
          📋 Meeting
        </button>
        <button
          className="hover:text-cyan-300"
          onClick={() => void refresh()}
          aria-label="Refresh state"
        >
          🔄 Refresh
        </button>
      </div>
      <MeetingDialog open={meetingOpen} onClose={() => setMeetingOpen(false)} />
    </>
  );
}
