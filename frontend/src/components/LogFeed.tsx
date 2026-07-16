"use client";

import type { LogEntry } from "@/types/game";
import { useEffect, useRef } from "react";

/** Bottom real-time log stream. */
export function LogFeed({ logs }: { logs: LogEntry[] }) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  return (
    <div className="pixel-panel mx-auto h-24 max-w-5xl overflow-y-auto px-3 py-1 text-xs">
      {logs.length === 0 && <div className="text-gray-500">Waiting for company activity…</div>}
      {logs.map((log, i) => (
        <div key={i} className="whitespace-pre-wrap">
          <span className="text-gray-500">[{new Date(log.ts).toLocaleTimeString()}]</span>{" "}
          {log.text}
        </div>
      ))}
      <div ref={endRef} />
    </div>
  );
}
