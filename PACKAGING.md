# Packaging SalmanPDF — Windows, macOS, Linux

Satu kode sumber yang sama untuk tiga OS. Perbedaan hanya di cara
membungkusnya (PyInstaller di Windows/macOS, .deb / checkout git di
Linux) dan SATU fitur khusus platform:

| Fitur | Linux | Windows | macOS |
|---|---|---|---|
| Semua konversi & alat PDF/gambar/Office | ✅ | ✅ | ✅ |
| Edit PDF (zoom, seret, susunan lapis) | ✅ | ✅ | ✅ |
| Pisah PDF manual, Hapus Background, tema gelap/terang | ✅ | ✅ | ✅ |
| Cek Update + notifikasi versi baru | ✅ | ✅ | ✅ |
| Mode Global (Shift+seret dari file manager) | ✅ khusus sesi X11 | ❌ (fitur X11) | ❌ (fitur X11) |
| Daftar font sistem di Edit PDF | semua font fontconfig | daftar cadangan (font bawaan PDF) bila fontconfig absen | idem |

Syarat bersama: konversi dokumen Office memakai **LibreOffice** yang
terpasang terpisah di mesin pengguna (di semua OS). Tanpa LibreOffice,
alat Office menampilkan pesan bahwa LibreOffice tidak ditemukan —
fitur lain tidak terpengaruh.

## Windows

Syarat: Python 3.11+ dari python.org (centang "Add python.exe to PATH").

```
build-windows.bat
```

Hasil: `dist\SalmanPDF\SalmanPDF.exe` dan `SalmanPDF-Windows.zip`
(isi zip = folder aplikasi; pengguna mengekstrak lalu menjalankan
SalmanPDF.exe — tanpa instalasi).

## macOS

Syarat: Python 3.11+ (python.org atau `brew install python`).

```
bash build-mac.sh
```

Hasil: `dist/SalmanPDF.app` dan `SalmanPDF-macOS.zip`.
Aplikasi tidak ditandatangani Apple Developer ID, jadi pembukaan
pertama: klik kanan `SalmanPDF.app` → Open → Open.

## Linux

- Cara dev (yang dipakai Ricco): clone repo → `bash update.sh` untuk
  update, `bash run.sh` untuk menjalankan.
- Cara paket: `./build-deb.sh` menghasilkan .deb siap pasang.

## Update di dalam aplikasi (semua OS)

- SalmanPDF memeriksa versi terbaru dari repo GitHub (berkas
  `salmanpdf/__init__.py` + `CHANGELOG.md` di branch main) sekali saat
  start (paling sering ~sehari sekali) dan lewat tombol 🔄 Update.
- Bila ada versi lebih baru: dialog berisi detail perubahan (diambil
  dari CHANGELOG.md) dan tombol **Update Sekarang**.
  - Instalasi checkout git (Linux dev / clone manual): update dipasang
    langsung dengan `git pull`, lalu pengguna cukup memulai ulang app.
  - Instalasi paket/biner: tombol membuka halaman Releases GitHub
    untuk mengunduh versi terbaru.

## Rilis otomatis dengan GitHub Actions (opsional)

Berkas `build-release.yml.txt` berisi workflow siap pakai: buat berkas
`.github/workflows/build-release.yml` di web GitHub dan tempel isinya.
Setelah itu, setiap push tag `v*` (mis. `v0.12.0`) memicu build
Windows + macOS + Linux sekaligus dan hasilnya terbit sebagai
GitHub Release dengan tautan unduh per OS.

## Checklist verifikasi rilis (per OS)

1. App terbuka, versi di header sesuai.
2. Gabung 2 PDF; Pisah manual rentang `1-2`; Kompres ke target KB.
3. Edit PDF: tempel teks + gambar, zoom roda mouse, seret tempelan,
   ubah susunan lapis, simpan.
4. Hapus Background satu gambar bertanda tangan.
5. Konversi DOCX → PDF (LibreOffice terpasang).
6. Tombol 🔄 Update: dialog/cek berjalan tanpa membekukan UI.
