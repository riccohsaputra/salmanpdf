# Changelog SalmanPDF

Semua perubahan penting per versi. Berkas ini juga dibaca oleh fitur
Cek Update di dalam aplikasi untuk menampilkan "apa yang baru".

## v0.12.1 — 2026-10-29

- **Perbaikan crash start di build Windows (dan build beku lain).**
  PyMuPDF versi baru mengaktifkan subpaket analisis layout (model ONNX)
  setiap kali diimpor; berkas modelnya tidak ikut terbundel PyInstaller
  sehingga build v0.12.0 mati sebelum jendela tampil dengan
  FileNotFoundError di pymupdf/layout. SalmanPDF tidak memakai analisis
  layout: build beku kini memblokir aktivasi itu, dan perintah
  PyInstaller mengecualikan pymupdf.layout + onnxruntime dari bundel
  (unduhan ikut jauh lebih ramping). Pengguna build v0.12.0 Windows:
  unduh ulang rilis ini — aplikasi lama tidak bisa start sama sekali
  sehingga tombol Update di dalamnya tidak dapat dipakai.

## v0.12.0 — 2026-10-27
- Konversi Office sekarang dua backend: di Windows, dokumen
  dikonversi memakai Microsoft Office asli (Word/PowerPoint/Excel
  lewat COM) bila terpasang — hasil render persis aplikasi aslinya —
  dengan LibreOffice sebagai cadangan di semua OS. Target ODP/ODS
  tetap khusus LibreOffice (aplikasi Microsoft tidak bisa menyimpan
  kedua format itu). Bila MS Office gagal di tengah jalan, otomatis
  dicoba ulang lewat LibreOffice.

## v0.11.4 — 2026-10-27
- Repo GitHub resmi berganti nama: riccohsaputra/tangerine-linux →
  riccohsaputra/salmanpdf. Updater sekarang menunjuk nama baru
  (alamat lama tetap dialihkan GitHub, jadi instalasi lama aman).
- Build GitHub Actions pertama yang sukses penuh: run #2 menghasilkan
  SalmanPDF untuk Windows, macOS, dan Linux sekaligus.

## v0.11.3 — 2026-10-27
- Perbaikan build GitHub Actions: langkah Icons gagal di run pertama
  karena icon-source-ref.png (berkas biner) memang tidak ada di repo.
  make_icon.py sekarang memakai ikon tertanam di salmanpdf/icon_data.py
  bila berkas sumber itu tidak ada, jadi build Windows/macOS/Linux di
  CI bisa berjalan. Data ikon tertanam juga disegarkan dari berkas
  sumber asli (byte-exact).

## v0.11.2 — 2026-10-27
- Tombol Update di instalasi checkout (Linux) sekarang memeriksa &
  memasang update lewat git lokal — bekerja walau repo privat, tanpa
  perlu terminal sama sekali. Dependensi ikut disinkronkan otomatis
  setelah update, sama seperti alur update.sh + run.sh.

## v0.11.1 — 2026-10-27
- Klik tombol Update saat aplikasi sudah versi terbaru kini memunculkan
  pemberitahuan dialog "SalmanPDF sudah dalam versi terbaru" (berlaku
  di semua OS), dan ada pesan terpisah bila server update tidak
  terjangkau.

## v0.11.0 — 2026-10-27
- Tombol 🔄 Update di header + cek update otomatis saat aplikasi dibuka:
  ada versi baru -> muncul pemberitahuan beserta detail perubahannya,
  tombol "Update Sekarang" memasang update (git pull di instalasi
  checkout) atau membuka halaman unduhan.
- Siap lintas platform dari kode sumber yang sama: perbaikan jalur
  LibreOffice di Windows/macOS, buka-folder mengikuti OS, dan pesan
  Mode Global yang sadar OS.
- Script build Windows (build-windows.bat) dan macOS (build-mac.sh)
  berbasis PyInstaller + panduan PACKAGING.md.

## v0.10.0 — 2026-10-27
- Pisah PDF sekarang manual: tulis rentang halaman sendiri (mis.
  1-3, 5, 8-10) menjadi beberapa PDF, atau ekstrak halaman pilihan
  menjadi satu PDF — dengan validasi langsung dan strip nomor halaman.

## v0.9.0 — 2026-10-27
- Edit PDF: preview bisa zoom (roda mouse / tombol + dan -),
  tempelan teks & gambar bisa dipilih dan diseret pindah posisi,
  dan susunannya bisa diatur (paling depan, paling belakang, maju,
  mundur) + hapus tempelan terpilih.

## v0.8.5 — 2026-10-25
- Tulisan "created by Ricco Abu Salman" dibuat lebih menonjol.

## v0.8.4 — 2026-10-25
- Audit menu menyeluruh: filter dialog file kini mencakup .gif dan
  .tif (sebelumnya hanya bisa lewat seret & letakkan).

## v0.8.2 — 2026-10-25
- Mode gelap: ikon logo berubah putih agar terlihat, label teks tidak
  lagi berbackground kotak hitam.

## v0.8.1 — 2026-10-25
- Switch mode terang/gelap di header, pilihan tersimpan otomatis.

## v0.8.0 — 2026-10-25
- Menu baru: Hapus Background gambar (hasil PNG transparan).

## v0.7.9 — 2026-10-25
- Logo header memakai ikon dokumen pilihan (menggantikan huruf S).

## v0.7.4 — 2026-10-25
- Ikon kartu ala iLovePDF: ubin warna solid dengan glyph putih,
  warna khas per alat. Tampilan dikunci sebagai acuan.
