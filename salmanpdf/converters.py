"""
Mesin konversi lokal SalmanPDF.

Semua konversi jalan lokal (tanpa upload):
- PDF  <-> gambar : PyMuPDF (render) + Pillow
- Gambar -> PDF   : Pillow (banyak gambar = digabung satu PDF)
- PDF  -> TXT     : PyMuPDF text extraction (bukan OCR)
- PDF tools       : GABUNG (merge), PISAH (split), KOMPRES (target size)
- Office          : Microsoft Office via COM (Windows) atau LibreOffice
                    headless (soffice) untuk docx/pptx/xlsx/odt/dll
- TXT  -> PDF     : PyMuPDF

(Video/audio SENGAJA tidak didukung — dihapus atas permintaan user,
 fokus ke dokumen, gambar, dan PDF.)

Aturan output (meniru Tangerine asli):
- Hasil selalu disimpan DI SEBELAH file asli.
- Tidak pernah menimpa file yang sudah ada -> tambah suffix (1), (2), ...
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pymupdf
from PIL import Image

PDF_DPI = 200  # render PDF -> gambar

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif", ".gif"}
WORD_EXTS = {".docx", ".doc", ".odt", ".rtf"}
SLIDE_EXTS = {".pptx", ".ppt", ".odp"}
SHEET_EXTS = {".xlsx", ".xls", ".ods"}
TEXT_EXTS = {
    ".txt", ".text", ".md", ".markdown", ".log", ".csv", ".tsv",
    ".ini", ".cfg", ".conf", ".config", ".sh", ".bash", ".zsh",
    ".py", ".js", ".ts", ".json", ".yml", ".yaml", ".xml", ".sql",
    ".java", ".c", ".cpp", ".h", ".php", ".rb", ".go", ".rs",
}
# Magic bytes biner yang TIDAK boleh ditebak sebagai teks.
_BINARY_MAGIC = (
    b"\x89PNG", b"\xff\xd8\xff", b"GIF8", b"%PDF", b"PK\x03\x04",
    b"\x7fELF", b"ID3", b"OggS", b"\x1aE\xdf\xa3",  # PNG/JPEG/GIF/PDF/ZIP/ELF/MP3/OGG/WebM-MKV
)


def sniff_text(path: Path) -> bool:
    """
    Tebak file teks dari ISINYA (untuk file Linux yang sering tanpa
    ekstensi, atau ekstensinya tak dikenal). Syarat: tidak ada byte NUL,
    tidak cocok magic biner, dan mayoritas byte bisa di-decode UTF-8.
    """
    try:
        if not path.is_file() or path.stat().st_size > 20 * 1024 * 1024:
            return False
        sample = path.read_bytes()[:8192]
    except OSError:
        return False
    if not sample:
        return False
    if b"\x00" in sample or sample.startswith(_BINARY_MAGIC):
        return False
    try:
        sample.decode("utf-8")
        return True
    except UnicodeDecodeError:
        # Toleransi file teks encoding lama: coba latin-1 selektif —
        # tolak kalau terlalu banyak karakter kontrol.
        text = sample.decode("latin-1")
        controls = sum(1 for c in text if ord(c) < 9 or (13 < ord(c) < 32))
        return controls / max(len(text), 1) < 0.02


class ConversionError(Exception):
    """Error konversi yang aman ditampilkan ke user (Bahasa Indonesia)."""


def detect_kind(path: Path) -> str | None:
    ext = path.suffix.lower()
    if ext == ".pdf":
        return "pdf"
    if ext in IMAGE_EXTS:
        return "image"
    if ext in WORD_EXTS:
        return "word"
    if ext in SLIDE_EXTS:
        return "slides"
    if ext in SHEET_EXTS:
        return "sheet"
    if ext in TEXT_EXTS:
        return "text"
    # Fallback ala Linux: file tanpa ekstensi / ekstensi asing yang
    # isinya teks polos tetap dianggap teks (-> bisa jadi PDF).
    if ext in {".deb", ".zip", ".tar", ".gz", ".xz", ".bz2", ".7z", ".rar",
               ".exe", ".bin", ".iso", ".img", ".db", ".sqlite", ".so", ".o"}:
        return None
    if sniff_text(path):
        return "text"
    return None


# Tabel routing: tipe input -> format output yang ditawarkan wheel.
# GABUNG tidak di sini (khusus multi-PDF, ditangani convert_many + app).
ROUTES: dict[str, list[str]] = {
    "pdf": ["JPG", "PNG", "TXT", "PISAH", "KOMPRES"],
    "image": ["JPG", "PNG", "WEBP", "PDF"],
    "word": ["PDF", "TXT", "DOCX", "ODT"],
    "slides": ["PDF", "PPTX", "ODP"],
    "sheet": ["PDF", "CSV", "XLSX", "ODS"],
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


# ---------------------------------------------------------------- PDF tools
def merge_pdfs(srcs: list[Path]) -> list[Path]:
    """Gabung banyak PDF -> satu PDF (urutan = urutan drop)."""
    if len(srcs) < 2:
        raise ConversionError("GABUNG butuh minimal 2 file PDF.")
    dest = unique_output(srcs[0], "pdf", "-gabung")
    out = pymupdf.open()
    try:
        for s in srcs:
            with pymupdf.open(s) as d:
                out.insert_pdf(d)
    except Exception as e:
        raise ConversionError(f"Gagal menggabung PDF: {e}") from e
    out.save(dest, garbage=3, deflate=True)
    out.close()
    return [dest]


def split_pdf(src: Path) -> list[Path]:
    """Pisah PDF -> satu PDF per halaman (-hal001, -hal002, ...)."""
    try:
        doc = pymupdf.open(src)
    except Exception as e:
        raise ConversionError(f"PDF tidak bisa dibuka: {e}") from e
    out: list[Path] = []
    for i in range(doc.page_count):
        dest = unique_output(src, "pdf", f"-hal{i + 1:03d}")
        single = pymupdf.open()
        single.insert_pdf(doc, from_page=i, to_page=i)
        single.save(dest)
        single.close()
        out.append(dest)
    doc.close()
    if not out:
        raise ConversionError("PDF kosong (0 halaman).")
    return out


def compress_pdf(src: Path, target_bytes: int) -> list[Path]:
    """
    Kompres PDF mendekati target ukuran user: turunkan resolusi+kualitas
    gambar tersemat bertahap (rewrite_images) sampai <= target. Kalau
    target tidak tercapai (PDF dominan teks/vektor), kembalikan hasil
    terkecil yang bisa dicapai.
    """
    if not target_bytes or target_bytes <= 0:
        raise ConversionError("KOMPRES butuh target ukuran (byte) dari user.")
    ladder: list[tuple[int | None, int]] = [
        (None, 0),      # lossless saja dulu (buang sampah + deflate)
        (220, 85), (180, 75), (150, 65), (120, 55),
        (96, 45), (72, 35), (50, 25),
    ]
    best_path: Path | None = None
    best_size = float("inf")
    tmpdir = Path(tempfile.mkdtemp(prefix="tng-kompres-"))
    try:
        for dpi, quality in ladder:
            cand = tmpdir / f"coba-{dpi or 'lossless'}.pdf"
            try:
                doc = pymupdf.open(src)
                if dpi is not None:
                    # Syarat PyMuPDF: dpi_target HARUS < dpi_threshold.
                    doc.rewrite_images(dpi_threshold=dpi + 40, dpi_target=dpi,
                                       quality=quality)
                doc.save(cand, garbage=4, deflate=True)
                doc.close()
            except Exception:
                continue
            size = cand.stat().st_size
            if size < best_size:
                best_size, best_path = size, cand
            if size <= target_bytes:
                break
        if best_path is None:
            raise ConversionError("Kompresi gagal total (PDF rusak?).")
        dest = unique_output(src, "pdf", "-kompres")
        shutil.copy2(best_path, dest)
        return [dest]
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------- Office (MS Office / LibreOffice)
def _find_soffice() -> str | None:
    """Lokasi biner LibreOffice (PATH atau lokasi instalasi baku per OS)."""
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if soffice is not None:
        return soffice
    if sys.platform.startswith("win"):
        cands = [
            r"C:\Program Files\LibreOffice\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        ]
    elif sys.platform == "darwin":
        cands = ["/Applications/LibreOffice.app/Contents/MacOS/soffice"]
    else:
        cands = ["/usr/bin/soffice", "/snap/bin/libreoffice"]
    for c in cands:
        if Path(c).exists():
            return c
    return None


def _office_convert_libre(src: Path, fmt: str, soffice: str) -> list[Path]:
    """Konversi via LibreOffice headless; output di sebelah file asli."""
    target = fmt.lower()
    convert_arg = "txt:Text" if target == "txt" else target
    with tempfile.TemporaryDirectory(prefix="tng-office-") as td:
        env = dict(os.environ)
        env["HOME"] = td  # profil LO terisolasi, hindari lock instance GUI
        proc = subprocess.run(
            [soffice, "--headless", "--norestore",
             f"-env:UserInstallation=file://{td}/profile",
             "--convert-to", convert_arg, "--outdir", td, str(src)],
            capture_output=True, text=True, timeout=240, env=env)
        produced = Path(td) / f"{src.stem}.{target}"
        if proc.returncode != 0 or not produced.exists():
            detail = (proc.stderr or proc.stdout or "").strip()[:200]
            raise ConversionError(f"LibreOffice gagal mengonversi: {detail}")
        dest = unique_output(src, target)
        shutil.move(str(produced), str(dest))
    return [dest]


def office_convert(src: Path, fmt: str) -> list[Path]:
    """
    Konversi dokumen Office (word/slides/sheet -> format di ROUTES).

    Urutan backend:
    1. Microsoft Office asli via COM — hanya Windows, dan hanya untuk
       pasangan format yang didukung aplikasinya (mis. PowerPoint
       tidak bisa ODP, Excel tidak bisa ODS).
    2. LibreOffice headless (semua OS) sebagai cadangan/universal.
    Kegagalan backend pertama dicatat lalu backend berikutnya dicoba;
    bila keduanya tidak tersedia/gagal, pesan errornya menjelaskan
    dua-duanya supaya user tahu harus memasang apa.
    """
    from . import msoffice

    kind = detect_kind(src)
    target = fmt.lower()
    ms_error: str | None = None
    if msoffice.available_plan(kind, target) is not None:
        try:
            with tempfile.TemporaryDirectory(prefix="tng-msoffice-") as td:
                out = Path(td) / f"{src.stem}.{target}"
                msoffice.convert_with_ms_office(src, kind, target, out)
                dest = unique_output(src, target)
                shutil.move(str(out), str(dest))
            return [dest]
        except msoffice.MsOfficeError as e:
            ms_error = str(e)
    soffice = _find_soffice()
    if soffice is not None:
        return _office_convert_libre(src, fmt, soffice)
    if ms_error is not None:
        raise ConversionError(
            f"Microsoft Office gagal mengonversi ({ms_error}), dan "
            "LibreOffice tidak ditemukan. Pasang LibreOffice sebagai "
            "cadangan, atau perbaiki instalasi Microsoft Office-nya.")
    if sys.platform.startswith("win") and msoffice.plan_for(kind, target) is None \
            and msoffice.find_ms_apps():
        raise ConversionError(
            f"Microsoft Office tidak bisa menyimpan format {fmt.upper()} — "
            f"konversi ini butuh LibreOffice, yang tidak ditemukan. "
            "Pasang LibreOffice lalu coba lagi.")
    raise ConversionError(
        "Konversi Office membutuhkan Microsoft Office (Windows) atau "
        "LibreOffice — keduanya tidak ditemukan di komputer ini. "
        "Pasang salah satunya lalu coba lagi.")


# ---------------------------------------------------------------- API utama
def convert(src: Path, fmt: str, *, target_bytes: int | None = None) -> list[Path]:
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
        if fmt == "TXT":
            return pdf_to_text(src)
        if fmt == "PISAH":
            return split_pdf(src)
        return compress_pdf(src, target_bytes or 0)  # KOMPRES
    if kind == "image":
        if fmt == "PDF":
            return images_to_pdf([src])
        return image_to_image(src, fmt)
    if kind == "text":
        return text_to_pdf(src)
    return office_convert(src, fmt)  # word / slides / sheet


def convert_many(srcs: list[Path], fmt: str, *,
                 target_bytes: int | None = None) -> list[Path]:
    """
    Konversi batch. Kasus khusus:
    - banyak gambar -> PDF digabung jadi SATU PDF
    - GABUNG + banyak PDF -> satu PDF gabungan
    Selain itu tiap file dikonversi sendiri.
    """
    fmt = fmt.upper()
    if fmt == "GABUNG":
        if not all(detect_kind(s) == "pdf" for s in srcs):
            raise ConversionError("GABUNG hanya untuk file PDF semua.")
        return merge_pdfs(srcs)
    if fmt == "PDF" and len(srcs) > 1 and all(detect_kind(s) == "image" for s in srcs):
        return images_to_pdf(srcs)
    out: list[Path] = []
    for s in srcs:
        out.extend(convert(s, fmt, target_bytes=target_bytes))
    return out


# ------------------------------------------------------- pisah PDF manual
def parse_page_spec(spec: str, total: int) -> list[list[int]]:
    """
    Urai spesifikasi halaman (1-based, ditulis user) menjadi kelompok
    halaman 0-based. Contoh: "1-3, 5, 8-10" -> [[0,1,2],[4],[7,8,9]].
    Token dipisah koma; tiap token satu halaman "5" atau rentang "8-10".
    """
    if total < 1:
        raise ConversionError("PDF tidak punya halaman.")
    groups: list[list[int]] = []
    for raw in spec.split(","):
        tok = raw.strip()
        if not tok:
            continue
        if "-" in tok:
            a_s, _, b_s = tok.partition("-")
            try:
                a, b = int(a_s.strip()), int(b_s.strip())
            except ValueError:
                raise ConversionError(f"Rentang tidak valid: '{tok}'.") from None
            if a > b:
                raise ConversionError(
                    f"Rentang terbalik: '{tok}' (awal harus <= akhir).")
            pages = list(range(a, b + 1))
        else:
            try:
                pages = [int(tok)]
            except ValueError:
                raise ConversionError(
                    f"Nomor halaman tidak valid: '{tok}'.") from None
        for pg in pages:
            if pg < 1 or pg > total:
                raise ConversionError(
                    f"Halaman {pg} di luar jangkauan (dokumen {total} halaman).")
        groups.append([pg - 1 for pg in pages])
    if not groups:
        raise ConversionError("Isi dulu halaman yang mau dipisah.")
    return groups


def split_pdf_groups(src: Path, groups: list[list[int]]) -> list[Path]:
    """Satu PDF keluaran per kelompok halaman. Nama: -hal{a} / -hal{a}-{b}
    (1-based mengikuti halaman pertama-terakhir kelompok)."""
    try:
        doc = pymupdf.open(src)
    except Exception as e:
        raise ConversionError(f"PDF tidak bisa dibuka: {e}") from e
    out: list[Path] = []
    with doc:
        for group in groups:
            if not group:
                continue
            first, last = group[0] + 1, group[-1] + 1
            suffix = (f"-hal{first}" if first == last
                      else f"-hal{first}-{last}")
            dest = unique_output(src, "pdf", suffix)
            single = pymupdf.open()
            for idx in group:
                single.insert_pdf(doc, from_page=idx, to_page=idx)
            single.save(dest, garbage=3, deflate=True)
            single.close()
            out.append(dest)
    return out


def extract_pages(src: Path, pages: list[int]) -> Path:
    """Satu PDF berisi halaman pilihan saja (0-based, urutan dipertahankan,
    duplikat dibuang). Nama: -pilihan."""
    seen: set[int] = set()
    ordered = [p for p in pages if not (p in seen or seen.add(p))]
    if not ordered:
        raise ConversionError("Belum ada halaman yang dipilih.")
    try:
        doc = pymupdf.open(src)
    except Exception as e:
        raise ConversionError(f"PDF tidak bisa dibuka: {e}") from e
    dest = unique_output(src, "pdf", "-pilihan")
    single = pymupdf.open()
    with doc:
        for idx in ordered:
            single.insert_pdf(doc, from_page=idx, to_page=idx)
    single.save(dest, garbage=3, deflate=True)
    single.close()
    return dest
