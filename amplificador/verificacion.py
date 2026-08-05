import re

from .pubmed import detalles


def verificar_citas(texto: str, refs: list[dict]) -> dict:
    citados = sorted(set(re.findall(r"\[(\d{7,8})\]", texto)))
    conocidos = {r["pmid"] for r in refs}
    por_revisar = [p for p in citados if p not in conocidos]

    validos, invalidos = [], []
    if por_revisar:
        encontrados = {d["pmid"] for d in detalles(por_revisar)}
        validos = [p for p in por_revisar if p in encontrados]
        invalidos = [p for p in por_revisar if p not in encontrados]

    return {
        "citados": citados,
        "de_la_bibliografia": [p for p in citados if p in conocidos],
        "externos_validos": validos,
        "inexistentes": invalidos,
        "sin_referencia": texto.count("[sin referencia disponible]"),
        "agregados": texto.count("[+]"),
    }
