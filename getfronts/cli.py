"""Interfaz de línea de comandos de GetFronts."""

from __future__ import annotations

import argparse
import glob
import logging
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from getfronts.about import about_text
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


# Textos de la ayuda: ``--help`` en inglés, ``--ayuda`` en español.
HELP_TEXTS = {
    "en": {
        "usage": "usage: ",
        "positionals": "positional arguments",
        "options": "options",
        "description": "Downloads album covers based on the tracks' metadata.",
        "folder": "folder",
        "roots": "starting folders; their whole tree is scanned. Wildcards are accepted: "
                 "'/internal1/Flac/Alaska*' processes every folder starting with Alaska",
        "help": "show this help message in English and exit",
        "ayuda": "show this help message in Spanish and exit",
        "dry_run": "show what would be done without downloading images or writing cover files",
        "verbose": "detailed logging",
        "existing": "what to do if the folder already has a cover (default: skip)",
        "embed": "also embed the cover in the tracks",
        "size": "side of the final PNG in pixels (default: 500)",
        "fit": "non-square images: pad = fill, crop = trim (default: pad)",
        "report": "report .csv or .json (default: getfronts_report_<date>.csv in the current directory)",
        "sources": "sources in order, comma separated (available: {sources})",
        "min_score": "minimum match 0..1 to accept a cover (default: 0.75)",
        "no_ai": "do not use AI to identify albums from the path",
        "model": "Claude model (default: {model})",
        "no_cache": "do not read or write the search cache",
        "cache_dir": "cache folder",
        "cache_days": "cache validity in days (default: 30)",
        "version": "show the program version and exit",
        "about": "show authorship, motivation and acknowledgments in English and exit",
        "acerca_de": "show authorship, motivation and acknowledgments in Spanish and exit",
    },
    "es": {
        "usage": "uso: ",
        "positionals": "argumentos posicionales",
        "options": "opciones",
        "description": "Descarga las carátulas de los álbumes a partir de los metadatos de las pistas.",
        "folder": "carpeta",
        "roots": "carpetas de inicio; se recorre todo su árbol. Admite comodines: "
                 "'/internal1/Flac/Alaska*' procesa todas las que empiezan por Alaska",
        "help": "muestra esta ayuda en inglés y sale",
        "ayuda": "muestra esta ayuda en español y sale",
        "dry_run": "muestra lo que haría sin descargar imágenes ni escribir ficheros de portada",
        "verbose": "registro detallado",
        "existing": "qué hacer si la carpeta ya tiene portada (por defecto: skip)",
        "embed": "incrusta también la portada en las pistas",
        "size": "lado del PNG final en píxeles (por defecto: 500)",
        "fit": "imágenes no cuadradas: pad = rellenar, crop = recortar (por defecto: pad)",
        "report": "informe .csv o .json (por defecto: getfronts_report_<fecha>.csv en el directorio actual)",
        "sources": "fuentes en orden, separadas por comas (disponibles: {sources})",
        "min_score": "coincidencia mínima 0..1 para aceptar una carátula (por defecto: 0.75)",
        "no_ai": "no usar la IA para identificar álbumes por la ruta",
        "model": "modelo de Claude (por defecto: {model})",
        "no_cache": "no leer ni guardar la caché de búsquedas",
        "cache_dir": "carpeta de la caché",
        "cache_days": "días de validez de la caché (por defecto: 30)",
        "version": "muestra la versión del programa y sale",
        "about": "muestra la autoría, la motivación y los agradecimientos en inglés y sale",
        "acerca_de": "muestra la autoría, la motivación y los agradecimientos en español y sale",
    },
}


class _HelpAction(argparse.Action):
    """``--help`` / ``--ayuda``: imprime la ayuda en el idioma de la opción."""

    def __init__(self, option_strings, dest, lang: str, **kwargs):
        super().__init__(option_strings, dest, nargs=0, default=argparse.SUPPRESS, **kwargs)
        self.lang = lang

    def __call__(self, parser, namespace, values, option_string=None):
        build_parser(self.lang).print_help()
        parser.exit()


class _AboutAction(argparse.Action):
    """``--about`` / ``--acerca-de``: imprime la autoría en el idioma de la opción."""

    def __init__(self, option_strings, dest, lang: str, **kwargs):
        super().__init__(option_strings, dest, nargs=0, default=argparse.SUPPRESS, **kwargs)
        self.lang = lang

    def __call__(self, parser, namespace, values, option_string=None):
        print(about_text(self.lang))
        parser.exit()


