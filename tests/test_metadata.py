import mutagen
import pytest
from mutagen.asf import ASF
from mutagen.id3 import ID3, TALB, TDRC, TPE1, TPE2

from getfronts.metadata import TrackTags, analyze_folder, read_track_tags, summarize_folder


def test_majority_vote():
    tracks = [
        TrackTags("Queen", None, "A Night at the Opera", "1975"),
        TrackTags("Queen", None, "A Night at the Opera", "1975"),
        TrackTags("Queen", None, "A night at the opera", "2011"),
        TrackTags("Queen & Bowie", None, "Bonus", "1975"),
    ]
    info = summarize_folder(tracks)
    assert (info.artist, info.album, info.year) == ("Queen", "A Night at the Opera", "1975")


def test_albumartist_preferred_over_artist():
    tracks = [TrackTags(f"Guest {i}", "Santana", "Supernatural", "1999") for i in range(5)]
    assert summarize_folder(tracks).artist == "Santana"


def test_compilation_becomes_various_artists():
    many = [TrackTags(f"Artist {i}", None, "Now 1", "1983") for i in range(6)]
    assert summarize_folder(many).artist == "Various Artists"
    flagged = [TrackTags("Madonna", None, "Hits", "1990", compilation=True)] * 3
    assert summarize_folder(flagged).artist == "Various Artists"
    va = [TrackTags("X", "VA", "Hits", "1990")]
    assert summarize_folder(va).artist == "Various Artists"


def test_no_tags_gives_unknown():
    info = summarize_folder([])
    assert (info.artist, info.album, info.year) == ("unknown", "unknown", "unknown")
    assert not info.searchable


def _tag_easy(path, artist, album, date, albumartist=None):
    audio = mutagen.File(path, easy=True)
    if audio.tags is None:
        audio.add_tags()
    audio["artist"] = artist
    audio["album"] = album
    audio["date"] = date
    if albumartist:
        audio["albumartist"] = albumartist
    audio.save()


@pytest.mark.parametrize("ext", [".mp3", ".flac", ".m4a", ".ogg", ".opus"])
def test_read_tags_easy_formats(tmp_path, make_track, ext):
    path = make_track(tmp_path / f"01{ext}")
    _tag_easy(path, "Radiohead", "OK Computer", "1997-05-21", albumartist="Radiohead")
    tags = read_track_tags(path)
    assert (tags.artist, tags.albumartist, tags.album, tags.year) == (
        "Radiohead", "Radiohead", "OK Computer", "1997")


@pytest.mark.parametrize("ext", [".wav", ".aiff"])
def test_read_tags_id3_in_wav_aiff(tmp_path, make_track, ext):
    path = make_track(tmp_path / f"01{ext}")
    audio = mutagen.File(path)
    audio.add_tags()
    audio.tags.add(TPE1(encoding=3, text="Daft Punk"))
    audio.tags.add(TPE2(encoding=3, text="Daft Punk"))
    audio.tags.add(TALB(encoding=3, text="Discovery"))
    audio.tags.add(TDRC(encoding=3, text="2001"))
    audio.save()
    tags = read_track_tags(path)
    assert (tags.artist, tags.album, tags.year) == ("Daft Punk", "Discovery", "2001")


def test_read_tags_wma(tmp_path, make_track):
    path = make_track(tmp_path / "01.wma")
    audio = ASF(path)
    audio["Author"] = "Mecano"
    audio["WM/AlbumTitle"] = "Descanso dominical"
    audio["WM/Year"] = "1988"
    audio.save()
    tags = read_track_tags(path)
    assert (tags.artist, tags.album, tags.year) == ("Mecano", "Descanso dominical", "1988")


def test_untagged_file_returns_none(tmp_path, make_track):
    assert read_track_tags(make_track(tmp_path / "x.mp3")) is None


def test_analyze_folder(tmp_path, make_track):
    paths = [make_track(tmp_path / f"{i:02}.mp3") for i in range(3)]
    for p in paths:
        _tag_easy(p, "Nirvana", "Nevermind", "1991")
    info = analyze_folder(paths)
    assert (info.artist, info.album, info.year) == ("Nirvana", "Nevermind", "1991")
    assert info.tracks_with_tags == 3
