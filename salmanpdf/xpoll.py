"""
Poller pointer global X11 (python-xlib).

Kenapa polling query_pointer? Karena mask yang dikembalikan X11 sudah
berisi status tombol mouse DAN modifier (ShiftMask) global, tanpa perlu
XRecord / grab. Cukup query root window tiap ~25 ms.

Hanya jalan di sesi X11. Di Wayland, XQueryPointer tidak memberi data
global seperti ini -> caller harus cek XDG_SESSION_TYPE lebih dulu.
"""
from __future__ import annotations

import os

from .statemachine import PointerSample

# Mask X11 (xcb / X.h)
BUTTON1_MASK = 0x100
SHIFT_MASK = 0x1


def session_is_x11() -> bool:
    return os.environ.get("XDG_SESSION_TYPE", "").lower() == "x11" or (
        "DISPLAY" in os.environ and "WAYLAND_DISPLAY" not in os.environ
    )


class X11Poller:
    def __init__(self):
        try:
            from Xlib import display as xdisplay
        except ImportError as e:
            raise RuntimeError(
                "python-xlib belum terinstall: pip install python-xlib"
            ) from e
        self._display = xdisplay.Display()
        self._root = self._display.screen().root

    def sample(self) -> PointerSample:
        q = self._root.query_pointer()
        return PointerSample(
            x=q.root_x, y=q.root_y,
            left_down=bool(q.mask & BUTTON1_MASK),
            shift_down=bool(q.mask & SHIFT_MASK),
        )

    def close(self) -> None:
        try:
            self._display.close()
        except Exception:
            pass
