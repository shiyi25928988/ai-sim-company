import Phaser from "phaser";

/** 会议室特写场景 (会议进行时切入)。 */
export class MeetingScene extends Phaser.Scene {
  constructor() {
    super("MeetingScene");
  }

  create(): void {
    this.cameras.main.setBackgroundColor("#15152a");
    this.add.text(480, 80, "会议进行中…", {
      fontSize: "24px",
      color: "#fff",
    }).setOrigin(0.5);

    // TODO: 排列参会者座位 + 显示实时发言气泡
  }
}
