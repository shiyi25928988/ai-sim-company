/**
 * 办公室 tile 地图 (见 §十 场景布局)。
 *
 * 30 列 x 20 行，每格 32px = 960x640。家具 (墙/工位/会议桌/白板/植物) 是障碍物，
 * 地板可通行。提供 walkable grid 给 EasyStar 寻路；deskSlots / meetingSlot 给 Agent 站位。
 */

export const TILE = 32;
export const COLS = 30;
export const ROWS = 20;

export type TileType =
  | "floor" | "wall" | "desk" | "table" | "whiteboard" | "plant";

export interface Point {
  x: number;
  y: number;
}

export class OfficeMap {
  readonly tile = TILE;
  readonly cols = COLS;
  readonly rows = ROWS;

  tiles: TileType[][] = [];
  /** 寻路网格: 0=可通行, 1=障碍。 */
  grid: number[][] = [];
  /** 工位前可站立的像素坐标 (Agent 入职落点)。 */
  deskSlots: Point[] = [];
  /** 会议室落点 (像素)。 */
  meetingSlot: Point = { x: 0, y: 0 };

  constructor() {
    this.build();
  }

  private build(): void {
    for (let r = 0; r < ROWS; r++) {
      const tileRow: TileType[] = [];
      const gridRow: number[] = [];
      for (let c = 0; c < COLS; c++) {
        tileRow.push("floor");
        gridRow.push(0);
      }
      this.tiles.push(tileRow);
      this.grid.push(gridRow);
    }
    // 外墙
    for (let c = 0; c < COLS; c++) {
      this.place(0, c, "wall");
      this.place(ROWS - 1, c, "wall");
    }
    for (let r = 0; r < ROWS; r++) {
      this.place(r, 0, "wall");
      this.place(r, COLS - 1, "wall");
    }
    // 工位区: 工位在 col [2,5,8,11] x row [2,5]，Agent 站其下一格
    for (const c of [2, 5, 8, 11]) {
      for (const r of [2, 5]) {
        this.place(r, c, "desk");
        this.deskSlots.push(this.tileCenter(c, r + 1));
      }
    }
    // 会议室: 会议桌 row 2-3 x col 18-21
    for (let r = 2; r <= 3; r++) {
      for (let c = 18; c <= 21; c++) this.place(r, c, "table");
    }
    this.meetingSlot = this.tileCenter(20, 5);
    // 白板区: row 17 x col 2-8
    for (let c = 2; c <= 8; c++) this.place(17, c, "whiteboard");
    // 休闲区: 植物 row 16 x col [22,24,26]
    for (const c of [22, 24, 26]) this.place(16, c, "plant");
  }

  private place(r: number, c: number, type: TileType): void {
    if (r < 0 || r >= ROWS || c < 0 || c >= COLS) return;
    this.tiles[r][c] = type;
    this.grid[r][c] = type === "floor" ? 0 : 1;
  }

  tileCenter(c: number, r: number): Point {
    return { x: c * TILE + TILE / 2, y: r * TILE + TILE / 2 };
  }

  pixelToTile(x: number, y: number): Point {
    return { x: Math.floor(x / TILE), y: Math.floor(y / TILE) };
  }
}
