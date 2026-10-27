import re
import subprocess
import sys
import types

import pytest

from getfronts import __version__, version
from getfronts.cli import main

FORMAT = re.compile(r"^\d+\.\d+\.\d+ - \d{4}_\d{4} - [0-9a-f]{7,}$")


@pytest.fixture(autouse=True)
def fresh_build_info():
    version.build_info.cache_clear()
    yield
    version.build_info.cache_clear()


def test_full_version_format():
    full = version.full_version()
    assert FORMAT.match(full), full
    assert full.startswith(__version__ + " - ")


def test_without_git_repo_commit_is_zeros(tmp_path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    assert version.git_commit(pkg) == "0000000"


def test_git_repo_without_commits_is_zeros(tmp_path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    assert version.git_commit(pkg) == "0000000"


def test_git_repo_with_commit(tmp_path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "a.py").write_text("x = 1\n")
    git = ["git", "-C", str(tmp_path), "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(git + ["add", "."], check=True)
    subprocess.run(git + ["commit", "-q", "-m", "init"], check=True)
    head = subprocess.run(git + ["rev-parse", "--short=7", "HEAD"], capture_output=True, text=True).stdout.strip()
    assert version.git_commit(pkg) == head


def test_enclosing_foreign_repo_is_ignored(tmp_path):
    # El paquete está dentro de un repositorio, pero no en su raíz: no es el nuestro.
    pkg = tmp_path / "otro" / "proyecto" / "pkg"
    pkg.mkdir(parents=True)
    git = ["git", "-C", str(tmp_path), "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(git + ["commit", "-q", "--allow-empty", "-m", "init"], check=True)
    assert version.git_commit(pkg) == "0000000"


def test_build_info_file_takes_precedence(monkeypatch):
    stamped = types.SimpleNamespace(BUILD_DATE="2026_1028", COMMIT="96f720e")
    monkeypatch.setitem(sys.modules, "getfronts._build_info", stamped)
    assert version.full_version() == f"{__version__} - 2026_1028 - 96f720e"


def test_cli_prints_version(tmp_path, capsys, caplog):
    with pytest.raises(SystemExit):
        main(["--version"])
    assert FORMAT.match(capsys.readouterr().out.strip().removeprefix("GetFronts "))

    caplog.set_level("INFO")
    main([str(tmp_path), "--no-ai", "--no-cache", "--report", str(tmp_path / "r.csv")])
    assert caplog.records[0].getMessage() == f"GetFronts {version.full_version()}"
