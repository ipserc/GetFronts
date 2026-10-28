import pytest

from getfronts.textutil import (
    clean_album_title,
    cover_filename,
    extract_year,
    main_title,
    is_various_artists,
    sanitize_component,
    similarity,
    strip_brackets,
    title_similarity,
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


@pytest.mark.parametrize("title, expected", [
    ("Liebe ist für alle da (CD 2)", "Liebe ist für alle da"),
    ("The Wall [Disc 1]", "The Wall"),
    ("The Wall (Disc 1 of 2)", "The Wall"),
    ("Descanso dominical (Disco 2 - Bonus)", "Descanso dominical"),
    ("Mellon Collie - CD2", "Mellon Collie"),
    ("Mellon Collie, Disc 2/2", "Mellon Collie"),
    ("Live CD.1", "Live"),
    ("The Best of Everything CD2", "The Best of Everything"),
    ("Mutter (FLAC)", "Mutter"),
    ("Mutter (flac)", "Mutter"),
    ("Mutter [Mp3]", "Mutter"),
    ("Mutter {OGG}", "Mutter"),
    ("Mutter (FLAC 24bit-96kHz)", "Mutter"),
    ("Mutter (MP3 320 kbps)", "Mutter"),
    ("Mutter (FLAC/MP3)", "Mutter"),
    ("Liebe ist für alle da (CD 2) (Flac)", "Liebe ist für alle da"),
    ("Liebe ist für alle da (FLAC) - CD2", "Liebe ist für alle da"),
    # No son marcas de disco ni de formato:
    ("Rumours (Deluxe Edition) (FLAC)", "Rumours (Deluxe Edition)"),
    ("FLAC", "FLAC"),
    ("(OGG)", "(OGG)"),
    ("Live (2003)", "Live (2003)"),
    ("Disco Inferno", "Disco Inferno"),
    ("Discovery", "Discovery"),
    ("Live CD 1999", "Live CD 1999"),
    ("CD 2", "CD 2"),
    ("The Dark Side of the Moon (2011 Remaster)", "The Dark Side of the Moon (2011 Remaster)"),
])
def test_clean_album_title(title, expected):
    assert clean_album_title(title) == expected


def test_strip_brackets():
    assert strip_brackets("Rumours (Deluxe Edition) [Remastered]") == "Rumours"
    assert strip_brackets("(What's the Story) Morning Glory?") == "Morning Glory?"
    assert strip_brackets("(Untitled)") == "(Untitled)"


def test_main_title():
    assert main_title("The Best of Everything: The Definitive Career Spanning Hits Collection") == \
        "The Best of Everything"
    assert main_title("The Best Of Everything - The Definitive Collection") == "The Best Of Everything"
    assert main_title("Blink-182") == "Blink-182"          # guion sin espacios: no es subtítulo
    assert main_title("Sgt. Pepper's Lonely Hearts Club Band") == "Sgt. Pepper's Lonely Hearts Club Band"


def test_title_similarity_with_subtitles():
    long = "The Best of Everything: The Definitive Career Spanning Hits Collection 1976–2016"
    assert title_similarity("The Best of Everything", long) == 0.9
    assert title_similarity(long, "The Best of Everything") == 0.9
    assert title_similarity("Greatest Hits", "Greatest Hits") == 1.0
    assert title_similarity("Greatest Hits", "Greatest Hits: Volume 2") == 0.9
    assert title_similarity("Abbey Road", "Let It Be: Naked") < 0.6
