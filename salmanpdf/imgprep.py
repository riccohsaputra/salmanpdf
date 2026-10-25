"""
Persiapan gambar sebelum ditempel ke PDF (dipakai dialog Edit PDF):
- Crop tepi dalam persen (kiri/atas/kanan/bawah).
- Hapus background putih "dengan halus": alpha dihitung dari kecerahan
  saluran minimum (whiteness) dengan ramp linier menuju transparan +
  blur tipis pada alpha, jadi tepi objek (mis. goresan tanda tangan)
  menyatu lembut tanpa tangga piksel.

Murni Pillow — tanpa numpy — supaya ringan & bisa diuji headless.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageChops, ImageFilter


def crop_percent(img: Image.Image, left: float = 0, top: float = 0,
                 right: float = 0, bottom: float = 0) -> Image.Image:
    """Potong tepi gambar sebesar persen dari lebar/tinggi (0–45/sisi)."""
    w, h = img.size
    x0 = int(w * max(0.0, min(45.0, left)) / 100)
    y0 = int(h * max(0.0, min(45.0, top)) / 100)
    x1 = w - int(w * max(0.0, min(45.0, right)) / 100)
    y1 = h - int(h * max(0.0, min(45.0, bottom)) / 100)
    if x1 - x0 < 8 or y1 - y0 < 8:
        return img
    return img.crop((x0, y0, x1, y1))


def remove_white_background(img: Image.Image, cutoff: int = 205,
                            blur: float = 0.9) -> Image.Image:
    """Ubah background (nyaris) putih menjadi transparan secara halus.

    cutoff: nilai whiteness (saluran minimum 0–255) di mana piksel masih
    dianggap objek penuh. Di atas cutoff, alpha turun linier sampai 0 di
    putih murni (255), lalu alpha di-blur tipis -> tepi lembut.
    """
    rgb = img.convert("RGB")
    r, g, b = rgb.split()
    whiteness = ImageChops.darker(ImageChops.darker(r, g), b)
    cutoff = max(80, min(250, int(cutoff)))
    span = max(1, 255 - cutoff)
    lut = [255 if i <= cutoff else int(255 * (255 - i) / span)
           for i in range(256)]
    alpha = whiteness.point(lut)
    if blur > 0:
        alpha = alpha.filter(ImageFilter.GaussianBlur(blur))
    out = rgb.convert("RGBA")
    out.putalpha(alpha)
    return out


def prepare_image(src: Path, dest: Path, left: float = 0, top: float = 0,
                  right: float = 0, bottom: float = 0,
                  remove_bg: bool = False, cutoff: int = 205) -> Path:
    """Pipeline penuh: buka -> crop -> (opsional) hapus BG -> simpan PNG."""
    with Image.open(src) as im:
        im.load()
        out = crop_percent(im, left, top, right, bottom)
        if remove_bg:
            out = remove_white_background(out, cutoff=cutoff)
        else:
            out = out.convert("RGBA")
        dest.parent.mkdir(parents=True, exist_ok=True)
        out.save(dest, "PNG")
    return dest
