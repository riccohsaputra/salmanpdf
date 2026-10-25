"""
Wheel overlay global (v2) — jendela transparan selalu-di-atas yang jadi
DROP TARGET beneran untuk drag dari Nemo/Nautilus (protokol XDND).

Alur XDND yang dimanfaatkan:
1. Tracker X11 mendeteksi Shift+drag -> overlay ditampilkan di kursor.
2. Saat drag MASUK ke overlay, Qt memberi mimeData berisi URL file ->
   baru di sini tipe file ketahuan, sektor wheel diisi format yang valid.
3. dragMove -> sektor di posisi pointer menyala.
4. Drop -> sektor di titik drop = format tujuan -> signal dropped().
5. Drag keluar / Shift dilepas / drop selesai -> overlay sembunyi.

Keterbatasan eksperimental (jujur): tidak semua aplikasi sumber drag
mengevaluasi ulang target XDND untuk jendela yang BARU muncul di tengah
drag. Nemo (GTK) umumnya mau. Kalau gagal, mode drop-zone v1 selalu
jadi fallback.
"""
from __future__ import annotations

import math
from pathlib import Path

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QGuiApplication, QPainter, QPainterPath
from PySide6.QtCore import QRectF
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QWidget

from .converters import detect_kind, formats_for

SIZE = 340
# Frosted glass ala Tangerine asli: putih transparan, teks gelap,
# hover merah + teks putih.
SECTOR = QColor(255, 255, 255, 215)
SECTOR_HOVER = QColor("#d92323")
SECTOR_EDGE = QColor(0, 0, 0, 70)
CENTER = QColor(255, 255, 255, 235)
TEXT = QColor("#26221f")
TEXT_HOVER = QColor("#ffffff")


