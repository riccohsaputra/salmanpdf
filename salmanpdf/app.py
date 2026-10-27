"""
GUI SalmanPDF — desain v0.6.0 meniru bahasa desain iLovePDF:
header putih bersih + hero typography besar + GRID KARTU ALAT
(ikon + judul + deskripsi, bisa diklik) + panel wheel khas SalmanPDF
di kanan. Palet: putih / abu hangat / merah. Semua flat, tanpa bayangan
berat — itu yang bikin UI terasa modern, bukan sekadar ganti warna.

Alur:
1. User seret file dari Nemo/Nautilus ke drop-zone (atau klik / tombol
   "Pilih File").
2. Wheel muncul berisi format yang valid, ATAU klik kartu alatnya.
3. Konversi lokal -> hasil di sebelah file asli.

Konversi jalan di QThread supaya UI tidak freeze.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QThread, QTimer, Signal
from PySide6.QtGui import (QDesktopServices, QIcon, QImage,
                           QPainter, QPixmap)
from PySide6.QtWidgets import (
    QApplication, QDialog, QFileDialog, QFrame, QGridLayout, QHBoxLayout,
    QInputDialog, QLabel, QMainWindow, QMessageBox, QProgressBar,
    QPushButton,
    QTextEdit,
    QScrollArea, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget,
)

FILE_FILTER = (
    "Didukung (*.pdf *.jpg *.jpeg *.png *.webp *.bmp *.gif *.tif *.tiff "
    "*.docx *.doc *.odt *.rtf *.pptx *.ppt *.odp "
    "*.xlsx *.xls *.ods "
    "*.txt *.text *.md *.log *.csv *.ini *.cfg *.sh *.py *.json);;"
    "Semua file (*)")

from .converters import ConversionError, convert_many, detect_kind, formats_for
from . import updater
from .editor import BgRemoveDialog, ImageEditorDialog
from .icons import tool_icon
from .overlay import WheelOverlay
from .pdf_editor import PdfEditorDialog, SplitDialog
from .statemachine import DragTracker
from .wheel import WheelWidget
from .xpoll import X11Poller, session_is_x11

KIND_LABEL = {
    "pdf": "PDF", "image": "Gambar", "text": "Teks",
    "word": "Dokumen Word", "slides": "Presentasi", "sheet": "Spreadsheet",
}


class ConvertWorker(QThread):
    done = Signal(list)
    failed = Signal(str)

    def __init__(self, files: list[Path], fmt: str,
                 target_bytes: int | None = None):
        super().__init__()
        self._files, self._fmt = files, fmt
        self._target = target_bytes

    def run(self) -> None:
        try:
            self.done.emit([str(p) for p in convert_many(
                self._files, self._fmt, target_bytes=self._target)])
        except ConversionError as e:
            self.failed.emit(str(e))
        except Exception as e:  # jaga-jaga: jangan sampai thread mati diam-diam
            self.failed.emit(f"Error tak terduga: {e}")


class ToolDropArea(QFrame):
    """Area drop halaman alat ala iLovePDF: tombol merah BESAR di tengah
    bertuliskan 'Pilih file', teks kecil 'atau seret file ke sini' di
    bawahnya, dan seluruh area menerima drag & drop."""

    filesDropped = Signal(list)
    pickRequested = Signal()

    def __init__(self, noun: str = "file"):
        super().__init__()
        self.setAcceptDrops(True)
        # Model iLovePDF: tombol merah BESAR tepat di bawah judul &
        # deskripsi halaman alat — BUKAN terapung di tengah halaman
        # (keluhan Ricco 2026-10-25). Area drop kompak, konten mulai
        # dari atas; sisa halaman kosong di bawahnya.
        self.setFixedHeight(132)
        self.pick_btn = QPushButton(f"Pilih {noun}")
        self.pick_btn.setStyleSheet(
            "QPushButton{background:#e5322d;color:#ffffff;"
            "font-size:19px;font-weight:700;border:none;border-radius:10px;"
            "padding:19px 72px}"
            "QPushButton:hover{background:#c92723;color:#ffffff}")
        self.pick_btn.clicked.connect(self.pickRequested.emit)
        hint = QLabel(f"atau seret {noun} ke sini")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet("font-size:13px;color:#7a7f87")
        self.hint_lbl = hint
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 10, 0, 0)
        col.setSpacing(10)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self.pick_btn)
        row.addStretch(1)
        col.addLayout(row)
        col.addWidget(hint)

    def dragEnterEvent(self, event):  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):  # noqa: N802
        files = [Path(u.toLocalFile()) for u in event.mimeData().urls()
                 if u.isLocalFile()]
        if files:
            self.filesDropped.emit(files)


class UpdateWorker(QThread):
    """Cek update di latar belakang (jaringan tak boleh memblokir UI).
    Dari checkout git: cek lewat git lokal (jalan walau repo privat).
    Instalasi paket: cek lewat HTTP ke GitHub."""
    done = Signal(object)

    def __init__(self, current: str, root=None):
        super().__init__()
        self._current = current
        self._root = root

    def run(self):  # noqa: N802 (Qt API)
        if self._root is not None:
            self.done.emit(
                updater.check_update_git(self._current, self._root))
        else:
            self.done.emit(updater.check_update_detailed(self._current))


class PullWorker(QThread):
    """git pull --ff-only di checkout lokal (jalur update Linux/dev)."""
    done = Signal(bool, str)

    def __init__(self, root: Path):
        super().__init__()
        self._root = root

    def run(self):  # noqa: N802 (Qt API)
        try:
            proc = subprocess.run(
                ["git", "pull", "--ff-only"], cwd=str(self._root),
                capture_output=True, text=True, timeout=180)
            if proc.returncode != 0:
                tail = (proc.stderr or proc.stdout or "").strip().splitlines()
                self.done.emit(False, tail[-1] if tail else "git pull gagal.")
                return
            note = ""
            req = self._root / "requirements.txt"
            if req.exists():
                try:
                    import sys as _sys

                    subprocess.run(
                        [_sys.executable, "-m", "pip", "install", "-q",
                         "-r", str(req)],
                        capture_output=True, text=True, timeout=600)
                    note = " Dependensi ikut disinkronkan."
                except Exception:
                    note = " (Sinkron dependensi dilewati — jalankan run.sh bila ada fitur baru yang butuh library tambahan.)"
            tail = (proc.stdout or "").strip().splitlines()
            self.done.emit(True, (tail[-1] if tail else "git pull selesai.") + note)
        except Exception as e:
            self.done.emit(False, str(e))


# ---------------------------------------------------------------- tema
C_LIGHT = dict(page="#ffffff", header_bg="#ffffff", header_border="#e2e6ee",
               title="#1f2430", text="#26221f", sub="#6b7280",
               faint="#9aa0a8", card_bg="#ffffff", card_border="#e2e6ee",
               desc="#6b7280", status="#555b63")
C_DARK = dict(page="#1d2025", header_bg="#23262d", header_border="#33373f",
              title="#f1f3f4", text="#e8eaed", sub="#9aa0a8",
              faint="#7a7f87", card_bg="#26292f", card_border="#363b44",
              desc="#9aa0a8", status="#b8bcc2")


def _white_variant(pix: QPixmap) -> QPixmap:
    """Versi putih dari pixmap glyph (alpha sama, warna jadi putih) —
    untuk mode gelap supaya ikon garis hitam tetap kelihatan."""
    img = pix.toImage().convertToFormat(QImage.Format.Format_ARGB32)
    out = QImage(img.size(), QImage.Format.Format_ARGB32)
    out.fill(0)
    painter = QPainter(out)
    try:
        painter.fillRect(out.rect(), Qt.GlobalColor.white)
        painter.setCompositionMode(
            QPainter.CompositionMode.CompositionMode_DestinationIn)
        painter.drawImage(0, 0, img)
    finally:
        painter.end()
    return QPixmap.fromImage(out)


# ---------------------------------------------------------------- kartu alat
# PENTING: selector WAJIB ter-scope ke #toolCard. QLabel adalah subclass
# QFrame di Qt — selector "QFrame{...}" polos MENULAR ke semua label anak
# (kejadian v0.6.0: judul & deskripsi kartu ikut kena border).
_CARD_BASE = ("#toolCard{background:#ffffff;border:1px solid #e2e6ee;"
              "border-radius:16px}")
_CARD_HOVER = ("#toolCard{background:#ffffff;border:1px solid #d92323;"
               "border-radius:16px}")


class ToolCard(QFrame):
    """Kartu alat gaya iLovePDF: ikon vektor BESAR di kiri-atas, judul
    tebal di bawahnya, deskripsi abu. Tinggi tetap, flat, hover merah."""

    clicked = Signal()
    MIN_HEIGHT = 138

    def __init__(self, icon: str, title: str, desc: str, category: str):
        super().__init__()
        self.setObjectName("toolCard")
        self.category = category
        self._icon_name = icon
        self._ss_base = _CARD_BASE
        self._ss_hover = _CARD_HOVER
        self.setStyleSheet(_CARD_BASE)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        # Ukuran konsisten ala iLovePDF: lebar fleksibel mengikuti kolom
        # grid responsif, tinggi tetap. Yang menyesuaikan jumlah KOLOM,
        # bukan ukuran kartu (kartu raksasa meregang = terlihat kosong).
        self.setFixedHeight(214)
        self.setMinimumWidth(225)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Fixed)
        self._desc = desc
        self.icon_lbl = QLabel()
        self.icon_lbl.setFixedSize(56, 56)
        self.icon_lbl.setPixmap(tool_icon(icon, 56))
        self.title_lbl = QLabel(title)
        self.title_lbl.setStyleSheet(
            "font-size:16px;font-weight:700;color:#1f2430")
        self.desc_lbl = QLabel(desc)
        self.desc_lbl.setWordWrap(True)
        self.desc_lbl.setStyleSheet("font-size:12.5px;color:#6b7280")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 14)
        lay.setSpacing(6)
        lay.addWidget(self.icon_lbl)
        lay.addWidget(self.title_lbl)
        lay.addWidget(self.desc_lbl)
        lay.addStretch(1)

    def enterEvent(self, event):  # noqa: N802
        self.setStyleSheet(self._ss_hover)
        super().enterEvent(event)

    def leaveEvent(self, event):  # noqa: N802
        self.setStyleSheet(self._ss_base)
        super().leaveEvent(event)

    def apply_theme(self, dark: bool) -> None:
        c = C_DARK if dark else C_LIGHT
        self._ss_base = (
            f"#toolCard{{background:{c['card_bg']};"
            f"border:1px solid {c['card_border']};border-radius:16px}}")
        self._ss_hover = (
            f"#toolCard{{background:{c['card_bg']};"
            "border:1px solid #d92323;border-radius:16px}")
        self.setStyleSheet(self._ss_base)
        self.title_lbl.setStyleSheet(
            f"font-size:16px;font-weight:700;color:{c['title']}")
        self.desc_lbl.setStyleSheet(
            f"font-size:12.5px;color:{c['desc']}")

    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def set_active(self, on: bool, desc: str | None = None) -> None:
        self.icon_lbl.setPixmap(tool_icon(self._icon_name, 56, active=on))
        self.desc_lbl.setText(desc if desc is not None else self._desc)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        from . import __version__
        self.setWindowTitle(f"SalmanPDF 📄 — v{__version__}")
        self.resize(1120, 740)
        # Ukuran minimum waras + hint tombol maximize EKSPLISIT: jendela
        # harus selalu bisa di-minimize/maximize/close normal.
        self.setMinimumSize(880, 580)
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowCloseButtonHint)
        self._files: list[Path] = []
        self._worker: ConvertWorker | None = None
        # Tema terang/gelap (persisten via QSettings)
        self._settings = QSettings("SalmanPDF", "SalmanPDF")
        self._dark = self._settings.value("dark", False, type=bool)
        self._c = C_DARK if self._dark else C_LIGHT
        self._pill_on, self._pill_off = self._pill_styles()

        self.info = QLabel("Belum ada file.")
        self.info.setWordWrap(True)
        self.info.setStyleSheet("font-size:12px;color:#555b63")

        self.wheel = WheelWidget()
        self.wheel.formatSelected.connect(self.on_format)
        # Wheel TIDAK lagi dipajang permanen di halaman utama (permintaan
        # Ricco 2026-10-25: placeholder "Seret file dulu ya" dihilangkan).
        # Ia tinggal di dialog Konversi Cepat yang muncul saat file dipilih
        # lewat tombol "Pilih File".
        self._wheel_dialog = QDialog(self)
        self._wheel_dialog.setWindowTitle("Konversi Cepat — SalmanPDF")
        wd_lay = QVBoxLayout(self._wheel_dialog)
        wd_lay.addWidget(self.wheel)
        wd_hint = QLabel("Klik format tujuan untuk langsung konversi.")
        wd_hint.setAlignment(Qt.AlignCenter)
        wd_hint.setStyleSheet("font-size:11.5px;color:#6b7280")
        wd_lay.addWidget(wd_hint)
        self._wheel_dialog.resize(336, 380)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # indeterminate
        self.progress.setFixedWidth(150)
        self.progress.hide()

        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setStyleSheet("font-size:12px;color:#555b63")

        self.open_btn = QPushButton("Buka folder hasil")
        self.open_btn.hide()
        self.open_btn.clicked.connect(self.open_folder)
        self._last_folder: Path | None = None

        # ---- Mode global Shift+Drag (v2, X11 eksperimental) ----
        self._poller: X11Poller | None = None
        self._tracker = DragTracker()
        self._overlay: WheelOverlay | None = None
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(25)
        self._poll_timer.timeout.connect(self._poll_global)

        # ================= Header (ala iLovePDF) =================
        header = QFrame()
        self._header = header
        header.setObjectName("appHeader")
        header.setStyleSheet(
            "#appHeader{background:#ffffff;"
            "border-bottom:1px solid #e2e6ee}")
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(20, 10, 20, 10)
        logo = QLabel()
        self._logo_lbl = logo
        self._logo_pix: QPixmap | None = None
        self._logo_white: QPixmap | None = None
        logo.setFixedSize(38, 38)
        logo.setAlignment(Qt.AlignCenter)
        try:
            import base64

            from PySide6.QtGui import QPixmap

            from .icon_data import APPICON_PNG_B64
            _pix = QPixmap()
            if _pix.loadFromData(base64.b64decode(APPICON_PNG_B64)):
                self._logo_pix = _pix
                logo.setPixmap(_pix.scaled(
                    38, 38, Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation))
            else:
                raise ValueError("ikon gagal dibaca")
        except Exception:
            logo.setText("S")
            logo.setStyleSheet(
                "background:#d92323;color:#ffffff;font-size:18px;"
                "font-weight:800;border-radius:9px")
        h_lay.addWidget(logo)
        brand = QVBoxLayout()
        brand.setSpacing(0)
        brand_name = QLabel("SalmanPDF")
        self._brand_name = brand_name
        brand_name.setStyleSheet(
            "font-size:17px;font-weight:800;color:#23272f")
        brand_tag = QLabel("Konverter PDF & dokumen — 100% lokal")
        self._brand_tag = brand_tag
        brand_tag.setStyleSheet("font-size:10.5px;color:#7a7f87")
        brand.addWidget(brand_name)
        brand.addWidget(brand_tag)
        h_lay.addLayout(brand)
        h_lay.addStretch(1)
        self.btn_update = QPushButton("🔄 Update")
        self.btn_update.setToolTip("Periksa & pasang update SalmanPDF")
        self.btn_update.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_update.clicked.connect(lambda: self._check_update(True))
        h_lay.addWidget(self.btn_update)
        self.theme_btn = QPushButton("🌙")
        self.theme_btn.setFixedSize(38, 38)
        self.theme_btn.setToolTip("Ganti mode gelap / terang")
        self.theme_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.theme_btn.clicked.connect(self._toggle_theme)
        h_lay.addWidget(self.theme_btn)
        ver_lbl = QLabel(f"v{__version__}")
        self._ver_lbl = ver_lbl
        ver_lbl.setStyleSheet("font-size:11px;color:#9aa0a8")
        h_lay.addWidget(ver_lbl)
        pick_btn = QPushButton("Pilih File")
        pick_btn.setStyleSheet(
            "QPushButton{background:#d92323;color:#ffffff;font-weight:700;"
            "border:none;border-radius:8px;padding:9px 20px}"
            "QPushButton:hover{background:#b91c1c;color:#ffffff}")
        pick_btn.clicked.connect(self._pick_quick)
        h_lay.addWidget(pick_btn)

        # ================= Hero =================
        hero_title = QLabel("Semua alat PDF & dokumen dalam satu tempat")
        self._hero_title = hero_title
        hero_title.setAlignment(Qt.AlignCenter)
        # Font 32px/800: tinggi label dikunci + padding vertikal supaya
        # puncak huruf tidak kepotong (VBox suka under-report tinggi QLabel)
        hero_title.setMinimumHeight(56)
        hero_title.setStyleSheet(
            "font-size:32px;font-weight:800;color:#1f2430;"
            "padding:8px 0 4px 0")
        self._hero_sub = None
        hero_sub = QLabel(
            "Gabung, pisah, kompres, konversi, dan edit — semuanya diproses "
            "lokal di laptop kamu, tanpa upload.")
        hero_sub.setAlignment(Qt.AlignCenter)
        self._hero_sub = hero_sub
        hero_sub.setWordWrap(True)
        hero_sub.setMaximumWidth(920)
        # QLabel word-wrap di VBox sering salah hitung tinggi (teks
        # kegencet/terpotong vertikal — dilaporkan Ricco 2026-10-25).
        # Teks ini membungkus jadi 3 baris pada lebar jendela umum:
        # kunci tinggi minimum 3 baris + padding supaya selalu lega.
        hero_sub.setMinimumHeight(78)
        hero_sub.setStyleSheet(
            "font-size:14.5px;color:#6b7280;padding:6px 0")

        # ================= Filter pills (ala iLovePDF) =================
        self._pills: list[tuple[QPushButton, str | None]] = []
        pills_row = QHBoxLayout()
        pills_row.addStretch(1)
        for label, cat in [("Semua", None), ("Atur PDF", "atur"),
                           ("Konversi", "konversi"), ("Edit", "edit"),
                           ("Lainnya", "lainnya")]:
            pill = QPushButton(label)
            pill.setCheckable(True)
            pill.setChecked(cat is None)
            pill.clicked.connect(
                lambda _=False, c=cat: self._filter_cards(c))
            self._pills.append((pill, cat))
            pills_row.addWidget(pill)
        pills_row.addStretch(1)
        self._style_pills()

        # ================= Grid kartu alat (4 kolom) =================
        self.card_gabung = ToolCard(
            "gabung", "Gabung PDF", "Satukan banyak PDF menjadi satu file", "atur")
        self.card_gabung.clicked.connect(lambda: self.open_tool("gabung"))
        self.card_pisah = ToolCard(
            "pisah", "Pisah PDF", "Pilih sendiri halaman yang mau dipisah jadi PDF baru", "atur")
        self.card_pisah.clicked.connect(lambda: self.open_tool("pisah"))
        self.card_kompres = ToolCard(
            "kompres", "Kompres PDF", "Kecilkan PDF ke target ukuran yang kamu mau",
            "atur")
        self.card_kompres.clicked.connect(lambda: self.open_tool("kompres"))
        self.card_editpdf = ToolCard(
            "edit", "Edit PDF", "Tempel teks & gambar ke dalam PDF", "edit")
        self.card_editpdf.clicked.connect(lambda: self.open_tool("editpdf"))
        self.card_pdfimg = ToolCard(
            "pdfimg", "PDF ke JPG", "Ubah tiap halaman PDF menjadi JPG",
            "konversi")
        self.card_pdfimg.clicked.connect(lambda: self.open_tool("pdfimg"))
        self.card_imgpdf = ToolCard(
            "imgpdf", "JPG ke PDF", "Ubah gambar JPG menjadi PDF dalam sekejap",
            "konversi")
        self.card_imgpdf.clicked.connect(lambda: self.open_tool("imgpdf"))
        self.card_office = ToolCard(
            "office", "Office ke PDF", "DOCX, PPTX, XLSX, ODT jadi PDF rapi",
            "konversi")
        self.card_office.clicked.connect(lambda: self.open_tool("office"))
        self.card_crop = ToolCard(
            "crop", "Crop & Add BG", "Potong gambar + beri background & shadow",
            "edit")
        self.card_crop.clicked.connect(lambda: self.open_tool("crop"))
        self.card_removebg = ToolCard(
            "removebg", "Hapus Background",
            "Hilangkan background putih gambar jadi transparan", "edit")
        self.card_removebg.clicked.connect(lambda: self.open_tool("removebg"))
        self.card_global = ToolCard(
            "global", "Mode Global", "Shift + seret file di Nemo, wheel muncul",
            "lainnya")
        self.card_global.clicked.connect(self.toggle_global)

        self._cards = [self.card_gabung, self.card_pisah, self.card_kompres,
                       self.card_editpdf, self.card_pdfimg, self.card_imgpdf,
                       self.card_office, self.card_crop, self.card_removebg,
                       self.card_global]
        # Grid RESPONSIF ala iLovePDF: jumlah kolom mengikuti lebar area
        # (jendela kecil 2-3 kolom, maximize sampai 6 kolom). Kartu ukurannya
        # konsisten & rata atas; sisa ruang vertikal jatuh ke bawah grid.
        self.grid = QGridLayout()
        self.grid.setSpacing(16)
        for c in range(6):
            self.grid.setColumnStretch(c, 1)
        self._grid_sig: tuple | None = None
        self._filter: str | None = None
        grid_wrap = QVBoxLayout()
        grid_wrap.setContentsMargins(0, 0, 0, 0)
        grid_wrap.addLayout(self.grid)
        grid_wrap.addStretch(1)
        self.grid_container = QWidget()
        self.grid_container.setLayout(grid_wrap)
        grid = grid_wrap
        self._relayout_grid()

        # ============ Strip status di bawah grid (tanpa sidebar) =======
        strip = QVBoxLayout()
        strip.setSpacing(4)
        strip.addWidget(self.info)
        strip.addWidget(self.status)
        prog_row = QHBoxLayout()
        prog_row.addWidget(self.progress)
        prog_row.addStretch(1)
        prog_row.addWidget(self.open_btn)
        strip.addLayout(prog_row)

        content_row = QHBoxLayout()
        content_row.setSpacing(16)
        content_row.addWidget(self.grid_container, 1)

        body = QVBoxLayout()
        body.setContentsMargins(26, 16, 26, 14)
        body.setSpacing(11)
        body.addWidget(hero_title)
        body.addWidget(hero_sub, 0, Qt.AlignmentFlag.AlignHCenter)
        body.addLayout(pills_row)
        body.addLayout(content_row, 1)
        body.addLayout(strip)
        credit = QLabel("created by Ricco Abu Salman")
        self._credit = credit
        credit.setAlignment(Qt.AlignCenter)
        credit.setStyleSheet(
            "font-size:13.5px;font-weight:700;color:#26221f;"
            "padding:6px 0 2px 0")
        body.addWidget(credit)
        inner = QWidget()
        inner.setLayout(body)
        home_outer = QHBoxLayout()
        home_outer.setContentsMargins(0, 0, 0, 0)
        home_outer.addStretch(1)
        home_outer.addWidget(inner)
        home_outer.addStretch(1)
        home_page = QWidget()
        home_page.setLayout(home_outer)

        self._stack = QStackedWidget()
        # Halaman utama dibungkus SCROLL AREA persis halaman web: konten
        # yang lebih tinggi dari jendela di-scroll, BUKAN memaksa jendela
        # jadi raksasa (v0.6.4: grid 2 kolom -> min height > layar ->
        # jendela meluber & tombol maximize hilang di tema Cinnamon-nya).
        home_scroll = QScrollArea()
        self._home_scroll = home_scroll
        home_scroll.setWidgetResizable(True)
        home_scroll.setFrameShape(QFrame.Shape.NoFrame)
        home_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        home_scroll.setStyleSheet("QScrollArea{background:#ffffff}")
        home_scroll.viewport().setStyleSheet(
            "background:#ffffff")
        home_scroll.setWidget(home_page)
        self._stack.addWidget(home_scroll)
        self._stack.addWidget(self._build_tool_page())

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(header)
        layout.addWidget(self._stack, 1)

        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)
        self._apply_theme()
        # Cek update senyap tak lama setelah start (maks. ~sekali sehari)
        QTimer.singleShot(2500, self._maybe_auto_check)

    # ------------------------------------------------- halaman alat (tool page)
    TOOLS = {
        "gabung": dict(
            title="Gabung PDF",
            desc="Satukan PDF sesuai urutan yang kamu mau dengan "
                 "penggabung PDF termudah.",
            kinds={"pdf"}, min_files=2, action="Gabung PDF",
            fmt="GABUNG", noun="file PDF"),
        "pisah": dict(
            title="Pisah PDF",
            desc="Tentukan sendiri halaman yang dipisah: tulis rentang "
                 "(mis. 1-3, 5, 8-10) menjadi beberapa PDF, atau ekstrak "
                 "halaman pilihan menjadi satu PDF.",
            kinds={"pdf"}, min_files=1, max_files=1,
            action="Atur Halaman & Pisahkan", run="split_pdf",
            noun="file PDF"),
        "kompres": dict(
            title="Kompres PDF",
            desc="Kecilkan ukuran file sambil mengoptimalkan kualitas — "
                 "target ukurannya kamu yang tentukan.",
            kinds={"pdf"}, min_files=1, action="Kompres PDF",
            fmt="KOMPRES", noun="file PDF"),
        "editpdf": dict(
            title="Edit PDF",
            desc="Tempel teks dan gambar ke dokumen PDF. Atur font, "
                 "ukuran, dan warnanya.",
            kinds={"pdf"}, min_files=1, max_files=1,
            action="Buka Editor PDF", run="edit_pdf", noun="file PDF"),
        "pdfimg": dict(
            title="PDF ke JPG",
            desc="Ubah setiap halaman PDF menjadi gambar JPG.",
            kinds={"pdf"}, min_files=1, action="Konversi ke JPG",
            fmt="JPG", noun="file PDF"),
        "imgpdf": dict(
            title="JPG ke PDF",
            desc="Ubah gambar menjadi PDF dalam sekejap. Banyak gambar "
                 "digabung menjadi satu PDF.",
            kinds={"image"}, min_files=1, action="Konversi ke PDF",
            fmt="PDF", noun="gambar"),
        "office": dict(
            title="Office ke PDF",
            desc="Buat file DOC dan DOCX, PPT, dan XLS mudah dibaca "
                 "dengan mengubahnya menjadi PDF.",
            kinds={"word", "slides", "sheet"}, min_files=1,
            action="Konversi ke PDF", fmt="PDF", noun="file Office"),
        "removebg": dict(
            title="Hapus Background Gambar",
            desc="Hilangkan background putih/terang pada gambar menjadi "
                 "transparan dengan tepi yang halus. Hasil PNG transparan.",
            kinds={"image"}, min_files=1, max_files=1,
            action="Buka Penghapus Background", run="remove_bg",
            noun="gambar"),
        "crop": dict(
            title="Crop & Add BG",
            desc="Potong sisi gambar, lalu beri background, sudut "
                 "membulat, dan shadow.",
            kinds={"image"}, min_files=1, max_files=1,
            action="Buka Editor Gambar", run="edit_image", noun="gambar"),
    }

    def _build_tool_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(26, 14, 26, 14)
        lay.setSpacing(10)
        back_btn = QPushButton("←  Kembali ke semua alat")
        self._back_btn = back_btn
        back_btn.setStyleSheet(
            "QPushButton{background:transparent;border:none;color:#555b63;"
            "font-size:12.5px;padding:4px 8px;text-align:left}"
            "QPushButton:hover{color:#d92323}")
        back_btn.clicked.connect(lambda: self._stack.setCurrentIndex(0))
        top = QHBoxLayout()
        top.addWidget(back_btn)
        top.addStretch(1)
        lay.addLayout(top)
        self.tool_title = QLabel("")
        self.tool_title.setAlignment(Qt.AlignCenter)
        self.tool_title.setMinimumHeight(50)
        self.tool_title.setStyleSheet(
            "font-size:29px;font-weight:800;color:#23272f;"
            "padding:6px 0 2px 0")
        lay.addWidget(self.tool_title)
        self.tool_desc = QLabel("")
        self.tool_desc.setAlignment(Qt.AlignCenter)
        self.tool_desc.setWordWrap(True)
        self.tool_desc.setMinimumHeight(40)
        self.tool_desc.setStyleSheet(
            "font-size:13px;color:#7a7f87;padding:2px 0")
        lay.addWidget(self.tool_desc)
        self.tool_area = ToolDropArea()
        self.tool_area.filesDropped.connect(self._tool_accept)
        self.tool_area.pickRequested.connect(self._tool_pick)
        lay.addWidget(self.tool_area)
        self.tool_files_lbl = QLabel("")
        self.tool_files_lbl.setAlignment(Qt.AlignCenter)
        self.tool_files_lbl.setStyleSheet("font-size:12.5px;color:#23272f")
        lay.addWidget(self.tool_files_lbl)
        self.tool_action = QPushButton("")
        self.tool_action.setStyleSheet(
            "QPushButton{background:#e5322d;color:#ffffff;"
            "font-size:15px;font-weight:700;border:none;border-radius:10px;"
            "padding:13px 40px}"
            "QPushButton:hover{background:#c92723;color:#ffffff}")
        self.tool_action.hide()
        self.tool_action.clicked.connect(self._tool_run)
        act_row = QHBoxLayout()
        act_row.addStretch(1)
        act_row.addWidget(self.tool_action)
        act_row.addStretch(1)
        lay.addLayout(act_row)
        self.tool_status = QLabel("")
        self.tool_status.setAlignment(Qt.AlignCenter)
        self.tool_status.setWordWrap(True)
        self.tool_status.setStyleSheet("font-size:12px;color:#555b63")
        lay.addWidget(self.tool_status)
        lay.addStretch(1)
        self._tool_key: str | None = None
        return page

    def open_tool(self, key: str) -> None:
        cfg = self.TOOLS[key]
        self._tool_key = key
        self.tool_title.setText(cfg["title"])
        self.tool_desc.setText(cfg["desc"])
        self.tool_area.pick_btn.setText(f"Pilih {cfg['noun']}")
        self.tool_files_lbl.setText("")
        self.tool_status.setText("")
        self.tool_action.setText(cfg["action"])
        self.tool_action.hide()
        self._stack.setCurrentIndex(1)
        if self._files:  # file dari mode cepat (wheel) yang cocok -> pakai
            self._tool_accept(self._files, quiet=True)

    def _tool_cfg(self) -> dict:
        return self.TOOLS[self._tool_key]

    def _tool_validate(self, files: list[Path]) -> str | None:
        cfg = self._tool_cfg()
        kinds = {detect_kind(f) for f in files}
        if None in kinds or not kinds <= cfg["kinds"]:
            return (f"Alat ini hanya menerima: "
                    f"{', '.join(sorted(cfg['kinds']))}. File yang kamu "
                    f"berikan tidak cocok.")
        if len(files) < cfg.get("min_files", 1):
            return f"Alat ini butuh minimal {cfg['min_files']} file."
        if "max_files" in cfg and len(files) > cfg["max_files"]:
            return f"Alat ini hanya untuk {cfg['max_files']} file."
        return None

    def _tool_accept(self, files: list[Path], quiet: bool = False) -> None:
        files = [Path(f) for f in files]
        err = self._tool_validate(files)
        if err:
            if not quiet:
                self.tool_status.setText(f"⚠️ {err}")
            return
        self._files = files
        names = ", ".join(f.name for f in files[:3])
        if len(files) > 3:
            names += f", +{len(files) - 3} lagi"
        self.tool_files_lbl.setText(f"📄 {len(files)} file dipilih: {names}")
        self.tool_status.setText("")
        self.tool_action.show()

    def _tool_pick(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Pilih file", "", FILE_FILTER)
        if paths:
            self._tool_accept([Path(p) for p in paths])

    def _tool_run(self) -> None:
        cfg = self._tool_cfg()
        if cfg.get("run") == "edit_pdf":
            self.on_pdf_edit()
        elif cfg.get("run") == "split_pdf":
            self.on_split()
        elif cfg.get("run") == "edit_image":
            self.on_edit()
        elif cfg.get("run") == "remove_bg":
            self.on_remove_bg()
        else:
            self.on_format(cfg["fmt"])

    def _pick_quick(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Pilih file", "", FILE_FILTER)
        if paths:
            self.on_files([Path(p) for p in paths])

    # ------------------------------------------------- filter pills
    _PILL_ON = ("QPushButton{background:#1f2430;color:#ffffff;font-weight:600;"
                "font-size:13px;border:1px solid #1f2430;border-radius:18px;"
                "padding:8px 17px}")
    _PILL_OFF = ("QPushButton{background:#ffffff;color:#3c4043;"
                 "font-size:13px;border:1px solid #d9dee7;border-radius:18px;"
                 "padding:8px 17px} QPushButton:hover{border-color:#d92323;"
                 "color:#d92323}")

    def _pill_styles(self) -> tuple[str, str]:
        if self._dark:
            on = ("QPushButton{background:#e8eaed;color:#1d2025;"
                  "font-weight:600;font-size:13px;border:1px solid #e8eaed;"
                  "border-radius:18px;padding:8px 17px}")
            off = ("QPushButton{background:#26292f;color:#e8eaed;"
                   "font-size:13px;border:1px solid #3a3f47;"
                   "border-radius:18px;padding:8px 17px}"
                   "QPushButton:hover{border-color:#ff6b61;color:#ff6b61}")
        else:
            on, off = self._PILL_ON, self._PILL_OFF
        return on, off

    def _style_pills(self) -> None:
        for pill, _cat in self._pills:
            pill.setStyleSheet(self._pill_on if pill.isChecked()
                               else self._pill_off)

    # ------------------------------------------------------------- tema
    def _toggle_theme(self) -> None:
        self._dark = not self._dark
        self._settings.setValue("dark", self._dark)
        self._apply_theme()

    def _apply_theme(self) -> None:
        c = C_DARK if self._dark else C_LIGHT
        self._c = c
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(DARK_THEME if self._dark else LIGHT_THEME)
        if self._logo_pix is not None:
            if self._dark:
                if self._logo_white is None:
                    self._logo_white = _white_variant(self._logo_pix)
                use = self._logo_white
            else:
                use = self._logo_pix
            self._logo_lbl.setPixmap(use.scaled(
                38, 38, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))
            self.setWindowIcon(QIcon(use))
        self.btn_update.setStyleSheet(
            f"QPushButton{{background:{c['card_bg']};color:{c['text']};"
            f"border:1px solid {c['card_border']};border-radius:10px;"
            "font-size:12.5px;padding:8px 12px}"
            "QPushButton:hover{border-color:#d92323;color:#d92323}")
        self.theme_btn.setText("☀️" if self._dark else "🌙")
        self.theme_btn.setStyleSheet(
            f"QPushButton{{background:{c['card_bg']};"
            f"border:1px solid {c['card_border']};border-radius:10px;"
            "font-size:16px}"
            "QPushButton:hover{border-color:#d92323}")
        self._header.setStyleSheet(
            f"#appHeader{{background:{c['header_bg']};"
            f"border-bottom:1px solid {c['header_border']}}}")
        self._brand_name.setStyleSheet(
            f"font-size:17px;font-weight:800;color:{c['title']}")
        self._brand_tag.setStyleSheet(
            f"font-size:10.5px;color:{c['sub']}")
        self._ver_lbl.setStyleSheet(f"font-size:11px;color:{c['faint']}")
        self._hero_title.setStyleSheet(
            f"font-size:32px;font-weight:800;color:{c['title']};"
            "padding:8px 0 4px 0")
        if self._hero_sub is not None:
            self._hero_sub.setStyleSheet(
                f"font-size:14.5px;color:{c['sub']};padding:6px 0")
        self.info.setStyleSheet(f"font-size:12px;color:{c['status']}")
        self.status.setStyleSheet(f"font-size:12px;color:{c['status']}")
        self._credit.setStyleSheet(
            f"font-size:13.5px;font-weight:700;color:{c['text']};"
            "padding:6px 0 2px 0")
        self._pill_on, self._pill_off = self._pill_styles()
        self._style_pills()
        for card in self._cards:
            card.apply_theme(self._dark)
        self._home_scroll.setStyleSheet(
            f"QScrollArea{{background:{c['page']}}}")
        self._home_scroll.viewport().setStyleSheet(
            f"background:{c['page']}")
        self.tool_title.setStyleSheet(
            f"font-size:29px;font-weight:800;color:{c['title']};"
            "padding:6px 0 2px 0")
        self.tool_desc.setStyleSheet(
            f"font-size:13px;color:{c['sub']};padding:2px 0")
        self.tool_files_lbl.setStyleSheet(
            f"font-size:12.5px;color:{c['title']}")
        self.tool_status.setStyleSheet(
            f"font-size:12px;color:{c['status']}")
        self.tool_area.hint_lbl.setStyleSheet(
            f"font-size:13px;color:{c['sub']}")
        self._back_btn.setStyleSheet(
            "QPushButton{background:transparent;border:none;"
            f"color:{c['status']};font-size:12.5px;padding:4px 8px;"
            "text-align:left}"
            "QPushButton:hover{color:#d92323}")

    def _filter_cards(self, category: str | None) -> None:
        for pill, cat in self._pills:
            pill.setChecked(cat == category)
        self._style_pills()
        self._filter = category
        self._grid_sig = None
        self._relayout_grid()

    # ------------------------------------------------- grid responsif
    def _relayout_grid(self) -> None:
        """Susun ulang kartu mengikuti lebar JENDELA & filter aktif.
        Lebar jendela dipakai (bukan lebar kontainer) karena lebar
        kontainer belum final saat resizeEvent beruntun — v0.6.4 sempat
        salah hitung jadi 2 kolom di jendela 1150px."""
        avail = self.width() - 56  # margin body kiri-kanan
        cols = max(2, min(6, avail // 280))
        vis = [c for c in self._cards
               if self._filter is None or c.category == self._filter]
        sig = (cols, tuple(id(c) for c in vis))
        if sig == self._grid_sig:
            return
        self._grid_sig = sig
        while self.grid.count():
            self.grid.takeAt(0)
        in_grid = set()
        for i, card in enumerate(vis):
            self.grid.addWidget(card, i // cols, i % cols)
            card.show()
            in_grid.add(id(card))
        for card in self._cards:
            if id(card) not in in_grid:
                card.hide()

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        QTimer.singleShot(0, self._relayout_grid)

    # ------------------------------------------------------------- flow
    def on_files(self, files: list[Path]) -> None:
        supported = [f for f in files if detect_kind(f) is not None]
        skipped = [f.name for f in files if detect_kind(f) is None]
        if not supported:
            self.status.setText("⚠️ Tipe file belum didukung di v1: "
                                + ", ".join(skipped))
            return
        kinds = {detect_kind(f) for f in supported}
        if len(kinds) > 1:
            self.status.setText("⚠️ Campur tipe file belum didukung — "
                                "drop file sejenis saja ya (mis. semua PDF / semua gambar).")
            return
        # Format wheel = irisan format valid semua file
        common = set(formats_for(supported[0]))
        for f in supported[1:]:
            common &= set(formats_for(f))
        if not common:
            self.status.setText("⚠️ Nggak ada format tujuan yang sama untuk file-file ini.")
            return
        order = [f for f in formats_for(supported[0]) if f in common]
        if len(supported) > 1 and all(detect_kind(f) == "pdf" for f in supported):
            order.append("GABUNG")  # fitur merge khusus multi-PDF
        self._files = supported
        kind = KIND_LABEL[detect_kind(supported[0])]
        names = ", ".join(f.name for f in supported[:3])
        if len(supported) > 3:
            names += f", +{len(supported) - 3} lagi"
        self.info.setText(f"📄 {len(supported)} file {kind}: {names}\n"
                          "Klik format di jendela Konversi Cepat, atau buka kartu alatnya.")
        center = supported[0].name if len(supported) == 1 else f"{len(supported)} file"
        self.wheel.set_wheel(order, center)
        self._wheel_dialog.show()
        self._wheel_dialog.raise_()
        msg = "Siap. Semua konversi lokal, hasil disimpan di sebelah file asli."
        if skipped:
            msg += f" (Dilewati, tak didukung: {', '.join(skipped)})"
        self.status.setText(msg)
        self.open_btn.hide()

    def on_format(self, fmt: str) -> None:
        if not self._files or (self._worker and self._worker.isRunning()):
            return
        target_bytes: int | None = None
        self._kompres_target = None
        if fmt == "KOMPRES":
            # User menentukan target ukuran sendiri (dalam KB).
            size_kb = max(1, self._files[0].stat().st_size // 1024)
            kb, ok = QInputDialog.getInt(
                self, "Kompres PDF",
                f"Ukuran sekarang: {size_kb} KB.\nTarget ukuran hasil (KB):",
                max(10, size_kb // 2), 10, max(20, size_kb), 10)
            if not ok:
                return
            target_bytes = kb * 1024
            self._kompres_target = kb
        self.progress.show()
        self.status.setText(f"⏳ Mengonversi ke {fmt}…")
        self._worker = ConvertWorker(self._files, fmt, target_bytes)
        self._worker.done.connect(self.on_done)
        self._worker.failed.connect(self.on_failed)
        self._worker.start()

    def on_done(self, outputs: list) -> None:
        self.progress.hide()
        names = "\n".join(f"• {Path(o).name}" for o in outputs)
        note = ""
        if getattr(self, "_kompres_target", None) and outputs:
            got_kb = Path(outputs[0]).stat().st_size // 1024
            note = (f"\n📦 Ukuran hasil: {got_kb} KB "
                    f"(target {self._kompres_target} KB)"
                    + ("" if got_kb <= self._kompres_target
                       else " — target tidak tercapai penuh, ini hasil "
                            "terkecil yang bisa dicapai."))
        text = f"✅ Beres! {len(outputs)} file hasil:\n{names}{note}"
        self.status.setText(text)
        self.tool_status.setText(text)
        if outputs:
            self._last_folder = Path(outputs[0]).parent
            self.open_btn.show()

    def on_failed(self, msg: str) -> None:
        self.progress.hide()
        self.status.setText(f"❌ {msg}")
        self.tool_status.setText(f"❌ {msg}")

    def on_edit(self) -> None:
        if len(self._files) != 1 or detect_kind(self._files[0]) != "image":
            return
        dlg = ImageEditorDialog(self._files[0], self)
        if dlg.exec() and dlg.saved_path is not None:
            msg = (f"✅ Hasil edit tersimpan: {dlg.saved_path.name} "
                   f"(di sebelah {self._files[0].name})")
            self.status.setText(msg)
            self.tool_status.setText(msg)
            self._last_folder = dlg.saved_path.parent
            self.open_btn.show()

    def on_remove_bg(self) -> None:
        if len(self._files) != 1 or detect_kind(self._files[0]) != "image":
            return
        dlg = BgRemoveDialog(self._files[0], self)
        if dlg.exec() and dlg.saved_path is not None:
            msg = (f"✅ Background terhapus: {dlg.saved_path.name} "
                   f"(di sebelah {self._files[0].name})")
            self.status.setText(msg)
            self.tool_status.setText(msg)
            self._last_folder = dlg.saved_path.parent
            self.open_btn.show()

    def on_split(self) -> None:
        if len(self._files) != 1 or detect_kind(self._files[0]) != "pdf":
            return
        dlg = SplitDialog(self._files[0], self)
        if dlg.exec() and dlg.saved_paths:
            names = "\n".join(f"• {p.name}" for p in dlg.saved_paths)
            msg = (f"✅ Beres! {len(dlg.saved_paths)} file hasil pisah:\n"
                   f"{names}")
            self.status.setText(msg)
            self.tool_status.setText(msg)
            self._last_folder = dlg.saved_paths[0].parent
            self.open_btn.show()

    def on_pdf_edit(self) -> None:
        if len(self._files) != 1 or detect_kind(self._files[0]) != "pdf":
            return
        dlg = PdfEditorDialog(self._files[0], self)
        if dlg.exec() and dlg.saved_path is not None:
            msg = (f"✅ Hasil edit PDF tersimpan: {dlg.saved_path.name} "
                   f"(di sebelah {self._files[0].name})")
            self.status.setText(msg)
            self.tool_status.setText(msg)
            self._last_folder = dlg.saved_path.parent
            self.open_btn.show()

    def open_folder(self) -> None:
        if not self._last_folder:
            return
        import sys as _sys

        try:
            if _sys.platform.startswith("win"):
                import os as _os

                _os.startfile(str(self._last_folder))  # noqa: S606 (Windows)
            elif _sys.platform == "darwin":
                subprocess.Popen(["open", str(self._last_folder)])
            else:
                subprocess.Popen(["xdg-open", str(self._last_folder)])
        except Exception:
            pass

    # ------------------------------------------------------------ update
    def _check_update(self, manual: bool) -> None:
        if getattr(self, "_upd_worker", None) is not None \
                and self._upd_worker.isRunning():
            return
        from . import __version__

        self._upd_manual = manual
        _root = Path(__file__).resolve().parent.parent
        self._upd_worker = UpdateWorker(
            __version__, _root if (_root / ".git").exists() else None)
        self._upd_worker.done.connect(self._on_update_checked)
        self._upd_worker.start()

    def _on_update_checked(self, info) -> None:
        import time as _time

        self._settings.setValue("last_update_check", int(_time.time()))
        from . import __version__

        state = (info or {}).get("state")
        if state == "update":
            self._show_update_dialog(info)
        elif getattr(self, "_upd_manual", False):
            if state == "current":
                QMessageBox.information(
                    self, "Cek Update",
                    "✅ SalmanPDF sudah dalam versi terbaru.\n\n"
                    f"Kamu memakai v{__version__} — ini versi paling "
                    "baru saat ini, belum ada update yang lebih baru.")
            else:
                QMessageBox.warning(
                    self, "Cek Update",
                    "⚠️ Pemeriksaan update tidak berhasil — server "
                    "update sedang tidak terjangkau. Periksa koneksi "
                    "internetmu, lalu coba lagi.")

    def _show_update_dialog(self, info: dict) -> None:
        from . import __version__

        dlg = QDialog(self)
        dlg.setWindowTitle("🚀 Update SalmanPDF Tersedia")
        dlg.resize(520, 420)
        lay = QVBoxLayout(dlg)
        head = QLabel(f"<b>Versi baru v{info['latest']}</b> tersedia "
                      f"(kamu memakai v{__version__}).")
        head.setWordWrap(True)
        lay.addWidget(head)
        lay.addWidget(QLabel("Apa yang baru:"))
        notes = QTextEdit()
        notes.setReadOnly(True)
        notes.setPlainText(info.get("notes") or
                           "Detail perubahan belum tersedia untuk versi ini.")
        lay.addWidget(notes, 1)
        row = QHBoxLayout()
        btn_now = QPushButton("⬇️ Update Sekarang")
        btn_now.clicked.connect(lambda: (dlg.accept(), self._do_update()))
        row.addWidget(btn_now)
        btn_later = QPushButton("Nanti Saja")
        btn_later.clicked.connect(dlg.reject)
        row.addWidget(btn_later)
        row.addStretch(1)
        lay.addLayout(row)
        dlg.exec()

    def _do_update(self) -> None:
        root = Path(__file__).resolve().parent.parent
        if (root / ".git").exists():
            self.status.setText("⏳ Mengunduh update (git pull)…")
            self._pull_worker = PullWorker(root)
            self._pull_worker.done.connect(self._on_pulled)
            self._pull_worker.start()
        else:
            from PySide6.QtCore import QUrl

            QDesktopServices.openUrl(QUrl(updater.RELEASES_URL))
            self.status.setText(
                "🌐 Halaman unduhan dibuka di browser — ambil versi terbaru "
                "di sana, lalu pasang seperti biasa.")

    def _on_pulled(self, ok: bool, message: str) -> None:
        if ok:
            self.status.setText(
                f"✅ Update terpasang: {message} — mulai ulang SalmanPDF "
                "untuk memakai versi baru.")
        else:
            self.status.setText(f"⚠️ Update gagal: {message}")

    def _maybe_auto_check(self) -> None:
        import time as _time

        last = self._settings.value("last_update_check", 0, type=int)
        if _time.time() - last > 20 * 3600:
            self._check_update(False)

    # ------------------------------------------------- mode global (v2)
    def toggle_global(self) -> None:
        if self._poller is not None:
            self._poll_timer.stop()
            self._poller.close()
            self._poller = None
            if self._overlay:
                self._overlay.hide()
            self.card_global.set_active(False)
            self.status.setText("Mode global mati.")
            return
        if not session_is_x11():
            import sys as _sys

            if _sys.platform == "linux":
                self.status.setText(
                    "⚠️ Mode global butuh sesi X11 — sesi kamu terdeteksi "
                    "bukan X11 (Wayland mengunci intip drag global). Di Mint: "
                    "logout, di layar login pilih sesi Cinnamon on X11, lalu "
                    "coba lagi. Semua alat lain tetap jalan di sesi apa pun.")
            else:
                self.status.setText(
                    "⚠️ Mode Global (Shift+seret) adalah fitur khusus Linux "
                    "X11 dan tidak tersedia di sistem operasi ini. Semua "
                    "alat lain di SalmanPDF berfungsi normal.")
            return
        try:
            self._poller = X11Poller()
        except RuntimeError as e:
            self.status.setText(f"⚠️ {e}")
            return
        if self._overlay is None:
            self._overlay = WheelOverlay()
            self._overlay.dropped.connect(self.on_overlay_drop)
        self._tracker.reset()
        self._poll_timer.start()
        self.card_global.set_active(
            True, "AKTIF — Shift + seret file di Nemo (klik lagi untuk mati)")
        self.status.setText(
            "🟢 Mode global AKTIF (eksperimental). Sekarang coba: seret file "
            "di Nemo, tahan Shift sambil menyeret — wheel muncul di kursor. "
            "Geser ke sektor format, lalu lepas mouse untuk konversi.")

    def _poll_global(self) -> None:
        if self._poller is None or self._overlay is None:
            return
        # Jangan ganggu drag yang sedang masuk ke overlay (Qt yang pegang).
        if self._overlay.isVisible() and self._overlay._files:
            return
        try:
            event = self._tracker.feed(self._poller.sample())
        except Exception:
            return
        if event == "show":
            self._overlay.show_at_cursor()
        elif event == "hide":
            self._overlay.hide()

    def on_overlay_drop(self, files: list, fmt: str) -> None:
        self._files = [Path(f) for f in files]
        self.info.setText(f"🎯 Dari mode global: {len(self._files)} file → {fmt}")
        self.on_format(fmt)


# Tema terang "frosted glass" ala Tangerine asli — berlaku app-wide,
# termasuk dialog editor (menimpa tema gelap bawaan desktop).
LIGHT_THEME = """
QMainWindow, QDialog { background: #ffffff; }
QLabel { color: #26221f; background: transparent; }
QCheckBox { color: #26221f; }
QPushButton { background: #ffffff; color: #26221f; border: 1px solid #e3d5d3;
              border-radius: 10px; padding: 8px 12px; }
QPushButton:hover { border-color: #d92323; color: #d92323; }
QPushButton:disabled { color: #a49e93; background: #efece6; }
QComboBox { background: #ffffff; color: #26221f; border: 1px solid #d8d3c8;
            border-radius: 6px; padding: 4px; }
QLineEdit, QSpinBox { background: #ffffff; color: #26221f;
            border: 1px solid #d8d3c8; border-radius: 6px; padding: 4px; }
QRadioButton { color: #26221f; }
QProgressBar { background: #e8eaed; border: none; height: 6px;
               border-radius: 3px; }
QProgressBar::chunk { background: #d92323; border-radius: 3px; }
"""

# Tema gelap — pasangan LIGHT_THEME, diganti lewat switch di header.
DARK_THEME = """
QMainWindow, QDialog { background: #1d2025; }
QLabel { color: #e8eaed; background: transparent; }
QCheckBox { color: #e8eaed; }
QPushButton { background: #2a2e35; color: #e8eaed; border: 1px solid #3a3f47;
              border-radius: 10px; padding: 8px 12px; }
QPushButton:hover { border-color: #ff6b61; color: #ff6b61; }
QPushButton:disabled { color: #7a7f87; background: #24272d; }
QComboBox { background: #26292f; color: #e8eaed; border: 1px solid #3a3f47;
            border-radius: 6px; padding: 4px; }
QLineEdit, QSpinBox { background: #26292f; color: #e8eaed;
            border: 1px solid #3a3f47; border-radius: 6px; padding: 4px; }
QRadioButton { color: #e8eaed; }
QProgressBar { background: #33373f; border: none; height: 6px;
               border-radius: 3px; }
QProgressBar::chunk { background: #d92323; border-radius: 3px; }
"""


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyleSheet(LIGHT_THEME)
    try:
        import base64

        from PySide6.QtGui import QPixmap

        from .icon_data import APPICON_PNG_B64
        pix = QPixmap()
        if pix.loadFromData(base64.b64decode(APPICON_PNG_B64)):
            app.setWindowIcon(QIcon(pix))
    except Exception:
        pass  # ikon jendela bonus — jangan gagalkan startup karenanya
    win = MainWindow()
    win.show()
    return app.exec()
