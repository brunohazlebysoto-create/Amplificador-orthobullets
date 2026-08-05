from datetime import date
from pathlib import Path

from .anthropic_client import llamar
from .pubmed import formatear_bibliografia

PROMPT_DEFECTO = Path(__file__).parent / "prompts" / "prompt_sistema.md"


def redactar(tema: str, base: str, procedencia: str, refs: list[dict],
             prompt_sistema: str, modelo: str) -> str:
    user = (
        f"<tema>\n{tema}\n</tema>\n\n"
        f"<base procedencia=\"{procedencia}\">\n{base[:120000]}\n</base>\n\n"
        f"<bibliografia>\n{formatear_bibliografia(refs)}\n</bibliografia>\n\n"
        f"Fecha de elaboracion: {date.today().isoformat()}"
    )
    return llamar(prompt_sistema, user, max_tokens=32000, con_busqueda=True, modelo=modelo)
