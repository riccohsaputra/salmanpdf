"""SalmanPDF — prototipe v1: drop-zone + radial wheel file converter."""
import sys as _sys

__version__ = "0.12.1"

# Build beku (PyInstaller): cegah PyMuPDF mengaktifkan subpaket "layout"-nya.
# pymupdf/__init__ menjalankan `import pymupdf.layout` di dalam try/except
# ImportError; aktivasi layout memuat model ONNX dari berkas data yang tidak
# ikut terbundel PyInstaller dan melempar FileNotFoundError (BUKAN ImportError)
# sehingga lolos dari penjaga itu dan aplikasi mati sebelum jendela tampil
# (kasus nyata: build Windows v0.12.0). Menaruh None di sys.modules membuat
# impornya gagal sebagai ImportError biasa -> tertangkap penjaga PyMuPDF ->
# _get_layout tetap None. SalmanPDF memang tidak memakai analisis layout.
if getattr(_sys, "frozen", False):
    _sys.modules.setdefault("pymupdf.layout", None)
