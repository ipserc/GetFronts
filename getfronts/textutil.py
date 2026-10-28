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
_DISC_WORDS = r"(?:cd|disc|disk|disco|disque|dvd)"
# Marcas de disco dentro de un título: "(CD 2)", "[Disc 1 of 2]", "(Disco 1 - Bonus)", "- CD2"...
_DISC_MARK_RE = re.compile(
    rf"\s*[\(\[]\s*{_DISC_WORDS}\s*\.?\s*\d{{1,2}}(?!\d)[^\)\]]*[\)\]]"
    rf"|\s*[-–:,]?\s+{_DISC_WORDS}\s*\.?\s*\d{{1,2}}(?:\s*(?:of|de|/)\s*\d{{1,2}})?\s*$",
    re.IGNORECASE,
)
_BRACKETS_RE = re.compile(r"\s*[\(\[][^\)\]]*[\)\]]")
_QUOTES_TABLE = str.maketrans({"″": '"', "“": '"', "”": '"', "„": '"', "’": "'", "‘": "'", "´": "'", "`": "'"})
# Marcas de formato del archivo: "(FLAC)", "[mp3 320]", "(Flac 24bit-96kHz)", "{OGG}"...
_AUDIO_FORMATS = {"flac", "ogg", "vorbis", "mp3", "m4a", "aac", "alac", "opus", "wma", "wav",
                  "aif", "aiff", "ape", "wv", "dsd"}
_FORMAT_EXTRAS_RE = re.compile(r"\d+(?:[.,]\d+)?(?:bits?|khz|kbps|k)?|bits?|khz|kbps|hi|res|lossless|cbr|vbr|v[02]",
                               re.IGNORECASE)
_BRACKET_GROUP_RE = re.compile(r"\s*[\(\[\{]([^\(\)\[\]\{\}]*)[\)\]\}]")
_SUBTITLE_SEP_RE = re.compile(r"\s*:\s+|\s+[-–—]\s+")
SUBTITLE_PENALTY = 0.9  # una coincidencia sólo del título principal vale algo menos que una exacta
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


def _is_format_mark(content: str) -> bool:
    """``True`` si lo que hay entre paréntesis sólo describe el formato: "FLAC", "MP3 320"..."""
    tokens = [t for t in re.split(r"[\s,/+_\-]+", content.casefold()) if t]
    return (any(t in _AUDIO_FORMATS for t in tokens)
            and all(t in _AUDIO_FORMATS or _FORMAT_EXTRAS_RE.fullmatch(t) for t in tokens))


def clean_album_title(album: str) -> str:
    """Quita las marcas de disco y de formato: "Liebe ist für alle da (CD 2) (FLAC)" -> "Liebe ist für alle da"."""
    cleaned = _BRACKET_GROUP_RE.sub(lambda m: "" if _is_format_mark(m.group(1)) else m.group(0), album)
    cleaned = _DISC_MARK_RE.sub("", cleaned.strip()).strip(" -–:,")
    return cleaned or album


def query_title(value: str) -> str:
    """Comillas tipográficas o dobladas a su forma simple para las búsquedas.

    MusicBrainz no encuentra ``12'' 80s Grooves`` pero sí ``12" 80s Grooves``.
    """
    value = value.replace("''", '"')
    return value.translate(_QUOTES_TABLE)


def strip_brackets(value: str) -> str:
    """Quita todo lo que vaya entre paréntesis o corchetes: "Album (Deluxe Edition)" -> "Album"."""
    stripped = _BRACKETS_RE.sub("", value).strip(" -–:,")
    return stripped or value


def main_title(value: str) -> str:
    """Título sin subtítulo: "The Best of Everything: The Definitive..." -> "The Best of Everything"."""
    head = _SUBTITLE_SEP_RE.split(value, maxsplit=1)[0].strip()
    return head or value


def title_similarity(ours: str, theirs: str) -> float:
    """Como ``similarity``, pero admite que uno de los dos títulos lleve subtítulo."""
    best = similarity(ours, theirs)
    for a, b in ((ours, main_title(theirs)), (main_title(ours), theirs)):
        if (a, b) != (ours, theirs):
            best = max(best, SUBTITLE_PENALTY * similarity(a, b))
    return best


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
