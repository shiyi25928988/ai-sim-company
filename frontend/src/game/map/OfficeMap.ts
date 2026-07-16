/**
 * Office tile map (see §10 scene layout).
 *
 * 30 cols x 20 rows, 32px each = 960x640. Furniture (wall/desk/meeting table/whiteboard/plant)
 * is an obstacle; the floor is walkable. Provides a walkable grid for EasyStar pathfinding;
 * deskSlots / meetingSlot are agent stand positions.
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
  /** Pathfinding grid: 0 = walkable, 1 = obstacle. */
  grid: number[][] = [];
  /** Pixel coords where an agent can stand in front of a desk (agent spawn point). */
  deskSlots: Point[] = [];
  /** Meeting room stand point (pixels). */
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
    // Outer walls
    for (let c = 0; c < COLS; c++) {
      this.place(0, c, "wall");
      this.place(ROWS - 1, c, "wall");
    }
    for (let r = 0; r < ROWS; r++) {
      this.place(r, 0, "wall");
      this.place(r, COLS - 1, "wall");
    }
    // Workstation area: desks at col [2,5,8,11] x row [2,5]; agent stands one tile below
    for (const c of [2, 5, 8, 11]) {
      for (const r of [2, 5]) {
        this.place(r, c, "desk");
        this.deskSlots.push(this.tileCenter(c, r + 1));
      }
    }
    // Meeting room: meeting table at row 2-3 x col 18-21
    for (let r = 2; r <= 3; r++) {
      for (let c = 18; c <= 21; c++) this.place(r, c, "table");
    }
    this.meetingSlot = this.tileCenter(20, 5);
    // Whiteboard area: row 17 x col 2-8
    for (let c = 2; c <= 8; c++) this.place(17, c, "whiteboard");
    // Lounge: plants at row 16 x col [22,24,26]
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
