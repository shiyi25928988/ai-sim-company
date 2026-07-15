import Phaser from "phaser";

/** 加载像素精灵 / 图块集 / 音效，然后切换到办公室主场景。 */
export class BootScene extends Phaser.Scene {
  constructor() {
    super("BootScene");
  }

  preload(): void {
    // TODO: this.load.spritesheet("agent", "/assets/sprites/agent.png", { frameWidth: 32, frameHeight: 32 });
    // TODO: this.load.image("office-tiles", "/assets/tilesets/office.png");
    // TODO: this.load.audio("message", "/assets/audio/message.mp3");
  }

  create(): void {
    this.scene.start("OfficeScene");
  }
}
