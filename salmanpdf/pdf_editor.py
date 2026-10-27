"""
Dialog Edit PDF: tempel teks (font sistem + warna + ukuran) dan gambar
ke halaman PDF dengan klik pada preview halaman.

Alur: pilih halaman -> isi teks / pilih gambar -> KLIK di preview untuk
menempel -> ulangi seperlunya -> Simpan (-edit.pdf di sebelah aslinya).
"""
from __future__ import annotations

import io
import tempfile
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QEvent, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QCheckBox, QColorDialog, QComboBox, QDialog, QFileDialog, QHBoxLayout,
    QGridLayout, QLabel, QLineEdit, QPushButton, QRadioButton,
    QScrollArea, QSlider, QSpinBox, QVBoxLayout, QWidget,
)

from .converters import (
    ConversionError, extract_pages, parse_page_spec, split_pdf_groups,
)
from .imgprep import crop_percent, prepare_image, remove_white_background
from .pdfedit import (
    BASE14, apply_edits, font_file_for, hit_test, list_system_fonts,
    move_op, op_bbox, render_preview,
)

PREVIEW_W = 440


class ImagePrepDialog(QDialog):
    """Siapkan gambar sebelum ditempel ke PDF: crop tepi + hapus
    background putih dengan halus (untuk tanda tangan/logo/foto).
    Preview di atas pola papan catur supaya transparansi terlihat."""

    def __init__(self, src: Path, parent=None):
        super().__init__(parent)
        self.src = src
        self.prepared: Path | None = None
        self.setWindowTitle(f"Siapkan Gambar — {src.name}")
        self.resize(720, 520)
        with Image.open(src) as im:
            im.load()
            self._full = im.convert("RGBA")
        self._work = self._full.copy()
        self._work.thumbnail((880, 880))

        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumSize(340, 340)
        self.preview.setStyleSheet(
            "background:#f0f0f0;border:1px solid #ddd;border-radius:8px")

        def crop_slider(label):
            row = QHBoxLayout()
            row.addWidget(QLabel(label))
            s = QSlider(Qt.Orientation.Horizontal)
            s.setRange(0, 45)
            s.setValue(0)
            val = QLabel("0%")
            s.valueChanged.connect(
                lambda v, lb=val: (lb.setText(f"{v}%"), self._refresh()))
            row.addWidget(s, 1)
            row.addWidget(val)
            return row, s

        right = QVBoxLayout()
        right.addWidget(QLabel("<b>✂️ Crop tepi (%)</b>"))
        r1, self.s_left = crop_slider("Kiri")
        r2, self.s_top = crop_slider("Atas")
        r3, self.s_right = crop_slider("Kanan")
        r4, self.s_bottom = crop_slider("Bawah")
        for r in (r1, r2, r3, r4):
            right.addLayout(r)
        right.addSpacing(10)
        self.chk_bg = QCheckBox("Hapus background putih (halus)")
        self.chk_bg.setChecked(True)
        self.chk_bg.toggled.connect(self._refresh)
        right.addWidget(self.chk_bg)
        bg_row = QHBoxLayout()
        bg_row.addWidget(QLabel("Ambang putih:"))
        self.s_cut = QSlider(Qt.Orientation.Horizontal)
        self.s_cut.setRange(140, 250)
        self.s_cut.setValue(205)
        self.s_cut.valueChanged.connect(self._refresh)
        bg_row.addWidget(self.s_cut, 1)
        right.addLayout(bg_row)
        hint = QLabel("Ambang lebih kecil = background lebih bersih, tapi "
                      "bagian putih di dalam gambar ikut hilang. Cocok "
                      "untuk tanda tangan & logo di kertas putih.")
        hint.setWordWrap(True)
        hint.setStyleSheet("font-size:11px;color:#6b7280")
        right.addWidget(hint)
        right.addStretch(1)
        btn_row = QHBoxLayout()
        ok = QPushButton("✅ Pakai gambar ini")
        ok.clicked.connect(self._accept)
        cancel = QPushButton("Batal")
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(ok)
        btn_row.addWidget(cancel)
        right.addLayout(btn_row)

        root = QHBoxLayout(self)
        root.addWidget(self.preview, 1)
        root.addLayout(right, 1)
        self._refresh()

    def _processed_work(self) -> Image.Image:
        out = crop_percent(self._work, self.s_left.value(),
                           self.s_top.value(), self.s_right.value(),
                           self.s_bottom.value())
        if self.chk_bg.isChecked():
            out = remove_white_background(out, cutoff=self.s_cut.value())
        return out

    def _refresh(self):
        out = self._processed_work()
        # Komposit di atas papan catur agar transparansi terlihat jelas
        # (blok 2x2 ubin ditempel berulang — cepat, tanpa loop per piksel)
        tile = 12
        pat = Image.new("RGB", (2, 2))
        pat.putdata([(255, 255, 255), (216, 216, 216),
                     (216, 216, 216), (255, 255, 255)])
        block = pat.resize((tile * 2, tile * 2), Image.Resampling.NEAREST)
        board = Image.new("RGB", out.size, (255, 255, 255))
        for y in range(0, out.height, tile * 2):
            for x in range(0, out.width, tile * 2):
                board.paste(block, (x, y))
        board.paste(out, (0, 0), out)
        buf = io.BytesIO()
        board.save(buf, "PNG")
        pix = QPixmap()
        pix.loadFromData(buf.getvalue())
        self.preview.setPixmap(pix)

    def _accept(self):
        dest = Path(tempfile.gettempdir()) / f"salmanpdf-prep-{self.src.stem}.png"
        self.prepared = prepare_image(
            self.src, dest, self.s_left.value(), self.s_top.value(),
            self.s_right.value(), self.s_bottom.value(),
            remove_bg=self.chk_bg.isChecked(), cutoff=self.s_cut.value())
        self.accept()


