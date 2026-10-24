"""Test mesin konversi — jalan tanpa GUI:  .venv/bin/python -m pytest tests/ -q"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pymupdf
import pytest
from PIL import Image

from tangerine.converters import (
    ConversionError, convert, convert_many, detect_kind, formats_for,
    unique_output,
)


@pytest.fixture()
def sample_pdf(tmp_path) -> Path:
    doc = pymupdf.open()
    for txt in ("Halo Tangerine halaman satu", "Halaman dua isi lain"):
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 72), txt, fontsize=14)
    p = tmp_path / "contoh.pdf"
    doc.save(p)
    doc.close()
    return p


@pytest.fixture()
def sample_png(tmp_path) -> Path:
    p = tmp_path / "foto.png"
    Image.new("RGBA", (120, 80), (255, 122, 26, 255)).save(p)
    return p


def test_detect_and_formats(sample_pdf, sample_png):
    assert detect_kind(sample_pdf) == "pdf"
    assert detect_kind(sample_png) == "image"
    assert formats_for(sample_pdf) == ["JPG", "PNG", "TXT"]
    assert "PNG" not in formats_for(sample_png)  # format sendiri dibuang
    assert "PDF" in formats_for(sample_png)


def test_unique_output_never_overwrites(sample_png):
    a = unique_output(sample_png, "jpg")
    a.touch()
    b = unique_output(sample_png, "jpg")
    assert a != b and "(1)" in b.name


def test_pdf_to_jpg_multipage(sample_pdf):
    outs = convert(sample_pdf, "JPG")
    assert len(outs) == 2  # 2 halaman -> 2 jpg
    for o in outs:
        assert o.exists() and o.suffix == ".jpg"
        Image.open(o).verify()


def test_pdf_to_txt(sample_pdf):
    (out,) = convert(sample_pdf, "TXT")
    assert "Halo Tangerine" in out.read_text(encoding="utf-8")


def test_image_to_pdf_and_jpg(sample_png):
    (pdf,) = convert(sample_png, "PDF")
    assert pymupdf.open(pdf).page_count == 1
    (jpg,) = convert(sample_png, "JPG")  # RGBA -> JPG harus di-flatten
    assert Image.open(jpg).mode == "RGB"


def test_merge_images_to_one_pdf(sample_png, tmp_path):
    second = tmp_path / "kedua.png"
    Image.new("RGB", (50, 50), (0, 0, 255)).save(second)
    (out,) = convert_many([sample_png, second], "PDF")
    assert pymupdf.open(out).page_count == 2


def test_text_to_pdf(tmp_path):
    t = tmp_path / "catatan.txt"
    t.write_text("baris satu\nbaris dua", encoding="utf-8")
    (out,) = convert(t, "PDF")
    assert "baris satu" in pymupdf.open(out)[0].get_text()


def test_unsupported_raises(tmp_path):
    bad = tmp_path / "aneh.xyz"
    bad.write_bytes(b"??")
    with pytest.raises(ConversionError):
        convert(bad, "PDF")
