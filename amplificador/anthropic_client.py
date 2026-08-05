import sys

import requests

from . import config

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


def llamar(system: str, user: str, max_tokens: int,
           con_busqueda: bool = False, modelo: str = "claude-opus-5") -> str:
    clave = config.anthropic_api_key()
    if not clave:
        sys.exit("Falta la clave de Anthropic: completa ANTHROPIC_API_KEY en "
                  "amplificador/config.py o expórtala como variable de entorno.")

    cuerpo = {
        "model": modelo,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    if con_busqueda:
        cuerpo["tools"] = [{"type": "web_search_20250305", "name": "web_search",
                            "max_uses": 8}]

    r = requests.post(
        ANTHROPIC_URL,
        headers={
            "x-api-key": clave,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        },
        json=cuerpo,
        timeout=900,
    )
    if r.status_code != 200:
        sys.exit(f"Error de la API ({r.status_code}): {r.text[:500]}")
    bloques = r.json().get("content", [])
    return "\n".join(b.get("text", "") for b in bloques if b.get("type") == "text")
