"""
Edit PDF sederhana: tempel TEKS dan GAMBAR ke halaman PDF.

- Font: diambil dari font yang terinstall di sistem device (fontconfig
  `fc-list` / `fc-match`) sehingga user bisa pakai font apa pun yang ada
  di laptopnya; fallback ke font bawaan PDF (Helvetica dkk).
- Warna teks: RGB 0..1 bebas (dipilih user via color picker di GUI).
- Posisi: titik koordinat PDF (pt) — GUI memetakannya dari klik pada
  preview halaman.
- Hasil selalu file baru (-edit.pdf) di sebelah aslinya, tidak menimpa.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pymupdf

from .converters import ConversionError, unique_output

FALLBACK_FONTS = ["Helvetica", "Times-Roman", "Courier", "DejaVu Sans"]


# ---------------------------------------------------------------- font sistem
def list_system_fonts() -> list[str]:
    """Daftar family font yang terinstall di device (via fontconfig)."""
    if shutil.which("fc-list"):
        try:
            proc = subprocess.run(["fc-list", ":", "family"],
                                  capture_output=True, text=True, timeout=15)
            fams = set()
            for line in proc.stdout.splitlines():
                for part in line.split(","):
                    part = part.strip()
                    if part:
                        fams.add(part)
            if fams:
                return sorted(fams)
        except Exception:
            pass
    return list(FALLBACK_FONTS)


def font_file_for(family: str) -> str | None:
    """File font (.ttf/.otf) untuk sebuah family, via fc-match."""
    if not family or family in ("Helvetica", "Times-Roman", "Courier"):
        return None  # font bawaan PDF, tak perlu file
    if shutil.which("fc-match"):
        try:
            proc = subprocess.run(["fc-match", "-f", "%{file}", family],
                                  capture_output=True, text=True, timeout=10)
            path = proc.stdout.strip()
            if path and Path(path).suffix.lower() in (".ttf", ".otf"):
                return path
        except Exception:
            pass
    return None


BASE14 = {
    "Helvetica": "helv", "Times-Roman": "tiro", "Courier": "cour",
}


# ---------------------------------------------------------------- operasi edit
def apply_ops(doc: pymupdf.Document, ops: list[dict]) -> None:
    """Terapkan daftar operasi ke dokumen (in-place)."""
    for op in ops:
        page = doc[op["page"]]
        if op["type"] == "text":
            family = op.get("font", "Helvetica")
            fontfile = font_file_for(family)
            if fontfile:
                fontname = "sysfont"
            else:
                fontname = BASE14.get(family, "helv")
            page.insert_text(
                pymupdf.Point(op["x"], op["y"]), op["text"],
                fontsize=float(op.get("size", 14)),
                fontname=fontname, fontfile=fontfile,
                color=tuple(op.get("color", (0, 0, 0))),
            )
        elif op["type"] == "image":
            rect = pymupdf.Rect(op["x"], op["y"],
                                op["x"] + op["w"], op["y"] + op["h"])
            page.insert_image(rect, filename=op["path"], keep_proportion=True)


def apply_edits(src: Path, ops: list[dict]) -> Path:
    """Terapkan operasi edit ke salinan PDF -> file -edit.pdf baru."""
    if not ops:
        raise ConversionError("Belum ada edit yang ditambahkan.")
    try:
        doc = pymupdf.open(src)
    except Exception as e:
        raise ConversionError(f"PDF tidak bisa dibuka: {e}") from e
    apply_ops(doc, ops)
    dest = unique_output(src, "pdf", "-edit")
    doc.save(dest, garbage=3, deflate=True)
    doc.close()
    return dest


def render_preview(src: Path, ops: list[dict], page_index: int,
                   width_px: int = 440) -> tuple[bytes, float, int]:
    """
    Render halaman (dengan operasi yang sudah ada diterapkan sementara)
    jadi PNG bytes. Return (png_bytes, zoom, page_count).
    """
    doc = pymupdf.open(src)
    apply_ops(doc, ops)
    page = doc[page_index]
    zoom = width_px / page.rect.width
    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
    data = pix.tobytes("png")
    count = doc.page_count
    doc.close()
    return data, zoom, count
