import Phaser from "phaser";
import { BootScene } from "./scenes/BootScene";
import { OfficeScene } from "./scenes/OfficeScene";
import { MeetingScene } from "./scenes/MeetingScene";

/**
 * Create a Phaser 3 pixel-art office game instance.
 * Scenes: Boot (load assets) -> Office (main office) + Meeting (meeting room close-up).
 */
export function createGame(parent: HTMLElement): Phaser.Game {
  return new Phaser.Game({
    parent,
    type: Phaser.AUTO,
    pixelArt: true,
    scale: {
      mode: Phaser.Scale.FIT,
      autoCenter: Phaser.Scale.CENTER_BOTH,
      width: 960,
      height: 640,
    },
    backgroundColor: "#0f0f1a",
    scene: [BootScene, OfficeScene, MeetingScene],
  });
}
