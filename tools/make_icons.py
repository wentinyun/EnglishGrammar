"""从设计源图生成主屏幕 App 图标（iOS apple-touch-icon / Android manifest icons）。

用法：python tools/make_icons.py              # 默认读 docs/icon-source.png
     python tools/make_icons.py 路径/图.png    # 换一张图重出全部尺寸

规则：
- 自动裁掉白边，按内容原始比例居中放置，绝不拉伸变形
- 内容高占画布 78%：iOS 会自己加圆角，这个留白量保证笔画不被切
- 背景压成纯白 #FFFFFF（源图若为 #FEFEFE 这类近白，不压会和系统底色出现接缝）
- 另出一版 maskable（内容占 70%），供 Android 圆形/方形遮罩取用
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "public" / "icons"
PUB = ROOT / "web" / "public"
WHITE = (255, 255, 255)

ANY_FILL = 0.78
MASK_FILL = 0.74


def content_box(im: Image.Image) -> tuple[int, int, int, int]:
    """非白像素的外接框，阈值 245 以容忍 JPEG 噪点。"""
    rgb = im.convert("RGB")
    w, h = rgb.size
    px = rgb.load()
    xs: list[int] = []
    ys: list[int] = []
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            r, g, b = px[x, y]
            if r < 245 or g < 245 or b < 245:
                xs.append(x)
                ys.append(y)
    if not xs:
        raise SystemExit("源图里没有内容（整张全白）")
    return min(xs), min(ys), max(xs) + 1, max(ys) + 1


def render(src: Image.Image, size: int, fill: float) -> Image.Image:
    """把 src 按 fill（内容高度占画布的比例）居中画到 size×size 白底上。"""
    sw, sh = src.size
    scale = (size * fill) / sh
    tw, th = sw * scale, sh * scale
    if tw > size * 0.92:                    # 横图也不能顶到边
        scale = (size * 0.92) / sw
        tw, th = sw * scale, sh * scale
    inner = src.resize((max(1, round(tw)), max(1, round(th))), Image.LANCZOS)
    canvas = Image.new("RGB", (size, size), WHITE)
    canvas.paste(inner, (round((size - inner.width) / 2), round((size - inner.height) / 2)))
    return canvas


def main() -> None:
    src_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "icon-source.png"
    if not src_path.is_absolute():
        src_path = ROOT / src_path
    raw = Image.open(src_path).convert("RGB")
    src = raw.crop(content_box(raw))
    print(f"源图 {raw.size} → 内容 {src.size}")

    OUT.mkdir(parents=True, exist_ok=True)
    for name, size, fill in [
        ("icon-192-v2.png", 192, ANY_FILL),           # Android 主屏幕 / 安装
        ("icon-512-v2.png", 512, ANY_FILL),           # 安装弹窗 / 启动图
        ("icon-maskable-512-v2.png", 512, MASK_FILL), # Android 自适应遮罩
        ("favicon-32.png", 32, 0.94),                 # 标签页，小尺寸内容放大一点
    ]:
        img = render(src, size, fill)
        img.save(OUT / name, "PNG", optimize=True)
        print(f"  icons/{name:28s} {size}x{size}   {(OUT / name).stat().st_size / 1024:5.1f} KB")

    # iOS 强制探测根路径 /apple-touch-icon.png，必须放真图；
    # 否则 SPA fallback 会返回 index.html，iOS 拿到的是一段 HTML。
    for name in ("apple-touch-icon.png", "apple-touch-icon-precomposed.png"):
        img = render(src, 180, ANY_FILL)
        img.save(PUB / name, "PNG", optimize=True)
        print(f"  {name:28s} 180x180   {(PUB / name).stat().st_size / 1024:5.1f} KB")


if __name__ == "__main__":
    main()
