import Phaser from "phaser";
import { BootScene } from "./scenes/BootScene";
import { OfficeScene } from "./scenes/OfficeScene";
import { MeetingScene } from "./scenes/MeetingScene";

/**
 * 创建 Phaser 3 像素风办公室游戏实例。
 * 场景: Boot (加载资源) -> Office (主办公室) + Meeting (会议室特写)。
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
