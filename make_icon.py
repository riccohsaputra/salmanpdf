"""
Ikon aplikasi SalmanPDF dari gambar referensi pilihan Ricco
(icon-source-ref.png, 2026-10-25): wajah chibi persis gambarnya,
background emas DIGANTI merah brand, sudut di luar kotak tetap
transparan, ditambah lencana putih bertuliskan "PDF" merah di
kanan-bawah (permintaan Ricco: "pake icon ini tapi background
merah" + "ada kata pdfnya").
Jalankan: .venv/bin/python make_icon.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

S = 1024
RED = (217, 35, 35, 255)
WHITE = (255, 255, 255, 255)
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

ROOT = Path(__file__).parent
OUT = ROOT / "salmanpdf" / "assets"


def build() -> Image.Image:
    src = Image.open(ROOT / "icon-source-ref.png").convert("RGBA")
    img = src.resize((S, S), Image.Resampling.LANCZOS)

    # Masker background emas: emas punya (R-B) besar (~168); kulit ~69,
    # pipi ~86, hitam/rambut ~0. Ramp mulai 100 -> kulit & pipi aman.
    r, _g, b, _a = img.split()
    diff = ImageChops.subtract(r, b)
    lut = [0 if i <= 100 else (255 if i >= 150 else int(255 * (i - 100) / 50))
           for i in range(256)]
    mask = diff.point(lut)
    red_bg = Image.new("RGBA", (S, S), RED)
    img = Image.composite(red_bg, img, mask)

    # Lencana PDF: putih, teks merah (kontras di atas bg merah & wajah)
    d = ImageDraw.Draw(img)
    bx0, by0, bx1, by1 = 588, 716, 972, 958
    d.rounded_rectangle([bx0 + 7, by0 + 9, bx1 + 7, by1 + 9], radius=54,
                        fill=(120, 10, 10, 130))
    d.rounded_rectangle([bx0, by0, bx1, by1], radius=54, fill=WHITE)
    font = ImageFont.truetype(FONT, 128)
    d.text(((bx0 + bx1) / 2, (by0 + by1) / 2 + 6), "PDF",
           font=font, fill=RED, anchor="mm")
    return img


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    master = build()
    master.save(OUT / "appicon-1024.png")
    for size in (512, 256, 128, 64, 48):
        master.resize((size, size), Image.Resampling.LANCZOS).save(
            OUT / f"appicon-{size}.png")
    (OUT / "appicon.png").write_bytes((OUT / "appicon-512.png").read_bytes())
    print("icons written to", OUT)


if __name__ == "__main__":
    main()
