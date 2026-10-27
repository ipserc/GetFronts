"""MusicBrainz (búsqueda de release-groups) + Cover Art Archive (imágenes)."""

from __future__ import annotations

import logging

from getfronts import VARIOUS_ARTISTS
from getfronts.sources.base import Candidate, CoverSource
from getfronts.textutil import extract_year

log = logging.getLogger(__name__)

MB_URL = "https://musicbrainz.org/ws/2/release-group/"
CAA_URL = "https://coverartarchive.org/release-group/{mbid}"


def _quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


class MusicBrainzSource(CoverSource):
    name = "musicbrainz"
    max_groups = 4

    def search(self, artist: str, album: str, year: str | None) -> list[Candidate]:
        query = f"releasegroup:{_quote(album)}"
        if artist != VARIOUS_ARTISTS:
            query += f" AND artist:{_quote(artist)}"
        data = self.http.get_json(MB_URL, {"query": query, "fmt": "json", "limit": 10})
        groups = (data or {}).get("release-groups", [])
        # La puntuación de MusicBrainz ordena los resultados; nos quedamos con los mejores.
        groups = [g for g in groups if int(g.get("score", 0)) >= 70][: self.max_groups]

        candidates = []
        for group in groups:
            mbid = group.get("id")
            credit = "".join(
                c.get("name", "") + c.get("joinphrase", "") for c in group.get("artist-credit", [])
            )
            images = (self.http.get_json(CAA_URL.format(mbid=mbid)) or {}).get("images", [])
            front = next((i for i in images if i.get("front")), None)
            if not front:
                continue
            thumbs = front.get("thumbnails", {})
            # La miniatura de 1200 px sobra para 500x500 y evita descargar escaneos de decenas de MB.
            url = thumbs.get("1200") or front.get("image") or thumbs.get("large")
            size = 1200 if thumbs.get("1200") else None
            candidates.append(
                Candidate(
                    source=self.name,
                    url=url,
                    artist=credit or artist,
                    album=group.get("title", ""),
                    year=extract_year(group.get("first-release-date")),
                    width=size,
                    height=size,
                )
            )
        return candidates
