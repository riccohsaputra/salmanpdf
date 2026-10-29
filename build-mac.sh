#!/usr/bin/env bash
# ============================================================
#  Build SalmanPDF untuk macOS (PyInstaller)
#  Hasil: dist/SalmanPDF.app  +  SalmanPDF-macOS.zip
#  Syarat: Python 3.11+ (python.org atau Homebrew)
#  Jalankan: bash build-mac.sh
# ============================================================
set -euo pipefail
cd "$(dirname "$0")"

echo "[1/4] Memasang dependency..."
python3 -m pip install --upgrade pip
python3 -m pip install PySide6-Essentials PyMuPDF Pillow pyinstaller

echo "[2/4] Menyiapkan ikon (.icns dari PNG 1024)..."
python3 make_icon.py
ICONSET=build/SalmanPDF.iconset
mkdir -p "$ICONSET" build
for s in 16 32 128 256 512; do
  sips -z "$s" "$s" salmanpdf/assets/appicon-1024.png \
    --out "$ICONSET/icon_${s}x${s}.png" >/dev/null
done
for s in 32 64 256 512 1024; do
  h=$((s / 2))
  sips -z "$s" "$s" salmanpdf/assets/appicon-1024.png \
    --out "$ICONSET/icon_${h}x${h}@2x.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o build/SalmanPDF.icns

echo "[3/4] Membangun SalmanPDF.app..."
pyinstaller --noconfirm --windowed --name SalmanPDF \
  --icon build/SalmanPDF.icns --exclude-module Xlib --exclude-module pymupdf.layout --exclude-module onnxruntime main.py

echo "[4/4] Mengemas zip..."
ditto -c -k --keepParent dist/SalmanPDF.app SalmanPDF-macOS.zip

echo
echo "SELESAI: dist/SalmanPDF.app"
echo "Zip siap bagikan: SalmanPDF-macOS.zip"
echo "Catatan: konversi Office butuh LibreOffice terpasang terpisah."
echo "Aplikasi belum ditandatangani Apple (tanpa Developer ID): saat"
echo "pertama dibuka, klik kanan > Open untuk melewati Gatekeeper."
