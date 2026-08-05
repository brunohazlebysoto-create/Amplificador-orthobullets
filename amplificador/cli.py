import argparse
import json
from pathlib import Path

from .catalog import Catalogo
from .orthobullets import cargar_base
from .pubmed import bibliografia
from .redaccion import redactar, PROMPT_DEFECTO
from .utils import log
from .verificacion import verificar_citas


def _categoria_desde_texto(texto: str | None) -> list[str]:
    if not texto:
        return []
    return [c.strip() for c in texto.split("/") if c.strip()]


def _generar(args: argparse.Namespace) -> None:
    prompt_sistema = (
        Path(args.prompt).read_text(encoding="utf-8")
        if args.prompt else PROMPT_DEFECTO.read_text(encoding="utf-8")
    )
    categoria = _categoria_desde_texto(args.categoria)

    log("1/4 topic base")
    base, procedencia = cargar_base(args.tema, args.base)

    log("2/4 bibliografia")
    refs = bibliografia(args.tema, args.extra, args.n)
    log(f"    {len(refs)} referencias con metadatos")

    log("3/4 redaccion")
    ficha = redactar(args.tema, base, procedencia, refs, prompt_sistema, args.modelo)

    log("4/4 verificacion de citas")
    reporte = verificar_citas(ficha, refs)

    catalogo = Catalogo(Path(args.salida))
    ficha_ruta, refs_ruta = catalogo.rutas(args.tema, categoria)
    ficha_ruta.write_text(ficha, encoding="utf-8")
    refs_ruta.write_text(
        json.dumps({"tema": args.tema, "procedencia": procedencia,
                    "referencias": refs, "verificacion": reporte},
                   ensure_ascii=False, indent=2),
        encoding="utf-8")

    entrada = catalogo.registrar(args.tema, categoria, procedencia, args.modelo,
                                  args.extra, len(refs), ficha_ruta, refs_ruta, reporte)

    print(f"\nFicha:    {ficha_ruta}")
    print(f"Refs:     {refs_ruta}")
    print(f"Slug:     {entrada['slug']}  (version {entrada['version']})")
    print(f"Citas:    {len(reporte['citados'])} PMID "
          f"({len(reporte['de_la_bibliografia'])} del set, "
          f"{len(reporte['externos_validos'])} externos validos)")
    print(f"Agregados [+]: {reporte['agregados']}")
    if reporte["inexistentes"]:
        print(f"\n⚠  PMID INEXISTENTES: {', '.join(reporte['inexistentes'])}")
        print("   Revisa y corrige esas afirmaciones antes de usar la ficha.")
    if reporte["sin_referencia"]:
        print(f"⚠  {reporte['sin_referencia']} afirmaciones sin referencia disponible")


def _actualizar(args: argparse.Namespace) -> None:
    catalogo = Catalogo(Path(args.salida))
    entrada = catalogo.buscar(args.slug)
    if not entrada:
        raise SystemExit(f"no existe una ficha con slug '{args.slug}'")
    ns = argparse.Namespace(
        tema=entrada["tema"],
        categoria="/".join(entrada["categoria"]),
        base=args.base,
        extra=args.extra if args.extra is not None else entrada["extra_consultas"],
        n=args.n if args.n is not None else entrada["num_referencias"],
        modelo=args.modelo if args.modelo is not None else entrada["modelo"],
        prompt=args.prompt,
        salida=args.salida,
    )
    _generar(ns)


def _imprimir_nodo(nodo: dict, nivel: int) -> None:
    sangria = "  " * nivel
    for tema in sorted(nodo.get("__temas__", []), key=lambda e: e["tema"]):
        print(f"{sangria}- {tema['tema']}  [{tema['slug']}]  "
              f"(v{tema['version']}, act. {tema['actualizado']})")
    for clave in sorted(k for k in nodo if k != "__temas__"):
        print(f"{sangria}{clave}/")
        _imprimir_nodo(nodo[clave], nivel + 1)


def _listar(args: argparse.Namespace) -> None:
    catalogo = Catalogo(Path(args.salida))
    arbol = catalogo.arbol()
    if not arbol:
        print("(catalogo vacio)")
        return
    _imprimir_nodo(arbol, 0)


def _mover(args: argparse.Namespace) -> None:
    catalogo = Catalogo(Path(args.salida))
    nueva = _categoria_desde_texto(args.categoria)
    catalogo.mover(args.slug, nueva)
    print(f"movido a: {'/'.join(nueva) or '(sin categoria)'}")


def _eliminar(args: argparse.Namespace) -> None:
    catalogo = Catalogo(Path(args.salida))
    catalogo.eliminar(args.slug)
    print(f"eliminado: {args.slug}")


def main() -> None:
    ap = argparse.ArgumentParser(
        prog="amplificador",
        description="Genera fichas medicas pediatricas tipo Orthobullets, "
                     "ampliadas con bibliografia verificada de PubMed.")
    sub = ap.add_subparsers(dest="comando", required=True)

    g = sub.add_parser("generar", help="genera (o regenera) una ficha")
    g.add_argument("tema")
    g.add_argument("--categoria", help="ruta jerarquica, ej. 'Trauma/Extremidad superior'")
    g.add_argument("--base", help="archivo con el topic completo de Orthobullets")
    g.add_argument("--extra", action="append", default=[],
                   help="consulta adicional de PubMed (repetible)")
    g.add_argument("-n", type=int, default=40, dest="n", help="maximo de referencias")
    g.add_argument("--modelo", default="claude-opus-5")
    g.add_argument("--prompt", default=None, help="prompt de sistema alternativo")
    g.add_argument("--salida", default="temas")
    g.set_defaults(func=_generar)

    a = sub.add_parser("actualizar", help="regenera una ficha existente reutilizando sus parametros")
    a.add_argument("slug")
    a.add_argument("--base")
    a.add_argument("--extra", action="append", default=None)
    a.add_argument("-n", type=int, default=None, dest="n")
    a.add_argument("--modelo", default=None)
    a.add_argument("--prompt", default=None)
    a.add_argument("--salida", default="temas")
    a.set_defaults(func=_actualizar)

    l = sub.add_parser("listar", help="muestra el catalogo jerarquico, tipo arbol de Orthobullets")
    l.add_argument("--salida", default="temas")
    l.set_defaults(func=_listar)

    m = sub.add_parser("mover", help="cambia la categoria de una ficha existente")
    m.add_argument("slug")
    m.add_argument("--categoria", required=True)
    m.add_argument("--salida", default="temas")
    m.set_defaults(func=_mover)

    e = sub.add_parser("eliminar", help="elimina una ficha del catalogo")
    e.add_argument("slug")
    e.add_argument("--salida", default="temas")
    e.set_defaults(func=_eliminar)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
