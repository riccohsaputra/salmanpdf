# SalmanPDF — Prototipe v0.8.3 (drop-zone + mode global Shift+Drag)

Kloningan konsep **Tangerine for Mac** (drag file → tahan Shift → wheel format)
yang disesuaikan untuk **Linux Mint**. Semua konversi **100% lokal**, tanpa upload.

> **Dulu bernama Tangerine Linux** — di-rename jadi **SalmanPDF** pada 2026-10-25 (v0.4.1).

Ada DUA mode:

## Mode A — Global Shift+Drag (v2, eksperimental, khusus sesi X11)

Persis yang asli:

1. Klik tombol **"Aktifkan mode global Shift+Drag (X11)"** di app.
2. Seret file di **Nemo** seperti biasa, lalu **tahan Shift sambil menyeret** —
   wheel transparan muncul di posisi kursor.
3. Geser ke sektor format (JPG/PNG/TXT/dll), **lepas mouse** → file langsung
   dikonversi, hasil di sebelah file asli.

Cara kerjanya: app me-*poll* pointer global X11 tiap 25 ms (`query_pointer` —
mask-nya berisi status tombol mouse + Shift sekaligus). Wheel-nya sendiri
adalah jendela drop-target XDND asli, jadi file yang di-drop Qt yang menerima
URL-nya. Status hasil konversi muncul di jendela utama app.

Syarat & keterbatasan jujur:
- **Wajib sesi X11.** Cek dengan `echo $XDG_SESSION_TYPE`. Di Wayland ini
  dikunci oleh protokol (app lain tidak boleh mengintip drag global) — app
  akan menolak dengan penjelasan + cara ganti sesi di layar login Mint.
- Eksperimental: tidak semua aplikasi sumber drag mengevaluasi ulang target
  drop untuk jendela yang baru muncul di tengah drag. Nemo (GTK) umumnya mau;
  kalau di laptop kamu tidak mau, pakai Mode B.

## Mode B — Drop-zone + wheel (v1, selalu jalan)

1. Buka app → seret file dari Nemo/Nautilus ke **drop-zone** (atau klik drop-zone
   untuk memilih file).
2. **Radial wheel** muncul berisi format yang valid untuk file itu.
3. **Klik satu sektor** → file dikonversi → hasil disimpan **di sebelah file
   asli**, tidak pernah menimpa (`nama (1).jpg`, `nama (2).jpg`, …).

## Yang sudah bisa

| Input | Wheel (output) | Mesin |
|---|---|---|
| PDF | JPG, PNG (per halaman, 200 DPI), TXT, **PISAH**, **KOMPRES** | PyMuPDF |
| Banyak PDF sekaligus | **GABUNG** (+ semua format PDF di atas) | PyMuPDF |
| Gambar (JPG/PNG/WebP/BMP/TIFF/GIF) | JPG, PNG, WebP, PDF | Pillow |
| Banyak gambar sekaligus | PDF (digabung jadi 1 PDF) | Pillow |
| Dokumen (DOCX/DOC/ODT/RTF) | PDF, TXT, DOCX, ODT | LibreOffice |
| Presentasi (PPTX/PPT/ODP) | PDF, PPTX, ODP | LibreOffice |
| Spreadsheet (XLSX/XLS/ODS) | PDF, CSV, XLSX, ODS | LibreOffice |
| Teks (TXT/MD/LOG/CSV/INI/SH/PY/JSON/dll) | PDF | PyMuPDF |

> Video & audio **sengaja tidak didukung** (dihapus di v0.4.0 atas
> permintaan user — fokus ke dokumen, gambar, PDF). Konversi Office butuh
> LibreOffice terinstall (`sudo apt install libreoffice`; di Linux Mint
> biasanya sudah bawaan).

**PDF tools (v0.4.0):** GABUNG = banyak PDF jadi satu; PISAH = satu PDF
per halaman; KOMPRES = kecilkan PDF ke **target ukuran yang kamu tentukan
sendiri** (dalam KB — resolusi & kualitas gambar di dalam PDF diturunkan
bertahap sampai muat; hasil terkecil yang bisa dicapai dilaporkan apa
adanya kalau target tidak tercapai).

**Edit PDF (v0.4.0):** drop 1 PDF → tombol **"📝 Edit PDF"**. Tempel teks
(pilih **font dari yang terinstall di sistem**, ukuran, dan **warna** via
color picker) dan tempel gambar (logo/tanda tangan/foto) dengan **klik
langsung di preview halaman** untuk menaruh posisinya. Hasil disimpan
sebagai `-edit.pdf`, file asli tidak diubah.

Deteksi teks ala Linux (v0.3.3): file teks **tanpa ekstensi** atau dengan
ekstensi asing tetap dikenali dari isinya (sniff: bukan biner + bisa
di-decode sebagai teks), jadi tetap bisa dibuat PDF. File biner dan format
paket/dokumen terkompresi (deb/zip/dll) tidak akan ditebak sebagai teks.

