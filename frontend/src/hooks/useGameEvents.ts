"use client";

import { useWebSocket } from "./useWebSocket";
import { useGameStore } from "@/store/useGameStore";
import { queryClient } from "@/lib/query-client";
import type { GameSnapshot } from "@/types/game";

/** Central WS subscriber: updates Zustand realtime state and invalidates Query caches. */
export function useGameEvents() {
  const pushLog = useGameStore((s) => s.pushLog);
  const setSnapshot = useGameStore((s) => s.setSnapshot);
  const setWsStatus = useGameStore((s) => s.setWsStatus);

  useWebSocket(
    (event) => {
      switch (event.type) {
        case "state_snapshot": {
          const snap: GameSnapshot = {
            company: event.company,
            tick: event.tick,
            economy: event.economy,
            agents: event.agents,
            tasks: event.tasks,
            skills: event.skills,
          };
          setSnapshot(snap);
          queryClient.invalidateQueries({ queryKey: ["agents"] });
          queryClient.invalidateQueries({ queryKey: ["tasks"] });
          queryClient.invalidateQueries({ queryKey: ["skills"] });
          break;
        }
        case "agent_message":
          pushLog(`${event.sender}: ${event.content}`, "message");
          break;
        case "agent_created":
          pushLog(`New hire: ${event.name} (${event.role})`, "created");
          queryClient.invalidateQueries({ queryKey: ["agents"] });
          break;
        case "agent_action":
          pushLog(
            `${event.agent} -> ${event.action}${event.target ? " -> " + event.target : ""}`,
            "action",
          );
          break;
        case "meeting_start":
          pushLog(`Meeting started: ${event.participants.join(", ")}`, "meeting");
          break;
        case "meeting_minutes":
          pushLog(`👥 Minutes [${event.topic}]: ${event.minutes.slice(0, 80)}`, "meeting");
          break;
        case "task_created":
          pushLog(`📝 New task: ${event.title} -> ${event.assignee_role || event.assignee}`, "task");
          queryClient.invalidateQueries({ queryKey: ["tasks"] });
          break;
        case "task_completed":
          pushLog(`✅ Done: ${event.title} (by ${event.by})`, "task");
          queryClient.invalidateQueries({ queryKey: ["tasks"] });
          break;
      }
    },
    setWsStatus,
  );
}
