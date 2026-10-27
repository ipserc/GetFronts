# GetFronts

Descarga automáticamente las carátulas (*fronts*) de los discos de una biblioteca musical,
a partir de los metadatos de las propias canciones.

Se le da una carpeta de inicio y recorre todo el árbol. En cada carpeta con pistas de audio
averigua el **Artista**, el **Álbum** y el **Año**, busca la carátula en internet, elige la de
mejor calidad y la guarda junto a las pistas como PNG de 500x500:

```
Pink Floyd/The Dark Side of the Moon/
├── 01 Speak to Me.flac
├── 02 Breathe.flac
├── ...
└── Pink_Floyd_The_Dark_Side_of_the_Moon_1973_Front.png
```

## Cómo funciona

1. **Recorrido**: busca las carpetas que contienen audio (mp3, flac, m4a/aac, ogg, opus, wma,
   wav, aiff). Cada carpeta se trata por separado, así que en los álbumes de varios discos
   (`CD1/`, `CD2/`…) cada subcarpeta recibe su portada.
2. **Metadatos**: lee las etiquetas de todas las pistas con [mutagen](https://mutagen.readthedocs.io/)
   y se queda con los valores que más se repiten.
   - Prefiere el campo *Artista del álbum* al *Artista* de cada pista.
   - Los recopilatorios (marca de compilación o muchos artistas distintos) se identifican como
     `Various Artists`.
   - De la fecha sólo se guarda el año.
3. **Identificación por IA**: si faltan datos, pregunta a Claude (`claude-haiku-5-5`) enviándole
   el final de la ruta, los nombres de las pistas y lo que ya se sepa. Si la IA no está
   disponible o no lo consigue, aplica una heurística sobre el nombre de las carpetas
   (`Artista - Álbum (Año)`, `Artista/Año - Álbum`, `Artista - Año - Álbum`…).
   Lo que no se averigua queda como `unknown`.
4. **Búsqueda**: con Artista y Álbum conocidos (el año sólo desempata) consulta las fuentes:

   | Fuente | Clave | Notas |
   |---|---|---|
   | [MusicBrainz](https://musicbrainz.org) + [Cover Art Archive](https://coverartarchive.org) | No | Máximo 1 petición por segundo |
   | [iTunes Search API](https://performance-partners.apple.com/search-api) | No | Hasta 1200x1200 |
   | [Deezer](https://developers.deezer.com/api) | No | Hasta 1000x1000 |
   | [Discogs](https://www.discogs.com/developers) | `DISCOGS_TOKEN` | Sólo si hay token |
   | [Last.fm](https://www.last.fm/api) | `LASTFM_API_KEY` | Sólo si hay clave |

5. **Elección**: puntúa cada resultado según su parecido con el Artista (45 %), el Álbum (45 %)
   y el Año (10 %), sin tener en cuenta mayúsculas, acentos ni sufijos como "(Remastered)".
   Descarta los que no llegan al mínimo, descarga las mejores candidatas y se queda con la de
   más calidad: la que alcanza el tamaño final, es cuadrada y tiene más resolución.
6. **Conversión**: la pasa a PNG de 500x500, rellenando con negro (o recortando) si no es
   cuadrada, y la guarda como `Artista_Album_Año_Front.png`. En el nombre se quitan los
   caracteres no válidos y los espacios se cambian por `_`.
7. **Informe**: al terminar escribe un CSV o JSON con la ruta, los datos encontrados, su origen
   y el resultado de cada carpeta, incluidas las que quedaron `unknown`.

## Requisitos

- Python 3.10 o superior
- `mutagen`, `requests`, `Pillow` y `anthropic` (este último sólo para la identificación por IA)
- Opcional: una credencial de Anthropic, en `ANTHROPIC_API_KEY` o con `ant auth login`. Sin ella
  todo funciona igual, salvo la identificación por IA.

## Instalación

```bash
git clone https://github.com/ipserc/GetFronts.git
cd GetFronts
pip install --user -r requirements.txt     # o: pip install -e .  (instala el comando getfronts)
```

## Uso

```bash
python3 -m getfronts /ruta/a/la/musica                 # procesa todo el árbol
python3 -m getfronts /ruta --dry-run -v                # simula y muestra el detalle
python3 -m getfronts /ruta --existing overwrite --embed --report informe.json
```

| Opción | Efecto |
|---|---|
| `-n`, `--dry-run` | Busca y muestra qué haría, sin descargar imágenes ni escribir portadas |
| `-v`, `--verbose` | Registro detallado (candidatas y puntuaciones de cada fuente) |
| `--existing skip\|overwrite` | Qué hacer si la carpeta ya tiene portada (`*_Front.png`, `folder.*`, `cover.*`, `front.*` o imagen incrustada en las pistas). Por defecto `skip` |
| `--embed` | Incrusta también la portada en las pistas (todos los formatos salvo wma) |
| `--size N` | Lado del PNG final en píxeles (por defecto 500) |
| `--fit pad\|crop` | Imágenes no cuadradas: rellenar con negro o recortar al centro (por defecto `pad`) |
| `--report FICHERO` | Informe `.csv` o `.json` (por defecto `getfronts_report_<fecha>.csv` en el directorio actual) |
| `--sources a,b,…` | Fuentes que se usan y en qué orden (`musicbrainz,itunes,deezer,discogs,lastfm`) |
| `--min-score X` | Coincidencia mínima entre 0 y 1 para aceptar una carátula (por defecto 0.75) |
| `--no-ai` | No usar la IA |
| `--model M` | Modelo de Claude (por defecto `claude-haiku-5-5`) |
| `--no-cache`, `--cache-dir`, `--cache-days` | Caché de búsquedas y respuestas de la IA (`~/.cache/getfronts`, 30 días) |
| `--version` | Muestra la versión |

### Variables de entorno

| Variable | Uso |
|---|---|
| `ANTHROPIC_API_KEY` | Credencial para la identificación por IA |
| `DISCOGS_TOKEN` | Activa la fuente Discogs |
| `LASTFM_API_KEY` | Activa la fuente Last.fm |
| `GETFRONTS_CONTACT` | Email o URL de contacto para el User-Agent, como pide MusicBrainz |

### Ejemplo de salida

```
GetFronts 0.1.0 - 2026_1028 - 96f720e
[downloaded] /musica/Mecano/Descanso dominical/CD1
    Mecano | Descanso Dominical | 1988  (datos: tags)
    musicbrainz 1200x1200 score=1.00 -> Mecano_Descanso_Dominical_1988_Front.png
[downloaded] /musica/Sin etiquetas/Radiohead - OK Computer (1997)
    Radiohead | OK Computer | 1997  (datos: ai)
    musicbrainz 1200x1200 score=1.00 -> Radiohead_OK_Computer_1997_Front.png
[unknown_skipped] /musica/Basura/xyz123
    unknown | unknown | unknown  (datos: none)
    no se pudo identificar artista y álbum

Carpetas procesadas: 3 (downloaded=2, unknown_skipped=1)
```

### Informe

Columnas: `path`, `artist`, `album`, `year`, `data_source` (`tags`, `ai`, `path` o
combinaciones), `status`, `cover_file`, `image_source`, `image_url`, `image_size`, `score`,
`embedded_tracks`, `message` y `tracks`.

Estados: `downloaded`, `dry_run`, `exists_skipped`, `unknown_skipped`, `not_found` y `error`.

## Versión

Cada ejecución muestra la versión al empezar (también `--version` y `--help`):

```
GetFronts 0.1.0 - 2026_1028 - 96f720e
          │       │           └ commit (0000000 si no hay repositorio git o commits)
          │       └ fecha de compilación, YYYY_MMDD
          └ mayor.minor.patch  (getfronts/__init__.py)
```

Desde el código fuente, el commit se lee de git y la fecha es la de la última modificación del
código. Para fijar ambos valores en una copia que se vaya a distribuir:

```bash
python3 tools/stamp_version.py     # genera getfronts/_build_info.py (no se versiona)
```

Cada versión publicada lleva su etiqueta de git (`v0.1.0`, `v0.2.0`…).

## Estructura del proyecto

```
getfronts/
├── cli.py          # línea de comandos y bucle principal
├── scanner.py      # recorrido del árbol de carpetas
├── metadata.py     # lectura de etiquetas y votación por mayoría
├── ai.py           # identificación con Claude y heurística por la ruta
├── sources/        # MusicBrainz, iTunes, Deezer, Discogs, Last.fm
├── finder.py       # puntuación de candidatas y elección de la mejor imagen
├── imaging.py      # conversión a PNG cuadrado
├── embed.py        # incrustación de la portada en las pistas
├── processor.py    # flujo completo para una carpeta
├── report.py       # informe CSV / JSON
├── http.py         # cliente HTTP con reintentos y límite de peticiones
├── cache.py        # caché persistente en JSON
└── version.py      # versión completa (versión - fecha - commit)
tools/stamp_version.py
tests/
Descripción_y_alcance.txt   # especificación original del proyecto
```

## Tests

```bash
python3 -m pytest
```

Necesitan `ffmpeg` para generar pistas de prueba en todos los formatos. No usan la red ni la
API de Anthropic.

## Problemas conocidos

Si la IA falla siempre con `Connection error`, revisa la versión de `brotli`: el paquete
`python3-brotli` 1.0.9 de Ubuntu 22.04 no es compatible con el cliente HTTP del SDK de
Anthropic. Se arregla con `pip install --user -U brotli`.

## Licencia

[MIT](LICENSE)
