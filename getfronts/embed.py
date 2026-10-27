"""Incrustación de la carátula en las pistas de audio (opcional, ``--embed``)."""

from __future__ import annotations

import base64
import logging
from pathlib import Path

import mutagen
from mutagen.aiff import AIFF
from mutagen.flac import FLAC, Picture
from mutagen.id3 import APIC, ID3, PictureType
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4, MP4Cover
from mutagen.oggopus import OggOpus
from mutagen.oggvorbis import OggVorbis
from mutagen.wave import WAVE

log = logging.getLogger(__name__)


def _flac_picture(png: bytes) -> Picture:
    pic = Picture()
    pic.type = PictureType.COVER_FRONT
    pic.mime = "image/png"
    pic.desc = "Front"
    pic.data = png
    return pic


def embed_cover(path: Path, png: bytes, replace: bool) -> bool:
    """Incrusta ``png`` como portada. Si ``replace`` es falso no toca pistas que ya tengan imagen.

    Devuelve ``True`` si la pista se modificó.
    """
    audio = mutagen.File(path)
    if audio is None:
        return False

    if isinstance(audio, FLAC):
        if audio.pictures and not replace:
            return False
        audio.clear_pictures()
        audio.add_picture(_flac_picture(png))
    elif isinstance(audio, (MP3, WAVE, AIFF)):
        if audio.tags is None:
            audio.add_tags()
        tags: ID3 = audio.tags
        if tags.getall("APIC") and not replace:
            return False
        tags.delall("APIC")
        tags.add(APIC(encoding=3, mime="image/png", type=PictureType.COVER_FRONT, desc="Front", data=png))
    elif isinstance(audio, MP4):
        if audio.tags is None:
            audio.add_tags()
        if audio.tags.get("covr") and not replace:
            return False
        audio.tags["covr"] = [MP4Cover(png, imageformat=MP4Cover.FORMAT_PNG)]
    elif isinstance(audio, (OggVorbis, OggOpus)):
        if audio.get("metadata_block_picture") and not replace:
            return False
        encoded = base64.b64encode(_flac_picture(png).write()).decode("ascii")
        audio["metadata_block_picture"] = [encoded]
    else:
        log.info("Formato sin soporte para incrustar portada: %s", path.name)
        return False

    audio.save()
    return True
