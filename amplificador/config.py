"""Configuracion del pipeline.

Uso privado: completa las claves directamente aqui abajo. Si las dejas
vacias, se usan las variables de entorno ANTHROPIC_API_KEY / NCBI_API_KEY
como respaldo. Este archivo se sube al repositorio junto con el resto del
codigo, asi que si el repositorio deja de ser privado en algun momento hay
que rotar las claves antes.
"""

import os

ANTHROPIC_API_KEY = ""  # pega aqui tu clave sk-ant-...
NCBI_API_KEY = ""       # opcional: eleva el limite de NCBI de 3 a 10 solicitudes/segundo


def anthropic_api_key() -> str:
    return ANTHROPIC_API_KEY or os.environ.get("ANTHROPIC_API_KEY", "")


def ncbi_api_key() -> str:
    return NCBI_API_KEY or os.environ.get("NCBI_API_KEY", "")
