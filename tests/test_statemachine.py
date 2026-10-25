"""Test state machine Shift+Drag global (v2) — logika murni, tanpa X/Qt."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from salmanpdf.statemachine import DragTracker, PointerSample


def S(x, y, left=True, shift=False):
    return PointerSample(x=x, y=y, left_down=left, shift_down=shift)


def test_show_only_after_movement_and_shift():
    t = DragTracker(threshold_px=8)
    assert t.feed(S(100, 100)) is None              # baru tekan
    assert t.feed(S(102, 101, shift=True)) is None  # gerak < threshold
    assert t.feed(S(130, 100, shift=True)) == "show"
    assert t.wheel_shown


def test_no_show_without_shift():
    t = DragTracker()
    t.feed(S(0, 0))
    assert t.feed(S(200, 0, shift=False)) is None
    assert not t.wheel_shown


def test_hide_on_release_and_on_shift_up():
    t = DragTracker()
    t.feed(S(0, 0)); t.feed(S(50, 0, shift=True))
    assert t.feed(S(50, 0, shift=False)) == "hide"   # Shift dilepas
    t.feed(S(0, 0)); t.feed(S(50, 0, shift=True))
    assert t.feed(S(50, 0, left=False)) == "hide"    # drop / lepas mouse


def test_new_drag_after_release():
    t = DragTracker()
    t.feed(S(0, 0)); t.feed(S(50, 0, shift=True)); t.feed(S(50, 0, left=False))
    assert t.feed(S(10, 10)) is None
    assert t.feed(S(60, 10, shift=True)) == "show"
