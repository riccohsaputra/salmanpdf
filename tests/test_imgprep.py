"""Test persiapan gambar Edit PDF: crop persen + hapus BG putih halus."""
from PIL import Image

from salmanpdf.imgprep import crop_percent, remove_white_background


def _white_with_black_box(size=100, box=40):
    img = Image.new("RGB", (size, size), (255, 255, 255))
    off = (size - box) // 2
    for x in range(off, off + box):
        for y in range(off, off + box):
            img.putpixel((x, y), (10, 10, 10))
    return img


def test_crop_percent_dims():
    img = Image.new("RGB", (200, 100))
    out = crop_percent(img, left=10, right=10, top=20, bottom=0)
    assert out.size == (160, 80)


def test_remove_bg_corners_transparent_center_opaque():
    out = remove_white_background(_white_with_black_box(), cutoff=205)
    assert out.mode == "RGBA"
    assert out.getpixel((2, 2))[3] == 0          # background putih -> hilang
    assert out.getpixel((50, 50))[3] == 255      # objek gelap -> penuh
    # Tepi objek harus punya piksel semi-transparan (transisi HALUS)
    alphas = [out.getpixel((x, 50))[3] for x in range(25, 36)]
    assert any(0 < a < 255 for a in alphas)


def test_remove_bg_respects_cutoff():
    # Abu muda (230) di atas cutoff 240 -> masih dianggap objek
    img = Image.new("RGB", (20, 20), (230, 230, 230))
    out = remove_white_background(img, cutoff=240, blur=0)
    assert out.getpixel((10, 10))[3] == 255
