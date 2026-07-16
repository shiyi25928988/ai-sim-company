"use client";

import type { Task } from "@/types/game";

const STATUS_COLOR: Record<string, string> = {
  pending: "text-yellow-300",
  in_progress: "text-cyan-300",
  done: "text-green-400",
  blocked: "text-red-400",
};

/** Left task board: in progress / done. Driven by state_snapshot tasks. */
export function TaskBoard({ tasks }: { tasks: Task[] }) {
  const pending = tasks.filter((t) => t.status !== "done");
  const done = tasks.filter((t) => t.status === "done");

  return (
    <div className="pixel-panel max-h-[70vh] w-64 overflow-y-auto p-3 text-xs">
      <h3 className="mb-2 text-sm font-bold">📋 Task Board</h3>

      <div className="mb-1 text-gray-400">In Progress ({pending.length})</div>
      {pending.length === 0 && <div className="italic text-gray-500">(none)</div>}
      {pending.map((t) => (
        <div key={t.id} className="mb-2 border-l-2 border-yellow-500 pl-2">
          <div className={STATUS_COLOR[t.status] ?? "text-gray-300"}>{t.title}</div>
          <div className="text-gray-500">-> {t.assignee || t.assignee_role || "Unassigned"}</div>
          {t.description && <div className="text-gray-600">{t.description.slice(0, 50)}</div>}
        </div>
      ))}

      {done.length > 0 && (
        <>
          <div className="mb-1 mt-3 text-gray-400">Done ({done.length})</div>
          {done.map((t) => (
            <div key={t.id} className="mb-1 border-l-2 border-green-600 pl-2 text-gray-500">
              <span className="line-through">{t.title}</span>
              {t.result && <div className="text-gray-600">↳ {t.result.slice(0, 60)}</div>}
            </div>
          ))}
        </>
      )}
    </div>
  );
}
