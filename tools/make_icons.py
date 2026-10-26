"""生成 PWA 图标（iOS 主屏 / Android 安装 / 站点图标）。

图形语言：从靛蓝到青绿的渐变底 + 三条递进的白条（对应四个层级的知识）+
右下角对勾（对应掌握）。全部为几何绘制，不依赖字体。
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "web" / "public" / "icons"

# 渐变端点
C1 = (95, 115, 255)
C2 = (52, 208, 190)


def _lerp(a: int, b: int, t: float) -> int:
    return round(a + (b - a) * t)


def _gradient(size: int) -> Image.Image:
    img = Image.new("RGB", (size, size), "#0d1016")
    px = img.load()
    for y in range(size):
        for x in range(size):
            t = (x / (size - 1) * 0.55 + y / (size - 1) * 0.45)
            t = max(0.0, min(1.0, t))
            px[x, y] = (
                _lerp(C1[0], C2[0], t),
                _lerp(C1[1], C2[1], t),
                _lerp(C1[2], C2[2], t),
            )
    return img


def draw_icon(size: int, radius_ratio: float = 0.0) -> Image.Image:
    base = _gradient(size)
    if radius_ratio:
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            [0, 0, size - 1, size - 1], radius=int(size * radius_ratio), fill=255
        )
        out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        out.paste(base, (0, 0), mask)
        base = out

    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    # 一条竖脊 + 三条递进白条 + 末端节点，读作「层级递进」
    spine_x = size * 0.255
    d.line(
        [(spine_x, size * 0.315), (spine_x, size * 0.700)],
        fill=(255, 255, 255, 110),
        width=max(2, int(size * 0.016)),
    )
    bars = [(0.315, 0.300, 0.245), (0.315, 0.470, 0.330), (0.315, 0.640, 0.415)]
    for left, top, width in bars:
        x0, y0 = size * left, size * top
        x1 = x0 + size * width
        h = size * 0.092
        d.rounded_rectangle([x0, y0, x1, y0 + h], radius=h / 2, fill=(255, 255, 255, 240))
        r = size * 0.036
        cx, cy = x1 + r * 0.85, y0 + h / 2
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 255, 255, 250))

    base = Image.alpha_composite(base.convert("RGBA"), layer)
    return base


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for size, name, r in [
        (192, "icon-192.png", 0.22),
        (512, "icon-512.png", 0.22),
        (512, "icon-maskable-512.png", 0.0),
        (180, "apple-touch-icon.png", 0.0),
        (32, "favicon-32.png", 0.18),
    ]:
        img = draw_icon(size, r)
        img.save(OUT / name, "PNG")
        print("wrote", (OUT / name).relative_to(OUT.parent.parent.parent), img.size)
    # 站点图标用同一个图形
    draw_icon(64, 0.2).save(OUT.parent / "favicon.png", "PNG")
    print("wrote favicon.png")


if __name__ == "__main__":
    main()
