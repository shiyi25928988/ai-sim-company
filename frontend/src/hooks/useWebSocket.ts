"use client";

import { useEffect, useRef } from "react";
import { WS_URL } from "@/lib/config";
import type { FrontendEvent } from "@/types/game";

/**
 * 连接 Company Hub 的 WebSocket，把收到的渲染事件交给回调。
 * 地址来自 NEXT_PUBLIC_WS_URL (默认 ws://localhost:8000)。
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
        // 忽略非 JSON 帧
      }
    };

    return () => ws.close();
  }, []);
}
