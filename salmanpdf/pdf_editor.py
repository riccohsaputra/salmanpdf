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
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QCheckBox, QColorDialog, QComboBox, QDialog, QFileDialog, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QRadioButton, QSlider, QSpinBox,
    QVBoxLayout,
)

from .imgprep import crop_percent, prepare_image, remove_white_background
from .pdfedit import apply_edits, list_system_fonts, render_preview

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
    clicked = Signal(int, int)

    def mousePressEvent(self, event):  # noqa: N802 (Qt API)
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position()
            self.clicked.emit(int(pos.x()), int(pos.y()))
        super().mousePressEvent(event)


class PdfEditorDialog(QDialog):
    def __init__(self, src: Path, parent=None):
        super().__init__(parent)
        self.src = Path(src)
        self.ops: list[dict] = []
        self.page = 0
        self.zoom = 1.0
        self.color = QColor(220, 40, 40)  # merah default (buat tanda tangan/catatan)
        self.image_path: Path | None = None
        self.saved_path: Path | None = None

        self.setWindowTitle(f"Edit PDF — {self.src.name}")
        self.setMinimumWidth(860)

        # ---------------- kiri: preview
        self.preview = ClickableLabel("Memuat preview…")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.preview.setStyleSheet("background: white; border: 1px solid #ddd;")
        self.preview.clicked.connect(self._on_preview_click)

        page_row = QHBoxLayout()
        page_row.addWidget(QLabel("Halaman:"))
        self.spin_page = QSpinBox(minimum=1, maximum=1, value=1)
        self.spin_page.valueChanged.connect(self._page_changed)
        page_row.addWidget(self.spin_page)
        self.lbl_pages = QLabel("")
        page_row.addWidget(self.lbl_pages)
        page_row.addStretch(1)

        left = QVBoxLayout()
        left.addLayout(page_row)
        left.addWidget(self.preview)

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
        self.lbl_hint = QLabel("Klik pada preview halaman untuk menempel.")
        self.lbl_hint.setWordWrap(True)
        right.addWidget(self.lbl_hint)
        self.lbl_ops = QLabel("Edit tertempel: 0")
        right.addWidget(self.lbl_ops)
        self.btn_undo = QPushButton("↩️ Urungkan tempelan terakhir")
        self.btn_undo.clicked.connect(self._undo)
        right.addWidget(self.btn_undo)
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
        self._refresh_preview()

    def _refresh_preview(self):
        png, self.zoom, count = render_preview(
            self.src, self.ops, self.page, PREVIEW_W)
        self.spin_page.setMaximum(count)
        self.lbl_pages.setText(f"dari {count}")
        pix = QPixmap()
        pix.loadFromData(png)
        self.preview.setPixmap(pix)
        self.preview.setFixedSize(pix.size())
        self.lbl_ops.setText(f"Edit tertempel: {len(self.ops)}")

    def _on_preview_click(self, px: int, py: int):
        x, y = px / self.zoom, py / self.zoom
        if self.radio_text.isChecked():
            text = self.edit_text.text().strip()
            if not text:
                self.lbl_hint.setText("Isi teksnya dulu, baru klik preview.")
                return
            self.ops.append({
                "type": "text", "page": self.page, "x": x, "y": y,
                "text": text, "font": self.combo_font.currentText(),
                "size": self.spin_size.value(),
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
        self._refresh_preview()

    def _undo(self):
        if self.ops:
            self.ops.pop()
            self._refresh_preview()

    def _save(self):
        if not self.ops:
            self.lbl_hint.setText("Belum ada edit yang ditempel.")
            return
        self.saved_path = apply_edits(self.src, self.ops)
        self.accept()
