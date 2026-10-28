import csv
import io
import json

import mutagen
import pytest
from PIL import Image

from conftest import FakeHttp, png_bytes
from getfronts.ai import AlbumGuesser
from getfronts.embed import embed_cover
from getfronts.finder import CoverFinder
from getfronts.metadata import has_embedded_cover
from getfronts.processor import FolderProcessor, Options
from getfronts.report import write_report
from getfronts.sources import Candidate, CoverSource

COVER_URL = "http://img/cover.jpg"


class FakeSource(CoverSource):
    name = "fake"

    def __init__(self):
        self.queries = []

    def search(self, artist, album, year):
        self.queries.append((artist, album, year))
        return [Candidate("fake", COVER_URL, artist, album, year)]


class FakeGuesser(AlbumGuesser):
    def __init__(self, answer=None):
        super().__init__(cache=None, enabled=answer is not None)
        self.answer = answer
        self.calls = 0

    def guess(self, folder, track_names, known):
        self.calls += 1
        return self.answer


def _tag(path, artist, album, date):
    audio = mutagen.File(path, easy=True)
    if audio.tags is None:
        audio.add_tags()
    audio.update({"artist": artist, "album": album, "date": date})
    audio.save()


def _processor(root, guesser=None, **opts):
    source = FakeSource()
    http = FakeHttp({COVER_URL: png_bytes(1000, 1000)})
    finder = CoverFinder([source], http, min_score=0.75, target_size=500)
    proc = FolderProcessor(Options(root=root, **opts), guesser or FakeGuesser(), finder)
    return proc, source, http


@pytest.fixture
def album(tmp_path, make_track):
    folder = tmp_path / "Rock" / "Dire Straits"
    tracks = [make_track(folder / f"{i:02} song.mp3") for i in range(1, 4)]
    for t in tracks:
        _tag(t, "Dire Straits", "Brothers in Arms", "1985")
    return folder, tracks


def test_downloads_png_with_expected_name(tmp_path, album):
    folder, tracks = album
    proc, source, _ = _processor(tmp_path)
    result = proc.process(folder, tracks)
    assert result.status == "downloaded", result.message
    assert result.data_source == "tags"
    target = folder / "Dire_Straits_Brothers_in_Arms_1985_Front.png"
    assert target.exists()
    img = Image.open(target)
    assert img.format == "PNG" and img.size == (500, 500)
    assert source.queries == [("Dire Straits", "Brothers in Arms", "1985")]


def test_existing_cover_is_skipped_by_default_and_overwritten_on_demand(tmp_path, album):
    folder, tracks = album
    (folder / "folder.jpg").write_bytes(png_bytes(100, 100))
    proc, source, _ = _processor(tmp_path)
    result = proc.process(folder, tracks)
    assert result.status == "exists_skipped" and "folder.jpg" in result.message
    assert source.queries == []

    proc, _, _ = _processor(tmp_path, existing="overwrite")
    assert proc.process(folder, tracks).status == "downloaded"


def test_dry_run_writes_nothing(tmp_path, album):
    folder, tracks = album
    proc, _, http = _processor(tmp_path, dry_run=True)
    result = proc.process(folder, tracks)
    assert result.status == "dry_run"
    assert result.cover_file == "Dire_Straits_Brothers_in_Arms_1985_Front.png"
    assert not list(folder.glob("*.png")) and http.downloaded == []


def test_untagged_folder_uses_ai_then_path(tmp_path, make_track):
    folder = tmp_path / "Sabina" / "19 dias y 500 noches (1999)"
    tracks = [make_track(folder / "01.mp3")]

    ai = FakeGuesser({"artist": "Joaquín Sabina", "album": "19 días y 500 noches", "year": "unknown"})
    proc, source, _ = _processor(tmp_path, guesser=ai)
    result = proc.process(folder, tracks)
    assert result.data_source == "ai+path"   # la IA no supo el año; lo aporta la ruta
    assert (result.artist, result.album, result.year) == ("Joaquín Sabina", "19 días y 500 noches", "1999")
    assert result.status == "downloaded"


def test_unknown_folder_is_reported_and_not_searched(tmp_path, make_track):
    folder = tmp_path / "misc"
    tracks = [make_track(folder / "track.mp3")]
    ai = FakeGuesser({"artist": "unknown", "album": "unknown", "year": "unknown"})
    proc, source, _ = _processor(tmp_path, guesser=ai)
    result = proc.process(folder, tracks)
    assert result.status == "unknown_skipped"
    assert (result.artist, result.album, result.year) == ("unknown", "unknown", "unknown")
    assert result.path == str(folder)
    assert source.queries == []


def test_embed_option(tmp_path, album):
    folder, tracks = album
    proc, _, _ = _processor(tmp_path, embed=True)
    result = proc.process(folder, tracks)
    assert result.embedded_tracks == 3
    assert all(has_embedded_cover(t) for t in tracks)
    # La carpeta ya tiene portada (incrustada y PNG): con "skip" no se vuelve a tocar.
    assert proc.process(folder, tracks).status == "exists_skipped"


@pytest.mark.parametrize("ext", [".mp3", ".flac", ".m4a", ".ogg", ".opus", ".wav", ".aiff"])
def test_embed_cover_formats(tmp_path, make_track, ext):
    track = make_track(tmp_path / f"t{ext}")
    png = png_bytes(50, 50, fmt="PNG")
    assert not has_embedded_cover(track)
    assert embed_cover(track, png, replace=False)
    assert has_embedded_cover(track)
    assert not embed_cover(track, png, replace=False)   # ya tenía imagen
    assert embed_cover(track, png, replace=True)


def test_report_csv_and_json(tmp_path, album):
    folder, tracks = album
    proc, _, _ = _processor(tmp_path, dry_run=True)
    results = [proc.process(folder, tracks)]
    write_report(results, tmp_path / "r.csv")
    write_report(results, tmp_path / "r.json")
    rows = list(csv.DictReader(io.StringIO((tmp_path / "r.csv").read_text())))
    assert rows[0]["path"] == str(folder) and rows[0]["artist"] == "Dire Straits"
    data = json.loads((tmp_path / "r.json").read_text())
    assert data[0]["status"] == "dry_run" and data[0]["year"] == "1985"


def test_disc_mark_removed_from_album(tmp_path, make_track):
    folder = tmp_path / "Rammstein" / "2009-Liebe ist für alle da (CD 2)"
    tracks = [make_track(folder / "01.mp3")]
    _tag(tracks[0], "Rammstein", "Liebe ist für alle da (CD 2)", "2009")
    proc, source, _ = _processor(tmp_path)
    result = proc.process(folder, tracks)
    assert source.queries == [("Rammstein", "Liebe ist für alle da", "2009")]
    assert result.album == "Liebe ist für alle da"
    assert result.cover_file == "Rammstein_Liebe_ist_für_alle_da_2009_Front.png"
    assert result.status == "downloaded"
