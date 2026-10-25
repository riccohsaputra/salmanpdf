"""
Generator ikon aplikasi SalmanPDF: wajah Shin-chan FACELESS (siluet
kepala + rambut hitam khas, tanpa mata/hidung/mulut) dengan lencana
PDF merah di pojok kanan-bawah. Digambar prosedural pakai Pillow di
kanvas 1024 lalu diturunkan ke ukuran ikon standar.
Jalankan: .venv/bin/python make_icon.py
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

S = 1024
SKIN = (248, 207, 163, 255)
SKIN_LINE = (214, 152, 92, 255)
HAIR = (32, 36, 42, 255)
CREAM = (255, 241, 222, 255)
CREAM_LINE = (240, 214, 170, 255)
RED = (217, 35, 35, 255)
RED_DARK = (178, 24, 24, 255)
WHITE = (255, 255, 255, 255)
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

OUT = Path(__file__).parent / "salmanpdf" / "assets"


def draw_icon() -> Image.Image:
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Latar: kotak membulat krem
    d.rounded_rectangle([28, 28, S - 28, S - 28], radius=210,
                        fill=CREAM, outline=CREAM_LINE, width=6)

    cx, cy, r = 500, 452, 292
    # Telinga
    for ex in (cx - r - 6, cx + r + 6):
        d.ellipse([ex - 58, cy + 18, ex + 58, cy + 134],
                  fill=SKIN, outline=SKIN_LINE, width=6)
    # Wajah (faceless: polos, tanpa fitur sama sekali)
    d.ellipse([cx - r, cy - r, cx + r, cy + r],
              fill=SKIN, outline=SKIN_LINE, width=6)

    # Rambut: topi hitam mengikuti lengkung kepala + poni bergelombang
    pts = []
    for a in range(180, 361, 4):  # busur atas kepala
        t = math.radians(a)
        pts.append((cx + r * math.cos(t), cy + r * math.sin(t)))
    for x in range(cx + r, cx - r - 1, -16):  # poni gelombang kanan->kiri
        wave = 14 * math.sin((x - (cx - r)) / 64.0)
        pts.append((x, cy - r * 0.34 + wave))
    d.polygon(pts, fill=HAIR)

    # Lencana PDF merah dengan pojok terlipat
    bx0, by0, bx1, by1 = 592, 606, 966, 962
    d.rounded_rectangle([bx0, by0, bx1, by1], radius=64,
                        fill=RED, outline=RED_DARK, width=6)
    fold = 62
    d.polygon([(bx1 - fold, by0), (bx1, by0 + fold), (bx1 - fold, by0 + fold)],
              fill=(255, 255, 255, 70))
    font = ImageFont.truetype(FONT, 148)
    d.text(((bx0 + bx1) / 2, (by0 + by1) / 2 + 8), "PDF",
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
