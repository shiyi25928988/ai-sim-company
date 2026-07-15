import Phaser from "phaser";
import { gameBridge } from "../bridge";

/** Agent 精灵动画状态机 (见 §十): IDLE -> WALKING -> WORKING -> TALKING。 */
export enum AgentAnimState {
  Idle = "idle",
  Walking = "walking",
  Working = "working",
  Talking = "talking",
}

/**
 * Agent 像素小人: 头 + 身体 (角色配色) + 名牌。
 * 容器 (this) 由 walkPath 移动；内部 char 容器做呼吸/走路 bob 动画 (互不冲突)。
 * 点击 -> gameBridge.select(name) -> React 选中。
 */
export class AgentSprite extends Phaser.GameObjects.Container {
  readonly agentId: string;
  readonly name: string;
  private animState: AgentAnimState = AgentAnimState.Idle;
  private readonly char: Phaser.GameObjects.Container;
  private readonly bodyRect: Phaser.GameObjects.Rectangle;
  private readonly head: Phaser.GameObjects.Rectangle;
  private readonly label: Phaser.GameObjects.Text;
  private bobTween?: Phaser.Tweens.Tween;

  constructor(scene: Phaser.Scene, x: number, y: number, agentId: string, name: string) {
    super(scene, x, y);
    this.agentId = agentId;
    this.name = name;

    this.char = scene.add.container(0, 0);
    this.bodyRect = scene.add.rectangle(0, 4, 16, 16, 0x66ccff);
    this.bodyRect.setOrigin(0.5);
    this.head = scene.add.rectangle(0, -8, 12, 12, 0xf1c27d); // 肤色
    this.head.setOrigin(0.5);
    this.char.add([this.head, this.bodyRect]);

    this.label = scene.add
      .text(0, 22, name, { fontSize: "9px", color: "#e5e7eb" })
      .setOrigin(0.5);

    this.add([this.char, this.label]);
    this.setSize(24, 32);

    // 点击选中 (整个小人范围)
    this.setInteractive(new Phaser.Geom.Rectangle(0, -12, 24, 34), Phaser.Geom.Rectangle.Contains);
    this.on("pointerup", () => gameBridge.select(this.name));
    this.on("pointerover", () => this.setScale(1.12));
    this.on("pointerout", () => this.setScale(1));

    this.startIdle();
  }

  getAnimState(): AgentAnimState {
    return this.animState;
  }

  setAnimState(state: AgentAnimState): void {
    if (state === this.animState) return;
    this.animState = state;
    this.bobTween?.stop();
    if (state === AgentAnimState.Walking) {
      // 走路: 快速上下 bob
      this.bobTween = this.scene.tweens.add({
        targets: this.char, y: -3, duration: 140, yoyo: true, repeat: -1, ease: "Sine.inOut",
      });
    } else {
      // idle / working: 慢呼吸
      this.bobTween = this.scene.tweens.add({
        targets: this.char, y: -2, duration: 900, yoyo: true, repeat: -1, ease: "Sine.inOut",
      });
    }
  }

  private startIdle(): void {
    this.setAnimState(AgentAnimState.Idle);
  }

  /** 沿网格路径走 (waypoints 为像素坐标)，走完回 idle。 */
  walkPath(waypoints: { x: number; y: number }[], onDone?: () => void): void {
    if (waypoints.length === 0) {
      this.setAnimState(AgentAnimState.Idle);
      onDone?.();
      return;
    }
    this.setAnimState(AgentAnimState.Walking);
    const wp = waypoints[0];
    this.scene.tweens.add({
      targets: this,
      x: wp.x,
      y: wp.y,
      duration: 260,
      ease: "Linear",
      onComplete: () => this.walkPath(waypoints.slice(1), onDone),
    });
  }

  /** 直线走到目标 (无寻路时的简单移动)。 */
  moveToPos(targetX: number, targetY: number): void {
    this.walkPath([{ x: targetX, y: targetY }]);
  }

  setColor(color: number): void {
    this.bodyRect.setFillStyle(color);
  }
}
