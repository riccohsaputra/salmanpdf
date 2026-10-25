"""Test v0.4.0: hapus media, Office, PDF tools, edit PDF."""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pymupdf
import pytest
from PIL import Image

from salmanpdf.converters import (
    ConversionError, convert, convert_many, detect_kind, formats_for,
)
from salmanpdf import pdfedit


def _make_pdf(tmp_path, name, pages=1, text="Isi halaman"):
    p = tmp_path / name
    doc = pymupdf.open()
    for i in range(pages):
        page = doc.new_page(width=300, height=300)
        page.insert_text((40, 60), f"{text} {i + 1}", fontsize=12)
    doc.save(p)
    doc.close()
    return p


# ---------------------------------------------------------------- media dihapus
def test_media_tidak_didukung_lagi(tmp_path):
    mp4 = tmp_path / "v.mp4"
    mp4.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64)
    mp3 = tmp_path / "a.mp3"
    mp3.write_bytes(b"ID3" + b"\x00" * 64)
    assert detect_kind(mp4) is None
    assert detect_kind(mp3) is None
    with pytest.raises(ConversionError):
        convert(mp4, "MP3")


# ---------------------------------------------------------------- office
def test_office_routing(tmp_path):
    for name, kind in [("a.docx", "word"), ("a.doc", "word"),
                       ("a.odt", "word"), ("a.rtf", "word"),
                       ("a.pptx", "slides"), ("a.odp", "slides"),
                       ("a.xlsx", "sheet"), ("a.ods", "sheet")]:
        p = tmp_path / name
        p.write_bytes(b"x")
        assert detect_kind(p) == kind, name
    assert "PDF" in formats_for(tmp_path / "a.docx")
    assert "DOCX" not in formats_for(tmp_path / "a.docx")  # format sendiri dibuang
    assert "ODT" in formats_for(tmp_path / "a.docx")


@pytest.mark.skipif(shutil.which("soffice") is None,
                    reason="LibreOffice tidak ada di mesin test")
def test_office_docx_ke_pdf_dan_txt(tmp_path):
    # Bikin docx asli pakai LibreOffice dari txt
    src_txt = tmp_path / "halo.txt"
    src_txt.write_text("Halo Office SalmanPDF", encoding="utf-8")
    import subprocess
    subprocess.run(["soffice", "--headless", "--convert-to", "docx",
                    "--outdir", str(tmp_path), str(src_txt)],
                   check=True, capture_output=True, timeout=120)
    docx = tmp_path / "halo.docx"
    assert docx.exists()
    (pdf,) = convert(docx, "PDF")
    assert "Halo Office" in pymupdf.open(pdf)[0].get_text()
    (txt,) = convert(docx, "TXT")
    assert "Halo Office" in txt.read_text(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------- pdf tools
def test_gabung_pdf(tmp_path):
    a = _make_pdf(tmp_path, "a.pdf", pages=2, text="Alpha")
    b = _make_pdf(tmp_path, "b.pdf", pages=3, text="Beta")
    (out,) = convert_many([a, b], "GABUNG")
    doc = pymupdf.open(out)
    assert doc.page_count == 5
    assert out.name.startswith("a-gabung")


def test_pisah_pdf(tmp_path):
    a = _make_pdf(tmp_path, "a.pdf", pages=3)
    outs = convert(a, "PISAH")
    assert len(outs) == 3
    assert all(pymupdf.open(o).page_count == 1 for o in outs)
    assert outs[0].name == "a-hal001.pdf"


def test_kompres_pdf(tmp_path):
    # PDF berisi gambar noise besar -> harus bisa dikecilkan jauh
    noise = Image.frombytes("RGB", (800, 800),
                            bytes((i * 2654435761) % 256
                                  for i in range(800 * 800 * 3)))
    img = tmp_path / "noise.png"
    noise.save(img)
    (big_pdf,) = convert(img, "PDF")
    before = big_pdf.stat().st_size
    (out,) = convert(big_pdf, "KOMPRES", target_bytes=80_000)
    after = out.stat().st_size
    assert after < before
    assert after <= 80_000 or after < before // 2


def test_kompres_butuh_target(tmp_path):
    a = _make_pdf(tmp_path, "a.pdf")
    with pytest.raises(ConversionError):
        convert(a, "KOMPRES")


# ---------------------------------------------------------------- edit pdf
def test_font_sistem_terdaftar():
    fonts = pdfedit.list_system_fonts()
    assert len(fonts) >= 1


def test_tambah_teks_ke_pdf(tmp_path):
    a = _make_pdf(tmp_path, "a.pdf", pages=1)
    dest = pdfedit.apply_edits(a, [{
        "type": "text", "page": 0, "x": 40, "y": 200,
        "text": "TANDA TANGAN RICCO", "font": "Helvetica",
        "size": 14, "color": (1, 0, 0),
    }])
    assert dest.name == "a-edit.pdf"
    page = pymupdf.open(dest)[0]
    assert "TANDA TANGAN RICCO" in page.get_text()
    # warna merah terdeteksi dari drawing/text color
    d = page.get_text("dict")
    colors = {span["color"] for block in d["blocks"] if "lines" in block
              for line in block["lines"] for span in line["spans"]}
    assert 0xFF0000 in colors


def test_tambah_teks_font_sistem(tmp_path):
    a = _make_pdf(tmp_path, "a.pdf", pages=1)
    family = pdfedit.list_system_fonts()[0]
    dest = pdfedit.apply_edits(a, [{
        "type": "text", "page": 0, "x": 40, "y": 200,
        "text": "Font Sistem OK", "font": family,
        "size": 12, "color": (0, 0, 0),
    }])
    assert "Font Sistem OK" in pymupdf.open(dest)[0].get_text()


def test_tambah_gambar_ke_pdf(tmp_path):
    a = _make_pdf(tmp_path, "a.pdf", pages=1)
    img = tmp_path / "cap.png"
    Image.new("RGB", (60, 30), (0, 128, 255)).save(img)
    dest = pdfedit.apply_edits(a, [{
        "type": "image", "page": 0, "x": 50, "y": 80,
        "w": 120, "h": 60, "path": str(img),
    }])
    page = pymupdf.open(dest)[0]
    assert len(page.get_images()) >= 1


def test_preview_render(tmp_path):
    a = _make_pdf(tmp_path, "a.pdf", pages=2)
    png, zoom, count = pdfedit.render_preview(a, [], 1)
    assert png[:4] == b"\x89PNG" and count == 2 and zoom > 0
