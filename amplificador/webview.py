"""Exporta el catalogo de fichas a una pagina web unica y autocontenida.

No depende de un servidor: todos los datos quedan embebidos como JSON en el
propio HTML, asi que el archivo resultante se puede abrir directamente con
doble clic o publicarse como esta. Se regenera cada vez que corres
`python -m amplificador exportar-web`.
"""

import json
import re
from pathlib import Path

import markdown as _markdown

from .catalog import Catalogo

_CITA_RE = re.compile(r"\[(\d{7,8})\]")
_AGREGADO_RE = re.compile(r"(?<![\w\[])\[\+\]")


def _marcar_citas_y_aportes(texto_md: str) -> str:
    """Convierte [PMID] y [+] en HTML inline antes de pasar por markdown."""
    texto_md = _CITA_RE.sub(
        r'<a class="cita" href="https://pubmed.ncbi.nlm.nih.gov/\1/" '
        r'target="_blank" rel="noopener">\1</a>',
        texto_md,
    )
    texto_md = _AGREGADO_RE.sub(
        '<span class="agregado" title="Contenido agregado, no proviene del topic base">+</span>',
        texto_md,
    )
    return texto_md


def _renderizar(texto_md: str) -> str:
    marcado = _marcar_citas_y_aportes(texto_md)
    return _markdown.markdown(marcado, extensions=["tables", "fenced_code", "sane_lists"])


