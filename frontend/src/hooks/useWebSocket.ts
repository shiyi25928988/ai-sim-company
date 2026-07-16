"use client";

import { useEffect, useRef } from "react";
import { WS_URL } from "@/lib/config";
import type { FrontendEvent } from "@/types/game";
import type { WsStatus } from "@/store/useGameStore";

/**
 * Connect to the Company Hub WebSocket and pass incoming render events to the callback.
 * Auto-reconnects with exponential backoff (cap 30s) and reports connection status.
 * URL comes from NEXT_PUBLIC_WS_URL (default ws://localhost:8000).
 */
export function useWebSocket(
  onEvent: (event: FrontendEvent) => void,
  onStatus?: (status: WsStatus) => void,
) {
  const cbRef = useRef(onEvent);
  const statusRef = useRef(onStatus);
  cbRef.current = onEvent;
  statusRef.current = onStatus;

  useEffect(() => {
    let ws: WebSocket | null = null;
    let retry = 0;
    let timer: ReturnType<typeof setTimeout> | null = null;
    let disposed = false;

    const connect = () => {
      if (disposed) return;
      statusRef.current?.("connecting");
      ws = new WebSocket(`${WS_URL}/ws`);
      ws.onopen = () => {
        retry = 0;
        statusRef.current?.("open");
      };
      ws.onmessage = (msg) => {
        try {
          cbRef.current(JSON.parse(msg.data) as FrontendEvent);
        } catch {
          // ignore non-JSON frames
        }
      };
      ws.onclose = () => {
        if (disposed) return;
        statusRef.current?.("closed");
        retry++;
        const delay = Math.min(1000 * 2 ** retry, 30000);
        timer = setTimeout(connect, delay);
      };
      ws.onerror = () => {
        ws?.close();
      };
    };

    connect();
    return () => {
      disposed = true;
      if (timer) clearTimeout(timer);
      ws?.close();
    };
  }, []);
}
