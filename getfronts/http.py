"""Cliente HTTP compartido: User-Agent, reintentos, límite de peticiones por host y caché."""

from __future__ import annotations

import logging
import os
import time
from urllib.parse import urlencode, urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from getfronts import __version__
from getfronts.cache import JsonCache

log = logging.getLogger(__name__)

# MusicBrainz pide un User-Agent con un dato de contacto (email o URL): GETFRONTS_CONTACT.
USER_AGENT = f"GetFronts/{__version__} ( {os.environ.get('GETFRONTS_CONTACT', 'getfronts-cli')} )"

# Intervalo mínimo entre peticiones por host, en segundos.
# MusicBrainz exige como máximo 1 petición por segundo.
RATE_LIMITS = {
    "musicbrainz.org": 1.1,
    "coverartarchive.org": 0.2,
    "api.discogs.com": 1.0,
    "api.deezer.com": 0.15,
    "itunes.apple.com": 0.5,
}


class HttpClient:
    def __init__(self, cache: JsonCache, timeout: float = 20.0):
        self.cache = cache
        self.timeout = timeout
        self._last: dict[str, float] = {}
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        retry = Retry(
            total=3,
            backoff_factor=1.0,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET"}),
            respect_retry_after_header=True,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def _throttle(self, url: str) -> None:
        host = urlparse(url).hostname or ""
        interval = next((v for h, v in RATE_LIMITS.items() if host == h or host.endswith("." + h)), 0)
        if not interval:
            return
        wait = self._last.get(host, 0) + interval - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self._last[host] = time.monotonic()

    def get_json(self, url: str, params: dict | None = None, cache_key_params: dict | None = None):
        """GET que devuelve JSON (o ``None`` si 404). Usa la caché salvo para parámetros secretos.

        ``cache_key_params`` permite excluir de la clave de caché valores como tokens.
        """
        key_params = cache_key_params if cache_key_params is not None else params
        key = "GET " + url + ("?" + urlencode(sorted((key_params or {}).items())) if key_params else "")
        cached = self.cache.get(key)
        if cached is not None:
            log.debug("caché: %s", key)
            return cached.get("json")
        self._throttle(url)
        log.debug("GET %s %s", url, key_params or "")
        resp = self.session.get(url, params=params, timeout=self.timeout)
        if resp.status_code == 404:
            data = None
        else:
            resp.raise_for_status()
            data = resp.json()
        self.cache.set(key, {"json": data})
        return data

    def get_bytes(self, url: str, max_bytes: int = 40 * 1024 * 1024) -> bytes:
        """Descarga binaria (imágenes). No se guarda en caché."""
        self._throttle(url)
        log.debug("GET %s", url)
        with self.session.get(url, timeout=self.timeout, stream=True) as resp:
            resp.raise_for_status()
            chunks, size = [], 0
            for chunk in resp.iter_content(64 * 1024):
                size += len(chunk)
                if size > max_bytes:
                    raise ValueError(f"imagen demasiado grande (> {max_bytes} bytes): {url}")
                chunks.append(chunk)
        return b"".join(chunks)
