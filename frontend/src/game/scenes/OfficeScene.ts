import Phaser from "phaser";
import { AgentSprite } from "../sprites/AgentSprite";
import { SpeechBubble } from "../sprites/SpeechBubble";
import { PathFinder } from "../pathfinding/PathFinder";
import { OfficeMap, TILE, type Point } from "../map/OfficeMap";
import { gameBridge } from "../bridge";
import type { AgentState, FrontendEvent } from "@/types/game";

// 角色 -> 身体配色
const ROLE_COLORS: Record<string, number> = {
  ceo: 0xffd700,
  "hr-director": 0xff6b9d,
  "senior-engineer": 0x4a9eff,
  "junior-engineer": 0x66ccff,
  designer: 0xb06bff,
};
const DEFAULT_COLOR = 0x66ccff;

// 家具配色
const TILE_COLORS: Record<string, number> = {
  wall: 0x3a3a5c,
  desk: 0x8a5a2b,
  table: 0x555577,
  whiteboard: 0xeeeeee,
  plant: 0x2e8b57,
};

/** 办公室主场景: tile 地板 + 家具 + Agent 像素小人 + 寻路移动。
 * 订阅 gameBridge 的 WS 事件来增删精灵、显示气泡、走到会议室。 */
export class OfficeScene extends Phaser.Scene {
  private officeMap = new OfficeMap();
  private pathfinder?: PathFinder;
  private agents = new Map<string, AgentSprite>(); // name -> sprite
  private bubbles = new Map<string, SpeechBubble>();
  private nextSlot = 0;
  private unsub?: () => void;

  constructor() {
    super("OfficeScene");
  }

  create(): void {
    this.cameras.main.setBackgroundColor("#0f0f1a");
    this.drawOffice();
    this.pathfinder = new PathFinder(this.officeMap.grid);

    this.unsub = gameBridge.onEvent((ev) => this.handleEvent(ev));
    this.events.once("shutdown", () => this.unsub?.());

    if (gameBridge.snapshot) this.reconcile(gameBridge.snapshot.agents);
  }

  private handleEvent(ev: FrontendEvent): void {
    switch (ev.type) {
      case "state_snapshot":
        this.reconcile(ev.agents);
        break;
      case "agent_created":
        this.spawn(ev.name, ev.role);
        break;
      case "agent_message":
        this.showBubble(ev.sender, ev.content);
        break;
      case "agent_action":
        this.showBubble(ev.agent, ev.action);
        break;
      case "meeting_start":
        this.moveToMeeting(ev.participants);
        break;
    }
  }

  /** 用快照里的 Agent 列表增删精灵。 */
  private reconcile(agents: AgentState[]): void {
    const names = new Set(agents.map((a) => a.name));
    for (const a of agents) {
      if (!this.agents.has(a.name)) this.spawn(a.name, a.role);
    }
    for (const [name, sprite] of this.agents) {
      if (!names.has(name)) {
        sprite.destroy();
        this.agents.delete(name);
        this.bubbles.get(name)?.destroy();
        this.bubbles.delete(name);
      }
    }
  }

  private spawn(name: string, role: string): AgentSprite | undefined {
    if (this.agents.has(name)) return this.agents.get(name);
    const slot = this.officeMap.deskSlots[this.nextSlot % this.officeMap.deskSlots.length];
    this.nextSlot++;
    const sprite = new AgentSprite(this, slot.x, slot.y, name, name);
    sprite.setColor(ROLE_COLORS[role] ?? DEFAULT_COLOR);
    this.add.existing(sprite);
    this.agents.set(name, sprite);
    // 入场动画
    sprite.setScale(0);
    this.tweens.add({ targets: sprite, scale: 1, duration: 300, ease: "Back.out" });
    return sprite;
  }

  /** 在精灵头顶显示对话气泡，4s 后淡出。 */
  private showBubble(name: string, content: string): void {
    const sprite = this.agents.get(name);
    if (!sprite) return;
    let bubble = this.bubbles.get(name);
    if (!bubble) {
      bubble = new SpeechBubble(this, sprite.x, sprite.y - 36, content);
      this.add.existing(bubble);
      this.bubbles.set(name, bubble);
    } else {
      bubble.setPosition(sprite.x, sprite.y - 36);
      bubble.setContent(content);
      bubble.setAlpha(1);
    }
    this.time.delayedCall(4000, () => {
      if (!bubble) return;
      this.tweens.add({
        targets: bubble,
        alpha: 0,
        duration: 400,
        onComplete: () => {
          bubble?.destroy();
          this.bubbles.delete(name);
        },
      });
    });
  }

  /** 参会者沿网格路径走到会议室。 */
  private async moveToMeeting(participants: string[]): Promise<void> {
    if (!this.pathfinder) return;
    const to = this.officeMap.pixelToTile(this.officeMap.meetingSlot.x, this.officeMap.meetingSlot.y);
    for (const name of participants) {
      const sprite = this.agents.get(name);
      if (!sprite) continue;
      const from = this.officeMap.pixelToTile(sprite.x, sprite.y);
      const path = await this.pathfinder.findPath(from.x, from.y, to.x, to.y);
      const wps: Point[] = path.map((p) => this.officeMap.tileCenter(p.x, p.y));
      sprite.walkPath(wps);
    }
  }

  /** 用单个 Graphics 画出 tile 地板 + 家具 (高效)。 */
  private drawOffice(): void {
    const g = this.add.graphics();
    const T = TILE;
    for (let r = 0; r < this.officeMap.rows; r++) {
      for (let c = 0; c < this.officeMap.cols; c++) {
        const type = this.officeMap.tiles[r][c];
        const x = c * T;
        const y = r * T;
        // 地板 (棋盘格)
        const shade = (c + r) % 2 === 0 ? 0x1a1a2e : 0x161627;
        g.fillStyle(shade, 1);
        g.fillRect(x, y, T, T);
        if (type !== "floor") {
          const color = TILE_COLORS[type] ?? 0x444466;
          g.fillStyle(color, 1);
          g.fillRect(x + 1, y + 1, T - 2, T - 2);
          if (type === "desk") {
            g.fillStyle(0xa9743f, 1); // 桌面高光
            g.fillRect(x + 4, y + 6, T - 8, 5);
          } else if (type === "plant") {
            g.fillStyle(0x6b3f1f, 1); // 花盆
            g.fillRect(x + T / 2 - 4, y + T - 12, 8, 8);
          } else if (type === "whiteboard") {
            g.fillStyle(0x888899, 1); // 边框
            g.lineStyle(2, 0x888899);
            g.strokeRect(x + 1, y + 1, T - 2, T - 2);
          }
        }
      }
    }
    // 区域标签
    const label = (x: number, y: number, t: string) =>
      this.add.text(x, y, t, { fontSize: "10px", color: "#6b7280" });
    label(40, 36, "工位区");
    label(18 * T + 8, 36, "会议室");
    label(40, 15 * T, "白板区");
    label(22 * T, 14 * T, "休闲区");
  }
}
