"""Caché persistente en JSON para búsquedas en internet y respuestas de la IA."""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


def default_cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
    return Path(base) / "getfronts"


class JsonCache:
    """Diccionario clave -> valor con caducidad, guardado en un único fichero JSON.

    Con ``path=None`` la caché está desactivada: ``get`` nunca encuentra nada.
    """

    def __init__(self, path: Path | None, ttl_days: float = 30):
        self.path = path
        self.ttl = ttl_days * 86400
        self._data: dict[str, dict[str, Any]] = {}
        self._dirty = False
        if path and path.exists():
            try:
                self._data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                log.warning("Caché ilegible (%s), se empieza de cero: %s", path, exc)

    def get(self, key: str) -> Any | None:
        if not self.path:
            return None
        entry = self._data.get(key)
        if not entry or time.time() - entry.get("t", 0) > self.ttl:
            return None
        return entry.get("v")

    def set(self, key: str, value: Any) -> None:
        if not self.path:
            return
        self._data[key] = {"t": time.time(), "v": value}
        self._dirty = True

    def save(self) -> None:
        if not self.path or not self._dirty:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)
        self._dirty = False
