import io

from PIL import Image

from conftest import FakeHttp, png_bytes
from getfronts.finder import CoverFinder, score_candidate
from getfronts.imaging import to_cover_png
from getfronts.sources import Candidate, CoverSource


def test_score_candidate():
    exact = Candidate("x", "u", "Pink Floyd", "The Wall", "1979")
    assert score_candidate(exact, "Pink Floyd", "The Wall", "1979") == 1.0
    wrong = Candidate("x", "u", "Pink Floyd", "Animals", "1977")
    assert score_candidate(wrong, "Pink Floyd", "The Wall", "1979") < 0.75
    no_year = Candidate("x", "u", "Pink Floyd", "The Wall", None)
    assert score_candidate(no_year, "Pink Floyd", "The Wall", "unknown") == 0.95


class StaticSource(CoverSource):
    def __init__(self, name, results):
        self.name = name
        self.results = results

    def search(self, artist, album, year):
        return list(self.results)


class BrokenSource(CoverSource):
    name = "broken"

    def __init__(self):
        pass

    def search(self, artist, album, year):
        raise RuntimeError("down")


def test_finder_prefers_larger_image_among_good_matches():
    small = Candidate("a", "http://a/small", "Muse", "Absolution", "2003")
    big = Candidate("b", "http://b/big", "Muse", "Absolution", "2003")
    bad = Candidate("c", "http://c/bad", "Muse", "Drones", "2015")
    http = FakeHttp({"http://a/small": png_bytes(300, 300), "http://b/big": png_bytes(1200, 1200)})
    finder = CoverFinder([BrokenSource(), StaticSource("a", [small]), StaticSource("b", [big, bad])],
                         http, min_score=0.75, target_size=500)
    candidates = finder.find_candidates("Muse", "Absolution", "2003")
    assert [c.url for c in candidates] == ["http://a/small", "http://b/big"]
    chosen = finder.choose(candidates)
    assert chosen.candidate.url == "http://b/big" and (chosen.width, chosen.height) == (1200, 1200)


def test_finder_falls_back_when_download_fails_and_dry_run_skips_download():
    ok = Candidate("a", "http://ok", "Muse", "Absolution", None)
    missing = Candidate("b", "http://missing", "Muse", "Absolution", "2003")
    http = FakeHttp({"http://ok": png_bytes(600, 600)})
    finder = CoverFinder([StaticSource("s", [missing, ok])], http, 0.75, 500)
    candidates = finder.find_candidates("Muse", "Absolution", "2003")
    assert finder.choose(candidates).candidate.url == "http://ok"

    http.downloaded.clear()
    dry = finder.choose(candidates, download=False)
    assert dry.data is None and http.downloaded == []


def _open(png):
    img = Image.open(io.BytesIO(png))
    return img.format, img.size, img


def test_to_cover_png_square_and_pad_and_crop():
    fmt, size, _ = _open(to_cover_png(png_bytes(1200, 1190), 500))
    assert (fmt, size) == ("PNG", (500, 500))

    _, size, img = _open(to_cover_png(png_bytes(1000, 500), 500, fit="pad"))
    assert size == (500, 500)
    assert img.getpixel((250, 10)) == (0, 0, 0)        # franja de relleno
    assert img.getpixel((250, 250))[0] > 150           # imagen original

    _, size, img = _open(to_cover_png(png_bytes(1000, 500), 500, fit="crop"))
    assert size == (500, 500) and img.getpixel((250, 10))[0] > 150


def test_to_cover_png_handles_transparency_and_cmyk():
    buf = io.BytesIO()
    Image.new("RGBA", (400, 400), (0, 255, 0, 128)).save(buf, format="PNG")
    assert _open(to_cover_png(buf.getvalue(), 500))[1] == (500, 500)
    buf = io.BytesIO()
    Image.new("CMYK", (400, 400)).save(buf, format="JPEG")
    assert _open(to_cover_png(buf.getvalue(), 500))[1] == (500, 500)


