// React <-> Phaser 的事件桥。
//
// useGameState 把 WS 事件转发到这里 (emit)，OfficeScene 订阅 (onEvent) 来
// 增删/移动精灵、显示气泡。反向: 点击精灵 -> select(name) -> React 选中该 Agent。
// 用单例而非 props 透传，因为 Phaser 场景不在 React 树内。

import type { FrontendEvent, GameSnapshot } from "@/types/game";

type EventHandler = (event: FrontendEvent) => void;
type SelectHandler = (name: string | null) => void;

class GameBridge {
  /** 最近一次快照 (供后挂载的 OfficeScene 立即渲染已有 Agent)。 */
  snapshot: GameSnapshot | null = null;

  private eventHandlers = new Set<EventHandler>();
  private selectHandlers = new Set<SelectHandler>();

  // WS 事件 -> Phaser
  onEvent(handler: EventHandler): () => void {
    this.eventHandlers.add(handler);
    return () => this.eventHandlers.delete(handler);
  }

  emit(event: FrontendEvent): void {
    this.eventHandlers.forEach((h) => h(event));
  }

  // Phaser 点击 -> React
  onSelect(handler: SelectHandler): () => void {
    this.selectHandlers.add(handler);
    return () => this.selectHandlers.delete(handler);
  }

  select(name: string | null): void {
    this.selectHandlers.forEach((h) => h(name));
  }
}

export const gameBridge = new GameBridge();
