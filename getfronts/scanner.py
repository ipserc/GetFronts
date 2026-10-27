"""Recorrido del árbol de directorios en busca de carpetas con pistas de audio."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator

AUDIO_EXTENSIONS = {
    ".mp3", ".flac", ".m4a", ".aac", ".mp4", ".ogg", ".oga", ".opus",
    ".wma", ".wav", ".aif", ".aiff", ".aifc",
}


def is_audio_file(path: Path) -> bool:
    return path.suffix.lower() in AUDIO_EXTENSIONS and not path.name.startswith("._")


def find_audio_folders(root: Path) -> Iterator[tuple[Path, list[Path]]]:
    """Genera ``(carpeta, pistas)`` para cada carpeta que contenga ficheros de audio.

    El recorrido es ordenado para que la salida sea reproducible. Se ignoran
    las carpetas ocultas.
    """
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        folder = Path(dirpath)
        tracks = [folder / f for f in sorted(filenames) if is_audio_file(folder / f)]
        if tracks:
            yield folder, tracks
