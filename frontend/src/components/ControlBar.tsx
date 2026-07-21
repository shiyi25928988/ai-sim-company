"use client";

import { useEffect, useState } from "react";
import { API_URL } from "@/lib/config";
import { useGameStore } from "@/store/useGameStore";
import { useToastStore } from "@/store/useToastStore";
import { useAddDirectiveMutation } from "@/hooks/useQueries";
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

/** Bottom bar controls: play/pause / speed / meeting / CEO directive / refresh. */
export function ControlBar() {
  const [speed, setSpeed] = useState(1);
  const [playing, setPlaying] = useState(true);
  const [meetingOpen, setMeetingOpen] = useState(false);
  const [directiveOpen, setDirectiveOpen] = useState(false);
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
      <div className="pixel-panel flex flex-wrap items-center justify-center gap-4 px-4 py-1 text-sm">
        <button onClick={togglePlay} className="hover:text-cyan-300" aria-label={playing ? "Pause" : "Play"}>
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
        <button className="hover:text-cyan-300" onClick={() => setMeetingOpen(true)} aria-label="Convene meeting">
          📋 Meeting
        </button>
        <button className="hover:text-cyan-300" onClick={() => setDirectiveOpen(true)} aria-label="CEO directive">
          📢 CEO Directive
        </button>
        <button className="hover:text-cyan-300" onClick={() => void refresh()} aria-label="Refresh state">
          🔄 Refresh
        </button>
      </div>
      <MeetingDialog open={meetingOpen} onClose={() => setMeetingOpen(false)} />
      <DirectiveModal open={directiveOpen} onClose={() => setDirectiveOpen(false)} />
    </>
  );
}

function DirectiveModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const toast = useToastStore((s) => s.push);
  const mut = useAddDirectiveMutation();
  const [text, setText] = useState("");

  useEffect(() => {
    if (!open) return;
    setText("");
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const submit = () => {
    if (!text.trim()) return;
    mut.mutate(text, {
      onSuccess: (data) => {
        if (data.stepped) {
          toast("Directive sent; CEO ticked (sim was paused). Check agent messages.", "success");
        } else {
          toast("Directive queued for CEO (sim running).", "success");
        }
        onClose();
      },
      onError: (e: Error) => toast(e.message, "error"),
    });
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
      onClick={onClose}
    >
      <div
        className="pixel-panel w-full max-w-lg space-y-3 p-4 text-sm"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <h2 className="text-base font-bold">CEO Directive</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white" aria-label="Close">
            ✕
          </button>
        </div>
        <p className="text-xs text-gray-400">
          Send an instruction to the CEO. Examples: &quot;add a task: implement login&quot;,
          &quot;reprioritize task-1 to high&quot;, &quot;this week focus on performance&quot;.
          The CEO will act on it immediately (sim auto-steps if paused).
        </p>
        <textarea
          className="h-32 w-full resize-y rounded border border-gray-600 bg-black/40 px-2 py-1 text-xs"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Enter directive..."
        />
        <button
          className="pixel-panel w-full py-1 hover:text-cyan-300"
          disabled={mut.isPending || !text.trim()}
          onClick={submit}
        >
          {mut.isPending ? "Sending…" : "Send to CEO"}
        </button>
      </div>
    </div>
  );
}
