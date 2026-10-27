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


# ---------------------------------------------------------- susunan & seleksi
def op_bbox(op: dict) -> tuple[float, float, float, float]:
    """Kotak batas op dalam koordinat titik PDF (x0, y0, x1, y1).
    Teks: titik sisip adalah awal baseline, jadi kotak naik sebesar
    ukuran font ke atas."""
    x, y = float(op["x"]), float(op["y"])
    if op["type"] == "image":
        return (x, y, x + float(op["w"]), y + float(op["h"]))
    size = float(op.get("size", 14))
    w = float(op.get("w", 0)) or len(op.get("text", "")) * size * 0.52
    return (x, y - size, x + w, y + size * 0.35)


def hit_test(ops: list[dict], page: int, x: float, y: float) -> int | None:
    """Indeks op PALING ATAS di halaman `page` yang kotaknya memuat titik
    (x, y), atau None. Urutan gambar = urutan daftar: yang terakhir
    digambar paling atas."""
    for i in range(len(ops) - 1, -1, -1):
        op = ops[i]
        if op["page"] != page:
            continue
        x0, y0, x1, y1 = op_bbox(op)
        if x0 <= x <= x1 and y0 <= y <= y1:
            return i
    return None


def move_op(ops: list[dict], idx: int, mode: str) -> int:
    """Geser urutan gambar satu op; hanya relatif terhadap op di halaman
    yang sama. mode: 'front' (paling depan), 'back' (paling belakang),
    'forward' (maju selangkah), 'backward' (mundur selangkah).
    Return: indeks op setelah dipindah."""
    op = ops[idx]
    page = op["page"]
    same = [i for i, o in enumerate(ops) if o["page"] == page]
    pos = same.index(idx)
    if mode == "forward" and pos < len(same) - 1:
        j = same[pos + 1]
        ops[idx], ops[j] = ops[j], ops[idx]
        return j
    if mode == "backward" and pos > 0:
        j = same[pos - 1]
        ops[idx], ops[j] = ops[j], ops[idx]
        return j
    if mode == "front" and pos < len(same) - 1:
        ops.pop(idx)
        rest = [i for i, o in enumerate(ops) if o["page"] == page]
        at = rest[-1] + 1 if rest else len(ops)
        ops.insert(at, op)
        return at
    if mode == "back" and pos > 0:
        ops.pop(idx)
        rest = [i for i, o in enumerate(ops) if o["page"] == page]
        at = rest[0] if rest else 0
        ops.insert(at, op)
        return at
    return idx
