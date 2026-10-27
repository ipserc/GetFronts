"""Lectura de metadatos de las pistas y votación por mayoría por carpeta."""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import mutagen

from getfronts import UNKNOWN, VARIOUS_ARTISTS
from getfronts.textutil import canonical_artist, extract_year, is_various_artists

log = logging.getLogger(__name__)

# Claves candidatas (en minúsculas) para cada campo, según el formato de etiquetas:
# Vorbis/FLAC/Opus, ID3 (MP3, WAV, AIFF), MP4 (m4a) y ASF (wma).
_ARTIST_KEYS = ("artist", "tpe1", "\xa9art", "author", "wm/author")
_ALBUMARTIST_KEYS = ("albumartist", "album artist", "album_artist", "tpe2", "aart", "wm/albumartist")
_ALBUM_KEYS = ("album", "talb", "\xa9alb", "wm/albumtitle")
_DATE_KEYS = (
    "originaldate", "originalyear", "tdor", "date", "year", "tdrc", "tyer",
    "\xa9day", "wm/originalreleaseyear", "wm/year",
)
_COMPILATION_KEYS = ("compilation", "tcmp", "cpil", "wm/iscompilation")
_PICTURE_KEYS = ("apic", "covr", "metadata_block_picture", "wm/picture")


@dataclass
class TrackTags:
    artist: str | None = None
    albumartist: str | None = None
    album: str | None = None
    year: str | None = None
    compilation: bool = False


@dataclass
class FolderInfo:
    artist: str = UNKNOWN
    album: str = UNKNOWN
    year: str = UNKNOWN
    tracks_with_tags: int = 0

    @property
    def complete(self) -> bool:
        return UNKNOWN not in (self.artist, self.album, self.year)

    @property
    def searchable(self) -> bool:
        """Se puede buscar la portada: la fecha sólo sirve para desempatar."""
        return self.artist != UNKNOWN and self.album != UNKNOWN


def _as_strings(value) -> list[str]:
    if hasattr(value, "text"):  # tramas ID3
        value = value.text
    if not isinstance(value, (list, tuple)):
        value = [value]
    out = []
    for item in value:
        if hasattr(item, "value"):  # ASFValue
            item = item.value
        if isinstance(item, bytes):
            continue
        text = str(item).strip()
        if text:
            out.append(text)
    return out


def _flatten_tags(tags) -> dict[str, list[str]]:
    flat: dict[str, list[str]] = {}
    for key in tags.keys():
        try:
            values = _as_strings(tags[key])
        except Exception:  # etiquetas binarias o corruptas
            continue
        # En ID3 las claves llevan sufijo (p. ej. "TXXX:ALBUMARTIST", "APIC:Cover").
        k = str(key).lower()
        if k.startswith("txxx:"):
            k = k[5:]
        elif ":" in k and not k.startswith("wm/"):
            k = k.split(":", 1)[0]
        flat.setdefault(k, []).extend(values)
    return flat


def _first(flat: dict[str, list[str]], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        for value in flat.get(key, ()):
            if value:
                return value
    return None


def read_track_tags(path: Path) -> TrackTags | None:
    """Lee Artista, Artista del álbum, Álbum, Año y marca de recopilatorio de una pista."""
    try:
        audio = mutagen.File(path)
    except Exception as exc:
        log.debug("No se pudo leer %s: %s", path, exc)
        return None
    if audio is None or not audio.tags:
        return None
    flat = _flatten_tags(audio.tags)
    year = None
    for key in _DATE_KEYS:
        for value in flat.get(key, ()):
            year = extract_year(value)
            if year:
                break
        if year:
            break
    compilation = (_first(flat, _COMPILATION_KEYS) or "").lower() in ("1", "true", "yes")
    tags = TrackTags(
        artist=_first(flat, _ARTIST_KEYS),
        albumartist=_first(flat, _ALBUMARTIST_KEYS),
        album=_first(flat, _ALBUM_KEYS),
        year=year,
        compilation=compilation,
    )
    if not any((tags.artist, tags.albumartist, tags.album, tags.year)):
        return None
    return tags


def has_embedded_cover(path: Path) -> bool:
    """Indica si la pista lleva una imagen incrustada."""
    try:
        audio = mutagen.File(path)
    except Exception:
        return False
    if audio is None:
        return False
    if getattr(audio, "pictures", None):  # FLAC
        return True
    if not audio.tags:
        return False
    for key in audio.tags.keys():
        k = str(key).lower()
        if k.split(":", 1)[0] in _PICTURE_KEYS or k in _PICTURE_KEYS:
            return True
    return False


def _most_common(values: list[str]) -> str | None:
    """Valor más frecuente; agrupa sin distinguir mayúsculas y conserva la grafía más usada."""
    if not values:
        return None
    groups: dict[str, Counter] = {}
    for v in values:
        groups.setdefault(v.casefold(), Counter())[v] += 1
    best = max(groups.values(), key=lambda c: sum(c.values()))  # max() respeta el primer empate
    return best.most_common(1)[0][0]


def summarize_folder(tracks: list[TrackTags]) -> FolderInfo:
    """Combina las etiquetas de las pistas de una carpeta quedándose con los valores mayoritarios."""
    info = FolderInfo(tracks_with_tags=len(tracks))
    if not tracks:
        return info

    album = _most_common([t.album for t in tracks if t.album])
    year = _most_common([t.year for t in tracks if t.year])

    albumartists = [t.albumartist for t in tracks if t.albumartist]
    artists = [t.artist for t in tracks if t.artist]
    compilation_votes = sum(t.compilation for t in tracks)

    artist: str | None
    if albumartists:
        artist = canonical_artist(_most_common(albumartists))
    elif compilation_votes * 2 > len(tracks):
        artist = VARIOUS_ARTISTS
    elif artists:
        top = _most_common(artists)
        share = sum(1 for a in artists if a.casefold() == top.casefold()) / len(artists)
        # Muchos artistas distintos y ninguno dominante => recopilatorio.
        if share < 0.5 and len({a.casefold() for a in artists}) > 2:
            artist = VARIOUS_ARTISTS
        else:
            artist = canonical_artist(top)
    else:
        artist = None

    info.artist = artist or UNKNOWN
    info.album = album or UNKNOWN
    info.year = year or UNKNOWN
    if is_various_artists(info.artist):
        info.artist = VARIOUS_ARTISTS
    return info


def analyze_folder(track_paths: list[Path]) -> FolderInfo:
    tags = [t for t in (read_track_tags(p) for p in track_paths) if t]
    return summarize_folder(tags)
