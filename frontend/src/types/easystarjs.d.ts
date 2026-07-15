// easystarjs 没有官方类型声明，这里给出最小可用声明。
declare module "easystarjs" {
  export class js {
    setGrid(grid: number[][]): void;
    setAcceptableTiles(tiles: number[]): void;
    enableDiagonals(): void;
    setIterationsPerCalculation(iterations: number): void;
    findPath(
      startX: number,
      startY: number,
      endX: number,
      endY: number,
      callback: (path: { x: number; y: number }[]) => void,
    ): void;
    calculate(): void;
  }
}
