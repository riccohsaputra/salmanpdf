"""Test edit gambar (crop + add BG + shadow) — murni Pillow."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from PIL import Image

from tangerine.imaging import add_background, apply_edits, crop_aspect, crop_sides


@pytest.fixture()
def foto() -> Image.Image:
    return Image.new("RGB", (200, 100), (200, 30, 30))


def test_crop_sides_persen(foto):
    out = crop_sides(foto, 10, 0, 10, 0)
    assert out.size == (160, 100)


def test_crop_sides_berlebihan_ditolak(foto):
    with pytest.raises(ValueError):
        crop_sides(foto, 45, 45, 45, 45)


def test_crop_aspect_1_1_dan_16_9(foto):
    assert crop_aspect(foto, 1.0).size == (100, 100)
    lebar = crop_aspect(Image.new("RGB", (100, 200)), 16 / 9)
    assert lebar.size[0] == 100 and abs(lebar.size[0] / lebar.size[1] - 16 / 9) < 0.03


def test_add_background_canvas_dan_warna_sudut(foto):
    out = add_background(foto, (250, 165, 30), padding=20, corner_radius=0,
                         shadow=False)
    assert out.size == (240, 140)
    assert out.getpixel((2, 2)) == (250, 165, 30)      # area padding = warna bg
    assert out.getpixel((120, 70)) == (200, 30, 30)    # tengah = gambar asli


def test_shadow_membuat_sisi_gelap_dan_canvas_lebih_besar(foto):
    polos = add_background(foto, (255, 255, 255), padding=20, corner_radius=0,
                           shadow=False)
    bayang = add_background(foto, (255, 255, 255), padding=20, corner_radius=0,
                            shadow=True, shadow_blur=10, shadow_offset=10,
                            shadow_opacity=140)
    assert bayang.size[0] > polos.size[0] and bayang.size[1] > polos.size[1]
    # Titik di jalur shadow (kanan gambar, masih di dalam canvas) lebih gelap
    # daripada bg putih polos.
    px = bayang.getpixel((20 + 200 + 5, 20 + 50))
    assert px[0] < 250 and px == bayang.getpixel((20 + 200 + 5, 20 + 50))


def test_corner_radius_sudut_jadi_background(foto):
    out = add_background(foto, (10, 20, 30), padding=10, corner_radius=28,
                         shadow=False)
    # Sudut gambar (bukan sudut canvas) harus transparan-> warna bg.
    assert out.getpixel((11, 11)) == (10, 20, 30)


def test_apply_edits_pipeline(foto):
    out = apply_edits(foto, crop=(10, 0, 10, 0), aspect=1.0,
                      background=dict(bg=(0, 0, 0), padding=5, corner_radius=0,
                                      shadow=False))
    assert out.size == (110, 110)  # 160x100 -> crop rasio 1:1 = 100x100, +padding 5*2
