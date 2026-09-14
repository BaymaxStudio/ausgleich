#!/usr/bin/env python3
"""把离线结算 demo 的真实终端输出渲染成 GIF。

    python3 scripts/make_gif.py

产物：docs/demo.gif
内容来自 make_demo.py 的同一份合成数据与同一套结算口径，不是摆拍；
改动 demo 数据后重跑本脚本即可重录。

依赖 Pillow（pip install Pillow）；找不到中文字体时回退到默认字体。
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from make_demo import LEDGER, RECORDS, terminal_text  # noqa: E402
from settlement import settle  # noqa: E402

W, H = 900, 440
BG = (13, 17, 23)
PANEL = (22, 27, 34)
FG = (201, 209, 217)
GREEN = (63, 185, 80)
MUTED = (139, 148, 158)
FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Songti.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]


def load_font(size):
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def frame(lines):
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([16, 16, W - 16, H - 16], radius=14, fill=PANEL)
    for i, color in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        draw.ellipse([36 + i * 22, 34, 48 + i * 22, 46], fill=color)
    draw.text((110, 31), "ausgleich  ·  scripts/make_demo.py", font=load_font(18), fill=MUTED)
    y = 84
    for line in lines:
        fill = GREEN if line.startswith("→") else FG
        size = 24 if line.startswith("→") else 21
        draw.text((46, y), line, font=load_font(size), fill=fill)
        y += 34
    return img


def main():
    result = settle(RECORDS, LEDGER["payers"])
    body = ["$ python3 scripts/make_demo.py", ""] + terminal_text(result).split("\n")
    frames = [frame(body[: i + 1]) for i in range(len(body))]
    frames.append(frame(body))
    out = ROOT / "docs" / "demo.gif"
    frames[0].save(out, save_all=True, append_images=frames[1:], duration=650, loop=0, disposal=2)
    print("已写入", out.relative_to(ROOT), f"({out.stat().st_size // 1024} KB, {len(frames)} 帧)")


if __name__ == "__main__":
    main()
