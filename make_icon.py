"""
Generator ikon aplikasi SalmanPDF — gaya referensi Ricco (2026-10-25):
wajah chibi Shin-chan besar memenuhi bingkai, latar kuning keemasan,
rambut hitam dengan DUA jambul tebal khas di poni, pipi merah muda,
senyum kecil, outline hitam tebal — plus lencana merah bertuliskan PDF.
Digambar prosedural pakai Pillow di kanvas 1024.
Jalankan: .venv/bin/python make_icon.py
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

S = 1024
GOLD = (243, 183, 63, 255)
SKIN = (255, 215, 184, 255)
BLACK = (26, 26, 26, 255)
HAIR = (30, 30, 30, 255)
BLUSH = (244, 158, 158, 255)
BROWN = (166, 102, 40, 255)
RED = (217, 35, 35, 255)
RED_DARK = (168, 20, 20, 255)
WHITE = (255, 255, 255, 255)
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

OUT = Path(__file__).parent / "salmanpdf" / "assets"


def draw_icon() -> Image.Image:
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Latar kuning keemasan memenuhi bingkai
    d.rounded_rectangle([0, 0, S, S], radius=190, fill=GOLD)

    cx, cy, rx, ry = 498, 516, 356, 336
    # Telinga kanan & kiri (di belakang wajah, menempel rapat)
    for ex in (cx - rx + 2, cx + rx - 2):
        d.ellipse([ex - 76, cy + 14, ex + 76, cy + 166],
                  fill=SKIN, outline=BLACK, width=15)
    # Wajah bulat besar, outline hitam tebal
    d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry],
              fill=SKIN, outline=BLACK, width=16)

    # Rambut: topi hitam + poni DUA JAMBUL tebal khas Shin-chan.
    # Digambar di layer terpisah lalu DIPOTONG masker elips wajah —
    # tanpa masker, ujung busurnya menyembul jadi balok hitam di sisi
    # kepala (cacat di draf pertama).
    hair_layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    hd = ImageDraw.Draw(hair_layer)
    pts = []
    for a in range(180, 361, 3):
        t = math.radians(a)
        pts.append((cx + (rx + 30) * math.cos(t), cy + (ry + 30) * math.sin(t)))
    for x in range(cx + rx, cx - rx - 1, -8):
        y = (cy - ry * 0.52
             + 92 * math.exp(-((x - (cx - 104)) / 80) ** 2)
             + 92 * math.exp(-((x - (cx + 104)) / 80) ** 2))
        pts.append((x, y))
    hd.polygon(pts, fill=HAIR)
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).ellipse([cx - rx, cy - ry, cx + rx, cy + ry],
                                 fill=255)
    hair_layer.putalpha(ImageChops.multiply(hair_layer.getchannel("A"), mask))
    img.alpha_composite(hair_layer)
    d = ImageDraw.Draw(img)

    # Pipi merah muda
    for bx in (cx - 218, cx + 218):
        d.ellipse([bx - 62, cy + 118, bx + 62, cy + 182], fill=BLUSH)
    # Senyum kecil
    d.arc([cx - 52, cy + 168, cx + 52, cy + 238], start=25, end=155,
          fill=BROWN, width=11)

    # Lencana PDF merah di kanan-bawah
    bx0, by0, bx1, by1 = 588, 716, 972, 958
    d.rounded_rectangle([bx0, by0, bx1, by1], radius=54,
                        fill=RED, outline=WHITE, width=9)
    fold = 54
    d.polygon([(bx1 - fold, by0 + 6), (bx1 - 6, by0 + fold),
               (bx1 - fold, by0 + fold)], fill=(255, 255, 255, 80))
    font = ImageFont.truetype(FONT, 128)
    d.text(((bx0 + bx1) / 2, (by0 + by1) / 2 + 6), "PDF",
           font=font, fill=WHITE, anchor="mm")
    return img


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    master = draw_icon()
    master.save(OUT / "appicon-1024.png")
    for size in (512, 256, 128, 64, 48):
        master.resize((size, size), Image.Resampling.LANCZOS).save(
            OUT / f"appicon-{size}.png")
    (OUT / "appicon.png").write_bytes((OUT / "appicon-512.png").read_bytes())
    print("icons written to", OUT)


if __name__ == "__main__":
    main()
