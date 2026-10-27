"""
Ikon aplikasi SalmanPDF = gambar pilihan Ricco
(glyph dokumen garis hitam tebal di atas transparan).

Sumber ikon, urutan prioritas:
1. icon-source-ref.png di root repo, bila ada (pemakaian lokal).
2. Data tertanam di salmanpdf/icon_data.py (base64) — jalur ini yang
   terpakai di GitHub Actions, karena berkas PNG biner tidak ikut
   terunggah ke repo (snapshot push hanya menerima file teks), jadi
   icon-source-ref.png memang tidak ada di checkout CI.

Script menurunkan master ke ukuran ikon standar + .ico Windows.
Jalankan: .venv/bin/python make_icon.py
"""
from __future__ import annotations

import base64
import io
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).parent
OUT = ROOT / "salmanpdf" / "assets"


def load_master() -> Image.Image:
    src = ROOT / "icon-source-ref.png"
    if src.exists():
        return Image.open(src).convert("RGBA")
    from salmanpdf.icon_data import APPICON_PNG_B64
    return Image.open(io.BytesIO(base64.b64decode(APPICON_PNG_B64))).convert("RGBA")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    master = load_master()
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
