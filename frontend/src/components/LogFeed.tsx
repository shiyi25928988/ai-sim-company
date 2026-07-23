"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useGameStore } from "@/store/useGameStore";
import type { LogKind } from "@/types/game";

const FILTERS: { key: LogKind | "all"; label: string }[] = [
  { key: "all", label: "All" },
  { key: "message", label: "Msg" },
  { key: "action", label: "Action" },
  { key: "created", label: "Hire" },
  { key: "meeting", label: "Meeting" },
  { key: "task", label: "Task" },
];

const KIND_COLOR: Record<string, string> = {
  message: "text-gray-300",
  action: "text-cyan-300",
  created: "text-emerald-300",
  meeting: "text-purple-300",
  task: "text-amber-300",
  system: "text-gray-400",
};

/** Center real-time log stream with kind filter + text search.
 *  Auto-scrolls to the bottom only when the user is already at the bottom;
 *  scrolling up to read history is not interrupted by new output. */
export function LogFeed() {
  const logs = useGameStore((s) => s.logs);
  const [filter, setFilter] = useState<LogKind | "all">("all");
  const [query, setQuery] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const atBottomRef = useRef(true);

  const filtered = useMemo(
    () =>
      logs.filter(
        (l) =>
          (filter === "all" || l.kind === filter) &&
          (query === "" || l.text.toLowerCase().includes(query.toLowerCase())),
      ),
    [logs, filter, query],
  );

  const handleScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    // Considered "at bottom" if within 40px of the bottom.
    atBottomRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
  };

  useEffect(() => {
    const el = scrollRef.current;
    if (el && atBottomRef.current) {
      el.scrollTop = el.scrollHeight;
    }
  }, [filtered.length]);

  return (
    <div className="pixel-panel flex h-full min-h-0 min-w-0 flex-col px-3 py-1 text-xs">
      <div className="mb-1 flex flex-wrap items-center gap-2">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={
              filter === f.key ? "text-cyan-300" : "text-gray-500 hover:text-gray-300"
            }
          >
            {f.label}
          </button>
        ))}
        <input
          className="ml-auto w-32 rounded border border-gray-600 bg-black/40 px-1 py-0.5 text-xs"
          placeholder="search…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          aria-label="Search logs"
        />
      </div>
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="min-h-0 flex-1 overflow-y-auto"
      >
        {filtered.length === 0 ? (
          <div className="text-gray-500">
            {logs.length === 0 ? "Waiting for company activity…" : "(no matches)"}
          </div>
        ) : (
          filtered.map((log, i) => (
            <div key={i} className="whitespace-pre-wrap">
              <span className="text-gray-500">[{new Date(log.ts).toLocaleTimeString()}]</span>{" "}
              <span className={KIND_COLOR[log.kind] ?? "text-gray-300"}>{log.text}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
