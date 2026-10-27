"""Discogs (requiere token personal en DISCOGS_TOKEN)."""

from __future__ import annotations

from getfronts import VARIOUS_ARTISTS
from getfronts.http import HttpClient
from getfronts.sources.base import Candidate, CoverSource
from getfronts.textutil import extract_year

SEARCH_URL = "https://api.discogs.com/database/search"


class DiscogsSource(CoverSource):
    name = "discogs"

    def __init__(self, http: HttpClient, token: str):
        super().__init__(http)
        self.token = token

    def search(self, artist: str, album: str, year: str | None) -> list[Candidate]:
        params = {"release_title": album, "type": "master", "per_page": 10}
        if artist != VARIOUS_ARTISTS:
            params["artist"] = artist
        # El token no forma parte de la clave de caché.
        data = self.http.get_json(SEARCH_URL, {**params, "token": self.token}, cache_key_params=params)
        candidates = []
        for item in (data or {}).get("results", []):
            url = item.get("cover_image")
            if not url or url.endswith("spacer.gif"):
                continue
            # El título viene como "Artista - Álbum".
            title = item.get("title", "")
            found_artist, _, found_album = title.partition(" - ")
            candidates.append(
                Candidate(
                    source=self.name,
                    url=url,
                    artist=found_artist or artist,
                    album=found_album or title,
                    year=extract_year(str(item.get("year", ""))),
                )
            )
        return candidates
