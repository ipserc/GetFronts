# GetFronts: guía para Claude

Descarga las carátulas de los álbumes a partir de los metadatos de las pistas. Especificación
original en `Descripción_y_alcance.txt`; funcionamiento en `README.md`; versiones en `CHANGELOG.md`.

## Comandos

```bash
python3 -m pytest -q                       # tests (usan ffmpeg; sin red ni API)
python3 -m getfronts <ruta> --dry-run -v   # o `getfronts`, instalado en modo editable
python3 tools/stamp_version.py             # fija fecha y commit en getfronts/_build_info.py
```

No hay venv (falta `python3-venv`): las dependencias se instalan con `pip install --user`.

## Reglas

- Todo en español: mensajes al usuario, logs, docstrings, commits y notas de Release.
- La versión está sólo en `getfronts/__init__.py` (`pyproject.toml` la lee de ahí).
- Cada corrección se publica como patch: subir la versión, tests, commit con
  `Co-Authored-By`, etiqueta anotada `vX.Y.Z`, push, `gh release create --notes-file`
  (el `gh` instalado no tiene `--verify-tag`) y entrada en `CHANGELOG.md`.
- El repositorio es público: preguntar antes de hacer push y no subir datos personales
  (`Claude_dialogos.txt` sólo con permiso explícito).
- Para un `not_found`: reproducir contra las fuentes reales con la puntuación de cada candidata
  (`CoverFinder` + `build_sources`, logging DEBUG) antes de cambiar nada; comprobar la portada
  descargada mirándola.
- Respetar las decisiones de diseño acordadas (500x500, `--existing skip` por defecto,
  una portada por subcarpeta de disco, sólo el año, `Various Artists`…).
