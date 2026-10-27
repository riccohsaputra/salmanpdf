@echo off
REM ============================================================
REM  Build SalmanPDF untuk Windows (PyInstaller)
REM  Hasil: dist\SalmanPDF\SalmanPDF.exe  +  SalmanPDF-Windows.zip
REM  Syarat: Python 3.11+ terpasang (python.org, centang "Add to PATH")
REM  Jalankan: klik dua kali berkas ini, atau `build-windows.bat`
REM ============================================================
setlocal
cd /d %~dp0

echo [1/4] Memasang dependency...
python -m pip install --upgrade pip
python -m pip install PySide6-Essentials PyMuPDF Pillow pyinstaller pywin32
if errorlevel 1 goto :gagal

echo [2/4] Menyiapkan ikon (.ico)...
python make_icon.py
if errorlevel 1 goto :gagal

echo [3/4] Membangun SalmanPDF.exe...
pyinstaller --noconfirm --windowed --name SalmanPDF --icon salmanpdf\assets\appicon.ico --exclude-module Xlib main.py
if errorlevel 1 goto :gagal

echo [4/4] Mengemas zip...
powershell -Command "Compress-Archive -Path dist\SalmanPDF -DestinationPath SalmanPDF-Windows.zip -Force"

echo.
echo SELESAI: dist\SalmanPDF\SalmanPDF.exe
echo Zip siap bagikan: SalmanPDF-Windows.zip
echo Catatan: konversi Office memakai Microsoft Office (bila ada) atau LibreOffice.
pause
exit /b 0

:gagal
echo.
echo BUILD GAGAL - baca pesan kesalahan di atas.
pause
exit /b 1
