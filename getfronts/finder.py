"""Búsqueda en todas las fuentes, puntuación de coincidencias y elección de la mejor imagen."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from getfronts import UNKNOWN, VARIOUS_ARTISTS
from getfronts.http import HttpClient
from getfronts.imaging import open_image
from getfronts.sources import Candidate, CoverSource
from getfronts.textutil import is_various_artists, similarity

log = logging.getLogger(__name__)

DOWNLOAD_TOP = 3        # candidatas que se descargan para comparar su resolución real
SCORE_WINDOW = 0.08     # sólo compiten por calidad las que están a esta distancia de la mejor puntuación


def score_candidate(c: Candidate, artist: str, album: str, year: str) -> float:
    """Coincidencia 0..1: 45 % artista, 45 % álbum, 10 % año."""
    if artist == VARIOUS_ARTISTS:
        artist_sim = 1.0 if is_various_artists(c.artist) else 0.7
    else:
        artist_sim = similarity(artist, c.artist)
    album_sim = similarity(album, c.album)
    if year == UNKNOWN or not c.year:
        year_sim = 0.5
    else:
        diff = abs(int(year) - int(c.year))
        year_sim = 1.0 if diff == 0 else 0.6 if diff <= 2 else 0.0
    return round(0.45 * artist_sim + 0.45 * album_sim + 0.10 * year_sim, 4)


@dataclass
class Chosen:
    candidate: Candidate
    data: bytes | None      # None en modo dry-run
    width: int | None
    height: int | None


class CoverFinder:
    def __init__(self, sources: list[CoverSource], http: HttpClient, min_score: float, target_size: int):
        self.sources = sources
        self.http = http
        self.min_score = min_score
        self.target_size = target_size

    def find_candidates(self, artist: str, album: str, year: str) -> list[Candidate]:
        found: list[Candidate] = []
        for source in self.sources:
            try:
                results = source.search(artist, album, None if year == UNKNOWN else year)
            except Exception as exc:  # una fuente caída no debe parar el proceso
                log.warning("Fuente %s falló para %s - %s: %s", source.name, artist, album, exc)
                continue
            for c in results:
                c.score = score_candidate(c, artist, album, year)
                log.debug("  %-11s %.3f  %s - %s (%s)", c.source, c.score, c.artist, c.album, c.year)
            found.extend(results)
        good = [c for c in found if c.score >= self.min_score]
        good.sort(key=lambda c: (c.score, c.width or 0), reverse=True)
        return good

    def choose(self, candidates: list[Candidate], download: bool = True) -> Chosen | None:
        """Entre las mejores coincidencias descarga hasta ``DOWNLOAD_TOP`` y elige la de más calidad."""
        if not candidates:
            return None
        best_score = candidates[0].score
        contenders = [c for c in candidates if best_score - c.score <= SCORE_WINDOW]
        if not download:
            c = contenders[0]
            return Chosen(c, None, c.width, c.height)

        downloaded: list[Chosen] = []
        for c in contenders:
            if len(downloaded) >= DOWNLOAD_TOP:
                break
            try:
                data = self.http.get_bytes(c.url)
                img = open_image(data)
            except Exception as exc:
                log.debug("Descarga fallida %s: %s", c.url, exc)
                continue
            downloaded.append(Chosen(c, data, img.width, img.height))
        if not downloaded:
            # Las mejores fallaron: se prueba con el resto de candidatas en orden.
            for c in candidates[len(contenders):]:
                try:
                    data = self.http.get_bytes(c.url)
                    img = open_image(data)
                except Exception as exc:
                    log.debug("Descarga fallida %s: %s", c.url, exc)
                    continue
                return Chosen(c, data, img.width, img.height)
            return None

        def quality(ch: Chosen) -> tuple:
            w, h = ch.width or 0, ch.height or 0
            short = min(w, h)
            squareness = short / max(w, h, 1)
            # Primero: alcanza el tamaño final; luego: cuadrada; luego: puntuación; luego: resolución.
            return (short >= self.target_size, round(squareness, 1), ch.candidate.score, short)

        return max(downloaded, key=quality)
