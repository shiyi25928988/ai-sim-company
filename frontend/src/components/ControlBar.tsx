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
    // 后端未启动时静默
  }
}

/** 底栏控制: 播放/暂停 / 倍速 (1x/10x/60x) / 快照。 */
export function ControlBar() {
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
    setPlaying(false); // 单步即暂停态
    void control("step");
  };

  return (
    <div className="pixel-panel flex items-center justify-center gap-4 px-4 py-1 text-sm">
      <button onClick={togglePlay} className="hover:text-cyan-300">
        {playing ? "⏸ 暂停" : "▶ 播放"}
      </button>
      <button onClick={step} className="hover:text-cyan-300">
        ⏭ 单步
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
        📸 快照
      </button>
    </div>
  );
}
