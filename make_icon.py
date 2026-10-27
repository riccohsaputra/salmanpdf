"""
Ikon aplikasi SalmanPDF = gambar pilihan Ricco persis apa adanya
(icon-source-ref.png, 2026-10-25): glyph dokumen garis hitam tebal
di atas transparan. Script ini hanya menurunkannya ke ukuran ikon
standar. Ganti file sumbernya kalau mau ganti ikon.
Jalankan: .venv/bin/python make_icon.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).parent
OUT = ROOT / "salmanpdf" / "assets"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    master = Image.open(ROOT / "icon-source-ref.png").convert("RGBA")
    if master.size != (1024, 1024):
        master = master.resize((1024, 1024), Image.Resampling.LANCZOS)
    master.save(OUT / "appicon-1024.png")
    for size in (512, 256, 128, 64, 48):
        master.resize((size, size), Image.Resampling.LANCZOS).save(
            OUT / f"appicon-{size}.png")
    (OUT / "appicon.png").write_bytes((OUT / "appicon-512.png").read_bytes())
    # .ico multi-ukuran untuk build Windows (PyInstaller --icon)
    master.save(OUT / "appicon.ico", format="ICO",
                sizes=[(16, 16), (32, 32), (48, 48), (64, 64),
                       (128, 128), (256, 256)])
    print("icons written to", OUT)


if __name__ == "__main__":
    main()