## Editor gambar: Crop & Add BG (v0.3.0)

Drop **satu gambar** → tombol **"✂️ Crop & Add BG"** aktif. Di jendela editor
(preview langsung berubah saat slider digeser):

- **Crop** — potong sisi kiri/atas/kanan/bawah (slider %) + preset rasio
  tengah: 1:1, 4:3, 3:4, 3:2, 2:3, 16:9, 9:16.
- **Add BG** — gambar ditaruh di atas background warna (swatch oranye,
  kuning, putih, hitam, abu, biru, hijau, ungu, atau warna bebas):
  **Padding** (jarak tepi), **Corners** (sudut membulat), dan **Shadow**
  (bayangan di sisi gambar — atur blur, geser/offset, dan gelapnya).

Hasil disimpan sebagai file baru berakhiran `-edit` di sebelah file asli.

Catatan jujur v1:
- PDF → TXT hanya mengekstrak *text layer*. PDF hasil scan (gambar) akan
  kosong — belum ada OCR.
- Batch harus sejenis (semua PDF / semua gambar). Campur tipe ditolak dengan
  pesan jelas.
- GIF animasi → dikonversi sebagai frame pertama untuk JPG/PNG/PDF.

## Jalanin di Linux Mint

```bash
sudo apt install python3-venv libegl1 libgl1 libxkbcommon0
unzip salmanpdf-v1.zip && cd salmanpdf
./run.sh
```

Pertama kali `run.sh` membuat `.venv` dan menginstall dependency
(PySide6-Essentials, PyMuPDF, Pillow), setelah itu langsung membuka GUI.

## Cara update ke versi berikutnya

### Jalur GitHub (utama, kayak KYAI)

Repo: `github.com/riccohsaputra/salmanpdf` (private).

Install cara clone (sekali saja):

```bash
git clone https://github.com/riccohsaputra/salmanpdf.git
cd salmanpdf
chmod +x run.sh update.sh build-deb.sh   # wajib sekali: file dari GitHub kehilangan bit executable
./run.sh
```

> Kalau `./run.sh` kena "Permission denied", jalankan `chmod +x` di atas,
> atau pakai `bash run.sh` (cara ini tidak butuh bit executable sama sekali).

Update setelah itu cukup satu perintah dari folder clone:

```bash
./update.sh     # git pull --ff-only + laporan versi lama -> baru
./run.sh        # dependency di-sync otomatis kalau requirements berubah
```

### Jalur file (cadangan)

Update dikirim sebagai file `.deb` / `.zip` versi baru — install menimpa
yang lama, tidak perlu uninstall:

- **Dari .deb:** `sudo dpkg -i salmanpdf_<versi>_all.deb`
  venv lama dipakai ulang, dependency otomatis di-sync ulang dari
  `requirements.txt` versi baru (postinst).
- **Dari .zip:** ekstrak menimpa folder lama (folder `.venv` jangan dihapus),
  lalu `./run.sh` — dependency hanya di-sync ulang kalau
  `requirements.txt` berubah (dicek via hash stamp).

Tidak ada data/settings yang disimpan app ini, jadi update tidak menghapus
apa pun. Versi yang sedang jalan terlihat di judul jendela app.

## Mode CLI (buat scripting / integrasi KYAI nanti)

```bash
./run.sh --formats contoh.pdf          # -> contoh.pdf: wheel = ['JPG', 'PNG', 'TXT']
./run.sh --convert contoh.pdf JPG      # -> OK -> contoh.jpg
```

## Test

```bash
.venv/bin/pip install pytest
.venv/bin/python -m pytest tests/ -q    # 19 test: konversi + state machine Shift+Drag + edit gambar
```

## Struktur

```
main.py               entry point (GUI + CLI)
salmanpdf/
  converters.py       mesin konversi + tabel routing wheel
  imaging.py          crop + add background/shadow (murni Pillow, ter-test)
  editor.py           dialog editor gambar (preview live + slider)
  wheel.py            widget radial wheel (QPainter, hit-test polar)
  overlay.py          wheel overlay global = drop-target XDND (v2)
  statemachine.py     state machine Shift+Drag (logika murni, ter-test)
  xpoll.py            poller pointer global X11 (python-xlib)
  app.py              jendela utama: drop-zone, mode global, worker thread
tests/
  test_converters.py  test_statemachine.py
```

## Roadmap berikutnya (belum dikerjakan)

- Tools wheel kedua di mode global: sektor Crop / Add BG langsung di wheel.
- Kompres PDF/gambar ke target ukuran file.
- OCR untuk PDF scan (tesseract).
- Tray mode: app sembunyi total sampai Shift+drag terdeteksi.
