import json
from pathlib import Path
from types import SimpleNamespace

from getfronts.ai import AlbumGuesser, album_folder, guess_from_path
from getfronts.cache import JsonCache

ROOT = Path("/music")


def test_album_folder_skips_disc_subfolder():
    assert album_folder(Path("/music/Pink Floyd/The Wall/CD1")) == Path("/music/Pink Floyd/The Wall")
    assert album_folder(Path("/music/X/Disc 2")) == Path("/music/X")
    assert album_folder(Path("/music/X/Cdx")) == Path("/music/X/Cdx")


def test_guess_from_path_patterns():
    assert guess_from_path(Path("/music/Pink Floyd - 1979 - The Wall"), ROOT) == {
        "artist": "Pink Floyd", "year": "1979", "album": "The Wall"}
    assert guess_from_path(Path("/music/Queen - Jazz (1978)/CD2"), ROOT) == {
        "artist": "Queen", "album": "Jazz", "year": "1978"}
    assert guess_from_path(Path("/music/Supertramp/1979 - Breakfast in America"), ROOT) == {
        "artist": "Supertramp", "year": "1979", "album": "Breakfast in America"}
    assert guess_from_path(Path("/music/Mecano/Entre el cielo y el suelo (1986)"), ROOT) == {
        "artist": "Mecano", "album": "Entre el cielo y el suelo", "year": "1986"}
    # Sin carpeta padre dentro de la raíz no se puede deducir el artista.
    assert guess_from_path(Path("/music/1979 - Breakfast in America"), ROOT) == {
        "year": "1979", "album": "Breakfast in America"}
    assert guess_from_path(Path("/music/Misc"), ROOT) == {}


class FakeMessages:
    def __init__(self, payload, stop_reason="end_turn"):
        self.payload = payload
        self.stop_reason = stop_reason
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        block = SimpleNamespace(type="text", text=json.dumps(self.payload))
        return SimpleNamespace(content=[block], stop_reason=self.stop_reason)


def _guesser(tmp_path, payload, stop_reason="end_turn"):
    guesser = AlbumGuesser(JsonCache(tmp_path / "c.json"))
    messages = FakeMessages(payload, stop_reason)
    guesser._client = SimpleNamespace(messages=messages)
    return guesser, messages


def test_guesser_parses_structured_output_and_caches(tmp_path):
    guesser, messages = _guesser(tmp_path, {"artist": "Various", "album": "Now 5", "year": "1985-03"})
    folder = Path("/music/Recopilatorios/Now 5")
    result = guesser.guess(folder, ["01 track.mp3"], {"artist": "unknown"})
    assert result == {"artist": "Various Artists", "album": "Now 5", "year": "1985"}
    request = messages.calls[0]
    assert request["model"] == "claude-haiku-5-5"
    assert request["output_config"]["format"]["type"] == "json_schema"
    assert "Recopilatorios/Now 5" in request["messages"][0]["content"]
    # Segunda vez: sale de la caché, sin llamar a la API.
    assert guesser.guess(folder, ["01 track.mp3"], {"artist": "unknown"}) == result
    assert len(messages.calls) == 1


def test_guesser_unknown_and_refusal(tmp_path):
    guesser, _ = _guesser(tmp_path, {"artist": "Unknown", "album": "unknown", "year": "unknown"})
    assert guesser.guess(Path("/m/x"), [], {}) == {"artist": "unknown", "album": "unknown", "year": "unknown"}
    guesser, _ = _guesser(tmp_path / "b", {}, stop_reason="refusal")
    assert guesser.guess(Path("/m/y"), [], {}) is None


def test_guesser_disabled(tmp_path):
    guesser = AlbumGuesser(JsonCache(None), enabled=False)
    assert guesser.guess(Path("/m/x"), [], {}) is None
