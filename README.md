# Amplificador Orthobullets

CLI que genera fichas medicas pediatricas ampliadas, con estructura tipo
Orthobullets, a partir de un topic base (cuando esta disponible) y
bibliografia verificada en PubMed. Redacta con la Messages API de
Anthropic y verifica que cada PMID citado exista realmente.

Uso privado: pensada para correr en local. Incluye un exportador a una
pagina web unica y autocontenida para navegar el catalogo (ver mas abajo).

## Instalacion

```bash
pip install -r requirements.txt
```

Completa tus claves en `amplificador/config.py`:

```python
ANTHROPIC_API_KEY = "sk-ant-..."
NCBI_API_KEY = ""    # opcional, eleva el limite de PubMed de 3 a 10 req/s
GEMINI_API_KEY = ""  # solo si vas a usar la auditoria bibliografica con Gemini
GEMINI_MODEL = ""    # opcional, fija un modelo; vacio = autodetectar
```

Si las dejas vacias, se usan las variables de entorno `ANTHROPIC_API_KEY`,
`NCBI_API_KEY`, `GEMINI_API_KEY` y `GEMINI_MODEL` como respaldo.

## Estructura del proyecto

```
amplificador/
  config.py            claves de API
  cli.py                subcomandos de la CLI
  orthobullets.py       descarga/lectura del topic base
  pubmed.py             busqueda y verificacion de bibliografia (E-utilities)
  anthropic_client.py   llamadas a la Messages API
  gemini_client.py      auditoria bibliografica adversarial con Gemini
  redaccion.py           arma el prompt final y redacta la ficha
  verificacion.py         valida que los PMID citados existan
  catalog.py               indice jerarquico de fichas generadas
  webview.py                genera la pagina web del catalogo (autocontenida)
  prompts/prompt_sistema.md  prompt de sistema (rol, esqueleto, reglas)
temas/                     fichas generadas + catalogo.json + index.html (se crean al usar la CLI)
.claude/commands/
  ficha-medica-orthobullets.md   skill de Claude Code que orquesta todo el
                                  flujo (busqueda agentica + verificacion
                                  estructurada + auditoria Gemini + registro
                                  en el catalogo) para un tema dado
```

Cada ficha se guarda como Markdown junto a un `.refs.json` con las
referencias usadas y el reporte de verificacion de citas.

## Uso

### Generar una ficha nueva

```bash
python -m amplificador generar "fractura supracondilea de humero en ninos" \
    --categoria "Trauma/Extremidad superior" \
    -n 60
```

Con topic base local (version completa copiada manualmente):

```bash
python -m amplificador generar "osteomielitis aguda pediatrica" \
    --categoria "Infeccion osteoarticular" \
    --base fuentes/osteomielitis.md \
    --extra "pediatric MRI"
```

Si ya existe una ficha con el mismo tema (mismo slug), `generar` la
regenera y sube la version en el catalogo.

### Listar el catalogo (arbol jerarquico, como en Orthobullets)

```bash
python -m amplificador listar
```

```
Trauma/
  Extremidad superior/
    - fractura supracondilea de humero en ninos  [fractura-supracondilea-de-humero-en-ninos]  (v2, act. 2026-08-05T14:03:10)
Infeccion osteoarticular/
  - osteomielitis aguda pediatrica  [osteomielitis-aguda-pediatrica]  (v1, act. 2026-08-05T13:40:02)
```

### Actualizar una ficha existente

Reutiliza tema, categoria y parametros guardados; vuelve a buscar
bibliografia y redactar:

```bash
python -m amplificador actualizar fractura-supracondilea-de-humero-en-ninos
```

### Reorganizar la jerarquia

```bash
python -m amplificador mover osteomielitis-aguda-pediatrica --categoria "Infeccion/Osteoarticular"
```

### Eliminar una ficha

```bash
python -m amplificador eliminar osteomielitis-aguda-pediatrica
```

### Generar una ficha con el skill agentico (`/ficha-medica-orthobullets`)

