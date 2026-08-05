import re

import requests

from .pubmed import detalles


def verificar_citas(texto: str, refs: list[dict]) -> dict:
    citados = sorted(set(re.findall(r"\[(\d{7,8})\]", texto)))
    conocidos = {r["pmid"] for r in refs}
    por_revisar = [p for p in citados if p not in conocidos]

    validos, invalidos, no_verificables = [], [], []
    if por_revisar:
        try:
            encontrados = {d["pmid"] for d in detalles(por_revisar)}
            validos = [p for p in por_revisar if p in encontrados]
            invalidos = [p for p in por_revisar if p not in encontrados]
        except requests.exceptions.RequestException:
            # No se pudo consultar PubMed: no sabemos si existen, asi que no
            # se marcan como inexistentes (seria una afirmacion falsa).
            no_verificables = list(por_revisar)

    return {
        "citados": citados,
        "de_la_bibliografia": [p for p in citados if p in conocidos],
        "externos_validos": validos,
        "inexistentes": invalidos,
        "no_verificables_por_red": no_verificables,
        "sin_referencia": texto.count("[sin referencia disponible]"),
        "agregados": texto.count("[+]"),
    }
