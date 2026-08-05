import time
import xml.etree.ElementTree as ET

import requests

from . import config
from .utils import log

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


def _pausa() -> float:
    # limites de NCBI: 10/s con api key, 3/s sin ella
    return 0.11 if config.ncbi_api_key() else 0.35


def _params(extra: dict) -> dict:
    p = {"db": "pubmed", "retmode": "json"}
    clave = config.ncbi_api_key()
    if clave:
        p["api_key"] = clave
    p.update(extra)
    return p


def buscar_pmids(consulta: str, n: int) -> list[str]:
    r = requests.get(
        f"{EUTILS}/esearch.fcgi",
        params=_params({"term": consulta, "retmax": n, "sort": "relevance"}),
        timeout=30,
    )
    r.raise_for_status()
    time.sleep(_pausa())
    return r.json().get("esearchresult", {}).get("idlist", [])


def detalles(pmids: list[str]) -> list[dict]:
    """Metadatos por esummary + resumen por efetch, en lotes."""
    salida: dict[str, dict] = {}
    for i in range(0, len(pmids), 100):
        lote = pmids[i:i + 100]
        r = requests.get(
            f"{EUTILS}/esummary.fcgi",
            params=_params({"id": ",".join(lote)}),
            timeout=30,
        )
        r.raise_for_status()
        time.sleep(_pausa())
        for pmid, d in r.json().get("result", {}).items():
            if pmid == "uids":
                continue
            salida[pmid] = {
                "pmid": pmid,
                "titulo": d.get("title", "").rstrip("."),
                "revista": d.get("source", ""),
                "anio": (d.get("pubdate") or "")[:4],
                "tipo": ", ".join(d.get("pubtype", [])),
                "resumen": "",
            }

        r = requests.get(
            f"{EUTILS}/efetch.fcgi",
            params={**_params({"id": ",".join(lote)}), "retmode": "xml"},
            timeout=60,
        )
        time.sleep(_pausa())
        try:
            raiz = ET.fromstring(r.content)
        except ET.ParseError:
            continue
        for art in raiz.iter("PubmedArticle"):
            pid = art.findtext(".//PMID")
            partes = [t.text or "" for t in art.iter("AbstractText")]
            if pid in salida:
                salida[pid]["resumen"] = " ".join(partes)[:1800]
    return list(salida.values())


def bibliografia(tema: str, extras: list[str], n: int) -> list[dict]:
    consultas = [
        f"{tema} AND (child[MeSH] OR pediatric*)",
        f"{tema} AND (guideline[pt] OR practice guideline[pt])",
        f"{tema} AND (systematic review[pt] OR meta-analysis[pt])",
        f"{tema} AND randomized controlled trial[pt]",
        f"{tema} AND complications",
    ] + [f"{tema} AND {e}" for e in extras]

    vistos: list[str] = []
    for c in consultas:
        for p in buscar_pmids(c, max(6, n // len(consultas))):
            if p not in vistos:
                vistos.append(p)
    log(f"PubMed: {len(vistos)} PMID unicos en {len(consultas)} consultas")
    refs = detalles(vistos[:n])
    refs.sort(key=lambda d: d["anio"], reverse=True)
    return refs


def formatear_bibliografia(refs: list[dict]) -> str:
    bloques = []
    for r in refs:
        bloques.append(
            f"PMID {r['pmid']} | {r['anio']} | {r['revista']} | {r['tipo']}\n"
            f"{r['titulo']}\n{r['resumen']}"
        )
    return "\n\n---\n\n".join(bloques)
