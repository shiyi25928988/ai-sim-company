"use client";

import { useEffect, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useGameStore } from "@/store/useGameStore";
import { useToastStore } from "@/store/useToastStore";
import { API_URL } from "@/lib/config";

/** Modal to convene an LLM-hosted meeting (POST /api/meetings) and show minutes. */
export function MeetingDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const agents = useGameStore((s) => s.snapshot.agents);
  const toast = useToastStore((s) => s.push);
  const [topic, setTopic] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [minutes, setMinutes] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const mutation = useMutation({
    mutationFn: async () => {
      const r = await fetch(`${API_URL}/api/meetings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic, participants: selected }),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || "meeting failed");
      return j as { minutes: string };
    },
    onSuccess: (data) => {
      setMinutes(data.minutes);
      setError(null);
      toast(`Meeting "${topic}" concluded`, "success");
    },
    onError: (e: Error) => {
      setError(e.message);
      toast(e.message, "error");
    },
  });

  const toggle = (id: string) =>
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div
        role="dialog"
        aria-label="Convene meeting"
        className="pixel-panel w-full max-w-lg space-y-3 p-4 text-sm"
      >
        <div className="flex items-center justify-between">
          <h2 className="text-base font-bold">Convene Meeting</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white" aria-label="Close">
            ✕
          </button>
        </div>
        <label className="block">
          Topic
          <input
            className="mt-1 w-full rounded border border-gray-600 bg-black/40 px-2 py-1 text-xs"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="e.g. Q2 roadmap"
          />
        </label>
        <div>
          <div className="mb-1">Participants ({selected.length})</div>
          <div className="flex flex-wrap gap-2 text-xs">
            {agents.length === 0 ? (
              <span className="italic text-gray-500">(no agents available)</span>
            ) : (
              agents.map((a) => (
                <button
                  key={a.agent_id}
                  type="button"
                  onClick={() => toggle(a.agent_id)}
                  className={`pixel-panel px-2 py-1 ${
                    selected.includes(a.agent_id) ? "text-cyan-300" : "text-gray-400"
                  }`}
                >
                  {a.name}
                </button>
              ))
            )}
          </div>
        </div>
        {error && <p className="text-bad">{error}</p>}
        {minutes && (
          <div className="pixel-panel max-h-48 overflow-y-auto p-2 text-xs">
            <div className="mb-1 text-gray-400">Minutes</div>
            {minutes}
          </div>
        )}
        <button
          className="pixel-panel w-full py-1 hover:text-cyan-300"
          disabled={mutation.isPending || !topic.trim() || selected.length === 0}
          onClick={() => {
            setMinutes(null);
            mutation.mutate();
          }}
        >
          {mutation.isPending ? "Hosting…" : "Host Meeting"}
        </button>
      </div>
    </div>
  );
}
