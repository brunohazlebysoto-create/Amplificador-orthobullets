"""Catalogo jerarquico de fichas generadas, al estilo del arbol de
categorias de Orthobullets (especialidad / region / tema)."""

import json
from datetime import datetime
from pathlib import Path

from .utils import slugify

CATALOGO_NOMBRE = "catalogo.json"


def _ruta_categoria(categoria: list[str]) -> Path:
    return Path(*[slugify(c, 40) for c in categoria]) if categoria else Path(".")


class Catalogo:
    def __init__(self, raiz: Path):
        self.raiz = Path(raiz)
        self.raiz.mkdir(parents=True, exist_ok=True)
        self.ruta_json = self.raiz / CATALOGO_NOMBRE
        self.entradas: dict[str, dict] = {}
        if self.ruta_json.exists():
            self.entradas = json.loads(self.ruta_json.read_text(encoding="utf-8"))

    def guardar(self) -> None:
        self.ruta_json.write_text(
            json.dumps(self.entradas, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8")

    def rutas(self, tema: str, categoria: list[str]) -> tuple[Path, Path]:
        slug = slugify(tema)
        carpeta = self.raiz / _ruta_categoria(categoria)
        carpeta.mkdir(parents=True, exist_ok=True)
        return carpeta / f"{slug}.md", carpeta / f"{slug}.refs.json"

    def registrar(self, tema: str, categoria: list[str], procedencia: str,
                   modelo: str, extra: list[str], n_refs: int,
                   ficha_ruta: Path, refs_ruta: Path, verificacion: dict) -> dict:
        slug = slugify(tema)
        ahora = datetime.now().isoformat(timespec="seconds")
        previa = self.entradas.get(slug)
        entrada = {
            "slug": slug,
            "tema": tema,
            "categoria": categoria,
            "archivo": str(ficha_ruta.relative_to(self.raiz)),
            "refs_archivo": str(refs_ruta.relative_to(self.raiz)),
            "procedencia": procedencia,
            "modelo": modelo,
            "extra_consultas": extra,
            "num_referencias": n_refs,
            "citas_inexistentes": len(verificacion.get("inexistentes", [])),
            "agregados": verificacion.get("agregados", 0),
            "creado": previa["creado"] if previa else ahora,
            "actualizado": ahora,
            "version": (previa["version"] + 1) if previa else 1,
        }
        self.entradas[slug] = entrada
        self.guardar()
        return entrada

    def buscar(self, slug: str) -> dict | None:
        return self.entradas.get(slug)

    def mover(self, slug: str, nueva_categoria: list[str]) -> dict:
        entrada = self.entradas.get(slug)
        if not entrada:
            raise KeyError(f"no existe una ficha con slug '{slug}'")
        origen_md = self.raiz / entrada["archivo"]
        origen_refs = self.raiz / entrada["refs_archivo"]
        carpeta_destino = self.raiz / _ruta_categoria(nueva_categoria)
        carpeta_destino.mkdir(parents=True, exist_ok=True)
        destino_md = carpeta_destino / origen_md.name
        destino_refs = carpeta_destino / origen_refs.name
        if origen_md.exists():
            origen_md.replace(destino_md)
        if origen_refs.exists():
            origen_refs.replace(destino_refs)
        entrada["categoria"] = nueva_categoria
        entrada["archivo"] = str(destino_md.relative_to(self.raiz))
        entrada["refs_archivo"] = str(destino_refs.relative_to(self.raiz))
        entrada["actualizado"] = datetime.now().isoformat(timespec="seconds")
        self.guardar()
        return entrada

    def eliminar(self, slug: str) -> None:
        entrada = self.entradas.pop(slug, None)
        if not entrada:
            raise KeyError(f"no existe una ficha con slug '{slug}'")
        for clave in ("archivo", "refs_archivo"):
            ruta = self.raiz / entrada[clave]
            if ruta.exists():
                ruta.unlink()
        self.guardar()

    def arbol(self) -> dict:
        """Estructura anidada {categoria: {..., '__temas__': [entradas]}}."""
        raiz: dict = {}
        for entrada in sorted(self.entradas.values(), key=lambda e: e["tema"]):
            nodo = raiz
            for nivel in entrada["categoria"] or ["Sin categoria"]:
                nodo = nodo.setdefault(nivel, {})
            nodo.setdefault("__temas__", []).append(entrada)
        return raiz
