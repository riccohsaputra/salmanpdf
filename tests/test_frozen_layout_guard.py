"""Regresi crash build Windows v0.12.0: saat start, PyMuPDF mengimpor
pymupdf.layout yang memuat model ONNX dari berkas data yang tidak terbundel
PyInstaller -> FileNotFoundError (bukan ImportError) lolos dari try/except
PyMuPDF dan aplikasi mati sebelum jendela tampil.

Perbaikan: di build beku, salmanpdf/__init__ menaruh None di
sys.modules["pymupdf.layout"] sehingga impornya gagal sebagai ImportError
biasa dan tertangkap penjaga PyMuPDF. Tes ini mensimulasikan build beku
(sys.frozen = True) dalam subprocess terpisah.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CODE = """
import sys
sys.frozen = True  # pura-pura build PyInstaller
sys.path.insert(0, {root!r})
import salmanpdf  # __init__ memasang penjaga
assert sys.modules.get("pymupdf.layout", "missing") is None, "penjaga tidak terpasang"
import pymupdf  # tidak boleh crash walau layout diblokir
assert pymupdf._get_layout is None, "layout seharusnya nonaktif"
import salmanpdf.converters as c
assert c.formats_for  # modul konverter bisa dimuat
print("FROZEN-GUARD-OK")
"""


def test_frozen_build_survives_blocked_layout():
    code = CODE.format(root=str(ROOT))
    r = subprocess.run([sys.executable, "-c", code],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    assert "FROZEN-GUARD-OK" in r.stdout


def test_source_run_does_not_block_layout():
    code = (
        "import sys; sys.path.insert(0, %r); import salmanpdf; "
        "assert sys.modules.get('pymupdf.layout') is not None or "
        "'pymupdf.layout' not in sys.modules; print('SRC-OK')" % str(ROOT)
    )
    r = subprocess.run([sys.executable, "-c", code],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    assert "SRC-OK" in r.stdout
