import { create } from "zustand";
import type { GameSnapshot, LogEntry, LogKind } from "@/types/game";

const EMPTY_SNAPSHOT: GameSnapshot = {
  company: "",
  economy: { capital: 0, monthly_burn: 0, revenue: 0, bankrupt: false },
  tick: 0,
  agents: [],
  tasks: [],
  skills: [],
};

export type WsStatus = "connecting" | "open" | "closed";

interface GameState {
  snapshot: GameSnapshot;
  logs: LogEntry[];
  selectedAgentId: string | null;
  wsStatus: WsStatus;
  pushLog: (text: string, kind?: LogKind) => void;
  setSnapshot: (snap: GameSnapshot) => void;
  setSelectedAgentId: (id: string | null) => void;
  setWsStatus: (status: WsStatus) => void;
}

/** Global realtime state fed by WebSocket events (see useGameEvents). */
export const useGameStore = create<GameState>((set) => ({
  snapshot: EMPTY_SNAPSHOT,
  logs: [],
  selectedAgentId: null,
  wsStatus: "connecting",
  pushLog: (text, kind = "system") =>
    set((s) => ({ logs: [...s.logs.slice(-200), { ts: Date.now(), text, kind }] })),
  setSnapshot: (snapshot) => set({ snapshot }),
  setSelectedAgentId: (selectedAgentId) => set({ selectedAgentId }),
  setWsStatus: (wsStatus) => set({ wsStatus }),
}));
