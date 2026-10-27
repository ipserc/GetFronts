from getfronts.textutil import (
    cover_filename,
    extract_year,
    is_various_artists,
    sanitize_component,
    similarity,
)


def test_extract_year():
    assert extract_year("1975-11-21") == "1975"
    assert extract_year("2003") == "2003"
    assert extract_year("Remastered 12345") is None
    assert extract_year(None) is None


def test_sanitize_component_removes_invalid_chars_and_spaces():
    assert sanitize_component('AC/DC: "Live" <1992>?') == "ACDC_Live_1992"
    assert sanitize_component("  Pink   Floyd ") == "Pink_Floyd"
    assert sanitize_component("???") == "unknown"


def test_cover_filename():
    assert cover_filename("Pink Floyd", "The Wall", "1979") == "Pink_Floyd_The_Wall_1979_Front.png"
    assert cover_filename("Björk", "Homogenic", "unknown") == "Björk_Homogenic_unknown_Front.png"
    long_name = cover_filename("A" * 300, "B" * 300, "2000")
    assert long_name.endswith("_Front.png") and len(long_name.encode()) <= 200


def test_similarity_ignores_case_accents_and_edition_suffixes():
    assert similarity("The Dark Side of the Moon", "Dark Side Of The Moon (2011 Remaster)") == 1.0
    assert similarity("Héroes del Silencio", "heroes del silencio") == 1.0
    assert similarity("Abbey Road", "Let It Be") < 0.6


def test_various_artists_variants():
    assert is_various_artists("Various Artists")
    assert is_various_artists("VA")
    assert is_various_artists("Varios Artistas")
    assert not is_various_artists("Vangelis")
