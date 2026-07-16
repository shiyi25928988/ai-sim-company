"use client";

import { useEffect, useRef } from "react";
import { WS_URL } from "@/lib/config";
import type { FrontendEvent } from "@/types/game";

/**
 * Connect to the Company Hub WebSocket and pass incoming render events to the callback.
 * URL comes from NEXT_PUBLIC_WS_URL (default ws://localhost:8000).
 */
export function useWebSocket(onEvent: (event: FrontendEvent) => void) {
  const cbRef = useRef(onEvent);
  cbRef.current = onEvent;

  useEffect(() => {
    const ws = new WebSocket(`${WS_URL}/ws`);

    ws.onmessage = (msg) => {
      try {
        const event = JSON.parse(msg.data) as FrontendEvent;
        cbRef.current(event);
      } catch {
        // ignore non-JSON frames
      }
    };

    return () => ws.close();
  }, []);
}
