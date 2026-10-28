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