class QuerySensitiveSource(CoverSource):
    """Sólo encuentra el álbum si la consulta no lleva paréntesis."""
    name = "qs"

    def __init__(self):
        self.queries = []

    def search(self, artist, album, year):
        self.queries.append(album)
        if "(" in album:
            return []
        return [Candidate("qs", "http://x", artist, "Rumours (Deluxe Edition)", year)]


def test_finder_retries_without_brackets():
    source = QuerySensitiveSource()
    finder = CoverFinder([source], FakeHttp(), 0.75, 500)
    candidates = finder.find_candidates("Fleetwood Mac", "Rumours (Deluxe Edition)", "1977")
    assert source.queries == ["Rumours (Deluxe Edition)", "Rumours"]
    assert len(candidates) == 1 and candidates[0].score == 1.0


def test_subtitled_title_is_accepted_but_exact_title_wins():
    long = Candidate("a", "http://long", "Tom Petty & The Heartbreakers",
                     "The Best of Everything: The Definitive Career Spanning Hits Collection 1976–2016", "2019")
    assert score_candidate(long, "Tom Petty and the Heartbreakers", "The Best of Everything", "2019") >= 0.75

    exact = Candidate("a", "http://v1", "Queen", "Greatest Hits", "1981")
    vol2 = Candidate("a", "http://v2", "Queen", "Greatest Hits: Volume II", "1981")
    assert score_candidate(exact, "Queen", "Greatest Hits", "1981") > score_candidate(vol2, "Queen", "Greatest Hits", "1981")


def test_single_with_same_title_loses_to_album():
    # Rammstein - Zeit (2022): el sencillo y el álbum se llaman igual y salen el mismo año.
    single = Candidate("a", "http://single", "Rammstein", "Zeit", "2022", release_type="single")
    album = Candidate("a", "http://album", "Rammstein", "Zeit", "2022", release_type="album")
    assert score_candidate(single, "Rammstein", "Zeit", "2022", tracks=11) == 0.9
    assert score_candidate(album, "Rammstein", "Zeit", "2022", tracks=11) == 1.0
    # Una carpeta corta puede ser el propio sencillo: no se penaliza.
    assert score_candidate(single, "Rammstein", "Zeit", "2022", tracks=3) == 1.0

    http = FakeHttp({"http://single": png_bytes(1200, 1200), "http://album": png_bytes(1200, 1200)})
    finder = CoverFinder([StaticSource("a", [single, album])], http, 0.75, 500)
    candidates = finder.find_candidates("Rammstein", "Zeit", "2022", tracks=11)
    assert finder.choose(candidates).candidate.url == "http://album"
    # Si sólo existe el sencillo, se sigue aceptando.
    finder = CoverFinder([StaticSource("a", [single])], http, 0.75, 500)
    assert finder.choose(finder.find_candidates("Rammstein", "Zeit", "2022", tracks=11)).candidate.url == "http://single"


class JsonHttp:
    def __init__(self, data):
        self.data = data

    def get_json(self, url, params=None, **kwargs):
        return self.data


def test_sources_report_release_type():
    from getfronts.sources.deezer import DeezerSource
    from getfronts.sources.itunes import ITunesSource

    itunes = ITunesSource(JsonHttp({"results": [
        {"artworkUrl100": "http://i/100x100bb.jpg", "artistName": "Rammstein",
         "collectionName": "Zeit - Single", "releaseDate": "2022-03-10T08:00:00Z"},
        {"artworkUrl100": "http://i/100x100bb.jpg", "artistName": "Rammstein",
         "collectionName": "Zeit", "releaseDate": "2022-04-29T07:00:00Z"},
    ]}))
    found = itunes.search("Rammstein", "Zeit", "2022")
    assert [(c.album, c.release_type) for c in found] == [("Zeit", "single"), ("Zeit", "album")]

    deezer = DeezerSource(JsonHttp({"data": [
        {"cover_xl": "http://d/xl.jpg", "artist": {"name": "Rammstein"}, "title": "Zeit",
         "record_type": "single"},
    ]}))
    assert deezer.search("Rammstein", "Zeit", "2022")[0].release_type == "single"
