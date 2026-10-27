"""Conversión de la imagen descargada al PNG cuadrado final."""

from __future__ import annotations

import io

from PIL import Image, ImageOps

# Si la imagen es casi cuadrada (diferencia de proporción menor que esto) se escala sin recortar ni rellenar.
NEAR_SQUARE = 0.03


def open_image(data: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(data))
    img.load()
    return img


def to_cover_png(data: bytes, size: int = 500, fit: str = "pad") -> bytes:
    """Convierte ``data`` en un PNG ``size``x``size``.

    ``fit``: ``pad`` (encaja la imagen entera y rellena con negro) o ``crop`` (recorte centrado).
    """
    img = open_image(data)
    img = ImageOps.exif_transpose(img)
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA" if "transparency" in img.info or img.mode in ("LA", "PA") else "RGB")
    if img.mode == "RGBA":
        background = Image.new("RGB", img.size, (0, 0, 0))
        background.paste(img, mask=img.getchannel("A"))
        img = background

    w, h = img.size
    if abs(w - h) / max(w, h) <= NEAR_SQUARE:
        out = img.resize((size, size), Image.LANCZOS)
    elif fit == "crop":
        out = ImageOps.fit(img, (size, size), Image.LANCZOS)
    else:
        img.thumbnail((size, size), Image.LANCZOS)
        out = Image.new("RGB", (size, size), (0, 0, 0))
        out.paste(img, ((size - img.width) // 2, (size - img.height) // 2))

    buf = io.BytesIO()
    out.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
