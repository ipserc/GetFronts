"""Genera ``getfronts/_build_info.py`` con la fecha de compilación (hoy) y el commit actual.

Uso (desde la raíz del proyecto, antes de empaquetar o distribuir una copia):

    python3 tools/stamp_version.py

``_build_info.py`` no se versiona: un fichero dentro del commit no puede contener su propio hash.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from getfronts import __version__  # noqa: E402
from getfronts.version import DATE_FORMAT, PACKAGE_DIR, git_commit  # noqa: E402


def main() -> int:
    build_date = datetime.now().strftime(DATE_FORMAT)
    commit = git_commit()
    target = PACKAGE_DIR / "_build_info.py"
    target.write_text(
        '"""Generado por tools/stamp_version.py. No editar ni versionar."""\n\n'
        f'BUILD_DATE = "{build_date}"\n'
        f'COMMIT = "{commit}"\n',
        encoding="utf-8",
    )
    print(f"{target.relative_to(ROOT)}: {__version__} - {build_date} - {commit}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
