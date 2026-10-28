from getfronts.cli import expand_roots, main


def _tree(tmp_path):
    for name in ("Alaska y Dinarama", "Alaska y los Pegamoides", "Alaska y otros", "Amaral"):
        (tmp_path / name).mkdir()
    (tmp_path / "Alaska.txt").write_text("no es una carpeta")


def test_expand_roots_with_wildcard(tmp_path):
    _tree(tmp_path)
    roots, missing = expand_roots([str(tmp_path / "Alaska*")])
    assert [r.name for r in roots] == ["Alaska y Dinarama", "Alaska y los Pegamoides", "Alaska y otros"]
    assert missing == []


def test_expand_roots_dedupes_and_reports_missing(tmp_path):
    _tree(tmp_path)
    # La shell ya expandió una parte; se repite una carpeta y otra está dentro de la raíz.
    roots, missing = expand_roots([str(tmp_path / "Amaral"), str(tmp_path / "Am*"), str(tmp_path),
                                   str(tmp_path / "Zz*"), str(tmp_path / "no-existe")])
    assert roots == [tmp_path.resolve()]
    assert missing == [str(tmp_path / "Zz*"), str(tmp_path / "no-existe")]


def test_main_fails_when_pattern_matches_nothing(tmp_path, caplog):
    assert main([str(tmp_path / "Nada*"), "--no-ai", "--no-cache", "--report", str(tmp_path / "r.csv")]) == 2
    assert "no existe" in caplog.text
