# Amplificador Orthobullets

CLI que genera fichas medicas pediatricas ampliadas, con estructura tipo
Orthobullets, a partir de un topic base (cuando esta disponible) y
bibliografia verificada en PubMed. Redacta con la Messages API de
Anthropic y verifica que cada PMID citado exista realmente.

Uso privado: pensada para correr en local, sin interfaz web.

## Instalacion

```bash
pip install -r requirements.txt
```

Completa tus claves en `amplificador/config.py`:

```python
ANTHROPIC_API_KEY = "sk-ant-..."
NCBI_API_KEY = ""  # opcional, eleva el limite de PubMed de 3 a 10 req/s
```

Si las dejas vacias, se usan las variables de entorno `ANTHROPIC_API_KEY`
y `NCBI_API_KEY` como respaldo.

## Estructura del proyecto

```
amplificador/
  config.py         claves de API
  cli.py             subcomandos (generar, actualizar, listar, mover, eliminar)
  orthobullets.py     descarga/lectura del topic base
  pubmed.py           busqueda y verificacion de bibliografia (E-utilities)
  anthropic_client.py llamadas a la Messages API
  redaccion.py        arma el prompt final y redacta la ficha
  verificacion.py      valida que los PMID citados existan
  catalog.py           indice jerarquico de fichas generadas
  prompts/prompt_sistema.md  prompt de sistema (rol, esqueleto, reglas)
temas/                 fichas generadas + catalogo.json (se crea al usar la CLI)
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

## Notas

- `amplificador/config.py` se sube al repositorio con las claves en texto
  plano, pensado para un repositorio privado de uso personal. Si el
  repositorio deja de ser privado, rota las claves antes.
- El prompt de sistema (`amplificador/prompts/prompt_sistema.md`) define
  el rol, el esqueleto de la ficha, las reglas de veracidad y de citado.
  Ajustalo ahi si necesitas cambiar la estructura de salida.
