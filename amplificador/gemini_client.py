"""Auditoria bibliografica adversarial via Gemini API.

Gemini nunca se cita como evidencia: solo detecta omisiones, propone
referencias candidatas y senala inconsistencias. Todo lo que devuelve se
considera propuesto y no verificado hasta confirmarlo de forma
independiente (ver amplificador.pubmed).
"""

import json
import sys
import time

import requests

from . import config

API_BASE = "https://generativelanguage.googleapis.com/v1beta"
MODELO_DEFECTO = "gemini-2.5-pro"

INSTRUCCIONES_PRE = """Eres un auditor bibliografico adversarial para una ficha medica \
academica de cirugia pediatrica / ortopedia. Recibiras un inventario parafraseado del \
topic base (cuando exista) y el tema clinico. Tu tarea es EXCLUSIVAMENTE: detectar \
secciones u omisiones de cobertura, identificar evidencia pediatrica reciente que falte, \
proponer guias/metaanalisis/series grandes como candidatos, senalar posibles \
contradicciones con el contenido base, identificar literatura chilena o latinoamericana \
aplicable, y proponer imagenes con licencia abierta. No redactes el documento final. No \
completes datos que no puedas verificar: toda referencia que propongas es un candidato, \
no un hecho confirmado. Responde unicamente con un objeto JSON valido que siga el \
esquema que se te indique en el mensaje del usuario, sin texto fuera del JSON."""

INSTRUCCIONES_POST = """Eres un auditor adversarial revisando el borrador final de una \
ficha medica academica de cirugia pediatrica / ortopedia. Recibiras el borrador completo, \
el inventario del topic base, las referencias ya verificadas y las reglas de citacion. Tu \
tarea es EXCLUSIVAMENTE: identificar elementos del inventario ausentes, secciones \
incompletas, cifras sin cita, controversias sin contrapunto, PMID mal asociados a su \
afirmacion, evidencia adulta presentada como pediatrica sin marcarla, parrafos agregados \
sin la marca [+], aportes [+] no listados en "Que se agrego", inconsistencias entre \
tratamiento y tecnica, complicaciones sin incidencia/factores de riesgo/manejo, \
referencias duplicadas, imagenes sin licencia demostrada, fragmentos telegraficos, \
repeticiones y conclusiones mas firmes que la evidencia citada. No reescribas el \
documento. Responde unicamente con un objeto JSON valido que siga el esquema indicado en \
el mensaje del usuario, sin texto fuera del JSON."""


def _modelos_disponibles(clave: str) -> list[str]:
    r = requests.get(f"{API_BASE}/models", params={"key": clave}, timeout=30)
    r.raise_for_status()
    nombres = []
    for m in r.json().get("models", []):
        if "generateContent" in m.get("supportedGenerationMethods", []):
            nombres.append(m["name"].removeprefix("models/"))
    return nombres


def _elegir_modelo(clave: str) -> str:
    modelo = config.gemini_model() or MODELO_DEFECTO
    try:
        disponibles = _modelos_disponibles(clave)
    except requests.RequestException:
        return modelo
    if not disponibles or modelo in disponibles:
        return modelo
    candidatos = [m for m in disponibles if "pro" in m] or disponibles
    elegido = candidatos[0]
    sys.stderr.write(f"  aviso: modelo Gemini '{modelo}' no disponible, usando '{elegido}'\n")
    return elegido


def auditar(etapa: str, entrada: dict, modelo: str | None = None) -> dict:
    """Ejecuta la auditoria pre o post. Lanza RuntimeError si falla tras un reintento."""
    if etapa not in ("pre", "post"):
        raise ValueError("etapa debe ser 'pre' o 'post'")

    clave = config.gemini_api_key()
    if not clave:
        raise RuntimeError(
            "Falta GEMINI_API_KEY: completala en amplificador/config.py o expórtala "
            "como variable de entorno."
        )

    modelo_usado = modelo or _elegir_modelo(clave)
    instrucciones = INSTRUCCIONES_PRE if etapa == "pre" else INSTRUCCIONES_POST

    cuerpo = {
        "system_instruction": {"parts": [{"text": instrucciones}]},
        "contents": [{"role": "user", "parts": [{"text": json.dumps(entrada, ensure_ascii=False)}]}],
        "generationConfig": {"responseMimeType": "application/json"},
        "tools": [{"google_search": {}}],
    }

    ultimo_error: Exception | None = None
    for intento in range(2):
        try:
            r = requests.post(
                f"{API_BASE}/models/{modelo_usado}:generateContent",
                params={"key": clave},
                json=cuerpo,
                timeout=180,
            )
            r.raise_for_status()
            partes = r.json()["candidates"][0]["content"]["parts"]
            texto = "".join(p.get("text", "") for p in partes)
            resultado = json.loads(texto)
            resultado["_etapa"] = etapa
            resultado["_modelo"] = modelo_usado
            return resultado
        except (requests.RequestException, KeyError, IndexError, ValueError) as e:
            ultimo_error = e
            time.sleep(2)

    raise RuntimeError(f"auditoria Gemini ({etapa}) fallo tras reintento: {ultimo_error}")