class _Formatter(argparse.HelpFormatter):
    usage_prefix = "usage: "

    def add_usage(self, usage, actions, groups, prefix=None):
        super().add_usage(usage, actions, groups, prefix or self.usage_prefix)


def build_parser(lang: str = "en") -> argparse.ArgumentParser:
    t = HELP_TEXTS[lang]
    formatter = type("Formatter", (_Formatter,), {"usage_prefix": t["usage"]})
    p = argparse.ArgumentParser(
        prog="getfronts",
        description=t["description"],
        epilog=f"GetFronts {full_version()}",
        formatter_class=formatter,
        add_help=False,
    )
    p._positionals.title = t["positionals"]
    p._optionals.title = t["options"]
    p.add_argument("roots", nargs="+", metavar=t["folder"], help=t["roots"])
    p.add_argument("-h", "--help", action=_HelpAction, lang="en", help=t["help"])
    p.add_argument("--ayuda", action=_HelpAction, lang="es", help=t["ayuda"])
    p.add_argument("-n", "--dry-run", action="store_true", help=t["dry_run"])
    p.add_argument("-v", "--verbose", action="store_true", help=t["verbose"])
    p.add_argument("--existing", choices=("skip", "overwrite"), default="skip", help=t["existing"])
    p.add_argument("--embed", action="store_true", help=t["embed"])
    p.add_argument("--size", type=int, default=500, help=t["size"])
    p.add_argument("--fit", choices=("pad", "crop"), default="pad", help=t["fit"])
    p.add_argument("--report", type=Path, help=t["report"])
    p.add_argument("--sources", default=",".join(DEFAULT_SOURCES),
                   help=t["sources"].format(sources=",".join(ALL_SOURCES)))
    p.add_argument("--min-score", type=float, default=0.75, help=t["min_score"])
    p.add_argument("--no-ai", action="store_true", help=t["no_ai"])
    p.add_argument("--model", default=DEFAULT_MODEL, help=t["model"].format(model=DEFAULT_MODEL))
    p.add_argument("--no-cache", action="store_true", help=t["no_cache"])
    p.add_argument("--cache-dir", type=Path, default=default_cache_dir(), help=t["cache_dir"])
    p.add_argument("--cache-days", type=float, default=30, help=t["cache_days"])
    p.add_argument("--version", action="version", version=f"GetFronts {full_version()}", help=t["version"])
    p.add_argument("--about", action=_AboutAction, lang="en", help=t["about"])
    p.add_argument("--acerca-de", action=_AboutAction, lang="es", help=t["acerca_de"])
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


def expand_roots(patterns: list[str]) -> tuple[list[Path], list[str]]:
    """Carpetas de inicio a partir de los argumentos, expandiendo comodines ``*``, ``?`` y ``[]``.

    Devuelve las carpetas (sin repetir y sin las que ya están dentro de otra) y los argumentos que
    no corresponden a ninguna carpeta.
    """
    found: list[Path] = []
    missing: list[str] = []
    for pattern in patterns:
        expanded = str(Path(pattern).expanduser())
        if glob.has_magic(expanded):
            matches = [Path(m) for m in sorted(glob.glob(expanded)) if Path(m).is_dir()]
        else:
            matches = [Path(expanded)] if Path(expanded).is_dir() else []
        if not matches:
            missing.append(pattern)
        found.extend(m.resolve() for m in matches)
    roots: list[Path] = []
    for root in sorted(set(found)):
        if not any(root.is_relative_to(r) for r in roots):
            roots.append(root)
    return roots, missing


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    setup_logging(args.verbose)
    log.info("GetFronts %s", full_version())

    roots, missing = expand_roots(args.roots)
    for pattern in missing:
        log.error("La ruta no existe o no es una carpeta: %s", pattern)
    if missing or not roots:
        return 2
    if len(roots) > 1:
        log.info("Carpetas de inicio (%d):\n  %s", len(roots), "\n  ".join(str(r) for r in roots))
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
    options = Options(root=roots[0], size=args.size, fit=args.fit, existing=args.existing,
                      embed=args.embed, dry_run=args.dry_run)
    processor = FolderProcessor(options, guesser, finder)

    if args.dry_run:
        log.info("Modo simulación: no se descargará ni escribirá ninguna portada.")
    results: list[FolderResult] = []
    try:
        for root in roots:
            options.root = root  # la heurística por la ruta mide la profundidad desde aquí
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
