"""生成 Agent 像素精灵图 (spritesheet) - 见 §十 AgentSprite。

输出 frontend/public/assets/sprites/agent.png: 4 帧 32x32 (idle1, idle2, walk1, walk2)，
横向排列 = 128x32。角色为浅色填充 + 深色描边/眼睛/鞋，运行时用 setTint 上角色色。
透明背景。可用 `python scripts/gen_agent_sprite.py` 重新生成。
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

W = H = 32
FRAMES = 4

OUTLINE = (20, 20, 35, 255)   # 深色描边
FILL = (210, 210, 220, 255)   # 浅色填充 (供 tint)
DARK = (35, 35, 55, 255)      # 头发/眼睛/鞋


def draw_char(d: ImageDraw.ImageDraw, ox: int, bob: int = 0, ll: int = 0, rl: int = 0) -> None:
    """画一帧角色。ox=帧 x 偏移; bob=身体上下抖动; ll/rl=左右腿 x 偏移 (走路)。"""
    y = bob
    # 头发
    d.rectangle([ox + 11, 3 + y, ox + 20, 4 + y], fill=DARK)
    # 头
    d.rectangle([ox + 11, 4 + y, ox + 20, 13 + y], outline=OUTLINE, fill=FILL)
    # 眼睛
    d.rectangle([ox + 13, 8 + y, ox + 14, 9 + y], fill=DARK)
    d.rectangle([ox + 17, 8 + y, ox + 18, 9 + y], fill=DARK)
    # 身体
    d.rectangle([ox + 10, 14 + y, ox + 21, 22 + y], outline=OUTLINE, fill=FILL)
    # 腰带
    d.rectangle([ox + 10, 21 + y, ox + 21, 22 + y], fill=DARK)
    # 手臂
    d.rectangle([ox + 8, 14 + y, ox + 9, 21 + y], fill=FILL)
    d.rectangle([ox + 22, 14 + y, ox + 23, 21 + y], fill=FILL)
    # 腿 (走路时左右交替)
    d.rectangle([ox + 12 + ll, 23 + y, ox + 15 + ll, 29 + y], outline=OUTLINE, fill=FILL)
    d.rectangle([ox + 16 + rl, 23 + y, ox + 19 + rl, 29 + y], outline=OUTLINE, fill=FILL)
    # 鞋
    d.rectangle([ox + 12 + ll, 29 + y, ox + 15 + ll, 30 + y], fill=DARK)
    d.rectangle([ox + 16 + rl, 29 + y, ox + 19 + rl, 30 + y], fill=DARK)


def main() -> None:
    img = Image.new("RGBA", (W * FRAMES, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    draw_char(d, 0, bob=0, ll=0, rl=0)        # idle1
    draw_char(d, W, bob=1, ll=0, rl=0)        # idle2 (微抖)
    draw_char(d, W * 2, bob=0, ll=-1, rl=1)   # walk1 (左腿前)
    draw_char(d, W * 3, bob=1, ll=1, rl=-1)   # walk2 (右腿前)
    out = Path("frontend/public/assets/sprites/agent.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    print(f"saved {out} ({img.size[0]}x{img.size[1]})")


if __name__ == "__main__":
    main()
