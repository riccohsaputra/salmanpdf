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

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QGridLayout, QHBoxLayout,
    QInputDialog, QLabel, QMainWindow, QProgressBar, QPushButton,
    QStackedWidget, QVBoxLayout, QWidget,
)

FILE_FILTER = (
    "Didukung (*.pdf *.jpg *.jpeg *.png *.webp *.bmp *.tiff "
    "*.docx *.doc *.odt *.rtf *.pptx *.ppt *.odp "
    "*.xlsx *.xls *.ods "
    "*.txt *.text *.md *.log *.csv *.ini *.cfg *.sh *.py *.json);;"
    "Semua file (*)")

from .converters import ConversionError, convert_many, detect_kind, formats_for
from .editor import ImageEditorDialog
from .icons import tool_icon
from .overlay import WheelOverlay
from .pdf_editor import PdfEditorDialog
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
        self.setMinimumHeight(240)
        self.pick_btn = QPushButton(f"Pilih {noun}")
        self.pick_btn.setStyleSheet(
            "QPushButton{background:#e5322d;color:#ffffff;"
            "font-size:17px;font-weight:700;border:none;border-radius:10px;"
            "padding:16px 46px}"
            "QPushButton:hover{background:#c92723;color:#ffffff}")
        self.pick_btn.clicked.connect(self.pickRequested.emit)
        hint = QLabel(f"atau seret {noun} ke sini")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet("font-size:12.5px;color:#7a7f87")
        col = QVBoxLayout(self)
        col.addStretch(1)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self.pick_btn)
        row.addStretch(1)
        col.addLayout(row)
        col.addWidget(hint)
        col.addStretch(1)

    def dragEnterEvent(self, event):  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):  # noqa: N802
        files = [Path(u.toLocalFile()) for u in event.mimeData().urls()
                 if u.isLocalFile()]
        if files:
            self.filesDropped.emit(files)


# ---------------------------------------------------------------- kartu alat
# PENTING: selector WAJIB ter-scope ke #toolCard. QLabel adalah subclass
# QFrame di Qt — selector "QFrame{...}" polos MENULAR ke semua label anak
# (kejadian v0.6.0: judul & deskripsi kartu ikut kena border).
_CARD_BASE = ("#toolCard{background:#ffffff;border:1px solid #e7e1dc;"
              "border-radius:12px}")
_CARD_HOVER = ("#toolCard{background:#ffffff;border:1px solid #d92323;"
               "border-radius:12px}")


