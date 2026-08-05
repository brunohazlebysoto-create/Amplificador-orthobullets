import argparse
import json
from pathlib import Path

import requests

from . import gemini_client
from .catalog import Catalogo
from .orthobullets import cargar_base, descargar
from .pipeline import generar_ficha
from .pubmed import bibliografia, buscar_pmids, detalles
from . import server as servidor_web
from .utils import log, slugify
from .verificacion import verificar_citas
from .webview import exportar as exportar_web


def _categoria_desde_texto(texto: str | None) -> list[str]:
    if not texto:
        return []
    return [c.strip() for c in texto.split("/") if c.strip()]


def _generar(args: argparse.Namespace) -> None:
    categoria = _categoria_desde_texto(args.categoria)
    entrada, reporte = generar_ficha(
        args.tema, categoria, base=args.base, extra=args.extra, n=args.n,
        modelo=args.modelo, prompt=args.prompt, salida=args.salida)

    ficha_ruta = Path(args.salida) / entrada["archivo"]
    refs_ruta = Path(args.salida) / entrada["refs_archivo"]

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


def _rutas(args: argparse.Namespace) -> None:
    """Calcula (y crea) las rutas jerarquicas para un tema+categoria, sin escribir nada.

    Pensado para que un skill agentico (ej. Claude Code) sepa exactamente donde
    debe escribir la ficha final y su archivo de referencias antes de redactarlos.
    """
    catalogo = Catalogo(Path(args.salida))
    categoria = _categoria_desde_texto(args.categoria)
    ficha_ruta, refs_ruta = catalogo.rutas(args.tema, categoria)
    print(json.dumps({
        "slug": slugify(args.tema),
        "ficha": str(ficha_ruta),
        "refs": str(refs_ruta),
    }, ensure_ascii=False))


def _pubmed_buscar(args: argparse.Namespace) -> None:
    try:
        ids = buscar_pmids(args.consulta, args.n)
    except requests.exceptions.RequestException as e:
        print(json.dumps({"error": f"no se pudo consultar PubMed: {e}"}, ensure_ascii=False))
        raise SystemExit(1)
    print(json.dumps(ids, ensure_ascii=False))


def _pubmed_detalles(args: argparse.Namespace) -> None:
    try:
        refs = detalles(args.pmids)
    except requests.exceptions.RequestException as e:
        print(json.dumps({"error": f"no se pudo consultar PubMed: {e}"}, ensure_ascii=False))
        raise SystemExit(1)
    print(json.dumps(refs, ensure_ascii=False, indent=2))


def _orthobullets_descargar(args: argparse.Namespace) -> None:
    contenido, procedencia = descargar(args.url)
    print(json.dumps({"contenido": contenido, "procedencia": procedencia}, ensure_ascii=False))


def _gemini_auditar(args: argparse.Namespace) -> None:
    entrada = json.loads(Path(args.input).read_text(encoding="utf-8"))
    try:
        resultado = gemini_client.auditar(args.stage, entrada, modelo=args.modelo)
    except RuntimeError as e:
        Path(args.output).write_text(
            json.dumps({"error": str(e), "_etapa": args.stage}, ensure_ascii=False, indent=2),
            encoding="utf-8")
        print(json.dumps({"estado": "fallida", "error": str(e)}, ensure_ascii=False))
        raise SystemExit(1)
    Path(args.output).write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"estado": "ejecutada", "modelo": resultado.get("_modelo")},
                     ensure_ascii=False))


def _registrar(args: argparse.Namespace) -> None:
    """Registra en el catalogo una ficha que un skill agentico ya escribio en disco."""
    catalogo = Catalogo(Path(args.salida))
    categoria = _categoria_desde_texto(args.categoria)
    ficha_ruta = Path(args.archivo)
    refs_ruta = Path(args.refs)

    refs_data = json.loads(refs_ruta.read_text(encoding="utf-8"))
    refs = refs_data["referencias"] if isinstance(refs_data, dict) and "referencias" in refs_data else refs_data

    texto = ficha_ruta.read_text(encoding="utf-8")
    reporte = verificar_citas(texto, refs)

    entrada = catalogo.registrar(args.tema, categoria, args.procedencia, args.modelo,
                                  args.extra or [], len(refs), ficha_ruta, refs_ruta, reporte)
    print(json.dumps({"entrada": entrada, "verificacion": reporte}, ensure_ascii=False, indent=2))


