"""Fuentes de carátulas en internet."""

from __future__ import annotations

import logging
import os

from getfronts.http import HttpClient
from getfronts.sources.base import Candidate, CoverSource
from getfronts.sources.deezer import DeezerSource
from getfronts.sources.discogs import DiscogsSource
from getfronts.sources.itunes import ITunesSource
from getfronts.sources.lastfm import LastFmSource
from getfronts.sources.musicbrainz import MusicBrainzSource

log = logging.getLogger(__name__)

ALL_SOURCES = ("musicbrainz", "itunes", "deezer", "discogs", "lastfm")
DEFAULT_SOURCES = ALL_SOURCES

__all__ = ["Candidate", "CoverSource", "ALL_SOURCES", "DEFAULT_SOURCES", "build_sources"]


def build_sources(names: list[str], http: HttpClient) -> list[CoverSource]:
    """Instancia las fuentes pedidas. Discogs y Last.fm sólo si hay clave en el entorno."""
    sources: list[CoverSource] = []
    for name in names:
        if name == "musicbrainz":
            sources.append(MusicBrainzSource(http))
        elif name == "itunes":
            sources.append(ITunesSource(http))
        elif name == "deezer":
            sources.append(DeezerSource(http))
        elif name == "discogs":
            token = os.environ.get("DISCOGS_TOKEN")
            if token:
                sources.append(DiscogsSource(http, token))
            else:
                log.debug("Discogs desactivado: falta DISCOGS_TOKEN")
        elif name == "lastfm":
            key = os.environ.get("LASTFM_API_KEY")
            if key:
                sources.append(LastFmSource(http, key))
            else:
                log.debug("Last.fm desactivado: falta LASTFM_API_KEY")
        else:
            raise ValueError(f"fuente desconocida: {name}")
    return sources
