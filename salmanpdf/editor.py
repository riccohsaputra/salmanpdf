"""
Dialog editor gambar: Crop + Add BG (padding, corners, shadow) —
meniru jendela Crop Image & Add BG di Tangerine asli.

Preview dihitung dari thumbnail (cepat), hasil simpan dihitung ulang
dari resolusi penuh. Semua parameter dinyatakan relatif (%) supaya
tampilan preview dan hasil akhir proporsinya sama.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPixmap
from PySide6.QtWidgets import (
    QCheckBox, QColorDialog, QComboBox, QDialog, QHBoxLayout, QLabel,
    QPushButton, QSlider, QVBoxLayout, QWidget,
)

from .converters import unique_output
from .imaging import ASPECTS, apply_edits

SWATCHES = [
    ("Oranye", (255, 138, 61)),
    ("Kuning", (250, 197, 44)),
    ("Putih", (255, 255, 255)),
    ("Hitam", (18, 18, 18)),
    ("Abu", (128, 135, 141)),
    ("Biru", (64, 120, 242)),
    ("Hijau", (52, 168, 83)),
    ("Ungu", (147, 88, 247)),
]


def _to_pixmap(im: Image.Image) -> QPixmap:
    rgb = im.convert("RGB")
    data = rgb.tobytes()
    qimg = QImage(data, rgb.width, rgb.height, rgb.width * 3,
                  QImage.Format_RGB888).copy()
    return QPixmap.fromImage(qimg)


class _SliderRow(QWidget):
    def __init__(self, label: str, maximum: int, value: int, suffix: str = "%"):
        super().__init__()
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, maximum)
        self.slider.setValue(value)
        self._suffix = suffix
        self._val = QLabel()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(QLabel(label))
        lay.addWidget(self.slider, stretch=1)
        lay.addWidget(self._val)
        self.slider.valueChanged.connect(self._sync)
        self._sync()

    def _sync(self) -> None:
        self._val.setText(f"{self.slider.value()}{self._suffix}")

    def value(self) -> int:
        return self.slider.value()


class ImageEditorDialog(QDialog):
    def __init__(self, src: Path, parent=None):
        super().__init__(parent)
        self.src = src
        self.saved_path: Path | None = None
        self.setWindowTitle(f"✂️ Edit gambar — {src.name}")
        self.resize(880, 560)

        self._full = Image.open(src)
        self._full.load()
        self._thumb = self._full.copy()
        self._thumb.thumbnail((520, 520))
        self._bg_color: tuple[int, int, int] = SWATCHES[0][1]

        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumSize(420, 420)
        self.err = QLabel("")
        self.err.setStyleSheet("color:#c0392b")
        self.preview.setStyleSheet(
            "background:#ffffff;border:1px solid #e3ded2;border-radius:12px")

        # --- Crop ---
        self.c_left = _SliderRow("Kiri", 45, 0)
        self.c_top = _SliderRow("Atas", 45, 0)
        self.c_right = _SliderRow("Kanan", 45, 0)
        self.c_bottom = _SliderRow("Bawah", 45, 0)
        self.aspect = QComboBox()
        self.aspect.addItems(list(ASPECTS.keys()))

        # --- Add BG ---
        self.use_bg = QCheckBox("Pakai background + shadow")
        self.use_bg.setChecked(True)
        self.pad = _SliderRow("Padding", 30, 8)
        self.radius = _SliderRow("Corners", 50, 12)
        self.use_shadow = QCheckBox("Shadow di sisi gambar")
        self.use_shadow.setChecked(True)
        self.sh_blur = _SliderRow("Blur shadow", 10, 3)
        self.sh_offset = _SliderRow("Geser shadow", 8, 2)
        self.sh_opacity = _SliderRow("Gelap shadow", 200, 110, suffix="")

        sw_row = QHBoxLayout()
        for name, rgb in SWATCHES:
            b = QPushButton(name)
            b.setStyleSheet(f"background:rgb{rgb};color:#111;border-radius:6px;padding:4px")
            b.clicked.connect(lambda _=False, c=rgb: self._set_bg(c))
            sw_row.addWidget(b)
        custom = QPushButton("Warna lain…")
        custom.clicked.connect(self._pick_color)
        sw_row.addWidget(custom)

        right = QVBoxLayout()
        right.addWidget(QLabel("<b>Crop</b>"))
        for w in (self.c_left, self.c_top, self.c_right, self.c_bottom):
            right.addWidget(w)
        r_row = QHBoxLayout()
        r_row.addWidget(QLabel("Rasio:"))
        r_row.addWidget(self.aspect)
        right.addLayout(r_row)
        right.addWidget(QLabel("<b>Add Background</b>"))
        right.addWidget(self.use_bg)
        right.addLayout(sw_row)
        right.addWidget(self.pad)
        right.addWidget(self.radius)
        right.addWidget(self.use_shadow)
        right.addWidget(self.sh_blur)
        right.addWidget(self.sh_offset)
        right.addWidget(self.sh_opacity)
        right.addStretch()
        self.err2 = self.err
        right.addWidget(self.err2)

        save_btn = QPushButton("💾 Simpan hasil (di sebelah file asli)")
        save_btn.clicked.connect(self._save)
        cancel_btn = QPushButton("Batal")
        cancel_btn.clicked.connect(self.reject)
        btn_row = QHBoxLayout()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        right.addLayout(btn_row)

        left = QVBoxLayout()
        left.addWidget(self.preview)

        root = QHBoxLayout(self)
        root.addLayout(left, stretch=1)
        root.addLayout(right)

        for w in (self.c_left, self.c_top, self.c_right, self.c_bottom,
                  self.pad, self.radius, self.sh_blur, self.sh_offset,
                  self.sh_opacity):
            w.slider.valueChanged.connect(self._refresh)
        for w in (self.use_bg, self.use_shadow):
            w.toggled.connect(self._refresh)
        self.aspect.currentTextChanged.connect(self._refresh)
        self._refresh()

    # ------------------------------------------------------------ params
    def _set_bg(self, rgb: tuple[int, int, int]) -> None:
        self._bg_color = rgb
        self._refresh()

    def _pick_color(self) -> None:
        c = QColorDialog.getColor(QColor(*self._bg_color), self, "Warna background")
        if c.isValid():
            self._set_bg((c.red(), c.green(), c.blue()))

    def _params(self, im: Image.Image) -> dict:
        """Parameter apply_edits untuk gambar berukuran `im` (relatif -> px)."""
        w, h = im.size
        kw: dict = {}
        crop = (self.c_left.value(), self.c_top.value(),
                self.c_right.value(), self.c_bottom.value())
        if any(crop):
            kw["crop"] = tuple(float(x) for x in crop)
        ratio = ASPECTS[self.aspect.currentText()]
        if ratio:
            kw["aspect"] = ratio
        if self.use_bg.isChecked():
            kw["background"] = dict(
                bg=self._bg_color,
                padding=int(w * self.pad.value() / 100),
                corner_radius=int(min(w, h) / 2 * self.radius.value() / 100),
                shadow=self.use_shadow.isChecked(),
                shadow_blur=int(w * self.sh_blur.value() / 100),
                shadow_offset=int(w * self.sh_offset.value() / 100),
                shadow_opacity=self.sh_opacity.value(),
            )
        return kw

    # ------------------------------------------------------------ flow
    def _refresh(self) -> None:
        try:
            out = apply_edits(self._thumb.copy(), **self._params(self._thumb))
            self.err.setText("")
        except ValueError as e:
            self.err.setText(str(e))
            return
        pix = _to_pixmap(out)
        self.preview.setPixmap(pix.scaled(520, 520, Qt.KeepAspectRatio,
                                          Qt.SmoothTransformation))

    def _save(self) -> None:
        try:
            out = apply_edits(self._full.copy(), **self._params(self._full))
        except ValueError as e:
            self.err.setText(str(e))
            return
        ext = self.src.suffix.lower().lstrip(".") or "png"
        if ext in ("jpg", "jpeg"):
            dest = unique_output(self.src, "jpg", "-edit")
            out.convert("RGB").save(dest, "JPEG", quality=92)
        elif ext == "webp":
            dest = unique_output(self.src, "webp", "-edit")
            out.save(dest, "WEBP", quality=90)
        else:
            dest = unique_output(self.src, "png", "-edit")
            out.save(dest, "PNG")
        self.saved_path = dest
        self.accept()


class BgRemoveDialog(QDialog):
    """Hapus background (putih) gambar dengan halus — alat mandiri.
    Preview di atas papan catur; hasil disimpan PNG transparan di
    sebelah file asli dengan akhiran -nobg."""

    def __init__(self, src: Path, parent=None):
        super().__init__(parent)
        self.src = src
        self.saved_path: Path | None = None
        self.setWindowTitle(f"Hapus Background — {src.name}")
        self.resize(700, 520)
        with Image.open(src) as im:
            im.load()
            self._full = im.convert("RGBA")
        self._work = self._full.copy()
        self._work.thumbnail((880, 880))

        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumSize(320, 320)
        self.preview.setStyleSheet(
            "background:#f0f0f0;border:1px solid #ddd;border-radius:8px")

        right = QVBoxLayout()
        right.addWidget(QLabel("<b>Ambang putih</b>"))
        self.s_cut = QSlider(Qt.Orientation.Horizontal)
        self.s_cut.setRange(140, 250)
        self.s_cut.setValue(205)
        self.s_cut.valueChanged.connect(self._refresh)
        right.addWidget(self.s_cut)
        hint = QLabel(
            "Geser sampai background hilang bersih tapi objek tetap utuh. "
            "Ambang kecil = lebih agresif. Paling cocok untuk gambar di "
            "atas background putih/terang polos (tanda tangan, logo, produk).")
        hint.setWordWrap(True)
        hint.setStyleSheet("font-size:11.5px;color:#6b7280")
        right.addWidget(hint)
        right.addStretch(1)
        btn_row = QHBoxLayout()
        ok = QPushButton("💾 Simpan hasil (PNG transparan)")
        ok.clicked.connect(self._save)
        cancel = QPushButton("Batal")
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(ok)
        btn_row.addWidget(cancel)
        right.addLayout(btn_row)

        root = QHBoxLayout(self)
        root.addWidget(self.preview, 1)
        root.addLayout(right, 1)
        self._refresh()

    def _refresh(self) -> None:
        from .imgprep import remove_white_background
        out = remove_white_background(self._work, cutoff=self.s_cut.value())
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
        pix = _to_pixmap(board)
        self.preview.setPixmap(pix.scaled(
            500, 500, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation))

    def _save(self) -> None:
        from .imgprep import remove_white_background
        out = remove_white_background(self._full, cutoff=self.s_cut.value())
        dest = unique_output(self.src, "png", "-nobg")
        out.save(dest, "PNG")
        self.saved_path = dest
        self.accept()
