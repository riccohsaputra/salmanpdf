"""Tes logika susunan tempelan Edit PDF (murni, tanpa GUI)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from salmanpdf.pdfedit import hit_test, move_op, op_bbox


def img(page, x, y, w=100, h=50):
    return {"type": "image", "page": page, "x": x, "y": y, "w": w, "h": h,
            "path": "x.png"}


def test_bbox_image_dan_teks():
    assert op_bbox(img(0, 10, 20)) == (10, 20, 110, 70)
    t = {"type": "text", "page": 0, "x": 50, "y": 100, "text": "Halo",
         "size": 20, "w": 44}
    x0, y0, x1, y1 = op_bbox(t)
    assert (x0, x1) == (50, 94)
    assert y0 == 80 and y1 == 107  # baseline 100, naik 20, turun 0.35*20


def test_hit_test_paling_atas_dan_halaman():
    ops = [img(0, 0, 0), img(0, 10, 10), img(1, 0, 0)]
    assert hit_test(ops, 0, 20, 20) == 1      # tumpukan: yang terakhir di atas
    assert hit_test(ops, 0, 5, 5) == 0
    assert hit_test(ops, 1, 20, 20) == 2      # halaman lain
    assert hit_test(ops, 0, 500, 500) is None


def test_move_op_sususan_satu_halaman():
    a, b, c = img(0, 0, 0), img(0, 5, 5), img(0, 9, 9)
    ops = [a, b, c]
    assert move_op(ops, 0, "forward") == 1 and ops == [b, a, c]
    assert move_op(ops, 1, "front") == 2 and ops == [b, c, a]
    assert move_op(ops, 2, "back") == 0 and ops == [a, b, c]
    assert move_op(ops, 0, "backward") == 0 and ops == [a, b, c]  # sudah paling belakang


def test_move_op_abaikan_halaman_lain():
    a, x, b = img(0, 0, 0), img(1, 0, 0), img(0, 5, 5)
    ops = [a, x, b]
    # b maju selangkah di hal. 0 -> bertukar dengan a, x (hal. 1) tak bergeser relatif
    assert move_op(ops, 2, "backward") == 0 and ops == [b, x, a]
    # front = sesudah op sehalaman terakhir (a); op halaman lain bebas
    assert move_op(ops, 0, "front") == 2 and ops == [x, a, b]
