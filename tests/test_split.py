"""Tes pisah PDF manual: parser spesifikasi + hasil file nyata."""
import sys
from pathlib import Path

import pymupdf
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from salmanpdf.converters import (
    ConversionError, extract_pages, parse_page_spec, split_pdf_groups,
)


def test_parse_dasar():
    assert parse_page_spec("1-3, 5, 8-10", 10) == [[0, 1, 2], [4], [7, 8, 9]]
    assert parse_page_spec(" 2 ", 5) == [[1]]
    assert parse_page_spec("3-3", 5) == [[2]]


def test_parse_error():
    with pytest.raises(ConversionError):
        parse_page_spec("0", 5)          # halaman mulai dari 1
    with pytest.raises(ConversionError):
        parse_page_spec("6", 5)          # melebihi jumlah halaman
    with pytest.raises(ConversionError):
        parse_page_spec("4-2", 5)        # rentang terbalik
    with pytest.raises(ConversionError):
        parse_page_spec("abc", 5)
    with pytest.raises(ConversionError):
        parse_page_spec("  ", 5)         # kosong


def _buat_pdf(path: Path, n: int) -> Path:
    doc = pymupdf.open()
    for i in range(n):
        page = doc.new_page(width=300, height=300)
        page.insert_text((40, 60), f"halaman {i + 1}")
    doc.save(path)
    doc.close()
    return path


def test_split_dan_extract_nyata(tmp_path):
    src = _buat_pdf(tmp_path / "dok.pdf", 6)
    outs = split_pdf_groups(src, parse_page_spec("1-2, 5", 6))
    assert len(outs) == 2
    assert outs[0].name == "dok-hal1-2.pdf"
    assert outs[1].name == "dok-hal5.pdf"
    with pymupdf.open(outs[0]) as d:
        assert d.page_count == 2
    gabung = extract_pages(src, [4, 0, 4, 2])   # duplikat dibuang, urutan jaga
    assert gabung.name == "dok-pilihan.pdf"
    with pymupdf.open(gabung) as d:
        assert d.page_count == 3
        assert "halaman 5" in d[0].get_text()
        assert "halaman 1" in d[1].get_text()
