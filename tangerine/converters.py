"""
Mesin konversi lokal Tangerine Linux v1.

Semua konversi jalan lokal (tanpa upload):
- PDF  <-> gambar : PyMuPDF (render) + Pillow
- Gambar -> PDF   : Pillow
- PDF  -> TXT     : PyMuPDF text extraction (bukan OCR)
- Video/audio     : ffmpeg (jika terinstall)
- TXT  -> PDF     : PyMuPDF

Aturan output (meniru Tangerine asli):
- Hasil selalu disimpan DI SEBELAH file asli.
- Tidak pernah menimpa file yang sudah ada -> tambah suffix (1), (2), ...
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pymupdf
from PIL import Image

PDF_DPI = 200  # render PDF -> gambar

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif", ".gif"}
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".avi"}
AUDIO_EXTS = {".mp3", ".wav", ".ogg", ".flac", ".m4a", ".opus"}
TEXT_EXTS = {".txt", ".md"}


class ConversionError(Exception):
    """Error konversi yang aman ditampilkan ke user (Bahasa Indonesia)."""


def detect_kind(path: Path) -> str | None:
    ext = path.suffix.lower()
    if ext == ".pdf":
        return "pdf"
    if ext in IMAGE_EXTS:
        return "image"
    if ext in VIDEO_EXTS:
        return "video"
    if ext in AUDIO_EXTS:
        return "audio"
    if ext in TEXT_EXTS:
        return "text"
    return None


# Tabel routing: tipe input -> format output yang ditawarkan wheel.
ROUTES: dict[str, list[str]] = {
    "pdf": ["JPG", "PNG", "TXT"],
    "image": ["JPG", "PNG", "WEBP", "PDF"],
    "video": ["MP3", "GIF", "WAV"],
    "audio": ["MP3", "WAV", "OGG"],
    "text": ["PDF"],
}


def formats_for(path: Path) -> list[str]:
    """Format wheel untuk satu file (format yang sama dgn aslinya dibuang)."""
    kind = detect_kind(path)
    if kind is None:
        return []
    own = path.suffix.lower().lstrip(".").replace("jpeg", "jpg")
    return [f for f in ROUTES[kind] if f.lower() != own]


def unique_output(src: Path, new_ext: str, stem_suffix: str = "") -> Path:
    """Path output di folder yang sama, tidak pernah menimpa file lain."""
    stem = src.stem + stem_suffix
    candidate = src.with_name(f"{stem}.{new_ext.lower()}")
    n = 1
    while candidate.exists():
        candidate = src.with_name(f"{stem} ({n}).{new_ext.lower()}")
        n += 1
    return candidate


# ---------------------------------------------------------------- PDF
def pdf_to_images(src: Path, fmt: str) -> list[Path]:
    out: list[Path] = []
    try:
        doc = pymupdf.open(src)
    except Exception as e:
        raise ConversionError(f"PDF tidak bisa dibuka: {e}") from e
    if doc.page_count == 0:
        raise ConversionError("PDF kosong (0 halaman).")
    multi = doc.page_count > 1
    for i, page in enumerate(doc):
        pix = page.get_pixmap(dpi=PDF_DPI)
        suffix = f"-hal{i + 1:03d}" if multi else ""
        dest = unique_output(src, fmt, suffix)
        pix.save(dest)
        out.append(dest)
    doc.close()
    return out


def pdf_to_text(src: Path) -> list[Path]:
    try:
        doc = pymupdf.open(src)
    except Exception as e:
        raise ConversionError(f"PDF tidak bisa dibuka: {e}") from e
    parts: list[str] = []
    for i, page in enumerate(doc):
        parts.append(f"--- Halaman {i + 1} ---\n{page.get_text()}")
    doc.close()
    dest = unique_output(src, "txt")
    dest.write_text("\n\n".join(parts), encoding="utf-8")
    return [dest]


def text_to_pdf(src: Path) -> list[Path]:
    text = src.read_text(encoding="utf-8", errors="replace")
    dest = unique_output(src, "pdf")
    doc = pymupdf.open()
    # Bagi teks jadi halaman sederhana: ~52 baris per halaman A4.
    lines: list[str] = []
    for raw in text.splitlines():
        while len(raw) > 95:  # wrap kasar per karakter
            lines.append(raw[:95])
            raw = raw[95:]
        lines.append(raw)
    per_page = 52
    for start in range(0, max(len(lines), 1), per_page):
        page = doc.new_page(width=595, height=842)  # A4 pt
        chunk = "\n".join(lines[start:start + per_page])
        page.insert_textbox(pymupdf.Rect(48, 48, 547, 794), chunk,
                            fontsize=10, fontname="cour")
    doc.save(dest)
    doc.close()
    return [dest]


# ---------------------------------------------------------------- Gambar
def _flatten_for_jpg(im: Image.Image) -> Image.Image:
    if im.mode in ("RGBA", "LA", "P"):
        rgba = im.convert("RGBA")
        bg = Image.new("RGB", rgba.size, (255, 255, 255))
        bg.paste(rgba, mask=rgba.split()[-1])
        return bg
    return im.convert("RGB")


def image_to_image(src: Path, fmt: str) -> list[Path]:
    try:
        im = Image.open(src)
        im.load()
    except Exception as e:
        raise ConversionError(f"Gambar tidak bisa dibuka: {e}") from e
    dest = unique_output(src, fmt)
    if fmt.upper() == "JPG":
        _flatten_for_jpg(im).save(dest, "JPEG", quality=92)
    elif fmt.upper() == "PNG":
        im.save(dest, "PNG")
    elif fmt.upper() == "WEBP":
        im.save(dest, "WEBP", quality=90)
    else:
        raise ConversionError(f"Format gambar tidak didukung: {fmt}")
    return [dest]


def images_to_pdf(srcs: list[Path]) -> list[Path]:
    """Satu / banyak gambar -> satu PDF (merge, urutan = urutan drop)."""
    first = srcs[0]
    dest = unique_output(first, "pdf", "-gabung" if len(srcs) > 1 else "")
    frames: list[Image.Image] = []
    try:
        for s in srcs:
            im = Image.open(s)
            im.load()
            frames.append(im.convert("RGB"))
    except Exception as e:
        raise ConversionError(f"Gambar tidak bisa dibuka: {e}") from e
    frames[0].save(dest, "PDF", save_all=True, append_images=frames[1:],
                   resolution=150.0)
    return [dest]


# ---------------------------------------------------------------- Media (ffmpeg)
def _ffmpeg(args: list[str]) -> None:
    if shutil.which("ffmpeg") is None:
        raise ConversionError("ffmpeg belum terinstall (sudo apt install ffmpeg).")
    proc = subprocess.run(["ffmpeg", "-y", "-v", "error", *args],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise ConversionError(f"ffmpeg gagal: {proc.stderr.strip()[:300]}")


def media_convert(src: Path, fmt: str) -> list[Path]:
    dest = unique_output(src, fmt)
    f = fmt.upper()
    if f == "MP3":
        _ffmpeg(["-i", str(src), "-vn", "-codec:a", "libmp3lame", "-q:a", "2", str(dest)])
    elif f == "WAV":
        _ffmpeg(["-i", str(src), "-vn", "-codec:a", "pcm_s16le", str(dest)])
    elif f == "OGG":
        _ffmpeg(["-i", str(src), "-codec:a", "libvorbis", "-q:a", "4", str(dest)])
    elif f == "GIF":
        _ffmpeg(["-i", str(src), "-vf", "fps=10,scale=480:-1:flags=lanczos", str(dest)])
    else:
        raise ConversionError(f"Format media tidak didukung: {fmt}")
    return [dest]


# ---------------------------------------------------------------- API utama
def convert(src: Path, fmt: str) -> list[Path]:
    """Konversi satu file ke format target. Return daftar file hasil."""
    fmt = fmt.upper()
    kind = detect_kind(src)
    if kind is None:
        raise ConversionError(f"Tipe file tidak didukung: {src.suffix}")
    if fmt not in ROUTES[kind]:
        raise ConversionError(f"{kind} -> {fmt} tidak ada di routing wheel.")
    if kind == "pdf":
        if fmt in ("JPG", "PNG"):
            return pdf_to_images(src, fmt)
        return pdf_to_text(src)
    if kind == "image":
        if fmt == "PDF":
            return images_to_pdf([src])
        return image_to_image(src, fmt)
    if kind == "text":
        return text_to_pdf(src)
    return media_convert(src, fmt)  # video / audio


def convert_many(srcs: list[Path], fmt: str) -> list[Path]:
    """
    Konversi batch. Kasus khusus: banyak gambar -> PDF digabung jadi SATU PDF
    (meniru fitur merge Tangerine). Selain itu tiap file dikonversi sendiri.
    """
    fmt = fmt.upper()
    if fmt == "PDF" and len(srcs) > 1 and all(detect_kind(s) == "image" for s in srcs):
        return images_to_pdf(srcs)
    out: list[Path] = []
    for s in srcs:
        out.extend(convert(s, fmt))
    return out
