"""Utilidades de texto: normalización, similitud, años y nombres de archivo."""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

from getfronts import UNKNOWN, VARIOUS_ARTISTS

_YEAR_RE = re.compile(r"(?<!\d)(1[89]\d\d|20\d\d)(?!\d)")
_INVALID_FS_CHARS = re.compile(r'[/\\:*?"<>|\x00-\x1f]')
# Sufijos de edición que no deben penalizar la comparación de títulos.
_EDITION_RE = re.compile(
    r"[\(\[][^\)\]]*(remaster|deluxe|edition|expanded|anniversary|bonus|mono|stereo|version|"
    r"reissue|disc|cd\s*\d)[^\)\]]*[\)\]]",
    re.IGNORECASE,
)
_VA_NAMES = {"various artists", "various", "va", "v a", "varios artistas", "varios", "artistes divers"}


def extract_year(value: str | None) -> str | None:
    """Devuelve el primer año plausible (1800-2099) que aparezca en ``value``."""
    if not value:
        return None
    m = _YEAR_RE.search(str(value))
    return m.group(1) if m else None


def normalize(value: str) -> str:
    """Minúsculas, sin acentos, sin sufijos de edición ni puntuación."""
    value = _EDITION_RE.sub(" ", value)
    value = unicodedata.normalize("NFKD", value)
    value = "".join(c for c in value if not unicodedata.combining(c))
    value = value.casefold().replace("&", " and ")
    value = re.sub(r"^the\s+", "", value.strip())
    value = re.sub(r"[^\w\s]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def similarity(a: str, b: str) -> float:
    """Similitud 0..1 entre dos cadenas tras normalizarlas."""
    na, nb = normalize(a), normalize(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    return SequenceMatcher(None, na, nb).ratio()


def is_various_artists(value: str | None) -> bool:
    return bool(value) and normalize(value) in _VA_NAMES


def canonical_artist(value: str) -> str:
    return VARIOUS_ARTISTS if is_various_artists(value) else value


def sanitize_component(value: str) -> str:
    """Limpia un fragmento del nombre de archivo: sin caracteres inválidos y espacios -> '_'."""
    value = _INVALID_FS_CHARS.sub("", value or "")
    value = re.sub(r"\s+", "_", value.strip())
    value = re.sub(r"_+", "_", value).strip("._")
    return value or UNKNOWN


def cover_filename(artist: str, album: str, year: str, max_len: int = 200) -> str:
    """Nombre ``Artista_Album_Fecha_Front.png`` saneado y con longitud acotada."""
    suffix = "_Front.png"
    parts = [sanitize_component(artist), sanitize_component(album), sanitize_component(year)]
    name = "_".join(parts)
    budget = max_len - len(suffix.encode("utf-8"))
    while len(name.encode("utf-8")) > budget:
        name = name[:-1]
    return name.rstrip("._") + suffix