def sector_index(pos: QPointF, center: QPointF, inner: float,
                 outer: float, count: int) -> int:
    """Hit-test polar, sama seperti WheelWidget._sector_at."""
    if count <= 0:
        return -1
    dx, dy = pos.x() - center.x(), pos.y() - center.y()
    dist = math.hypot(dx, dy)
    if dist < inner or dist > outer + 12:
        return -1
    ang = (math.degrees(math.atan2(-dy, dx)) + 360) % 360
    from_top = (90 - ang + 360) % 360
    return int(from_top // (360 / count)) % count


class WheelOverlay(QWidget):
    dropped = Signal(list, str)   # (files, format)
    dragEnded = Signal()

    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFixedSize(SIZE, SIZE)
        self.setAcceptDrops(True)
        # Bayangan lembut mengikuti siluet lingkaran wheel — bikin tepi
        # lingkaran tegas terlihat (tidak "hilang" di atas jendela putih)
        # dan lingkarannya terbaca simetris.
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(0, 0, 0, 110))
        self.setGraphicsEffect(shadow)
        self._formats: list[str] = []
        self._files: list[Path] = []
        self._hover = -1
        self._label = "📄"

    # ------------------------------------------------------------ show
    def show_at_cursor(self) -> None:
        pos = QCursor.pos()
        # PENTING: clamp supaya SELURUH lingkaran selalu di dalam layar.
        # Dulu wheel ditengahin persis di kursor — kalau drag-nya dekat
        # tepi/atas layar, separuh lingkaran keluar layar dan wheel
        # kelihatan "tidak simetris" / terpotong.
        screen = QGuiApplication.screenAt(pos) or QGuiApplication.primaryScreen()
        geo = screen.availableGeometry()
        x = pos.x() - SIZE // 2
        y = pos.y() - SIZE // 2
        x = max(geo.left() + 4, min(x, geo.right() - SIZE - 4))
        y = max(geo.top() + 4, min(y, geo.bottom() - SIZE - 4))
        self.move(x, y)
        self._formats, self._files, self._hover = [], [], -1
        self._label = "📄 drop di wheel…"
        self.show()
        self.update()

    # ------------------------------------------------------------ DnD
    def dragEnterEvent(self, event):  # noqa: N802
        if event.mimeData().hasUrls():
            files = [Path(u.toLocalFile()) for u in event.mimeData().urls()
                     if u.isLocalFile()]
            files = [f for f in files if detect_kind(f) is not None]
            if files:
                common = set(formats_for(files[0]))
                for f in files[1:]:
                    common &= set(formats_for(f))
                self._files = files
                self._formats = [f for f in formats_for(files[0]) if f in common]
                self._label = files[0].name if len(files) == 1 else f"{len(files)} file"
                event.acceptProposedAction()
                self.update()
                return
        event.ignore()

    def dragMoveEvent(self, event):  # noqa: N802
        center = QPointF(SIZE / 2, SIZE / 2)
        idx = sector_index(event.position(), center, SIZE * 0.21,
                           SIZE / 2 - 6, len(self._formats))
        if idx != self._hover:
            self._hover = idx
            self.update()
        event.acceptProposedAction()

    def dragLeaveEvent(self, event):  # noqa: N802
        self._hover = -1
        self.update()

    def dropEvent(self, event):  # noqa: N802
        center = QPointF(SIZE / 2, SIZE / 2)
        idx = sector_index(event.position(), center, SIZE * 0.21,
                           SIZE / 2 - 6, len(self._formats))
        files, formats = self._files, self._formats
        self.hide()
        self.dragEnded.emit()
        if idx >= 0 and files:
            self.dropped.emit([str(f) for f in files], formats[idx])
            event.acceptProposedAction()
        else:
            event.ignore()

    # ------------------------------------------------------------ paint
    def paintEvent(self, event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        center = QPointF(SIZE / 2, SIZE / 2)
        outer, inner = SIZE / 2 - 6, SIZE * 0.21
        n = len(self._formats)
        if n == 0:
            p.setBrush(SECTOR)
            p.setPen(Qt.NoPen)
            p.drawEllipse(center, outer, outer)
            p.setPen(TEXT)
            p.setFont(QFont("Sans", 13, QFont.Bold))
            p.drawText(QRectF(10, SIZE / 2 - 16, SIZE - 20, 32),
                       Qt.AlignCenter, self._label)
            return
        step, gap = 360.0 / n, 2.5
        for i, fmt in enumerate(self._formats):
            hovered = i == self._hover
            r_out = outer + (8 if hovered else 0)
            path = QPainterPath()
            start = 90 - i * step - gap / 2
            span = -(step - gap)
            ro = QRectF(center.x() - r_out, center.y() - r_out, r_out * 2, r_out * 2)
            ri = QRectF(center.x() - inner, center.y() - inner, inner * 2, inner * 2)
            path.arcMoveTo(ro, start)
            path.arcTo(ro, start, span)
            path.arcTo(ri, start + span, -span)
            path.closeSubpath()
            p.setPen(SECTOR_EDGE)
            p.setBrush(SECTOR_HOVER if hovered else SECTOR)
            p.drawPath(path)
            mid = math.radians(90 - (i + 0.5) * step)
            r_mid = (inner + r_out) / 2
            lx = center.x() + r_mid * math.cos(mid)
            ly = center.y() - r_mid * math.sin(mid)
            p.setPen(TEXT_HOVER if hovered else TEXT)
            p.setFont(QFont("Sans", 15 if hovered else 13, QFont.Bold))
            p.drawText(QRectF(lx - 50, ly - 14, 100, 28), Qt.AlignCenter, fmt)
        p.setBrush(CENTER)
        p.setPen(QColor("#d92323"))
        ri = QRectF(center.x() - inner, center.y() - inner, inner * 2, inner * 2)
        p.drawEllipse(ri)
        p.setPen(TEXT)
        p.setFont(QFont("Sans", 10, QFont.Bold))
        label = self._label if len(self._label) <= 20 else self._label[:17] + "…"
        p.drawText(ri, Qt.AlignCenter | Qt.TextWordWrap, label)