class ToolCard(QFrame):
    """Kartu alat gaya iLovePDF: ikon vektor BESAR di kiri-atas, judul
    tebal di bawahnya, deskripsi abu. Tinggi tetap, flat, hover merah."""

    clicked = Signal()
    HEIGHT = 138

    def __init__(self, icon: str, title: str, desc: str, category: str):
        super().__init__()
        self.setObjectName("toolCard")
        self.category = category
        self._icon_name = icon
        self.setStyleSheet(_CARD_BASE)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(self.HEIGHT)
        self._desc = desc
        self.icon_lbl = QLabel()
        self.icon_lbl.setFixedSize(56, 56)
        self.icon_lbl.setPixmap(tool_icon(icon, 56))
        self.title_lbl = QLabel(title)
        self.title_lbl.setStyleSheet(
            "font-size:14px;font-weight:700;color:#23272f")
        self.desc_lbl = QLabel(desc)
        self.desc_lbl.setWordWrap(True)
        self.desc_lbl.setStyleSheet("font-size:11px;color:#7a7f87")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 10)
        lay.setSpacing(6)
        lay.addWidget(self.icon_lbl)
        lay.addWidget(self.title_lbl)
        lay.addWidget(self.desc_lbl)
        lay.addStretch(1)

    def enterEvent(self, event):  # noqa: N802
        self.setStyleSheet(_CARD_HOVER)
        super().enterEvent(event)

    def leaveEvent(self, event):  # noqa: N802
        self.setStyleSheet(_CARD_BASE)
        super().leaveEvent(event)

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
        self._files: list[Path] = []
        self._worker: ConvertWorker | None = None

        self.info = QLabel("Belum ada file.")
        self.info.setWordWrap(True)
        self.info.setStyleSheet("font-size:12px;color:#555b63")

        self.wheel = WheelWidget()
        self.wheel.formatSelected.connect(self.on_format)

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
        header.setObjectName("appHeader")
        header.setStyleSheet(
            "#appHeader{background:#ffffff;"
            "border-bottom:1px solid #e7e1dc}")
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(20, 10, 20, 10)
        logo = QLabel("S")
        logo.setFixedSize(36, 36)
        logo.setAlignment(Qt.AlignCenter)
        logo.setStyleSheet(
            "background:#d92323;color:#ffffff;font-size:18px;"
            "font-weight:800;border-radius:9px")
        h_lay.addWidget(logo)
        brand = QVBoxLayout()
        brand.setSpacing(0)
        brand_name = QLabel("SalmanPDF")
        brand_name.setStyleSheet(
            "font-size:17px;font-weight:800;color:#23272f")
        brand_tag = QLabel("Konverter PDF & dokumen — 100% lokal")
        brand_tag.setStyleSheet("font-size:10.5px;color:#7a7f87")
        brand.addWidget(brand_name)
        brand.addWidget(brand_tag)
        h_lay.addLayout(brand)
        h_lay.addStretch(1)
        ver_lbl = QLabel(f"v{__version__}")
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
        hero_title.setAlignment(Qt.AlignCenter)
        hero_title.setStyleSheet(
            "font-size:25px;font-weight:800;color:#23272f")
        hero_sub = QLabel(
            "Gabung, pisah, kompres, konversi, dan edit — semuanya diproses "
            "lokal di laptop kamu, tanpa upload.")
        hero_sub.setAlignment(Qt.AlignCenter)
        hero_sub.setStyleSheet("font-size:12.5px;color:#7a7f87")

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
            "pisah", "Pisah PDF", "Pecah PDF menjadi satu file per halaman", "atur")
        self.card_pisah.clicked.connect(lambda: self.open_tool("pisah"))
        self.card_kompres = ToolCard(
            "kompres", "Kompres PDF", "Kecilkan PDF ke target ukuran yang kamu mau",
            "atur")
        self.card_kompres.clicked.connect(lambda: self.open_tool("kompres"))
        self.card_editpdf = ToolCard(
            "edit", "Edit PDF", "Tempel teks & gambar ke dalam PDF", "edit")
        self.card_editpdf.clicked.connect(lambda: self.open_tool("editpdf"))
        self.card_pdfimg = ToolCard(
            "pdfimg", "PDF ke Gambar", "Ubah tiap halaman PDF menjadi JPG",
            "konversi")
        self.card_pdfimg.clicked.connect(lambda: self.open_tool("pdfimg"))
        self.card_imgpdf = ToolCard(
            "imgpdf", "Gambar ke PDF", "Jadikan gambar (banyak sekaligus) satu PDF",
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
        self.card_global = ToolCard(
            "global", "Mode Global", "Shift + seret file di Nemo, wheel muncul",
            "lainnya")
        self.card_global.clicked.connect(self.toggle_global)

        self._cards = [self.card_gabung, self.card_pisah, self.card_kompres,
                       self.card_editpdf, self.card_pdfimg, self.card_imgpdf,
                       self.card_office, self.card_crop, self.card_global]
        grid = QGridLayout()
        grid.setSpacing(12)
        for i, card in enumerate(self._cards):
            grid.addWidget(card, i // 3, i % 3)

        # ================= Sidebar kanan: wheel + status =================
        wheel_box = QFrame()
        wheel_box.setObjectName("wheelBox")
        wheel_box.setStyleSheet(
            "#wheelBox{background:#ffffff;border:1px solid #e7e1dc;"
            "border-radius:14px}")
        wheel_box.setFixedSize(248, 248)
        wb_lay = QVBoxLayout(wheel_box)
        wb_lay.setContentsMargins(8, 8, 8, 8)
        wb_lay.addWidget(self.wheel)

        side_col = QVBoxLayout()
        side_col.addWidget(wheel_box)
        side_col.addWidget(self.info)
        side_col.addWidget(self.status, 1)
        prog_row = QHBoxLayout()
        prog_row.addWidget(self.progress)
        prog_row.addStretch(1)
        prog_row.addWidget(self.open_btn)
        side_col.addLayout(prog_row)

        content_row = QHBoxLayout()
        content_row.setSpacing(16)
        content_row.addLayout(grid, 1)
        content_row.addLayout(side_col)

        body = QVBoxLayout()
        body.setContentsMargins(26, 16, 26, 14)
        body.setSpacing(11)
        body.addWidget(hero_title)
        body.addWidget(hero_sub)
        body.addLayout(pills_row)
        body.addLayout(content_row, 1)
        inner = QWidget()
        inner.setMaximumWidth(1180)
        inner.setLayout(body)
        home_outer = QHBoxLayout()
        home_outer.setContentsMargins(0, 0, 0, 0)
        home_outer.addStretch(1)
        home_outer.addWidget(inner)
        home_outer.addStretch(1)
        home_page = QWidget()
        home_page.setLayout(home_outer)

        self._stack = QStackedWidget()
        self._stack.addWidget(home_page)
        self._stack.addWidget(self._build_tool_page())

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(header)
        layout.addWidget(self._stack, 1)

        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)

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
            desc="Pisahkan satu halaman atau satu set halaman menjadi "
                 "file PDF mandiri.",
            kinds={"pdf"}, min_files=1, action="Pisah PDF",
            fmt="PISAH", noun="file PDF"),
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
        self.tool_title.setStyleSheet(
            "font-size:29px;font-weight:800;color:#23272f")
        lay.addWidget(self.tool_title)
        self.tool_desc = QLabel("")
        self.tool_desc.setAlignment(Qt.AlignCenter)
        self.tool_desc.setWordWrap(True)
        self.tool_desc.setStyleSheet("font-size:13px;color:#7a7f87")
        lay.addWidget(self.tool_desc)
        self.tool_area = ToolDropArea()
        self.tool_area.filesDropped.connect(self._tool_accept)
        self.tool_area.pickRequested.connect(self._tool_pick)
        lay.addWidget(self.tool_area, 1)
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
        elif cfg.get("run") == "edit_image":
            self.on_edit()
        else:
            self.on_format(cfg["fmt"])

    def _pick_quick(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Pilih file", "", FILE_FILTER)
        if paths:
            self.on_files([Path(p) for p in paths])

    # ------------------------------------------------- filter pills
    _PILL_ON = ("QPushButton{background:#23272f;color:#ffffff;font-weight:600;"
                "border:1px solid #23272f;border-radius:14px;"
                "padding:5px 14px}")
    _PILL_OFF = ("QPushButton{background:#ffffff;color:#23272f;"
                 "border:1px solid #ddd6d0;border-radius:14px;"
                 "padding:5px 14px} QPushButton:hover{border-color:#d92323;"
                 "color:#d92323}")

    def _style_pills(self) -> None:
        for pill, _cat in self._pills:
            pill.setStyleSheet(self._PILL_ON if pill.isChecked()
                               else self._PILL_OFF)

    def _filter_cards(self, category: str | None) -> None:
        for pill, cat in self._pills:
            pill.setChecked(cat == category)
        self._style_pills()
        for card in self._cards:
            card.setVisible(category is None or card.category == category)

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
                          "Klik format di wheel (kiri bawah) atau kartu alatnya.")
        center = supported[0].name if len(supported) == 1 else f"{len(supported)} file"
        self.wheel.set_wheel(order, center)
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
        if self._last_folder:
            subprocess.Popen(["xdg-open", str(self._last_folder)])

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
            self.status.setText(
                "⚠️ Mode global butuh sesi X11 — sesi kamu terdeteksi bukan X11 "
                "(Wayland mengunci intip drag global). Di Mint: logout, di layar "
                "login pilih sesi Cinnamon on X11, lalu coba lagi. Mode drop-zone "
                "di atas tetap jalan di sesi apa pun.")
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
QMainWindow, QDialog { background: #f3f1ee; }
QLabel { color: #26221f; }
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
"""


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyleSheet(LIGHT_THEME)
    win = MainWindow()
    win.show()
    return app.exec()
