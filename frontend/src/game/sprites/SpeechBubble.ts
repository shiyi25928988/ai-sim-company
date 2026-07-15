import Phaser from "phaser";

/** Agent 头顶对话气泡 (见 §十 💬 气泡)。 */
export class SpeechBubble extends Phaser.GameObjects.Container {
  private readonly background: Phaser.GameObjects.Graphics;
  private readonly text: Phaser.GameObjects.Text;

  constructor(scene: Phaser.Scene, x: number, y: number, content: string) {
    super(scene, x, y);
    this.background = scene.add.graphics();
    this.text = scene.add
      .text(0, 0, content, { fontSize: "11px", color: "#0f0f1a", wordWrap: { width: 140 } })
      .setOrigin(0.5);
    this.add([this.background, this.text]);
    this.drawBubble();
  }

  setContent(content: string): void {
    this.text.setText(content);
    this.drawBubble();
  }

  private drawBubble(): void {
    const bounds = this.text.getBounds();
    const pad = 6;
    const w = bounds.width + pad * 2;
    const h = bounds.height + pad * 2;
    this.background.clear();
    this.background.fillStyle(0xffffff, 0.95);
    this.background.fillRoundedRect(-w / 2, -h / 2, w, h, 4);
    this.background.lineStyle(2, 0x000000);
    this.background.strokeRoundedRect(-w / 2, -h / 2, w, h, 4);
  }
}
