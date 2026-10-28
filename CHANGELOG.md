# Cambios

Formato: `mayor.minor.patch`. Cada versión tiene su etiqueta de git y su
[Release en GitHub](https://github.com/ipserc/GetFronts/releases).

## [0.1.4] - 2026-10-28

### Corregido
- Sencillo en lugar de álbum: en *Zeit* de Rammstein el sencillo y el álbum tienen el mismo
  título y año, empataban a 1.0 y se descargaba la portada del sencillo. Ahora MusicBrainz,
  iTunes y Deezer indican el tipo de lanzamiento y, si la carpeta tiene más de 4 pistas, los
  sencillos y EP se puntúan un 10 % menos.
- iTunes: se quita el sufijo " - Single" / " - EP" del título antes de compararlo.

## [0.1.3] - 2026-10-28

### Corregido
- Títulos con subtítulo: *The Best of Everything* no coincidía con *The Best of Everything: The
  Definitive Career Spanning Hits Collection 1976–2016* (puntuación 0.72 frente a un mínimo de
  0.75). Ahora también se compara el título principal, con un 10 % de penalización.
- La deducción por la ruta entiende carpetas `Año-Álbum` sin espacios (`2019-The Best of Everything CD2`).

## [0.1.2] - 2026-10-28

### Corregido
- Se quitan del título del álbum las marcas de disco (`(CD 2)`, `[Disc 1 of 2]`,
  `(Disco 2 - Bonus)`, `- CD2`…). Antes se enviaban a las fuentes, que no encontraban el disco,
  y acababan también en el nombre del archivo.

### Añadido
- Si una búsqueda no da resultados, se reintenta sin lo que haya entre paréntesis o corchetes.

## [0.1.1] - 2026-10-28

### Corregido
- `pyproject.toml` requiere `setuptools>=64` (instalación editable, PEP 660).
- README: instalación en dos pasos y solución al fallo de `pip install -e .` con el pip 22.0.2
  de Ubuntu 22.04.

## [0.1.0] - 2026-10-28

Primera versión.
- Recorrido del árbol, lectura de metadatos y votación por mayoría (Artista del álbum,
  `Various Artists`, sólo el año).
- Identificación por IA con Claude (`claude-haiku-5-5`) y heurística por la ruta.
- Fuentes: MusicBrainz + Cover Art Archive, iTunes, Deezer, Discogs y Last.fm.
- PNG de 500x500 `Artista_Album_Año_Front.png`, informe CSV/JSON.
- Opciones `--dry-run`, `--verbose`, `--existing`, `--embed`, `--size`, `--fit`, `--sources`,
  `--min-score`, `--no-ai` y caché.
- Versión `mayor.minor.patch - YYYY_MMDD - commit` en cada ejecución.

[0.1.3]: https://github.com/ipserc/GetFronts/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/ipserc/GetFronts/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/ipserc/GetFronts/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/ipserc/GetFronts/releases/tag/v0.1.0
