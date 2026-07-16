"use client";

import { useCallback, useEffect, useState } from "react";
import { useWebSocket } from "./useWebSocket";
import { gameBridge } from "@/game/bridge";
import { API_URL } from "@/lib/config";
import type { AgentState, GameSnapshot, LogEntry } from "@/types/game";

const EMPTY_SNAPSHOT: GameSnapshot = {
  company: "",
  economy: { capital: 0, monthly_burn: 0, revenue: 0, bankrupt: false },
  tick: 0,
  agents: [],
  tasks: [],
  skills: [],
};

/**
 * Maintains the overall frontend game state: snapshot + log stream + selected agent.
 * WS events are fed to both React (HUD/logs) and gameBridge (Phaser sprites).
 */
export function useGameState() {
  const [snapshot, setSnapshot] = useState<GameSnapshot>(EMPTY_SNAPSHOT);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<AgentState | null>(null);

  const pushLog = useCallback((text: string) => {
    setLogs((prev) => [...prev.slice(-200), { ts: Date.now(), text }]);
  }, []);

  // Fetch the initial state once on mount (no need to wait for the first tick)
  useEffect(() => {
    fetch(`${API_URL}/api/state`)
      .then((r) => r.json())
      .then((s: GameSnapshot) => {
        setSnapshot(s);
        gameBridge.snapshot = s;
      })
      .catch(() => {});
  }, []);

  // Phaser agent click -> select
  useEffect(() => {
    return gameBridge.onSelect((name) => {
      if (!name) {
        setSelectedAgent(null);
        return;
      }
      const found = (gameBridge.snapshot ?? EMPTY_SNAPSHOT).agents.find(
        (a) => a.name === name,
      );
      setSelectedAgent(found ?? null);
    });
  }, []);

  useWebSocket((event) => {
    gameBridge.emit(event); // forward to Phaser

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
        gameBridge.snapshot = snap;
        break;
      }
      case "agent_message":
        pushLog(`${event.sender}: ${event.content}`);
        break;
      case "agent_created":
        pushLog(`New hire: ${event.name} (${event.role})`);
        break;
      case "agent_action":
        pushLog(`${event.agent} -> ${event.action}${event.target ? " -> " + event.target : ""}`);
        break;
      case "meeting_start":
        pushLog(`Meeting started: ${event.participants.join(", ")}`);
        break;
      case "meeting_minutes":
        pushLog(`👥 Minutes [${event.topic}]: ${event.minutes.slice(0, 80)}`);
        break;
      case "task_created":
        pushLog(`📝 New task: ${event.title} -> ${event.assignee_role || event.assignee}`);
        break;
      case "task_completed":
        pushLog(`✅ Done: ${event.title} (by ${event.by})`);
        break;
    }
  });

  const selectAgent = useCallback((agent: AgentState | null) => {
    setSelectedAgent(agent);
    gameBridge.select(agent?.name ?? null);
  }, []);

  return { snapshot, logs, selectedAgent, selectAgent, pushLog };
}
