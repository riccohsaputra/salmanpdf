"""
Radial wheel widget — jantungnya Tangerine.

Wheel digambar manual pakai QPainter (annular sectors / donat):
- Tiap sektor = satu format output.
- Hover: sektor membesar + menyala oranye.
- Klik sektor -> signal formatSelected(str).
- Tengah: nama file sumber.

Hit-test pakai koordinat polar (sudut + jarak), bukan bounding box.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath
from PySide6.QtWidgets import QWidget

ORANGE = QColor("#ff7a1a")
ORANGE_LIGHT = QColor("#ffa04d")
DARK = QColor("#232323")
SECTOR = QColor("#3a3a3a")
SECTOR_HOVER = QColor("#ff7a1a")
TEXT = QColor("#ffffff")


class WheelWidget(QWidget):
    formatSelected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(380, 380)
        self.setMouseTracking(True)
        self._formats: list[str] = []
        self._center_label = "🍊"
        self._hover = -1

    def set_wheel(self, formats: list[str], center_label: str) -> None:
        self._formats = list(formats)
        self._center_label = center_label
        self._hover = -1
        self.update()

    def clear_wheel(self) -> None:
        self._formats = []
        self._hover = -1
        self.update()

    # ---------------------------------------------------------- geometry
    def _geometry(self) -> tuple[QPointF, float, float]:
        side = min(self.width(), self.height())
        center = QPointF(self.width() / 2, self.height() / 2)
        outer = side / 2 - 8
        inner = outer * 0.42
        return center, inner, outer

    def _sector_at(self, pos: QPointF) -> int:
        if not self._formats:
            return -1
        center, inner, outer = self._geometry()
        dx, dy = pos.x() - center.x(), pos.y() - center.y()
        dist = math.hypot(dx, dy)
        if dist < inner or dist > outer + 10:
            return -1
        # Qt drawPie pakai 0° di jam 3, berlawanan jarum jam; kita mulai di jam 12.
        ang = (math.degrees(math.atan2(-dy, dx)) + 360) % 360  # 0=timur, CCW
        from_top = (90 - ang + 360) % 360  # 0=utara, searah jarum jam
        step = 360 / len(self._formats)
        return int(from_top // step) % len(self._formats)

    # ---------------------------------------------------------- events
    def mouseMoveEvent(self, event):  # noqa: N802 (Qt naming)
        idx = self._sector_at(event.position())
        if idx != self._hover:
            self._hover = idx
            self.setCursor(Qt.PointingHandCursor if idx >= 0 else Qt.ArrowCursor)
            self.update()

    def mousePressEvent(self, event):  # noqa: N802
        idx = self._sector_at(event.position())
        if idx >= 0:
            self.formatSelected.emit(self._formats[idx])

    def leaveEvent(self, event):  # noqa: N802
        self._hover = -1
        self.update()

    # ---------------------------------------------------------- paint
    def paintEvent(self, event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        center, inner, outer = self._geometry()
        n = len(self._formats)

        if n == 0:
            p.setPen(QColor("#888888"))
            p.setFont(QFont("Sans", 12))
            p.drawText(self.rect(), Qt.AlignCenter, "Seret file dulu ya 🍊")
            return

        step = 360.0 / n
        gap = 2.5  # derajat celah antar sektor
        for i, fmt in enumerate(self._formats):
            hovered = i == self._hover
            r_out = outer + (10 if hovered else 0)
            # Sektor donat: arc luar + arc dalam (arah berlawanan)
            path = QPainterPath()
            start = 90 - i * step - gap / 2  # Qt: derajat, CCW dari jam 3
            span = -(step - gap)             # negatif = searah jarum jam
            rect_out = QRectF(center.x() - r_out, center.y() - r_out, r_out * 2, r_out * 2)
            rect_in = QRectF(center.x() - inner, center.y() - inner, inner * 2, inner * 2)
            path.arcMoveTo(rect_out, start)
            path.arcTo(rect_out, start, span)
            path.arcTo(rect_in, start + span, -span)
            path.closeSubpath()
            p.setPen(Qt.NoPen)
            p.setBrush(SECTOR_HOVER if hovered else SECTOR)
            p.drawPath(path)

            # Label di tengah sektor
            mid_deg = 90 - (i + 0.5) * step
            mid = math.radians(mid_deg)
            r_mid = (inner + r_out) / 2
            lx = center.x() + r_mid * math.cos(mid)
            ly = center.y() - r_mid * math.sin(mid)
            p.setPen(TEXT)
            p.setFont(QFont("Sans", 15 if hovered else 13, QFont.Bold))
            p.drawText(QRectF(lx - 50, ly - 14, 100, 28), Qt.AlignCenter, fmt)

        # Lingkaran tengah
        p.setBrush(DARK)
        p.setPen(ORANGE)
        rect_in = QRectF(center.x() - inner, center.y() - inner, inner * 2, inner * 2)
        p.drawEllipse(rect_in)
        p.setPen(TEXT)
        p.setFont(QFont("Sans", 11, QFont.Bold))
        label = self._center_label
        if len(label) > 22:
            label = label[:19] + "…"
        p.drawText(rect_in, Qt.AlignCenter | Qt.TextWordWrap, label)
