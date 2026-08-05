import re
from pathlib import Path

import requests

from .anthropic_client import llamar
from .utils import log


def buscar_url(tema: str) -> str | None:
    """Localiza el topic con la herramienta de busqueda web de la API."""
    r = llamar(
        system="Devuelves solo una URL de orthobullets.com/<seccion>/<id>/<slug>, "
               "sin texto adicional. Si no encuentras el topic, devuelves NINGUNA.",
        user=f"Busca el topic de Orthobullets sobre: {tema}",
        max_tokens=1024,
        con_busqueda=True,
    )
    m = re.search(r"https?://(?:www\.)?orthobullets\.com/\S+/\d+/\S+", r)
    return m.group(0).rstrip(".,)") if m else None


def descargar(url: str) -> tuple[str, str]:
    """Descarga y limpia el HTML publico de un topic. Devuelve (contenido, procedencia).

    Usa esta funcion cuando la URL del topic ya fue localizada por otro medio
    (por ejemplo, WebSearch dentro de un skill de Claude Code) y no hace falta
    volver a buscarla con la herramienta de busqueda de la API de Anthropic.
    """
    try:
        html = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"}).text
    except requests.RequestException as e:
        log(f"no se pudo descargar el topic base: {e}")
        return "", f"sin base (fallo de descarga: {e})"

    texto = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S)
    texto = re.sub(r"<[^>]+>", "\n", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    oculto = texto.count("login to view")
    log(f"base publica: {url} ({oculto} bloques tras login)")
    return texto.strip(), f"version publica de {url} — {oculto} bloques ocultos tras login"


def cargar_base(tema: str, ruta: str | None) -> tuple[str, str]:
    """Devuelve (contenido, procedencia)."""
    if ruta:
        texto = Path(ruta).read_text(encoding="utf-8")
        log(f"base local: {ruta} ({len(texto)} caracteres)")
        return texto, f"archivo local {ruta} (presuntamente version completa)"

    url = buscar_url(tema)
    if not url:
        log("sin topic base — la ficha se construira solo desde literatura")
        return "", "sin base"

    return descargar(url)