Para fichas mas exhaustivas y auditadas (inventario completo del topic,
busqueda agentica en PubMed/guias/literatura chilena, auditoria adversarial
con Gemini, control de calidad determinista), usa el skill de Claude Code
en `.claude/commands/ficha-medica-orthobullets.md`:

```
/ficha-medica-orthobullets fractura supracondilea de humero en ninos --categoria "Trauma/Extremidad superior"
```

Este skill no reemplaza al comando `generar`: es un flujo mas lento y
minucioso, pensado para temas donde vale la pena la profundidad extra. Usa
los mismos subcomandos de bajo nivel del paquete `amplificador` en vez de
reimplementar busqueda o verificacion:

| Comando | Para que sirve |
|---|---|
| `python -m amplificador rutas TEMA --categoria RUTA` | Calcula donde debe quedar la ficha final dentro del catalogo, antes de escribirla. |
| `python -m amplificador pubmed-buscar "CONSULTA" -n N` | Busca PMID candidatos (solo IDs, rapido). |
| `python -m amplificador pubmed-detalles PMID [PMID ...]` | Verifica que un PMID exista y trae sus metadatos/resumen. |
| `python -m amplificador orthobullets-descargar --url URL` | Descarga y limpia el HTML publico de un topic ya localizado. |
| `python -m amplificador gemini-auditar --stage pre\|post --input IN.json --output OUT.json` | Ejecuta la auditoria bibliografica adversarial con Gemini. |
| `python -m amplificador registrar TEMA --categoria RUTA --archivo FICHA.md --refs REFS.json` | Registra en `catalogo.json` una ficha ya escrita en disco. |
| `python -m amplificador exportar-web` | Regenera `temas/index.html` a partir del catalogo actual. |

### Visualizar el catalogo en una pagina web

```bash
python -m amplificador exportar-web
```

Genera `temas/index.html`: una sola pagina autocontenida (sin servidor, sin
dependencias externas en tiempo de ejecucion) con panel lateral navegable
por categoria, buscador por tema, y el contenido de cada ficha renderizado
desde Markdown con las citas `[PMID]` convertidas en enlaces a PubMed y los
aportes `[+]` resaltados. Abrila con doble clic o `python -m http.server`
en la carpeta `temas/`.

Arriba de cada ficha se muestran chips de estado: categoria, version,
numero de referencias, y una de estas tres senales de integridad —
**citas verificadas** (todas las citas de PMID están confirmadas contra las
referencias registradas), **N PMID sin verificar (sin red)** (no se pudo
consultar PubMed para confirmarlas, por ejemplo por falta de conexion — no
se asumen validas ni invalidas), o **N PMID inexistentes** (se consulto
PubMed y esos PMID no existen: revisa la ficha antes de confiar en ella).

Vuelve a correr `exportar-web` cada vez que generes, actualices o muevas
una ficha para refrescar la pagina.

## Notas

- `amplificador/config.py` se sube al repositorio con las claves en texto
  plano, pensado para un repositorio privado de uso personal. Si el
  repositorio deja de ser privado, rota las claves antes.
- El prompt de sistema (`amplificador/prompts/prompt_sistema.md`) define
  el rol, el esqueleto de la ficha, las reglas de veracidad y de citado
  para el flujo del comando `generar`. Ajustalo ahi si necesitas cambiar
  esa estructura de salida.
- Gemini nunca se usa como fuente citable: solo detecta omisiones y
  propone referencias candidatas, que siempre se verifican de forma
  independiente contra PubMed antes de incorporarlas.
- `temas/` viene con 3 fichas `[EJEMPLO]` (pie equino varo congenito,
  fractura supracondilea de humero, atresia de vias biliares) para poder
  ver el visualizador funcionando sin tener que generar nada primero.
  Tienen un aviso en rojo al inicio, sus citas no estan verificadas y no
  deben usarse para estudio ni practica clinica real. Elimínalas con
  `python -m amplificador eliminar <slug>` (mira los slugs con `listar`)
  antes de empezar a generar fichas de verdad, y corre `exportar-web` de
  nuevo.
