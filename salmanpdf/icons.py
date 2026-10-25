"""
Ikon alat digambar vektor pakai QPainter — TIDAK pakai emoji.

Kenapa: di laptop user, font emoji merender glyph mungil/monokrom
sehingga ikon kartu nyaris tak terlihat (keluhan 2026-10-25). Ikon di
sini digambar dari garis/bentuk sederhana berwarna merah di atas
kotak merah muda, ukuran besar (chip 56px), selalu tajam & konsisten.

Grid gambar 48x48, digambar pada pixmap 2x untuk ketajaman retina.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap, QPolygonF

RED = QColor("#d92323")
WHITE = QColor("#ffffff")
DARK = QColor("#23272f")
CHIP_BG = QColor("#fdecec")
GRID = 48.0
_INK = [RED]  # warna glyph aktif (diganti putih saat kartu "aktif")


def _pen(width: float = 3.4, color: QColor | None = None) -> QPen:
    color = color or _INK[0]
    pen = QPen(color, width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pen


def _arrow(p: QPainter, x1, y1, x2, y2, head=6.5):
    """Panah garis dari (x1,y1) ke (x2,y2) dengan kepala di ujung."""
    p.drawLine(QPointF(x1, y1), QPointF(x2, y2))
    import math
    ang = math.atan2(y2 - y1, x2 - x1)
    for da in (2.65, -2.65):
        hx = x2 + head * math.cos(ang + da)
        hy = y2 + head * math.sin(ang + da)
        p.drawLine(QPointF(x2, y2), QPointF(hx, hy))


def _page(p: QPainter, x, y, w, h):
    """Outline selembar halaman dengan lipatan pojok kanan-atas."""
    path = QPainterPath()
    fold = 7
    path.moveTo(x, y)
    path.lineTo(x + w - fold, y)
    path.lineTo(x + w, y + fold)
    path.lineTo(x + w, y + h)
    path.lineTo(x, y + h)
    path.closeSubpath()
    p.drawPath(path)
    p.drawLine(QPointF(x + w - fold, y), QPointF(x + w - fold, y + fold))
    p.drawLine(QPointF(x + w - fold, y + fold), QPointF(x + w, y + fold))


def _draw_gabung(p: QPainter):
    _arrow(p, 6, 17, 21, 17)
    _arrow(p, 42, 31, 27, 31)
    _page(p, 19, 12, 10, 24)


def _draw_pisah(p: QPainter):
    _page(p, 5, 11, 15, 26)
    _page(p, 28, 11, 15, 26)
    pen = _pen(2.6)
    pen.setStyle(Qt.PenStyle.DashLine)
    p.setPen(pen)
    p.drawLine(QPointF(24, 8), QPointF(24, 40))


def _draw_kompres(p: QPainter):
    _arrow(p, 9, 9, 19, 19)
    _arrow(p, 39, 9, 29, 19)
    _arrow(p, 9, 39, 19, 29)
    _arrow(p, 39, 39, 29, 29)


def _draw_edit(p: QPainter):
    # Pensil diagonal: badan + ujung runcing + garis tulis
    body = QPolygonF([QPointF(30, 6), QPointF(38, 14), QPointF(20, 32),
                      QPointF(12, 24)])
    p.drawPolygon(body)
    tip = QPolygonF([QPointF(12, 24), QPointF(20, 32), QPointF(9, 35)])
    p.setBrush(_INK[0])
    p.drawPolygon(tip)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawLine(QPointF(8, 42), QPointF(26, 42))


def _draw_pdfimg(p: QPainter):
    _page(p, 13, 6, 22, 36)
    p.drawEllipse(QPointF(21, 20), 2.6, 2.6)
    p.drawPolyline(QPolygonF([QPointF(16, 34), QPointF(22, 27),
                              QPointF(26, 31), QPointF(29, 28),
                              QPointF(32, 32)]))


def _draw_imgpdf(p: QPainter):
    p.drawRect(QRectF(6, 13, 20, 22))
    p.drawEllipse(QPointF(12, 20), 2.2, 2.2)
    p.drawPolyline(QPolygonF([QPointF(8, 33), QPointF(15, 26),
                              QPointF(19, 30), QPointF(22, 27),
                              QPointF(24, 30)]))
    _arrow(p, 29, 24, 37, 24)
    _page(p, 36, 10, 8, 28)


def _draw_office(p: QPainter):
    _page(p, 12, 6, 24, 36)
    for i, w in enumerate((14, 14, 9)):
        y = 20 + i * 7
        p.drawLine(QPointF(18, y), QPointF(18 + w, y))
    p.setBrush(_INK[0])
    p.drawRect(QRectF(18, 11, 6, 5))
    p.setBrush(Qt.BrushStyle.NoBrush)


def _draw_crop(p: QPainter):
    pen = _pen(3.6)
    p.setPen(pen)
    for (x, y, dx, dy) in ((10, 16, 1, 1), (38, 16, -1, 1),
                           (10, 34, 1, -1), (38, 34, -1, -1)):
        p.drawLine(QPointF(x, y), QPointF(x + 10 * dx, y))
        p.drawLine(QPointF(x, y), QPointF(x, y + 8 * dy))
    p.setPen(_pen(2.2))
    p.drawRect(QRectF(17, 15, 14, 18))


def _draw_global(p: QPainter):
    cursor = QPolygonF([QPointF(16, 6), QPointF(16, 36), QPointF(23, 29),
                        QPointF(27, 40), QPointF(31, 38), QPointF(27, 27),
                        QPointF(35, 27)])
    p.setBrush(_INK[0])
    p.drawPolygon(cursor)
    p.setBrush(Qt.BrushStyle.NoBrush)


_DRAWERS = {
    "gabung": _draw_gabung, "pisah": _draw_pisah, "kompres": _draw_kompres,
    "edit": _draw_edit, "pdfimg": _draw_pdfimg, "imgpdf": _draw_imgpdf,
    "office": _draw_office, "crop": _draw_crop, "global": _draw_global,
}


# Gaya ikon iLovePDF (disesuaikan 2026-10-25 atas permintaan Ricco):
# kotak membulat SOLID berwarna khas per alat + glyph PUTIH di atasnya.
# Alat konversi (pdfimg/imgpdf) dapat ubin belakang pucat yang bergeser
# diagonal — motif khas ikon konversi iLovePDF.
# name -> (warna ubin, pakai ubin belakang?)
_TILE_STYLE = {
    "gabung": ("#f4631e", False),   # oranye Merge
    "pisah": ("#f4631e", False),    # oranye Split
    "kompres": ("#7cb342", False),  # hijau Compress
    "edit": ("#9b51b0", False),     # ungu Edit
    "pdfimg": ("#d9a514", True),    # emas PDF to JPG
    "imgpdf": ("#d9a514", True),    # emas JPG to PDF
    "office": ("#2f6db3", False),   # biru dokumen Office
    "crop": ("#5b8c5a", False),     # hijau zaitun Crop & BG (alat khas SalmanPDF)
    "global": ("#455a64", False),   # abu baja Mode Global (alat khas SalmanPDF)
}


def tool_icon(name: str, size: int = 56, active: bool = False) -> QPixmap:
    """Pixmap ikon alat gaya iLovePDF: ubin solid berwarna + glyph putih.
    active=True (Mode Global ON) -> ubin berubah merah brand SalmanPDF."""
    bg_hex, back = _TILE_STYLE[name]
    bg = RED if active else QColor(bg_hex)
    _INK[0] = WHITE
    scale = 2  # supersampling biar tajam
    px = QPixmap(size * scale, size * scale)
    px.setDevicePixelRatio(scale)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    inset = 5 if back else 0
    if back:
        p.setBrush(bg.lighter(155))
        p.drawRoundedRect(QRectF(0, 0, size - inset, size - inset), 13, 13)
    p.setBrush(bg)
    p.drawRoundedRect(QRectF(inset, inset, size - inset, size - inset),
                      13, 13)
    # Peta grid 48 -> area glyph di dalam ubin (padding 17%)
    f = size / GRID
    p.translate(size * 0.17, size * 0.17)
    p.scale(f * 0.66, f * 0.66)
    p.setPen(_pen())
    p.setBrush(Qt.BrushStyle.NoBrush)
    _DRAWERS[name](p)
    p.end()
    _INK[0] = RED
    return px
