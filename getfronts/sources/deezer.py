"""API pública de Deezer (sin clave)."""

from __future__ import annotations

from getfronts import VARIOUS_ARTISTS
from getfronts.sources.base import Candidate, CoverSource

SEARCH_URL = "https://api.deezer.com/search/album"


def _quote(value: str) -> str:
    return '"' + value.replace('"', " ") + '"'


class DeezerSource(CoverSource):
    name = "deezer"

    def search(self, artist: str, album: str, year: str | None) -> list[Candidate]:
        query = f"album:{_quote(album)}"
        if artist != VARIOUS_ARTISTS:
            query = f"artist:{_quote(artist)} " + query
        data = self.http.get_json(SEARCH_URL, {"q": query, "limit": 15})
        candidates = []
        for item in (data or {}).get("data", []):
            url = item.get("cover_xl") or item.get("cover_big")
            if not url:
                continue
            size = 1000 if item.get("cover_xl") else 500
            candidates.append(
                Candidate(
                    source=self.name,
                    url=url,
                    artist=(item.get("artist") or {}).get("name", ""),
                    album=item.get("title", ""),
                    year=None,  # la búsqueda de Deezer no devuelve la fecha
                    width=size,
                    height=size,
                )
            )
        return candidates
