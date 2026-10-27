"""Interfaz de línea de comandos de GetFronts."""

from __future__ import annotations

import argparse
import logging
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from getfronts.ai import DEFAULT_MODEL, AlbumGuesser
from getfronts.cache import JsonCache, default_cache_dir
from getfronts.finder import CoverFinder
from getfronts.http import HttpClient
from getfronts.processor import FolderProcessor, FolderResult, Options
from getfronts.report import write_report
from getfronts.scanner import find_audio_folders
from getfronts.sources import ALL_SOURCES, DEFAULT_SOURCES, build_sources
from getfronts.version import full_version

log = logging.getLogger("getfronts")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="getfronts",
        description="Descarga las carátulas de los álbumes a partir de los metadatos de las pistas.",
        epilog=f"GetFronts {full_version()}",
    )
    p.add_argument("root", type=Path, help="carpeta de inicio; se recorre todo su árbol")
    p.add_argument("-n", "--dry-run", action="store_true",
                   help="muestra lo que haría sin descargar imágenes ni escribir ficheros de portada")
    p.add_argument("-v", "--verbose", action="store_true", help="registro detallado")
    p.add_argument("--existing", choices=("skip", "overwrite"), default="skip",
                   help="qué hacer si la carpeta ya tiene portada (por defecto: skip)")
    p.add_argument("--embed", action="store_true", help="incrusta también la portada en las pistas")
    p.add_argument("--size", type=int, default=500, help="lado del PNG final en píxeles (por defecto: 500)")
    p.add_argument("--fit", choices=("pad", "crop"), default="pad",
                   help="imágenes no cuadradas: pad = rellenar, crop = recortar (por defecto: pad)")
    p.add_argument("--report", type=Path,
                   help="informe .csv o .json (por defecto: getfronts_report_<fecha>.csv en el directorio actual)")
    p.add_argument("--sources", default=",".join(DEFAULT_SOURCES),
                   help=f"fuentes en orden, separadas por comas (disponibles: {','.join(ALL_SOURCES)})")
    p.add_argument("--min-score", type=float, default=0.75,
                   help="coincidencia mínima 0..1 para aceptar una carátula (por defecto: 0.75)")
    p.add_argument("--no-ai", action="store_true", help="no usar la IA para identificar álbumes por la ruta")
    p.add_argument("--model", default=DEFAULT_MODEL, help=f"modelo de Claude (por defecto: {DEFAULT_MODEL})")
    p.add_argument("--no-cache", action="store_true", help="no leer ni guardar la caché de búsquedas")
    p.add_argument("--cache-dir", type=Path, default=default_cache_dir(), help="carpeta de la caché")
    p.add_argument("--cache-days", type=float, default=30, help="días de validez de la caché (por defecto: 30)")
    p.add_argument("--version", action="version", version=f"GetFronts {full_version()}")
    return p


def setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)-7s %(message)s" if verbose else "%(message)s",
    )
    # Las librerías sólo hablan en modo detallado.
    for noisy in ("urllib3", "httpx", "httpx2", "anthropic", "PIL"):
        logging.getLogger(noisy).setLevel(logging.INFO if verbose else logging.WARNING)


def _describe(r: FolderResult) -> str:
    line = f"[{r.status}] {r.path}\n    {r.artist} | {r.album} | {r.year}  (datos: {r.data_source})"
    if r.image_source:
        line += f"\n    {r.image_source} {r.image_size} score={r.score:.2f} -> {r.cover_file}"
    if r.embedded_tracks:
        line += f"\n    portada incrustada en {r.embedded_tracks} pistas"
    if r.message:
        line += f"\n    {r.message}"
    return line


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    setup_logging(args.verbose)
    log.info("GetFronts %s", full_version())

    root = args.root.expanduser().resolve()
    if not root.is_dir():
        log.error("La ruta no existe o no es una carpeta: %s", root)
        return 2
    source_names = [s.strip().lower() for s in args.sources.split(",") if s.strip()]
    unknown = [s for s in source_names if s not in ALL_SOURCES]
    if unknown:
        log.error("Fuentes desconocidas: %s (disponibles: %s)", ", ".join(unknown), ", ".join(ALL_SOURCES))
        return 2
    report_path = args.report or Path.cwd() / f"getfronts_report_{datetime.now():%Y%m%d_%H%M%S}.csv"

    cache = JsonCache(None if args.no_cache else args.cache_dir / "cache.json", ttl_days=args.cache_days)
    http = HttpClient(cache)
    sources = build_sources(source_names, http)
    log.debug("Fuentes activas: %s", ", ".join(s.name for s in sources))
    finder = CoverFinder(sources, http, min_score=args.min_score, target_size=args.size)
    guesser = AlbumGuesser(cache, model=args.model, enabled=not args.no_ai)
    options = Options(root=root, size=args.size, fit=args.fit, existing=args.existing,
                      embed=args.embed, dry_run=args.dry_run)
    processor = FolderProcessor(options, guesser, finder)

    if args.dry_run:
        log.info("Modo simulación: no se descargará ni escribirá ninguna portada.")
    results: list[FolderResult] = []
    try:
        for folder, tracks in find_audio_folders(root):
            result = processor.process(folder, tracks)
            results.append(result)
            log.info(_describe(result))
            if len(results) % 20 == 0:
                cache.save()
    except KeyboardInterrupt:
        log.warning("Interrumpido por el usuario; se guarda el informe parcial.")
    finally:
        cache.save()
        write_report(results, report_path)

    counts = Counter(r.status for r in results)
    summary = ", ".join(f"{k}={v}" for k, v in sorted(counts.items())) or "sin carpetas con audio"
    log.info("\nCarpetas procesadas: %d (%s)", len(results), summary)
    log.info("Informe: %s", report_path)
    return 1 if counts.get("error") else 0


if __name__ == "__main__":
    sys.exit(main())
