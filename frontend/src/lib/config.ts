// Frontend runtime config - backend API / WebSocket URLs.
// Local dev defaults to localhost:8000; docker compose injects via NEXT_PUBLIC_*.

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export const WS_URL =
  process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000";
