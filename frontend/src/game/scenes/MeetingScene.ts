import Phaser from "phaser";

/** Meeting room close-up scene (switched to while a meeting is in progress). */
export class MeetingScene extends Phaser.Scene {
  constructor() {
    super("MeetingScene");
  }

  create(): void {
    this.cameras.main.setBackgroundColor("#15152a");
    this.add.text(480, 80, "Meeting in progress…", {
      fontSize: "24px",
      color: "#fff",
    }).setOrigin(0.5);

    // TODO: arrange participant seats + show real-time speech bubbles
  }
}
