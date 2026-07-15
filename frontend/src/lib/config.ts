// 前端运行时配置 - 后端 API / WebSocket 地址。
// 本地开发默认 localhost:8000; docker compose 通过 NEXT_PUBLIC_* 注入。

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export const WS_URL =
  process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000";
