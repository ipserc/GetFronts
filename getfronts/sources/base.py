from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from getfronts.http import HttpClient


@dataclass
class Candidate:
    """Una posible carátula encontrada en una fuente."""

    source: str
    url: str
    artist: str
    album: str
    year: str | None = None
    width: int | None = None   # tamaño anunciado por la fuente (si lo da)
    height: int | None = None
    score: float = 0.0         # coincidencia con Artista/Álbum/Fecha, 0..1
    release_type: str | None = None  # "album", "single", "ep"… en minúsculas, si la fuente lo indica


class CoverSource(ABC):
    name: str = ""

    def __init__(self, http: HttpClient):
        self.http = http

    @abstractmethod
    def search(self, artist: str, album: str, year: str | None) -> list[Candidate]:
        """Busca carátulas candidatas. ``year`` puede ser ``None``."""