class ClickableLabel(QLabel):
    """Label preview yang melaporkan tekan/geser/lepas klik + roda mouse
    (untuk zoom, memilih & menyeret tempelan)."""

    pressed = Signal(int, int)
    moved = Signal(int, int)
    released = Signal(int, int)
    wheeled = Signal(int)

    def mousePressEvent(self, event):  # noqa: N802 (Qt API)
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position()
            self.pressed.emit(int(pos.x()), int(pos.y()))
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):  # noqa: N802 (Qt API)
        if event.buttons() & Qt.MouseButton.LeftButton:
            pos = event.position()
            self.moved.emit(int(pos.x()), int(pos.y()))
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):  # noqa: N802 (Qt API)
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position()
            self.released.emit(int(pos.x()), int(pos.y()))
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):  # noqa: N802 (Qt API)
        self.wheeled.emit(event.angleDelta().y())
        event.accept()


class PdfEditorDialog(QDialog):
    def __init__(self, src: Path, parent=None):
        super().__init__(parent)
        self.src = Path(src)
        self.ops: list[dict] = []
        self.page = 0
        self._scale = 1.0            # titik PDF per piksel preview
        self.zoom_factor = 1.0       # perbesaran preview (0.5x–3x)
        self._sel: int | None = None  # indeks tempelan terpilih
        self._drag_idx: int | None = None
        self._drag_off = (0.0, 0.0)
        self._press_pt = (0.0, 0.0)
        self._dragging = False
        self._drag_timer = QTimer(self)
        self._drag_timer.setSingleShot(True)
        self._drag_timer.timeout.connect(self._refresh_preview)
        self.color = QColor(220, 40, 40)  # merah default (buat tanda tangan/catatan)
        self.image_path: Path | None = None
        self.saved_path: Path | None = None

        self.setWindowTitle(f"Edit PDF — {self.src.name}")
        self.setMinimumSize(960, 660)

        # ---------------- kiri: preview
        self.preview = ClickableLabel("Memuat preview…")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.preview.setStyleSheet("background: white; border: 1px solid #ddd;")
        self.preview.pressed.connect(self._on_press)
        self.preview.moved.connect(self._on_move)
        self.preview.released.connect(self._on_release)
        self.preview.wheeled.connect(
            lambda d: self._zoom_by(0.15 if d > 0 else -0.15))
        self.scroll = QScrollArea()
        self.scroll.setWidget(self.preview)
        self.scroll.setWidgetResizable(False)
        self.scroll.viewport().installEventFilter(self)

        page_row = QHBoxLayout()
        page_row.addWidget(QLabel("Halaman:"))
        self.spin_page = QSpinBox(minimum=1, maximum=1, value=1)
        self.spin_page.valueChanged.connect(self._page_changed)
        page_row.addWidget(self.spin_page)
        self.lbl_pages = QLabel("")
        page_row.addWidget(self.lbl_pages)
        page_row.addStretch(1)

        zoom_row = QHBoxLayout()
        zoom_row.addWidget(QLabel("Zoom:"))
        self.btn_zout = QPushButton("−")
        self.btn_zout.setFixedWidth(34)
        self.btn_zout.clicked.connect(lambda: self._zoom_by(-0.25))
        zoom_row.addWidget(self.btn_zout)
        self.lbl_zoom = QLabel("100%")
        self.lbl_zoom.setFixedWidth(44)
        self.lbl_zoom.setAlignment(Qt.AlignCenter)
        zoom_row.addWidget(self.lbl_zoom)
        self.btn_zin = QPushButton("+")
        self.btn_zin.setFixedWidth(34)
        self.btn_zin.clicked.connect(lambda: self._zoom_by(0.25))
        zoom_row.addWidget(self.btn_zin)
        self.btn_zfit = QPushButton("Pas")
        self.btn_zfit.clicked.connect(self._zoom_reset)
        zoom_row.addWidget(self.btn_zfit)
        zoom_row.addStretch(1)

        left = QVBoxLayout()
        left.addLayout(page_row)
        left.addLayout(zoom_row)
        left.addWidget(self.scroll, 1)

        # ---------------- kanan: kontrol
        right = QVBoxLayout()
        right.addWidget(QLabel("<b>Tempel apa?</b>"))
        self.radio_text = QRadioButton("Teks")
        self.radio_text.setChecked(True)
        self.radio_image = QRadioButton("Gambar (logo / tanda tangan / foto)")
        right.addWidget(self.radio_text)
        right.addWidget(self.radio_image)

        right.addWidget(QLabel("Teks:"))
        self.edit_text = QLineEdit()
        self.edit_text.setPlaceholderText("tulis teksnya di sini…")
        right.addWidget(self.edit_text)

        right.addWidget(QLabel("Font (dari sistem device ini):"))
        self.combo_font = QComboBox()
        self.combo_font.addItems(list_system_fonts())
        if "DejaVu Sans" in [self.combo_font.itemText(i) for i in range(self.combo_font.count())]:
            self.combo_font.setCurrentText("DejaVu Sans")
        right.addWidget(self.combo_font)

        size_row = QHBoxLayout()
        size_row.addWidget(QLabel("Ukuran font:"))
        self.spin_size = QSpinBox(minimum=6, maximum=96, value=14)
        size_row.addWidget(self.spin_size)
        size_row.addStretch(1)
        right.addLayout(size_row)

        color_row = QHBoxLayout()
        color_row.addWidget(QLabel("Warna teks:"))
        self.btn_color = QPushButton()
        self.btn_color.setFixedWidth(64)
        self._refresh_color_btn()
        self.btn_color.clicked.connect(self._pick_color)
        color_row.addWidget(self.btn_color)
        color_row.addStretch(1)
        right.addLayout(color_row)

        right.addSpacing(8)
        img_row = QHBoxLayout()
        self.btn_image = QPushButton("Pilih gambar…")
        self.btn_image.clicked.connect(self._pick_image)
        img_row.addWidget(self.btn_image)
        self.lbl_image = QLabel("(belum ada)")
        img_row.addWidget(self.lbl_image)
        right.addLayout(img_row)
        w_row = QHBoxLayout()
        w_row.addWidget(QLabel("Lebar gambar (pt):"))
        self.spin_imgw = QSpinBox(minimum=20, maximum=560, value=160)
        w_row.addWidget(self.spin_imgw)
        w_row.addStretch(1)
        right.addLayout(w_row)

        right.addSpacing(8)
        self.lbl_hint = QLabel(
            "Klik area kosong di preview untuk menempel. Klik tempelan "
            "untuk memilih, seret untuk memindah. Zoom: roda mouse atau "
            "tombol + / −.")
        self.lbl_hint.setWordWrap(True)
        right.addWidget(self.lbl_hint)
        self.lbl_ops = QLabel("Edit tertempel: 0")
        right.addWidget(self.lbl_ops)
        self.btn_undo = QPushButton("↩️ Urungkan tempelan terakhir")
        self.btn_undo.clicked.connect(self._undo)
        right.addWidget(self.btn_undo)
        right.addSpacing(8)
        right.addWidget(QLabel("<b>Susunan tempelan terpilih</b>"))
        layer_hint = QLabel("Klik tempelan di preview untuk memilih, "
                            "seret untuk memindah posisinya.")
        layer_hint.setWordWrap(True)
        layer_hint.setStyleSheet("font-size:11px;color:#6b7280")
        right.addWidget(layer_hint)
        lay_row1 = QHBoxLayout()
        self.btn_front = QPushButton("⏫ Paling depan")
        self.btn_front.clicked.connect(lambda: self._layer("front"))
        self.btn_back = QPushButton("⏬ Paling belakang")
        self.btn_back.clicked.connect(lambda: self._layer("back"))
        lay_row1.addWidget(self.btn_front)
        lay_row1.addWidget(self.btn_back)
        right.addLayout(lay_row1)
        lay_row2 = QHBoxLayout()
        self.btn_fwd = QPushButton("⬆ Maju")
        self.btn_fwd.clicked.connect(lambda: self._layer("forward"))
        self.btn_bwd = QPushButton("⬇ Mundur")
        self.btn_bwd.clicked.connect(lambda: self._layer("backward"))
        lay_row2.addWidget(self.btn_fwd)
        lay_row2.addWidget(self.btn_bwd)
        right.addLayout(lay_row2)
        self.btn_delsel = QPushButton("🗑 Hapus tempelan terpilih")
        self.btn_delsel.clicked.connect(self._delete_selected)
        right.addWidget(self.btn_delsel)
        self._layer_btns = [self.btn_front, self.btn_back, self.btn_fwd,
                            self.btn_bwd, self.btn_delsel]
        right.addStretch(1)

        btn_row = QHBoxLayout()
        self.btn_save = QPushButton("💾 Simpan PDF hasil edit")
        self.btn_save.clicked.connect(self._save)
        btn_row.addWidget(self.btn_save)
        btn_cancel = QPushButton("Batal")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)
        right.addLayout(btn_row)

        root = QHBoxLayout(self)
        root.addLayout(left)
        root.addLayout(right, 1)
        self._refresh_preview()

    # ------------------------------------------------------------ helpers
    def _refresh_color_btn(self):
        self.btn_color.setStyleSheet(
            f"background: {self.color.name()}; border: 1px solid #999;")

    def _pick_color(self):
        c = QColorDialog.getColor(self.color, self, "Pilih warna teks")
        if c.isValid():
            self.color = c
            self._refresh_color_btn()

    def _pick_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Pilih gambar", "",
            "Gambar (*.png *.jpg *.jpeg *.webp *.bmp);;Semua file (*)")
        if not path:
            return
        src = Path(path)
        # Menu persiapan: crop + hapus background dengan halus
        prep = ImagePrepDialog(src, self)
        if prep.exec() and prep.prepared is not None:
            self.image_path = prep.prepared
            self.lbl_image.setText(f"{src.name} (disiapkan)")
        else:
            self.image_path = src
            self.lbl_image.setText(src.name)
        self.radio_image.setChecked(True)

    def _page_changed(self, value: int):
        self.page = value - 1
        self._sel = None
        self._refresh_preview()

    def _refresh_preview(self):
        width = max(220, int(PREVIEW_W * self.zoom_factor))
        png, self._scale, count = render_preview(
            self.src, self.ops, self.page, width)
        self.spin_page.setMaximum(count)
        self.lbl_pages.setText(f"dari {count}")
        pix = QPixmap()
        pix.loadFromData(png)
        if self._selected_op() is not None:
            pix = self._draw_selection(pix)
        self.preview.setPixmap(pix)
        self.preview.setFixedSize(pix.size())
        self.lbl_ops.setText(f"Edit tertempel: {len(self.ops)}")
        self.lbl_zoom.setText(f"{round(self.zoom_factor * 100)}%")
        for b in self._layer_btns:
            b.setEnabled(self._selected_op() is not None)

    def _selected_op(self) -> dict | None:
        if self._sel is None or not (0 <= self._sel < len(self.ops)):
            return None
        op = self.ops[self._sel]
        return op if op["page"] == self.page else None

    def _draw_selection(self, pix: QPixmap) -> QPixmap:
        op = self._selected_op()
        out = QPixmap(pix)
        painter = QPainter(out)
        try:
            pen = QPen(QColor(217, 35, 35), 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            x0, y0, x1, y1 = op_bbox(op)
            sc = self._scale
            painter.drawRect(int(x0 * sc) - 3, int(y0 * sc) - 3,
                             int((x1 - x0) * sc) + 6, int((y1 - y0) * sc) + 6)
        finally:
            painter.end()
        return out

    # ------------------------------------------------------------ zoom
    def _zoom_by(self, delta: float):
        self.zoom_factor = min(3.0, max(0.5, round(
            (self.zoom_factor + delta) * 100) / 100))
        self._refresh_preview()

    def _zoom_reset(self):
        self.zoom_factor = 1.0
        self._refresh_preview()

    def eventFilter(self, obj, event):  # noqa: N802 (Qt API)
        if (obj is self.scroll.viewport()
                and event.type() == QEvent.Type.Wheel):
            self._zoom_by(0.15 if event.angleDelta().y() > 0 else -0.15)
            return True
        return super().eventFilter(obj, event)

    # ------------------------------------------------- pilih, seret, tempel
    def _on_press(self, px: int, py: int):
        x, y = px / self._scale, py / self._scale
        idx = hit_test(self.ops, self.page, x, y)
        if idx is not None:
            self._sel = idx
            op = self.ops[idx]
            self._drag_idx = idx
            self._drag_off = (x - op["x"], y - op["y"])
            self._press_pt = (x, y)
            self._dragging = False
            self._refresh_preview()
            return
        self._place(x, y)

    def _on_move(self, px: int, py: int):
        if self._drag_idx is None:
            return
        x, y = px / self._scale, py / self._scale
        if not self._dragging:
            if (abs(x - self._press_pt[0]) + abs(y - self._press_pt[1])
                    < 2.0):
                return
            self._dragging = True
        op = self.ops[self._drag_idx]
        op["x"] = x - self._drag_off[0]
        op["y"] = y - self._drag_off[1]
        if not self._drag_timer.isActive():
            self._drag_timer.start(40)

    def _on_release(self, px: int, py: int):
        if self._dragging:
            self._refresh_preview()
        self._drag_idx = None
        self._dragging = False

    def _place(self, x: float, y: float):
        if self.radio_text.isChecked():
            text = self.edit_text.text().strip()
            if not text:
                self.lbl_hint.setText("Isi teksnya dulu, baru klik preview.")
                return
            fam = self.combo_font.currentText()
            size = self.spin_size.value()
            self.ops.append({
                "type": "text", "page": self.page, "x": x, "y": y,
                "text": text, "font": fam, "size": size,
                "w": _measure_text(text, fam, size),
                "color": (self.color.redF(), self.color.greenF(),
                          self.color.blueF()),
            })
        else:
            if self.image_path is None:
                self.lbl_hint.setText("Pilih gambarnya dulu, baru klik preview.")
                return
            w = self.spin_imgw.value()
            with Image.open(self.image_path) as im:
                h = w * im.height / max(im.width, 1)
            self.ops.append({
                "type": "image", "page": self.page, "x": x, "y": y,
                "w": w, "h": h, "path": str(self.image_path),
            })
        self._sel = len(self.ops) - 1
        self._refresh_preview()

    # ------------------------------------------------------------ susunan
    def _layer(self, mode: str):
        if self._sel is None:
            return
        self._sel = move_op(self.ops, self._sel, mode)
        self._refresh_preview()

    def _delete_selected(self):
        if self._sel is None:
            return
        self.ops.pop(self._sel)
        self._sel = None
        self._refresh_preview()

    def _undo(self):
        if self.ops:
            self.ops.pop()
            if self._sel is not None and self._sel >= len(self.ops):
                self._sel = None
            self._refresh_preview()

    def _save(self):
        if not self.ops:
            self.lbl_hint.setText("Belum ada edit yang ditempel.")
            return
        self.saved_path = apply_edits(self.src, self.ops)
        self.accept()


def _measure_text(text: str, family: str, size: int) -> float:
    """Lebar teks (titik PDF) memakai metrik font aslinya bila bisa,
    supaya kotak seleksi & uji klik akurat. Gagal -> perkiraan kasar."""
    try:
        import pymupdf

        ff = font_file_for(family)
        if ff:
            return pymupdf.Font(fontfile=str(ff)).text_length(
                text, fontsize=size)
        return pymupdf.get_text_length(
            text, fontname=BASE14.get(family, "helv"), fontsize=size)
    except Exception:
        return len(text) * size * 0.52


class SplitDialog(QDialog):
    """Pisah PDF manual: user menentukan sendiri halaman yang dipisah.
    Mode Rentang: tiap kelompok (dipisah koma) menjadi satu PDF.
    Mode Ekstrak: semua halaman pilihan digabung jadi satu PDF."""

    _CHIP_ON = ("background:#d92323;color:#ffffff;border-radius:4px;"
                "padding:3px 0;font-size:11px;font-weight:700")
    _CHIP_OFF = ("background:#eceff3;color:#555b63;border-radius:4px;"
                 "padding:3px 0;font-size:11px")

    def __init__(self, src: Path, parent=None):
        super().__init__(parent)
        self.src = Path(src)
        self.saved_paths: list[Path] = []
        import pymupdf

        with pymupdf.open(self.src) as doc:
            self.total = doc.page_count
        self.setWindowTitle(f"Pisah PDF — {self.src.name}")
        self.setMinimumWidth(620)

        root = QVBoxLayout(self)
        root.addWidget(QLabel(
            f"<b>{self.src.name}</b> — {self.total} halaman"))

        mode_row = QHBoxLayout()
        self.rb_rentang = QRadioButton(
            "Rentang: tiap kelompok jadi 1 PDF")
        self.rb_rentang.setChecked(True)
        self.rb_ekstrak = QRadioButton(
            "Ekstrak: pilihan jadi 1 PDF gabungan")
        self.rb_rentang.toggled.connect(self._validate)
        mode_row.addWidget(self.rb_rentang)
        mode_row.addWidget(self.rb_ekstrak)
        mode_row.addStretch(1)
        root.addLayout(mode_row)

        self.edit_spec = QLineEdit()
        self.edit_spec.setPlaceholderText("contoh: 1-3, 5, 8-10")
        self.edit_spec.textChanged.connect(self._validate)
        root.addWidget(self.edit_spec)

        quick = QHBoxLayout()
        for label, fn in (("Semua halaman", self._fill_all),
                          ("Ganjil saja", self._fill_odd),
                          ("Genap saja", self._fill_even),
                          ("Bersihkan", lambda: self.edit_spec.clear())):
            btn = QPushButton(label)
            btn.clicked.connect(fn)
            quick.addWidget(btn)
        quick.addStretch(1)
        root.addLayout(quick)

        self.lbl_fb = QLabel("Tulis nomor/rentang halaman, dipisah koma.")
        self.lbl_fb.setWordWrap(True)
        root.addWidget(self.lbl_fb)

        self._chips_host = QWidget()
        self._chips_lay = QGridLayout(self._chips_host)
        self._chips_lay.setSpacing(4)
        self._chip_scroll = QScrollArea()
        self._chip_scroll.setWidget(self._chips_host)
        self._chip_scroll.setWidgetResizable(True)
        self._chip_scroll.setFixedHeight(118)
        root.addWidget(self._chip_scroll)
        self._chips: list[QLabel] = []
        self._build_chips()

        btn_row = QHBoxLayout()
        self.btn_save = QPushButton("✂️ Pisahkan")
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self._save)
        btn_row.addWidget(self.btn_save)
        cancel = QPushButton("Batal")
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)
        btn_row.addStretch(1)
        root.addLayout(btn_row)
        self._validate()

    # ------------------------------------------------------------ bantuan isi
    def _fill_all(self):
        self.edit_spec.setText(f"1-{self.total}")

    def _fill_odd(self):
        self.edit_spec.setText(
            ", ".join(str(i) for i in range(1, self.total + 1, 2)))

    def _fill_even(self):
        self.edit_spec.setText(
            ", ".join(str(i) for i in range(2, self.total + 1, 2)))

    # ------------------------------------------------------------ pratinjau
    def _build_chips(self):
        if self.total > 200:
            self._chip_scroll.hide()
            return
        for i in range(self.total):
            chip = QLabel(str(i + 1))
            chip.setAlignment(Qt.AlignCenter)
            chip.setMinimumWidth(30)
            chip.setStyleSheet(self._CHIP_OFF)
            self._chips_lay.addWidget(chip, i // 10, i % 10)
            self._chips.append(chip)

    def _paint_chips(self, included: set[int]):
        for i, chip in enumerate(self._chips):
            chip.setStyleSheet(
                self._CHIP_ON if i in included else self._CHIP_OFF)

    # ------------------------------------------------------------ inti
    def _groups(self) -> list[list[int]]:
        return parse_page_spec(self.edit_spec.text(), self.total)

    def _validate(self):
        rentang = self.rb_rentang.isChecked()
        self.edit_spec.setPlaceholderText(
            "contoh: 1-3, 5, 8-10" if rentang else "contoh: 1, 3, 5-7")
        if not self.edit_spec.text().strip():
            self.lbl_fb.setText(
                "Tulis nomor/rentang halaman, dipisah koma.")
            self.lbl_fb.setStyleSheet("")
            self.btn_save.setEnabled(False)
            self._paint_chips(set())
            return
        try:
            groups = self._groups()
        except ConversionError as e:
            self.lbl_fb.setText(f"⚠️ {e}")
            self.lbl_fb.setStyleSheet("color:#c81e1e")
            self.btn_save.setEnabled(False)
            self._paint_chips(set())
            return
        included = {pg for g in groups for pg in g}
        self._paint_chips(included)
        self.lbl_fb.setStyleSheet("color:#137333")
        if rentang:
            ringkas = " • ".join(
                f"{g[0] + 1}" if len(g) == 1 else f"{g[0] + 1}–{g[-1] + 1}"
                for g in groups)
            self.lbl_fb.setText(
                f"Hasil: {len(groups)} file PDF ({ringkas}) — "
                f"total {len(included)} halaman.")
        else:
            self.lbl_fb.setText(
                f"Hasil: 1 file PDF berisi {len(included)} halaman pilihan.")
        self.btn_save.setEnabled(True)

    def _save(self):
        try:
            groups = self._groups()
            if self.rb_rentang.isChecked():
                self.saved_paths = split_pdf_groups(self.src, groups)
            else:
                flat = [pg for g in groups for pg in g]
                self.saved_paths = [extract_pages(self.src, flat)]
        except ConversionError as e:
            self.lbl_fb.setText(f"⚠️ {e}")
            self.lbl_fb.setStyleSheet("color:#c81e1e")
            return
        self.accept()
