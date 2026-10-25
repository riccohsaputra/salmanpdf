"""Test deteksi file teks ala Linux (ekstensi luas + sniff isi)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pymupdf

from salmanpdf.converters import convert, detect_kind, formats_for, sniff_text


def _w(tmp_path, name, data, binary=False):
    p = tmp_path / name
    p.write_bytes(data if binary else data.encode("utf-8"))
    return p


def test_ekstensi_teks_luas(tmp_path):
    for name in ("a.txt", "a.text", "a.md", "a.log", "a.csv", "a.ini",
                 "a.sh", "a.py", "CATATAN.TXT"):
        assert detect_kind(_w(tmp_path, name, "halo dunia")) == "text", name
        assert formats_for(_w(tmp_path, name, "halo")) == ["PDF"]


def test_tanpa_ekstensi_isi_teks(tmp_path):
    p = _w(tmp_path, "catatan-rapat", "Isi rapat hari ini\nbaris kedua")
    assert sniff_text(p)
    assert detect_kind(p) == "text"
    (out,) = convert(p, "PDF")
    assert "Isi rapat" in pymupdf.open(out)[0].get_text()


def test_backup_gedit_txt_tilde(tmp_path):
    p = _w(tmp_path, "draft.txt~", "cadangan gedit")
    assert detect_kind(p) == "text"


def test_biner_tidak_ditebak_teks(tmp_path):
    png = _w(tmp_path, "aneh", b"\x89PNG\r\n\x1a\n" + bytes(range(256)), binary=True)
    assert not sniff_text(png)
    assert detect_kind(png) is None
    acak = _w(tmp_path, "acak.xyz", b"\x01\x02\x00\xff\xfe" * 40, binary=True)
    assert detect_kind(acak) is None


def test_deb_dikecualikan_dari_sniff(tmp_path):
    p = _w(tmp_path, "paket.deb", "!<arch>\nisi pura-pura teks")
    assert detect_kind(p) is None