def _cargar_refs(refs_ruta: Path) -> dict:
    if not refs_ruta.exists():
        return {}
    try:
        data = json.loads(refs_ruta.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if isinstance(data, dict):
        return data
    return {"referencias": data}


def construir_datos(raiz: Path) -> dict:
    catalogo = Catalogo(raiz)
    fichas = []
    for entrada in sorted(catalogo.entradas.values(), key=lambda e: e["tema"]):
        ficha_ruta = raiz / entrada["archivo"]
        refs_ruta = raiz / entrada["refs_archivo"]
        texto_md = ficha_ruta.read_text(encoding="utf-8") if ficha_ruta.exists() else ""
        refs_data = _cargar_refs(refs_ruta)
        verificacion = refs_data.get("verificacion", {})
        fichas.append({
            "slug": entrada["slug"],
            "tema": entrada["tema"],
            "categoria": entrada["categoria"],
            "version": entrada["version"],
            "actualizado": entrada["actualizado"],
            "creado": entrada["creado"],
            "procedencia": entrada.get("procedencia", ""),
            "modelo": entrada.get("modelo", ""),
            "numReferencias": entrada.get("num_referencias", 0),
            "citasInexistentes": entrada.get("citas_inexistentes",
                                              len(verificacion.get("inexistentes", []))),
            "citasNoVerificables": entrada.get("citas_no_verificables",
                                                len(verificacion.get("no_verificables_por_red", []))),
            "agregados": entrada.get("agregados", verificacion.get("agregados", 0)),
            "html": _renderizar(texto_md),
        })
    return {"fichas": fichas}


_PLANTILLA = """<!doctype html>
<meta charset="utf-8">
<title>__TITULO__</title>
<style>
:root{
  --bg:#f5f6f3; --panel:#ffffff; --ink:#16211e; --muted:#5b6560; --line:#dce1db;
  --accent:#2a6f6b; --accent-strong:#0f4c46; --amber:#8a5a1a; --amber-bg:#f4e6cd;
  --danger:#b5502e; --danger-bg:#f8e4dc; --good:#3f7d4f; --good-bg:#e2efe2;
  --radius:10px;
  --serif: ui-serif, "Iowan Old Style", "Palatino Linotype", Georgia, "Times New Roman", serif;
  --sans: ui-sans-serif, "Segoe UI", "Helvetica Neue", Arial, sans-serif;
  --mono: ui-monospace, "SF Mono", "Cascadia Code", Consolas, monospace;
}
@media (prefers-color-scheme: dark){
  :root{
    --bg:#12181a; --panel:#182220; --ink:#e7ece8; --muted:#94a199; --line:#2a3532;
    --accent:#4fb3a6; --accent-strong:#7bcfc2; --amber:#d9a24e; --amber-bg:#3a2f18;
    --danger:#e08a6b; --danger-bg:#3a241c; --good:#6fbf7f; --good-bg:#1e2f22;
  }
}
:root[data-theme="dark"]{
  --bg:#12181a; --panel:#182220; --ink:#e7ece8; --muted:#94a199; --line:#2a3532;
  --accent:#4fb3a6; --accent-strong:#7bcfc2; --amber:#d9a24e; --amber-bg:#3a2f18;
  --danger:#e08a6b; --danger-bg:#3a241c; --good:#6fbf7f; --good-bg:#1e2f22;
}
:root[data-theme="light"]{
  --bg:#f5f6f3; --panel:#ffffff; --ink:#16211e; --muted:#5b6560; --line:#dce1db;
  --accent:#2a6f6b; --accent-strong:#0f4c46; --amber:#8a5a1a; --amber-bg:#f4e6cd;
  --danger:#b5502e; --danger-bg:#f8e4dc; --good:#3f7d4f; --good-bg:#e2efe2;
}
*{box-sizing:border-box;}
html,body{margin:0;padding:0;}
body{
  background:var(--bg); color:var(--ink); font-family:var(--sans);
  font-size:15px; line-height:1.55; -webkit-font-smoothing:antialiased;
}
a{color:var(--accent-strong);}
.shell{display:flex; min-height:100vh;}
.sidebar{
  width:300px; min-width:300px; border-right:1px solid var(--line);
  background:var(--panel); display:flex; flex-direction:column;
  height:100vh; position:sticky; top:0; overflow:hidden;
}
.sidebar__head{padding:20px 18px 14px; border-bottom:1px solid var(--line);}
.sidebar__head h1{
  font-family:var(--serif); font-size:1.25rem; font-weight:600; margin:0 0 2px;
  text-wrap:balance; color:var(--accent-strong);
}
.sidebar__head p{margin:0; font-size:.78rem; color:var(--muted); letter-spacing:.02em;}
.search{
  margin:12px 18px 6px; padding:8px 10px; border:1px solid var(--line);
  border-radius:var(--radius); background:var(--bg); color:var(--ink);
  font-family:var(--sans); font-size:.85rem; width:calc(100% - 36px);
}
.search:focus{outline:2px solid var(--accent); outline-offset:1px;}
.tree{overflow-y:auto; padding:8px 10px 24px; flex:1;}
.tree__group{margin-bottom:2px;}
.tree__label{
  display:flex; align-items:center; gap:6px; padding:7px 8px; border-radius:8px;
  font-size:.78rem; text-transform:uppercase; letter-spacing:.06em; color:var(--muted);
  cursor:pointer; user-select:none;
}
.tree__label:hover{background:var(--bg);}
.tree__children{margin-left:14px; border-left:1px solid var(--line); padding-left:10px;}
.tree__item{
  display:block; padding:7px 10px; border-radius:8px; font-size:.88rem; color:var(--ink);
  cursor:pointer; text-decoration:none; line-height:1.3;
}
.tree__item:hover{background:var(--bg);}
.tree__item.active{background:var(--accent); color:#fff;}
.tree__item .ver{
  display:block; font-size:.72rem; color:var(--muted); font-family:var(--mono);
  font-variant-numeric:tabular-nums; margin-top:1px;
}
.tree__item.active .ver{color:rgba(255,255,255,.8);}
.main{flex:1; min-width:0; overflow-y:auto; height:100vh;}
.main__inner{max-width:800px; margin:0 auto; padding:40px 32px 80px;}
.empty{max-width:800px; margin:0 auto; padding:60px 32px; color:var(--muted); font-family:var(--serif); font-size:1.1rem;}
.chips{display:flex; flex-wrap:wrap; gap:8px; margin-bottom:24px;}
.chip{
  display:inline-flex; align-items:center; gap:5px; padding:4px 10px; border-radius:999px;
  font-size:.74rem; font-weight:600; letter-spacing:.02em; border:1px solid var(--line);
  color:var(--muted); background:var(--panel);
}
.chip.chip--good{color:var(--good); background:var(--good-bg); border-color:transparent;}
.chip.chip--warn{color:var(--danger); background:var(--danger-bg); border-color:transparent;}
.chip.chip--amber{color:var(--amber); background:var(--amber-bg); border-color:transparent;}
article h1{
  font-family:var(--serif); font-size:1.9rem; text-wrap:balance; margin:0 0 6px;
  color:var(--ink);
}
article h2{
  font-family:var(--serif); font-size:1.3rem; margin:2em 0 .6em; padding-top:.3em;
  border-top:1px solid var(--line); color:var(--accent-strong);
}
article h3{font-family:var(--serif); font-size:1.08rem; margin:1.6em 0 .5em;}
article p{margin:0 0 1em; max-width:68ch;}
article ul,article ol{margin:0 0 1em; padding-left:1.3em;}
article li{margin-bottom:.3em;}
article strong{color:var(--ink);}
article table{border-collapse:collapse; margin:0 0 1.4em; font-size:.86rem; display:block; overflow-x:auto;}
article th,article td{border:1px solid var(--line); padding:7px 10px; text-align:left; vertical-align:top;}
article th{background:var(--bg); font-weight:600; white-space:nowrap;}
article code{font-family:var(--mono); font-size:.85em; background:var(--bg); padding:1px 5px; border-radius:4px;}
a.cita{
  font-family:var(--mono); font-variant-numeric:tabular-nums; font-size:.78em;
  color:var(--amber); background:var(--amber-bg); padding:1px 5px; border-radius:5px;
  text-decoration:none; white-space:nowrap;
}
a.cita:hover{text-decoration:underline;}
span.agregado{
  display:inline-flex; align-items:center; justify-content:center; width:15px; height:15px;
  border-radius:4px; background:var(--accent); color:#fff; font-size:.7rem; font-weight:700;
  margin-right:3px; vertical-align:middle;
}
@media (max-width:820px){
  .shell{flex-direction:column;}
  .sidebar{width:100%; min-width:0; height:auto; position:relative; max-height:44vh;}
  .main{height:auto;}
}
</style>
<div class="shell">
  <nav class="sidebar">
    <div class="sidebar__head">
      <h1>Amplificador Orthobullets</h1>
      <p>__CONTADOR__ fichas en el catalogo</p>
    </div>
    <input class="search" type="search" id="buscador" placeholder="Buscar tema...">
    <div class="tree" id="arbol"></div>
  </nav>
  <main class="main">
    <div class="main__inner" id="contenido"></div>
  </main>
</div>
<script>
const FICHAS = __DATA_JSON__;

function agrupar(fichas){
  const raiz = {};
  for(const f of fichas){
    let nodo = raiz;
    const ruta = f.categoria && f.categoria.length ? f.categoria : ["Sin categoria"];
    for(const nivel of ruta){
      nodo.hijos = nodo.hijos || {};
      nodo.hijos[nivel] = nodo.hijos[nivel] || {};
      nodo = nodo.hijos[nivel];
    }
    nodo.temas = nodo.temas || [];
    nodo.temas.push(f);
  }
  return raiz;
}

function pintarNodo(nodo, contenedor, filtro){
  if(nodo.temas){
    const temas = nodo.temas
      .filter(f => !filtro || f.tema.toLowerCase().includes(filtro))
      .sort((a,b) => a.tema.localeCompare(b.tema));
    for(const f of temas){
      const a = document.createElement("a");
      a.href = "#" + f.slug;
      a.className = "tree__item";
      a.dataset.slug = f.slug;
      a.innerHTML = f.tema + '<span class="ver">v' + f.version + ' &middot; ' + f.actualizado.slice(0,10) + '</span>';
      a.addEventListener("click", (e) => { e.preventDefault(); mostrar(f.slug); });
      contenedor.appendChild(a);
    }
  }
  if(nodo.hijos){
    for(const clave of Object.keys(nodo.hijos).sort()){
      const hijo = nodo.hijos[clave];
      const tieneCoincidencia = filtro ? contieneCoincidencia(hijo, filtro) : true;
      if(!tieneCoincidencia) continue;
      const grupo = document.createElement("div");
      grupo.className = "tree__group";
      const etiqueta = document.createElement("div");
      etiqueta.className = "tree__label";
      etiqueta.textContent = clave;
      const hijos = document.createElement("div");
      hijos.className = "tree__children";
      grupo.appendChild(etiqueta);
      grupo.appendChild(hijos);
      contenedor.appendChild(grupo);
      pintarNodo(hijo, hijos, filtro);
    }
  }
}

function contieneCoincidencia(nodo, filtro){
  if(nodo.temas && nodo.temas.some(f => f.tema.toLowerCase().includes(filtro))) return true;
  if(nodo.hijos) return Object.values(nodo.hijos).some(h => contieneCoincidencia(h, filtro));
  return false;
}

function repintarArbol(){
  const filtro = document.getElementById("buscador").value.trim().toLowerCase();
  const cont = document.getElementById("arbol");
  cont.innerHTML = "";
  pintarNodo(agrupar(FICHAS), cont, filtro);
  const activo = document.querySelector(".tree__item.active");
  if(!activo && filtro === "") return;
}

function chip(texto, variante){
  return '<span class="chip' + (variante ? ' chip--' + variante : '') + '">' + texto + '</span>';
}

function mostrar(slug){
  const f = FICHAS.find(x => x.slug === slug);
  const cont = document.getElementById("contenido");
  if(!f){
    cont.innerHTML = '<div class="empty">Ficha no encontrada.</div>';
    return;
  }
  document.querySelectorAll(".tree__item").forEach(el => el.classList.toggle("active", el.dataset.slug === slug));

  const chips = [];
  chips.push(chip((f.categoria && f.categoria.length ? f.categoria.join(" / ") : "Sin categoria")));
  chips.push(chip("v" + f.version + " &middot; " + f.actualizado.slice(0,10)));
  chips.push(chip(f.numReferencias + " referencias", "amber"));
  if(f.citasInexistentes > 0){
    chips.push(chip(f.citasInexistentes + " PMID inexistentes", "warn"));
  } else if(f.citasNoVerificables > 0){
    chips.push(chip(f.citasNoVerificables + " PMID sin verificar (sin red)", "amber"));
  } else {
    chips.push(chip("citas verificadas", "good"));
  }
  if(f.agregados > 0) chips.push(chip(f.agregados + " aportes [+]"));

  cont.innerHTML =
    '<div class="chips">' + chips.join("") + '</div>' +
    '<article>' + f.html + '</article>';
  window.location.hash = slug;
  window.scrollTo(0,0);
  cont.scrollTop = 0;
}

document.getElementById("buscador").addEventListener("input", repintarArbol);
repintarArbol();

const inicial = window.location.hash.replace("#", "");
if(inicial && FICHAS.some(f => f.slug === inicial)){
  mostrar(inicial);
} else if(FICHAS.length){
  document.getElementById("contenido").innerHTML =
    '<div class="empty">Elige un tema del panel izquierdo para verlo aqui.</div>';
} else {
  document.getElementById("contenido").innerHTML =
    '<div class="empty">El catalogo todavia no tiene fichas. Genera una con '
    + '<code>python -m amplificador generar</code> o el skill '
    + '<code>/ficha-medica-orthobullets</code>, despues corre '
    + '<code>python -m amplificador exportar-web</code> de nuevo.</div>';
}
</script>
"""


def generar_pagina(raiz: Path) -> str:
    datos = construir_datos(raiz)
    data_json = json.dumps(datos["fichas"], ensure_ascii=False).replace("</script>", "<\\/script>")
    html = _PLANTILLA.replace("__DATA_JSON__", data_json)
    html = html.replace("__TITULO__", "Amplificador Orthobullets — catalogo")
    html = html.replace("__CONTADOR__", str(len(datos["fichas"])))
    return html


def exportar(raiz: Path, destino: Path) -> Path:
    html = generar_pagina(raiz)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(html, encoding="utf-8")
    return destino
