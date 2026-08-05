import re
import sys
import unicodedata


def slugify(texto: str, max_len: int = 60) -> str:
    limpio = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    limpio = re.sub(r"[^a-zA-Z0-9]+", "-", limpio).strip("-").lower()
    return limpio[:max_len] or "tema"


def log(msg: str) -> None:
    print(f"  {msg}", file=sys.stderr)
