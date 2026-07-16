// React <-> Phaser event bridge.
//
// useGameState forwards WS events here (emit); OfficeScene subscribes (onEvent) to
// add/remove/move sprites and show bubbles. Reverse: sprite click -> select(name) ->
// React selects that agent.
// Uses a singleton rather than prop drilling, because Phaser scenes live outside the React tree.

import type { FrontendEvent, GameSnapshot } from "@/types/game";

type EventHandler = (event: FrontendEvent) => void;
type SelectHandler = (name: string | null) => void;

class GameBridge {
  /** Most recent snapshot (lets a late-mounted OfficeScene render existing agents immediately). */
  snapshot: GameSnapshot | null = null;

  private eventHandlers = new Set<EventHandler>();
  private selectHandlers = new Set<SelectHandler>();

  // WS events -> Phaser
  onEvent(handler: EventHandler): () => void {
    this.eventHandlers.add(handler);
    return () => this.eventHandlers.delete(handler);
  }

  emit(event: FrontendEvent): void {
    this.eventHandlers.forEach((h) => h(event));
  }

  // Phaser click -> React
  onSelect(handler: SelectHandler): () => void {
    this.selectHandlers.add(handler);
    return () => this.selectHandlers.delete(handler);
  }

  select(name: string | null): void {
    this.selectHandlers.forEach((h) => h(name));
  }
}

export const gameBridge = new GameBridge();
