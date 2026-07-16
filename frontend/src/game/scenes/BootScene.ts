import Phaser from "phaser";

/** Load pixel sprites / tilesets / audio, then switch to the main office scene. */
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
