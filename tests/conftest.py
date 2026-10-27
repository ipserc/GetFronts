from __future__ import annotations

import io
import shutil
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from getfronts.cache import JsonCache

FFMPEG_CODECS = {
    ".mp3": ["-c:a", "libmp3lame"],
    ".flac": ["-c:a", "flac"],
    ".m4a": ["-c:a", "aac"],
    ".ogg": ["-c:a", "libvorbis"],
    ".opus": ["-c:a", "libopus"],
    ".wma": ["-c:a", "wmav2"],
    ".wav": ["-c:a", "pcm_s16le"],
    ".aiff": ["-c:a", "pcm_s16be"],
}


@pytest.fixture(scope="session")
def audio_templates(tmp_path_factory) -> dict[str, Path]:
    """Un fichero de audio sin etiquetas (0,2 s de silencio) por cada formato."""
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg no disponible")
    base = tmp_path_factory.mktemp("templates")
    out = {}
    for ext, codec in FFMPEG_CODECS.items():
        path = base / f"silence{ext}"
        cmd = ["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
               "-t", "0.2", *codec, "-map_metadata", "-1", str(path)]
        if subprocess.run(cmd).returncode == 0:
            out[ext] = path
    return out


@pytest.fixture
def make_track(audio_templates):
    """Copia una plantilla de audio a ``dest`` (la extensión decide el formato)."""
    def _make(dest: Path) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(audio_templates[dest.suffix], dest)
        return dest
    return _make


def png_bytes(width: int, height: int, color=(200, 30, 30), fmt="JPEG") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buf, format=fmt)
    return buf.getvalue()


@pytest.fixture
def no_cache() -> JsonCache:
    return JsonCache(None)


class FakeHttp:
    """Sustituye a HttpClient: sirve imágenes desde un diccionario url -> bytes."""

    def __init__(self, images: dict[str, bytes] | None = None):
        self.images = images or {}
        self.downloaded: list[str] = []

    def get_bytes(self, url: str) -> bytes:
        self.downloaded.append(url)
        if url not in self.images:
            raise OSError("404")
        return self.images[url]
