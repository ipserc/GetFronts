from getfronts.cli import expand_roots, main


def _tree(tmp_path):
    for name in ("Alaska y Dinarama", "Alaska y los Pegamoides", "Alaska y otros", "Amaral"):
        (tmp_path / name).mkdir()
    (tmp_path / "Alaska.txt").write_text("no es una carpeta")


def test_expand_roots_with_wildcard(tmp_path):
    _tree(tmp_path)
    roots, missing, not_dirs = expand_roots([str(tmp_path / "Alaska*")])
    assert [r.name for r in roots] == ["Alaska y Dinarama", "Alaska y los Pegamoides", "Alaska y otros"]
    assert missing == [] and not_dirs == []


def test_expand_roots_dedupes_and_reports_missing(tmp_path):
    _tree(tmp_path)
    # La shell ya expandió una parte; se repite una carpeta y otra está dentro de la raíz.
    roots, missing, _ = expand_roots([str(tmp_path / "Amaral"), str(tmp_path / "Am*"), str(tmp_path),
                                   str(tmp_path / "Zz*"), str(tmp_path / "no-existe")])
    assert roots == [tmp_path.resolve()]
    assert missing == [str(tmp_path / "Zz*"), str(tmp_path / "no-existe")]


def test_expand_roots_ignores_files_expanded_by_the_shell(tmp_path):
    # `getfronts M*` sin comillas: la shell pasa también los ficheros (Max Richter.7z).
    _tree(tmp_path)
    roots, missing, not_dirs = expand_roots([str(tmp_path / "Alaska y otros"), str(tmp_path / "Alaska.txt")])
    assert [r.name for r in roots] == ["Alaska y otros"]
    assert missing == [] and not_dirs == [str(tmp_path / "Alaska.txt")]


def test_main_skips_files_and_processes_folders(tmp_path, caplog):
    _tree(tmp_path)
    code = main([str(tmp_path / "Amaral"), str(tmp_path / "Alaska.txt"), "--dry-run", "--no-ai", "--no-cache",
                 "--report", str(tmp_path / "r.csv")])
    assert code == 0
    assert "Se ignora porque no es una carpeta" in caplog.text


def test_main_fails_when_pattern_matches_nothing(tmp_path, caplog):
    assert main([str(tmp_path / "Nada*"), "--no-ai", "--no-cache", "--report", str(tmp_path / "r.csv")]) == 2
    assert "no existe" in caplog.text


def _output(capsys, *argv):
    import pytest
    with pytest.raises(SystemExit):
        main(list(argv))
    return capsys.readouterr().out


def test_help_in_english_and_ayuda_in_spanish(capsys):
    english = _output(capsys, "--help")
    assert english.startswith("usage: getfronts") and "positional arguments" in english
    assert "starting folders" in english and "carpetas de inicio" not in english
    spanish = _output(capsys, "--ayuda")
    assert spanish.startswith("uso: getfronts") and "argumentos posicionales" in spanish
    assert "carpetas de inicio" in spanish and "starting folders" not in spanish


def test_help_texts_cover_the_same_options():
    from getfronts.cli import HELP_TEXTS
    assert HELP_TEXTS["en"].keys() == HELP_TEXTS["es"].keys()


def test_about_and_acerca_de(capsys):
    from pathlib import Path
    from getfronts.about import ABOUT
    english = _output(capsys, "--about")
    assert "Author: Ipserc & Claude" in english and "Thank you." in english
    spanish = _output(capsys, "--acerca-de")
    assert "Autores: Ipserc & Claude" in spanish and "Motivación:" in spanish
    # El README repite la autoría en español: no deben desincronizarse.
    readme = (Path(__file__).parent.parent / "README.md").read_text(encoding="utf-8")
    for line in ("ipserc at selenitas dot es", "2026.10.27",
                 "me encanta ver las carátulas de los álbumes en mi reproductor musical"):
        assert line in ABOUT["es"] and line in readme
