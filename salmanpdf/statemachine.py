"""
State machine untuk mode global Shift+Drag (v2, X11).

Logika murni (tanpa Xlib / Qt) supaya bisa di-unit-test headless.
Input: sampel pointer global (tombol kiri, Shift, posisi) dari poller X11.
Output: event "show" (tampilkan wheel di posisi ini) / "hide".

Aturan:
- Drag dianggap mulai saat tombol kiri ditekan.
- Kalau, selagi drag, pointer bergerak > threshold dari titik tekan
  DAN Shift ditekan -> "show" (sekali).
- Wheel sembunyi saat tombol kiri dilepas (drop / batal) atau Shift
  dilepas sebelum drop.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class PointerSample:
    x: int
    y: int
    left_down: bool
    shift_down: bool


class DragTracker:
    def __init__(self, threshold_px: int = 8):
        self.threshold = threshold_px
        self._press_origin: tuple[int, int] | None = None
        self._wheel_shown = False

    @property
    def wheel_shown(self) -> bool:
        return self._wheel_shown

    def feed(self, s: PointerSample) -> str | None:
        """Kembalikan 'show' / 'hide' / None untuk satu sampel."""
        if not s.left_down:
            # Tombol dilepas: akhiri drag apa pun statusnya.
            was_shown = self._wheel_shown
            self._press_origin = None
            self._wheel_shown = False
            return "hide" if was_shown else None

        if self._press_origin is None:
            self._press_origin = (s.x, s.y)
            return None

        if self._wheel_shown:
            if not s.shift_down:
                self._wheel_shown = False
                return "hide"
            return None

        moved = math.hypot(s.x - self._press_origin[0],
                           s.y - self._press_origin[1])
        if s.shift_down and moved > self.threshold:
            self._wheel_shown = True
            return "show"
        return None

    def reset(self) -> None:
        self._press_origin = None
        self._wheel_shown = False
