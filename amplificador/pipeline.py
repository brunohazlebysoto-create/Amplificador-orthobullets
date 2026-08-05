"""Logica central del comando `generar`, factorizada para que la use tanto
la CLI como el servidor web (amplificador.server)."""

import json
from pathlib import Path

from .catalog import Catalogo
from .orthobullets import cargar_base
from .pubmed import bibliografia
from .redaccion import redactar, PROMPT_DEFECTO
from .utils import log
from .verificacion import verificar_citas


def generar_ficha(tema: str, categoria: list[str], base: str | None = None,
                   extra: list[str] | None = None, n: int = 40,
                   modelo: str = "claude-opus-5", prompt: str | None = None,
                   salida: str = "temas") -> tuple[dict, dict]:
    """Corre el pipeline completo (busqueda + redaccion + verificacion +
    registro en el catalogo) y devuelve (entrada_catalogo, reporte_verificacion).
    """
    extra = extra or []
    prompt_sistema = (
        Path(prompt).read_text(encoding="utf-8")
        if prompt else PROMPT_DEFECTO.read_text(encoding="utf-8")
    )

    log("1/4 topic base")
    base_texto, procedencia = cargar_base(tema, base)

    log("2/4 bibliografia")
    refs = bibliografia(tema, extra, n)
    log(f"    {len(refs)} referencias con metadatos")

    log("3/4 redaccion")
    ficha = redactar(tema, base_texto, procedencia, refs, prompt_sistema, modelo)

    log("4/4 verificacion de citas")
    reporte = verificar_citas(ficha, refs)

    catalogo = Catalogo(Path(salida))
    ficha_ruta, refs_ruta = catalogo.rutas(tema, categoria)
    ficha_ruta.write_text(ficha, encoding="utf-8")
    refs_ruta.write_text(
        json.dumps({"tema": tema, "procedencia": procedencia,
                    "referencias": refs, "verificacion": reporte},
                   ensure_ascii=False, indent=2),
        encoding="utf-8")

    entrada = catalogo.registrar(tema, categoria, procedencia, modelo, extra,
                                  len(refs), ficha_ruta, refs_ruta, reporte)
    return entrada, reporte
