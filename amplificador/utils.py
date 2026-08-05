import re
import sys
import threading
import unicodedata

_registro_local = threading.local()


def slugify(texto: str, max_len: int = 60) -> str:
    limpio = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    limpio = re.sub(r"[^a-zA-Z0-9]+", "-", limpio).strip("-").lower()
    return limpio[:max_len] or "tema"


def log(msg: str) -> None:
    print(f"  {msg}", file=sys.stderr)
    buffer = getattr(_registro_local, "buffer", None)
    if buffer is not None:
        buffer.append(msg)


def registrar_en(buffer: list | None) -> None:
    """Ademas de stderr, cada log() de este hilo se agrega a `buffer`.

    Pensado para que el servidor web capture el progreso de un job en
    background sin tocar cada llamada a log() individualmente.
    """
    _registro_local.buffer = buffer
