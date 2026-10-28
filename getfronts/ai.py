"""Identificación de Artista/Álbum/Fecha a partir de la ruta: Claude + heurística local."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from getfronts import UNKNOWN
from getfronts.cache import JsonCache
from getfronts.textutil import canonical_artist, extract_year

log = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-haiku-5-5"
PATH_DEPTH = 4          # componentes finales de la ruta que se envían a la IA
MAX_TRACK_NAMES = 30

_DISC_RE = re.compile(r"^(cd|disc|disk|disco|disque)\s*[-_ ]?\s*\d+\b", re.IGNORECASE)

SYSTEM_PROMPT = """You identify music albums from the folder path where their audio files are stored.
You get the last components of the path, some track file names and any values already known from tags.
Work out the album artist, the album title and the original release year.
- Folder names often follow patterns like "Artist/Album", "Artist - Album (Year)", "Year - Album" \
or end in a disc folder such as "CD1"; disc numbers are not part of the album title.
- Use your knowledge of real discographies to correct spelling and to supply the original \
release year when the artist and album are clear.
- For compilations of several artists use "Various Artists" as the artist.
- Keep the values already known from tags unless they are obviously wrong.
- Answer "unknown" for any field you cannot determine with reasonable confidence. Never invent albums.
- year must be four digits or "unknown"."""

SCHEMA = {
    "type": "object",
    "properties": {
        "artist": {"type": "string"},
        "album": {"type": "string"},
        "year": {"type": "string"},
    },
    "required": ["artist", "album", "year"],
    "additionalProperties": False,
}


def album_folder(folder: Path) -> Path:
    """Carpeta que da nombre al álbum (sube un nivel si es una carpeta CD1/Disc 2...)."""
    return folder.parent if _DISC_RE.match(folder.name) else folder


def guess_from_path(folder: Path, root: Path) -> dict[str, str]:
    """Heurística sin IA para nombres de carpeta habituales. Devuelve sólo lo que reconoce."""
    base = album_folder(folder)
    name = base.name.strip()
    try:
        depth = len(base.relative_to(root).parts)
    except ValueError:
        depth = 0
    parent = base.parent.name.strip() if depth >= 2 else ""

    patterns = [
        # Artista - Año - Álbum
        (r"^(?P<artist>.+?)\s+-\s+(?P<year>(?:19|20)\d\d)\s+-\s+(?P<album>.+)$", False),
        # Artista - Álbum (Año) / [Año]
        (r"^(?P<artist>.+?)\s+-\s+(?P<album>.+?)\s*[\(\[](?P<year>(?:19|20)\d\d)[\)\]]$", False),
        # Año - Álbum   (artista = carpeta padre); antes que "Artista - Álbum"
        (r"^[\(\[]?(?P<year>(?:19|20)\d\d)[\)\]]?(?:\s*[-.]\s*|\s+)(?P<album>.+)$", True),
        # Artista - Álbum
        (r"^(?P<artist>.+?)\s+-\s+(?P<album>.+)$", False),
        # Álbum (Año)   (artista = carpeta padre)
        (r"^(?P<album>.+?)\s*[\(\[](?P<year>(?:19|20)\d\d)[\)\]]$", True),
    ]
    for pattern, artist_from_parent in patterns:
        m = re.match(pattern, name)
        if not m:
            continue
        found = {k: v.strip() for k, v in m.groupdict().items() if v}
        if artist_from_parent and parent:
            found["artist"] = parent
        return found
    return {}


class AlbumGuesser:
    """Pregunta a Claude qué álbum corresponde a una carpeta. Se desactiva sola si no hay credenciales."""

    def __init__(self, cache: JsonCache, model: str = DEFAULT_MODEL, enabled: bool = True):
        self.cache = cache
        self.model = model
        self.enabled = enabled
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import anthropic
            except ImportError:
                log.warning("Paquete 'anthropic' no instalado: identificación por IA desactivada")
                self.enabled = False
                return None
            try:
                self._client = anthropic.Anthropic()
            except anthropic.AnthropicError as exc:
                log.warning("Sin credenciales de Anthropic (%s): identificación por IA desactivada", exc)
                self.enabled = False
                return None
        return self._client

    def guess(self, folder: Path, track_names: list[str], known: dict[str, str]) -> dict[str, str] | None:
        if not self.enabled:
            return None
        path_tail = "/".join(folder.parts[-PATH_DEPTH:])
        user = {
            "path": path_tail,
            "track_files": track_names[:MAX_TRACK_NAMES],
            "known_from_tags": {k: v for k, v in known.items() if v and v != UNKNOWN},
        }
        user_text = json.dumps(user, ensure_ascii=False, indent=1)
        cache_key = f"AI {self.model} {user_text}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            log.debug("caché IA: %s", path_tail)
            return cached

        client = self._get_client()
        if client is None:
            return None
        import anthropic

        try:
            response = client.messages.create(
                model=self.model,
                max_tokens=2048,
                system=SYSTEM_PROMPT,
                output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
                messages=[{"role": "user", "content": user_text}],
            )
        except anthropic.AuthenticationError as exc:
            log.warning("Credenciales de Anthropic rechazadas (%s): IA desactivada", exc)
            self.enabled = False
            return None
        except anthropic.APIStatusError as exc:
            log.warning("Error de la API de Anthropic (%s) en %s", exc.status_code, path_tail)
            return None
        except anthropic.APIConnectionError as exc:
            log.warning("Sin conexión con la API de Anthropic: %s", exc)
            return None

        if response.stop_reason in ("refusal", "max_tokens"):
            log.warning("La IA no respondió para %s (stop_reason=%s)", path_tail, response.stop_reason)
            return None
        text = next((b.text for b in response.content if b.type == "text"), "")
        try:
            data = json.loads(text)
        except ValueError:
            log.warning("Respuesta de la IA no válida para %s: %r", path_tail, text[:200])
            return None

        result = {
            "artist": canonical_artist(data.get("artist", "").strip()) or UNKNOWN,
            "album": data.get("album", "").strip() or UNKNOWN,
            "year": extract_year(data.get("year")) or UNKNOWN,
        }
        for key in ("artist", "album"):
            if result[key].lower() == UNKNOWN:
                result[key] = UNKNOWN
        log.debug("IA %s -> %s", path_tail, result)
        self.cache.set(cache_key, result)
        return result
