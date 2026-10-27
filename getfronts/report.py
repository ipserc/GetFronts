"""Informe final en CSV o JSON (según la extensión del fichero)."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, fields
from pathlib import Path

from getfronts.processor import FolderResult


def write_report(results: list[FolderResult], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [asdict(r) for r in results]
    if path.suffix.lower() == ".json":
        path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=[f.name for f in fields(FolderResult)])
        writer.writeheader()
        writer.writerows(rows)
