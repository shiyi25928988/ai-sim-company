"use client";

import { useGameEvents } from "@/hooks/useGameEvents";

/** Mounts the central WS subscriber so realtime state is available app-wide. */
export function GameProvider({ children }: { children: React.ReactNode }) {
  useGameEvents();
  return <>{children}</>;
}
