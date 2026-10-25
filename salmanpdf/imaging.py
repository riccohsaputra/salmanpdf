"""
Edit gambar ala SalmanPDF (Crop + Add BG) — murni Pillow, tanpa Qt,
jadi bisa di-unit-test headless.

- crop_sides : potong tiap sisi (dalam % dari ukuran asal)
- crop_aspect: potong tengah mengikuti rasio (1:1, 4:3, 16:9, ...)
- add_background: taruh gambar di atas canvas warna dengan padding,
  sudut membulat (corner radius), dan bayangan lembut (shadow) di sisinya.
"""
from __future__ import annotations

from PIL import Image, ImageDraw, ImageFilter

ASPECTS: dict[str, float | None] = {
    "Bebas": None,
    "1:1": 1.0,
    "4:3": 4 / 3,
    "3:4": 3 / 4,
    "3:2": 3 / 2,
    "2:3": 2 / 3,
    "16:9": 16 / 9,
    "9:16": 9 / 16,
}


def crop_sides(im: Image.Image, left: float, top: float,
               right: float, bottom: float) -> Image.Image:
    """Potong sisi dalam persen (0-45 per sisi). Minimal sisa 10% tiap sumbu."""
    w, h = im.size
    l = int(w * min(max(left, 0), 45) / 100)
    t = int(h * min(max(top, 0), 45) / 100)
    r = w - int(w * min(max(right, 0), 45) / 100)
    b = h - int(h * min(max(bottom, 0), 45) / 100)
    if r - l <= max(1, w // 10) or b - t <= max(1, h // 10):
        raise ValueError("Potongan terlalu besar — hasilnya kekecilan.")
    return im.crop((l, t, r, b))


def crop_aspect(im: Image.Image, ratio: float) -> Image.Image:
    """Crop TENGAH mengikuti rasio lebar/tinggi."""
    w, h = im.size
    cur = w / h
    if abs(cur - ratio) < 0.01:
        return im.copy()
    if cur > ratio:  # terlalu lebar -> potong kiri/kanan
        new_w = int(h * ratio)
        x0 = (w - new_w) // 2
        return im.crop((x0, 0, x0 + new_w, h))
    new_h = int(w / ratio)
    y0 = (h - new_h) // 2
    return im.crop((0, y0, w, y0 + new_h))


def _rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle([0, 0, size[0] - 1, size[1] - 1],
                        radius=max(0, radius), fill=255)
    return mask


def add_background(im: Image.Image, bg: tuple[int, int, int],
                   padding: int, corner_radius: int,
                   shadow: bool = True, shadow_blur: int = 24,
                   shadow_offset: int = 14, shadow_opacity: int = 110,
                   ) -> Image.Image:
    """
    Gambar ditaruh di canvas warna `bg`:
      canvas = gambar + 2*padding + ruang shadow di bawah/kanan.
    Shadow = rounded-rect hitam buram yang digeser lalu di-blur, digambar
    DI BELAKANG gambar — itu yang bikin sisi gambar ada bayangannya.
    """
    src = im.convert("RGBA")
    w, h = src.size
    pad = max(0, padding)
    off = max(0, shadow_offset) if shadow else 0
    blur = max(0, shadow_blur) if shadow else 0
    margin = pad + blur + off  # ruang ekstra sisi bawah/kanan untuk shadow
    canvas = Image.new("RGBA", (w + pad * 2 + (blur + off if shadow else 0),
                                h + pad * 2 + (blur + off if shadow else 0)), bg + (255,))
    if shadow:
        sh = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(sh)
        x0, y0 = pad + off, pad + off
        d.rounded_rectangle([x0, y0, x0 + w - 1, y0 + h - 1],
                            radius=max(0, corner_radius),
                            fill=(0, 0, 0, max(0, min(shadow_opacity, 255))))
        canvas.alpha_composite(sh.filter(ImageFilter.GaussianBlur(blur)))
    if corner_radius > 0:
        # Sudut dibulatkan, sambil menghormati alpha asli gambar.
        from PIL import ImageChops
        mask = _rounded_mask(src.size, corner_radius)
        src.putalpha(ImageChops.multiply(src.getchannel("A"), mask))
    canvas.alpha_composite(src, (pad, pad))
    return canvas.convert("RGB")


def apply_edits(im: Image.Image, *, crop: tuple[float, float, float, float] | None = None,
                aspect: float | None = None, background: dict | None = None,
                ) -> Image.Image:
    """Pipeline editor: crop sisi -> crop rasio -> add background."""
    out = im
    if crop and any(crop):
        out = crop_sides(out, *crop)
    if aspect:
        out = crop_aspect(out, aspect)
    if background is not None:
        out = add_background(out, **background)
    return out