def _exportar_web(args: argparse.Namespace) -> None:
    raiz = Path(args.salida)
    destino = Path(args.destino) if args.destino else raiz / "index.html"
    ruta = exportar_web(raiz, destino)
    n = len(Catalogo(raiz).entradas)
    print(f"Pagina generada: {ruta} ({n} fichas)")


def _servir(args: argparse.Namespace) -> None:
    servidor_web.ejecutar(Path(args.salida), host=args.host, puerto=args.puerto)


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

    # --- subcomandos de bajo nivel, pensados para que un skill agentico ---
    # --- (ej. Claude Code) los invoque como building blocks, en vez de   ---
    # --- reimplementar busqueda/verificacion/catalogacion por su cuenta. ---

    r = sub.add_parser("rutas", help="calcula las rutas de archivo para tema+categoria en el catalogo")
    r.add_argument("tema")
    r.add_argument("--categoria")
    r.add_argument("--salida", default="temas")
    r.set_defaults(func=_rutas)

    pb = sub.add_parser("pubmed-buscar", help="busca PMID en PubMed (esearch, solo IDs)")
    pb.add_argument("consulta")
    pb.add_argument("-n", type=int, default=20, dest="n")
    pb.set_defaults(func=_pubmed_buscar)

    pd = sub.add_parser("pubmed-detalles", help="obtiene metadatos y resumen de PMID especificos")
    pd.add_argument("pmids", nargs="+")
    pd.set_defaults(func=_pubmed_detalles)

    od = sub.add_parser("orthobullets-descargar",
                        help="descarga y limpia el HTML publico de una URL de topic ya localizada")
    od.add_argument("--url", required=True)
    od.set_defaults(func=_orthobullets_descargar)

    ga = sub.add_parser("gemini-auditar", help="ejecuta una auditoria bibliografica (pre/post) con Gemini")
    ga.add_argument("--stage", required=True, choices=["pre", "post"])
    ga.add_argument("--input", required=True, help="archivo JSON con el contexto para Gemini")
    ga.add_argument("--output", required=True, help="donde escribir la respuesta JSON de Gemini")
    ga.add_argument("--modelo", default=None)
    ga.set_defaults(func=_gemini_auditar)

    rg = sub.add_parser("registrar", help="registra en el catalogo una ficha ya escrita en disco")
    rg.add_argument("tema")
    rg.add_argument("--categoria")
    rg.add_argument("--archivo", required=True, help="ruta de la ficha .md ya escrita")
    rg.add_argument("--refs", required=True, help="ruta del .refs.json ya escrito")
    rg.add_argument("--procedencia", default="")
    rg.add_argument("--modelo", default="claude-code (skill ficha-medica-orthobullets)")
    rg.add_argument("--extra", action="append", default=None)
    rg.add_argument("--salida", default="temas")
    rg.set_defaults(func=_registrar)

    ew = sub.add_parser("exportar-web",
                        help="genera una pagina HTML autocontenida para navegar el catalogo")
    ew.add_argument("--salida", default="temas", help="carpeta del catalogo (catalogo.json)")
    ew.add_argument("--destino", default=None, help="ruta del HTML de salida (default: <salida>/index.html)")
    ew.set_defaults(func=_exportar_web)

    sv = sub.add_parser("servir",
                        help="levanta un servidor local con formulario para pedir fichas nuevas")
    sv.add_argument("--salida", default="temas", help="carpeta del catalogo (catalogo.json)")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--puerto", type=int, default=8420)
    sv.set_defaults(func=_servir)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
