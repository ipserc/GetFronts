# GetFronts

Descarga automáticamente las carátulas (*fronts*) de los discos de una biblioteca musical,
a partir de los metadatos de las propias canciones.

Se le dan una o varias carpetas de inicio (admite comodines) y recorre todo su árbol. En cada
carpeta con pistas de audio averigua el **Artista**, el **Álbum** y el **Año**, busca la carátula
en internet, elige la de mejor calidad y la guarda junto a las pistas como PNG de 500x500:

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
   (`Artista - Álbum (Año)`, `Artista/Año - Álbum`, `Artista/Año-Álbum`, `Artista - Año - Álbum`…).
   Lo que no se averigua queda como `unknown`.
   Al final se quitan del título las marcas de disco (`(CD 2)`, `[Disc 1 of 2]`, `- CD2`…) y de
   formato (`(FLAC)`, `(ogg)`, `[Mp3]`, `(FLAC 24bit-96kHz)`…).
4. **Búsqueda**: con Artista y Álbum conocidos consulta las fuentes; si falta el año se busca
   igualmente. En la consulta, las comillas `''` o `″` se escriben como `"` (`12'' 80s` → `12" 80s`).
   Si no encuentra nada, repite la búsqueda sin lo que haya entre paréntesis o corchetes
   (`(Deluxe Edition)`, `[Remastered]`…):

   | Fuente | Clave | Notas |
   |---|---|---|
   | [MusicBrainz](https://musicbrainz.org) + [Cover Art Archive](https://coverartarchive.org) | No | Máximo 1 petición por segundo |
   | [iTunes Search API](https://performance-partners.apple.com/search-api) | No | Hasta 1200x1200 |
   | [Deezer](https://developers.deezer.com/api) | No | Hasta 1000x1000 |
   | [Discogs](https://www.discogs.com/developers) | `DISCOGS_TOKEN` | Sólo si hay token |
   | [Last.fm](https://www.last.fm/api) | `LASTFM_API_KEY` | Sólo si hay clave |

5. **Elección**: puntúa cada resultado según su parecido con el Artista (45 %), el Álbum (45 %)
   y el Año (10 %), sin tener en cuenta mayúsculas, acentos ni sufijos como "(Remastered)".
   Si una fuente devuelve el título con subtítulo ("The Best of Everything: The Definitive…"),
   también se compara el título principal, con un 10 % de penalización frente a una
   coincidencia exacta.
   Si la carpeta tiene más de 4 pistas, los sencillos y EP también pierden un 10 %: así no
   ganan al álbum cuando se llaman igual (Rammstein - *Zeit*), aunque se aceptan si no hay otra cosa.
   Si el título no coincide exactamente y los años se llevan más de 2, la candidata pierde un 15 %
   y queda descartada: casi seguro que es otro disco. Con el título exacto se acepta aunque el año
   no cuadre, porque algunas fuentes dan la fecha de una reedición.
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
pip install --user -r requirements.txt
python3 -m getfronts --version
```

Para tener además el comando `getfronts` (instalación editable: los cambios en el código se
aplican sin reinstalar):

```bash
python3 -m pip install --user -e .
getfronts --version
```

> **Ubuntu 22.04**: su pip 22.0.2 falla con *"build backend is missing the 'build_editable'
> hook"*, porque mezcla el setuptools 59 del sistema en la compilación. Actualiza pip para tu
> usuario y repite con `python3 -m pip`:
>
> ```bash
> python3 -m pip install --user -U pip
> python3 -m pip install --user -e .
> ```

## Uso

```bash
python3 -m getfronts /ruta/a/la/musica                 # procesa todo el árbol
python3 -m getfronts /ruta --dry-run -v                # simula y muestra el detalle
python3 -m getfronts /ruta --existing overwrite --embed --report informe.json
python3 -m getfronts '/internal1/Flac/Alaska*'          # todas las carpetas que empiezan por Alaska
python3 -m getfronts /ruta/Rammstein /ruta/Muse        # varias carpetas, un solo informe
```

Los comodines `*`, `?` y `[...]` funcionan con comillas (los expande GetFronts) y sin ellas
(los expande la shell). Si un argumento no corresponde a ninguna carpeta, no se procesa nada.

| Opción | Efecto |
|---|---|
| `-n`, `--dry-run` | Busca y muestra qué haría, sin descargar imágenes ni escribir portadas |
| `-v`, `--verbose` | Registro detallado (candidatas de cada fuente con su puntuación y su tipo: `[album]`, `[single]`, `[ep]`…) |
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
| `-h`, `--help` / `--ayuda` | Ayuda en inglés / en español |
| `--about` / `--acerca-de` | Autoría, motivación y agradecimientos en inglés / en español |

### Variables de entorno

| Variable | Uso |
|---|---|
| `ANTHROPIC_API_KEY` | Credencial para la identificación por IA |
| `DISCOGS_TOKEN` | Activa la fuente Discogs |
| `LASTFM_API_KEY` | Activa la fuente Last.fm |
| `GETFRONTS_CONTACT` | Email o URL de contacto para el User-Agent, como pide MusicBrainz |

### Ejemplo de salida

```
GetFronts 0.1.5 - 2026_1028 - 268df87
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

Cada ejecución muestra la versión al empezar (también `--version`, `--help`, `--about`…):

```
GetFronts 0.1.5 - 2026_1028 - 268df87
          │       │           └ commit (0000000 si no hay repositorio git o commits)
          │       └ fecha de compilación, YYYY_MMDD
          └ mayor.minor.patch  (getfronts/__init__.py)
```

Desde el código fuente, el commit se lee de git y la fecha es la de la última modificación del
código. Para fijar ambos valores en una copia que se vaya a distribuir:

```bash
python3 tools/stamp_version.py     # genera getfronts/_build_info.py (no se versiona)
```

Cada versión publicada lleva su etiqueta de git y su Release en GitHub. Los cambios de cada
versión están en [CHANGELOG.md](CHANGELOG.md).

## Estructura del proyecto

```
getfronts/
├── cli.py          # línea de comandos (ayuda en inglés y español) y bucle principal
├── about.py        # autoría: --about / --acerca-de
├── scanner.py      # recorrido del árbol de carpetas
├── metadata.py     # lectura de etiquetas y votación por mayoría
├── ai.py           # identificación con Claude y heurística por la ruta
├── sources/        # MusicBrainz, iTunes, Deezer, Discogs, Last.fm
├── finder.py       # puntuación de candidatas y elección de la mejor imagen
├── textutil.py     # limpieza y comparación de títulos, nombres de archivo
├── imaging.py      # conversión a PNG cuadrado
├── embed.py        # incrustación de la portada en las pistas
├── processor.py    # flujo completo para una carpeta
├── report.py       # informe CSV / JSON
├── http.py         # cliente HTTP con reintentos y límite de peticiones
├── cache.py        # caché persistente en JSON
└── version.py      # versión completa (versión - fecha - commit)
tools/stamp_version.py
tests/
CHANGELOG.md                # cambios de cada versión
CLAUDE.md                   # guía de trabajo para Claude Code
Descripción_y_alcance.txt   # especificación original del proyecto
```

## Tests

```bash
python3 -m pytest
```

Necesitan `ffmpeg` para generar pistas de prueba en todos los formatos. No usan la red ni la
API de Anthropic.

## Problemas conocidos

- `pip install -e .` falla en Ubuntu 22.04 con el pip del sistema: ver [Instalación](#instalación).
- Si la IA falla siempre con `Connection error`, revisa la versión de `brotli`: el paquete
  `python3-brotli` 1.0.9 de Ubuntu 22.04 no es compatible con el cliente HTTP del SDK de
  Anthropic. Se arregla con `pip install --user -U brotli`.
- Muchos recopilatorios (por ejemplo la serie *12" 80s*) no están en MusicBrainz, iTunes ni
  Deezer, o están sin imagen, y salen como `not_found`. Discogs suele tenerlos: crea un token
  gratuito en discogs.com (*Settings → Developers*) y expórtalo en `DISCOGS_TOKEN`.

## Autoría

- **Autores**: Ipserc & Claude
- **Email**: ipserc at selenitas dot es
- **Fecha de concepción**: 2026.10.27
- **Motivación**: me encanta ver las carátulas de los álbumes en mi reproductor musical.

**Agradecimientos**: gracias a Linux, gracias a la FSF, gracias a Python.
Gracias a quienes contribuyen desinteresadamente al mundo del software. Gracias.

## Licencia

[MIT](LICENSE)
