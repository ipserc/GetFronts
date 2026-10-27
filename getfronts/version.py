"""Versión completa: ``mayor.minor.patch - YYYY_MMDD - commit``.

La fecha de compilación y el commit salen de ``_build_info.py`` si existe (lo genera
``tools/stamp_version.py``). Si no, se calculan al vuelo: commit de git (o ``0000000`` si
no hay repositorio o commits) y fecha de modificación más reciente del código.
"""

from __future__ import annotations

import subprocess
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from getfronts import __version__

NO_COMMIT = "0000000"
DATE_FORMAT = "%Y_%m%d"
PACKAGE_DIR = Path(__file__).resolve().parent


def git_commit(path: Path = PACKAGE_DIR) -> str:
    """Hash corto del commit actual del repositorio que contiene ``path``, o ``NO_COMMIT``."""
    try:
        out = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--show-toplevel", "--short=7", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return NO_COMMIT
    lines = out.stdout.split()
    if out.returncode != 0 or len(lines) != 2:
        return NO_COMMIT
    toplevel, commit = lines
    # Sólo vale el repositorio del proyecto, no uno que lo contenga por casualidad.
    if Path(toplevel).resolve() != path.parent:
        return NO_COMMIT
    return commit


def source_date(path: Path = PACKAGE_DIR) -> str:
    """Fecha (YYYY_MMDD) del fichero de código modificado más recientemente."""
    mtime = max((p.stat().st_mtime for p in path.rglob("*.py")), default=0)
    return datetime.fromtimestamp(mtime).strftime(DATE_FORMAT)


@lru_cache(maxsize=1)
def build_info() -> tuple[str, str]:
    """``(fecha_compilación, commit)``."""
    try:
        from getfronts import _build_info
        return _build_info.BUILD_DATE, _build_info.COMMIT
    except ImportError:
        return source_date(), git_commit()


def full_version() -> str:
    build_date, commit = build_info()
    return f"{__version__} - {build_date} - {commit}"
