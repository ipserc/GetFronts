"""Last.fm (requiere clave en LASTFM_API_KEY)."""

from __future__ import annotations

from getfronts.http import HttpClient
from getfronts.sources.base import Candidate, CoverSource

API_URL = "https://ws.audioscrobbler.com/2.0/"


class LastFmSource(CoverSource):
    name = "lastfm"

    def __init__(self, http: HttpClient, api_key: str):
        super().__init__(http)
        self.api_key = api_key

    def search(self, artist: str, album: str, year: str | None) -> list[Candidate]:
        params = {"method": "album.getinfo", "artist": artist, "album": album, "format": "json"}
        data = self.http.get_json(API_URL, {**params, "api_key": self.api_key}, cache_key_params=params)
        info = (data or {}).get("album")
        if not info:
            return []
        images = {img.get("size"): img.get("#text") for img in info.get("image", [])}
        url = images.get("mega") or images.get("extralarge")
        if not url:
            return []
        # La URL ".../300x300/..." sin tamaño ("/_/") devuelve la imagen original.
        url = url.replace("/300x300/", "/_/")
        return [
            Candidate(
                source=self.name,
                url=url,
                artist=info.get("artist", artist),
                album=info.get("name", album),
            )
        ]
