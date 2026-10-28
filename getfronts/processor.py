"""Procesado de una carpeta de pistas: identificar el álbum, buscar la carátula y guardarla."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from getfronts import UNKNOWN
from getfronts.ai import AlbumGuesser, guess_from_path
from getfronts.embed import embed_cover
from getfronts.finder import CoverFinder
from getfronts.imaging import to_cover_png
from getfronts.metadata import FolderInfo, analyze_folder, has_embedded_cover
from getfronts.textutil import canonical_artist, clean_album_title, cover_filename, extract_year

log = logging.getLogger(__name__)

# Estados posibles de una carpeta en el informe.
DOWNLOADED = "downloaded"
DRY_RUN = "dry_run"
EXISTS_SKIPPED = "exists_skipped"
UNKNOWN_SKIPPED = "unknown_skipped"
NOT_FOUND = "not_found"
ERROR = "error"

_COVER_STEMS = {"folder", "cover", "front", "albumart"}
_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}


@dataclass
class Options:
    root: Path
    size: int = 500
    fit: str = "pad"
    existing: str = "skip"      # skip | overwrite
    embed: bool = False
    dry_run: bool = False


@dataclass
class FolderResult:
    path: str
    artist: str = UNKNOWN
    album: str = UNKNOWN
    year: str = UNKNOWN
    data_source: str = ""       # tags, ai, path o combinaciones (tags+ai)
    status: str = ""
    cover_file: str = ""
    image_source: str = ""
    image_url: str = ""
    image_size: str = ""
    score: float | None = None
    embedded_tracks: int = 0
    message: str = ""
    tracks: int = field(default=0)


def find_existing_cover(folder: Path, tracks: list[Path]) -> str | None:
    """Describe la portada que ya tenga la carpeta (fichero o imagen incrustada), o ``None``."""
    for entry in sorted(folder.iterdir()):
        if not entry.is_file() or entry.suffix.lower() not in _IMAGE_EXTS:
            continue
        stem = entry.stem.lower()
        if stem in _COVER_STEMS or stem.endswith("_front"):
            return entry.name
    if tracks and has_embedded_cover(tracks[0]):
        return f"imagen incrustada en {tracks[0].name}"
    return None


def _fill_missing(info: FolderInfo, values: dict[str, str]) -> bool:
    """Completa los campos ``unknown`` de ``info`` con ``values``. Devuelve si aportó algo."""
    changed = False
    for key in ("artist", "album", "year"):
        value = (values.get(key) or "").strip()
        if key == "year":
            value = extract_year(value) or ""
        elif key == "artist":
            value = canonical_artist(value) if value else ""
        if value and value.lower() != UNKNOWN and getattr(info, key) == UNKNOWN:
            setattr(info, key, value)
            changed = True
    return changed


class FolderProcessor:
    def __init__(self, options: Options, guesser: AlbumGuesser, finder: CoverFinder):
        self.opt = options
        self.guesser = guesser
        self.finder = finder

    def identify(self, folder: Path, tracks: list[Path]) -> tuple[FolderInfo, str]:
        """Artista/Álbum/Fecha de la carpeta y de dónde salieron (tags, ai, path)."""
        info = analyze_folder(tracks)
        origins = ["tags"] if info.tracks_with_tags else []
        if not info.complete:
            known = {"artist": info.artist, "album": info.album, "year": info.year}
            guess = self.guesser.guess(folder, [t.name for t in tracks], known)
            if guess and _fill_missing(info, guess):
                origins.append("ai")
        if not info.complete and _fill_missing(info, guess_from_path(folder, self.opt.root)):
            origins.append("path")
        if info.album != UNKNOWN:
            info.album = clean_album_title(info.album)
        return info, "+".join(origins) or "none"

    def process(self, folder: Path, tracks: list[Path]) -> FolderResult:
        result = FolderResult(path=str(folder), tracks=len(tracks))
        try:
            self._process(folder, tracks, result)
        except Exception as exc:
            if log.isEnabledFor(logging.DEBUG):
                log.exception("Error procesando %s", folder)
            result.status = ERROR
            result.message = f"{type(exc).__name__}: {exc}"
        return result

    def _process(self, folder: Path, tracks: list[Path], result: FolderResult) -> None:
        info, origin = self.identify(folder, tracks)
        result.artist, result.album, result.year = info.artist, info.album, info.year
        result.data_source = origin

        if not info.searchable:
            result.status = UNKNOWN_SKIPPED
            result.message = "no se pudo identificar artista y álbum"
            return

        target = folder / cover_filename(info.artist, info.album, info.year)
        result.cover_file = target.name
        existing = find_existing_cover(folder, tracks)
        if existing and self.opt.existing == "skip":
            result.status = EXISTS_SKIPPED
            result.message = f"ya tiene portada: {existing}"
            return

        candidates = self.finder.find_candidates(info.artist, info.album, info.year)
        chosen = self.finder.choose(candidates, download=not self.opt.dry_run)
        if not chosen:
            result.status = NOT_FOUND
            result.message = "ninguna fuente devolvió una carátula que coincida"
            return

        c = chosen.candidate
        result.image_source, result.image_url, result.score = c.source, c.url, c.score
        if chosen.width and chosen.height:
            result.image_size = f"{chosen.width}x{chosen.height}"

        if self.opt.dry_run:
            result.status = DRY_RUN
            result.message = "simulación: no se ha descargado nada"
            return

        png = to_cover_png(chosen.data, self.opt.size, self.opt.fit)
        target.write_bytes(png)
        result.status = DOWNLOADED

        if self.opt.embed:
            replace = self.opt.existing == "overwrite"
            for track in tracks:
                try:
                    if embed_cover(track, png, replace=replace):
                        result.embedded_tracks += 1
                except Exception as exc:
                    log.warning("No se pudo incrustar la portada en %s: %s", track.name, exc)
