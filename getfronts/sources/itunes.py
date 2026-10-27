"""API de búsqueda de iTunes (sin clave)."""

from __future__ import annotations

import re

from getfronts import VARIOUS_ARTISTS
from getfronts.sources.base import Candidate, CoverSource
from getfronts.textutil import extract_year

SEARCH_URL = "https://itunes.apple.com/search"
ARTWORK_SIZE = 1200


class ITunesSource(CoverSource):
    name = "itunes"

    def search(self, artist: str, album: str, year: str | None) -> list[Candidate]:
        term = album if artist == VARIOUS_ARTISTS else f"{artist} {album}"
        data = self.http.get_json(
            SEARCH_URL, {"term": term, "entity": "album", "media": "music", "limit": 15}
        )
        candidates = []
        for item in (data or {}).get("results", []):
            art = item.get("artworkUrl100")
            if not art:
                continue
            # La URL admite cualquier tamaño: .../100x100bb.jpg -> .../1200x1200bb.jpg
            url = re.sub(r"/\d+x\d+bb\.", f"/{ARTWORK_SIZE}x{ARTWORK_SIZE}bb.", art)
            candidates.append(
                Candidate(
                    source=self.name,
                    url=url,
                    artist=item.get("artistName", ""),
                    album=item.get("collectionName", ""),
                    year=extract_year(item.get("releaseDate")),
                    width=ARTWORK_SIZE,
                    height=ARTWORK_SIZE,
                )
            )
        return candidates
