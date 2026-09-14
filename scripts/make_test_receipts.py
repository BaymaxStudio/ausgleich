#!/usr/bin/env python3
"""生成 test-prompts.json 用的合成支付截图（不含任何真实账单）。

    python3 scripts/make_test_receipts.py

产物在 examples/evals/：
    receipt-cny-dinner.png     微信支付 ¥100.00 海底捞
    receipt-cny-taxi.png       ¥40.00 滴滴出行
    receipt-hkd-hotpot.png     HK$428.00 海底捞
    receipt-cny-starbucks.png  ¥68.00 星巴克
    receipt-blurry-taxi.png    金额模糊（88 与 38 难辨），用于测「压低置信度」

界面为模拟样式，纯合成数据，可公开分发与复现。
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "examples" / "evals"
FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Songti.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]


def font(size):
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def wechat(amount, merchant, when, accent=(7, 193, 96)):
    w, h = 460, 600
    im = Image.new("RGB", (w, h), (245, 246, 248))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, w, 90], fill=accent)
    d.text((28, 32), "\u5fae\u4fe1\u652f\u4ed8", font=font(26), fill=(255, 255, 255))
    d.text((w // 2, 150), "\u652f\u4ed8\u6210\u529f", font=font(22), fill=(120, 120, 120), anchor="mm")
    d.text((w // 2, 230), amount, font=font(52), fill=(20, 20, 20), anchor="mm")
    d.line([40, 300, w - 40, 300], fill=(225, 225, 225))
    d.text((40, 330), "\u5546\u6237\u540d\u79f0", font=font(18), fill=(150, 150, 150))
    d.text((w - 40, 330), merchant, font=font(20), fill=(30, 30, 30), anchor="ra")
    d.text((40, 390), "\u652f\u4ed8\u65f6\u95f4", font=font(18), fill=(150, 150, 150))
    d.text((w - 40, 390), when, font=font(20), fill=(30, 30, 30), anchor="ra")
    d.text((40, 450), "\u652f\u4ed8\u65b9\u5f0f", font=font(18), fill=(150, 150, 150))
    d.text((w - 40, 450), "\u96f6\u94b1", font=font(20), fill=(30, 30, 30), anchor="ra")
    return im


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    items = {
        "receipt-cny-dinner.png": wechat("\u00a5100.00", "\u6d77\u5e95\u635e", "2026-09-01 19:24"),
        "receipt-cny-taxi.png": wechat("\u00a540.00", "\u6ef4\u6ef4\u51fa\u884c", "2026-09-01 22:05"),
        "receipt-hkd-hotpot.png": wechat("HK$428.00", "\u6d77\u5e95\u635e", "2026-09-01 20:10"),
        "receipt-cny-starbucks.png": wechat("\u00a568.00", "\u661f\u5df4\u514b", "2026-09-01 15:40"),
    }
    for name, im in items.items():
        im.save(OUT / name)
        print("wrote", (OUT / name).relative_to(ROOT))

    blurry = wechat("\u00a588.00", "\u6ef4\u6ef4\u51fa\u884c", "2026-09-02 08:12")
    blurry = blurry.filter(ImageFilter.GaussianBlur(radius=3.2))
    blurry.save(OUT / "receipt-blurry-taxi.png")
    print("wrote", (OUT / "receipt-blurry-taxi.png").relative_to(ROOT))


if __name__ == "__main__":
    main()
