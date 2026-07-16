import * as EasyStar from "easystarjs";

/** A* pathfinding wrapper (EasyStar.js) - agents walking around the office (see §10). */
export class PathFinder {
  private readonly easystar: EasyStar.js;

  constructor(grid: number[][]) {
    this.easystar = new EasyStar.js();
    this.easystar.setGrid(grid);
    this.easystar.setAcceptableTiles([0]); // 0 = walkable
    this.easystar.enableDiagonals();
  }

  /** Compute a path asynchronously; returns a list of tile coords. */
  findPath(
    fromX: number,
    fromY: number,
    toX: number,
    toY: number,
  ): Promise<{ x: number; y: number }[]> {
    return new Promise((resolve) => {
      this.easystar.findPath(fromX, fromY, toX, toY, (path) => resolve(path ?? []));
      this.easystar.calculate();
    });
  }
}
