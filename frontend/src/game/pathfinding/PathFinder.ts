import * as EasyStar from "easystarjs";

/** A* 寻路封装 (EasyStar.js) - Agent 在办公室中走动 (见 §十)。 */
export class PathFinder {
  private readonly easystar: EasyStar.js;

  constructor(grid: number[][]) {
    this.easystar = new EasyStar.js();
    this.easystar.setGrid(grid);
    this.easystar.setAcceptableTiles([0]); // 0 = 可通行
    this.easystar.enableDiagonals();
  }

  /** 异步计算路径; 返回格子坐标列表。 */
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
