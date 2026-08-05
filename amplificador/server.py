"""Servidor web local: navega el catalogo y dispara generacion real de fichas.

Uso:
    python -m amplificador servir
    (abre http://127.0.0.1:8420)

Solo escucha en localhost por defecto: el formulario "Nueva ficha" dispara
llamadas reales (con costo) a la API de Anthropic y a PubMed. No lo expongas
a una red compartida sin agregarle autenticacion primero.
"""

import json
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from .catalog import Catalogo
from .pipeline import generar_ficha
from .utils import log, registrar_en
from .webview import _renderizar

_JOBS: dict[str, dict] = {}
_JOBS_LOCK = threading.Lock()


def _iniciar_job(raiz: Path, tema: str, categoria: list[str], extra: list[str],
                  n: int, modelo: str) -> str:
    job_id = uuid.uuid4().hex[:12]
    job = {
        "id": job_id, "tema": tema, "estado": "en_progreso",
        "log": [], "error": None, "entrada": None, "creado": time.time(),
    }
    with _JOBS_LOCK:
        _JOBS[job_id] = job

    def _correr() -> None:
        registrar_en(job["log"])
        try:
            entrada, reporte = generar_ficha(
                tema, categoria, extra=extra, n=n, modelo=modelo, salida=str(raiz))
            job["entrada"] = entrada
            job["reporte"] = reporte
            job["estado"] = "listo"
        except SystemExit as e:
            job["error"] = str(e.code) if e.code else "fallo desconocido"
            job["estado"] = "error"
        except Exception as e:  # noqa: BLE001 - se reporta al usuario, no se oculta
            job["error"] = f"{type(e).__name__}: {e}"
            job["estado"] = "error"
        finally:
            registrar_en(None)

    threading.Thread(target=_correr, daemon=True).start()
    return job_id


def _catalogo_json(raiz: Path) -> list[dict]:
    catalogo = Catalogo(raiz)
    salida = []
    for e in catalogo.entradas.values():
        salida.append({
            "slug": e["slug"], "tema": e["tema"], "categoria": e["categoria"],
            "version": e["version"], "actualizado": e["actualizado"],
            "numReferencias": e.get("num_referencias", 0),
            "citasInexistentes": e.get("citas_inexistentes", 0),
            "citasNoVerificables": e.get("citas_no_verificables", 0),
            "agregados": e.get("agregados", 0),
        })
    return salida


def _ficha_json(raiz: Path, slug: str) -> dict | None:
    catalogo = Catalogo(raiz)
    entrada = catalogo.buscar(slug)
    if not entrada:
        return None
    ficha_ruta = raiz / entrada["archivo"]
    texto = ficha_ruta.read_text(encoding="utf-8") if ficha_ruta.exists() else ""
    datos = dict(entrada)
    datos["html"] = _renderizar(texto)
    return datos


def _crear_handler(raiz: Path):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # silencia el log por defecto de http.server
            pass

        def _json(self, data: dict, status: int = 200) -> None:
            cuerpo = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)

        def _html(self, texto: str, status: int = 200) -> None:
            cuerpo = texto.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)

        def do_GET(self) -> None:  # noqa: N802 - nombre fijado por BaseHTTPRequestHandler
            partes = urlparse(self.path)
            qs = parse_qs(partes.query)

            if partes.path == "/":
                self._html(_PAGINA)
            elif partes.path == "/api/catalogo":
                self._json({"fichas": _catalogo_json(raiz)})
            elif partes.path == "/api/ficha":
                slug = (qs.get("slug") or [""])[0]
                datos = _ficha_json(raiz, slug)
                if datos is None:
                    self._json({"error": "no encontrada"}, status=404)
                else:
                    self._json(datos)
            elif partes.path == "/api/estado":
                job_id = (qs.get("job") or [""])[0]
                with _JOBS_LOCK:
                    job = _JOBS.get(job_id)
                if not job:
                    self._json({"error": "job no encontrado"}, status=404)
                else:
                    self._json({
                        "estado": job["estado"], "log": job["log"],
                        "error": job["error"], "entrada": job["entrada"],
                    })
            else:
                self._json({"error": "not found"}, status=404)

        def do_POST(self) -> None:  # noqa: N802
            partes = urlparse(self.path)
            if partes.path != "/api/generar":
                self._json({"error": "not found"}, status=404)
                return

            largo = int(self.headers.get("Content-Length", 0))
            crudo = self.rfile.read(largo) if largo else b"{}"
            try:
                body = json.loads(crudo.decode("utf-8"))
            except json.JSONDecodeError:
                self._json({"error": "JSON invalido"}, status=400)
                return

            tema = (body.get("tema") or "").strip()
            if not tema:
                self._json({"error": "falta el tema"}, status=400)
                return
            categoria = [c.strip() for c in (body.get("categoria") or "").split("/") if c.strip()]
            extra = [e.strip() for e in (body.get("extra") or "").split(",") if e.strip()]
            try:
                n = int(body.get("n") or 40)
            except (TypeError, ValueError):
                n = 40
            modelo = (body.get("modelo") or "claude-opus-5").strip()

            job_id = _iniciar_job(raiz, tema, categoria, extra, n, modelo)
            self._json({"job_id": job_id})

    return Handler


_PAGINA = """<!doctype html>
<meta charset="utf-8">
<title>Amplificador Orthobullets</title>
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
*{box-sizing:border-box;}
html,body{margin:0;padding:0;}
body{background:var(--bg); color:var(--ink); font-family:var(--sans); font-size:15px; line-height:1.55;}
a{color:var(--accent-strong);}
.shell{display:flex; min-height:100vh;}
.sidebar{width:320px; min-width:320px; border-right:1px solid var(--line); background:var(--panel);
  display:flex; flex-direction:column; height:100vh; position:sticky; top:0; overflow:hidden;}
.sidebar__head{padding:20px 18px 14px; border-bottom:1px solid var(--line);}
.sidebar__head h1{font-family:var(--serif); font-size:1.2rem; font-weight:600; margin:0 0 2px; color:var(--accent-strong);}
.sidebar__head p{margin:0; font-size:.76rem; color:var(--muted);}
.btn{
  display:inline-flex; align-items:center; justify-content:center; gap:6px; width:100%;
  padding:9px 12px; margin:12px 18px 0; border-radius:var(--radius); border:1px solid var(--accent);
  background:var(--accent); color:#fff; font-weight:600; font-size:.85rem; cursor:pointer;
  width:calc(100% - 36px);
}
.btn:hover{background:var(--accent-strong); border-color:var(--accent-strong);}
.btn--ghost{background:transparent; color:var(--accent-strong); border-color:var(--line);}
.search{margin:10px 18px 6px; padding:8px 10px; border:1px solid var(--line); border-radius:var(--radius);
  background:var(--bg); color:var(--ink); font-size:.85rem; width:calc(100% - 36px);}
.tree{overflow-y:auto; padding:8px 10px 24px; flex:1;}
.tree__label{padding:7px 8px; font-size:.76rem; text-transform:uppercase; letter-spacing:.06em; color:var(--muted);}
.tree__children{margin-left:14px; border-left:1px solid var(--line); padding-left:10px;}
.tree__item{display:block; padding:7px 10px; border-radius:8px; font-size:.87rem; color:var(--ink);
  cursor:pointer; text-decoration:none; line-height:1.3;}
.tree__item:hover{background:var(--bg);}
.tree__item.active{background:var(--accent); color:#fff;}
.tree__item .ver{display:block; font-size:.71rem; color:var(--muted); font-family:var(--mono); margin-top:1px;}
.tree__item.active .ver{color:rgba(255,255,255,.8);}
.main{flex:1; min-width:0; overflow-y:auto; height:100vh;}
.main__inner{max-width:800px; margin:0 auto; padding:40px 32px 80px;}
.empty{max-width:800px; margin:0 auto; padding:60px 32px; color:var(--muted); font-family:var(--serif); font-size:1.1rem;}
.chips{display:flex; flex-wrap:wrap; gap:8px; margin-bottom:24px;}
.chip{display:inline-flex; align-items:center; gap:5px; padding:4px 10px; border-radius:999px; font-size:.74rem;
  font-weight:600; border:1px solid var(--line); color:var(--muted); background:var(--panel);}
.chip.chip--good{color:var(--good); background:var(--good-bg); border-color:transparent;}
.chip.chip--warn{color:var(--danger); background:var(--danger-bg); border-color:transparent;}
.chip.chip--amber{color:var(--amber); background:var(--amber-bg); border-color:transparent;}
article h1{font-family:var(--serif); font-size:1.9rem; margin:0 0 6px;}
article h2{font-family:var(--serif); font-size:1.3rem; margin:2em 0 .6em; padding-top:.3em;
  border-top:1px solid var(--line); color:var(--accent-strong);}
article p{margin:0 0 1em; max-width:68ch;}
article ul,article ol{margin:0 0 1em; padding-left:1.3em;}
article table{border-collapse:collapse; margin:0 0 1.4em; font-size:.86rem; display:block; overflow-x:auto;}
article th,article td{border:1px solid var(--line); padding:7px 10px; text-align:left;}
article th{background:var(--bg); font-weight:600;}
a.cita{font-family:var(--mono); font-size:.78em; color:var(--amber); background:var(--amber-bg);
  padding:1px 5px; border-radius:5px; text-decoration:none;}
span.agregado{display:inline-flex; align-items:center; justify-content:center; width:15px; height:15px;
  border-radius:4px; background:var(--accent); color:#fff; font-size:.7rem; font-weight:700; margin-right:3px;}
.hidden{display:none !important;}
.overlay{position:fixed; inset:0; background:rgba(10,14,12,.5); display:flex; align-items:flex-start;
  justify-content:center; padding:60px 20px; z-index:10;}
.modal{background:var(--panel); border-radius:14px; border:1px solid var(--line); width:100%; max-width:460px;
  padding:22px 24px; box-shadow:0 20px 60px rgba(0,0,0,.25);}
.modal h2{font-family:var(--serif); margin:0 0 4px; font-size:1.2rem;}
.modal p.hint{color:var(--muted); font-size:.82rem; margin:0 0 18px;}
.field{margin-bottom:14px;}
.field label{display:block; font-size:.78rem; font-weight:600; margin-bottom:4px; color:var(--muted);}
.field input{width:100%; padding:8px 10px; border:1px solid var(--line); border-radius:8px;
  background:var(--bg); color:var(--ink); font-size:.88rem;}
.field input:focus{outline:2px solid var(--accent); outline-offset:1px;}
.modal__actions{display:flex; gap:10px; margin-top:18px;}
.modal__actions .btn{margin:0;}
.progreso{margin-top:16px; border-top:1px solid var(--line); padding-top:14px;}
.progreso pre{background:var(--bg); border-radius:8px; padding:10px; font-family:var(--mono); font-size:.76rem;
  max-height:160px; overflow-y:auto; margin:8px 0 0; white-space:pre-wrap;}
.error{color:var(--danger); font-size:.85rem; margin-top:10px;}
@media (max-width:820px){ .shell{flex-direction:column;} .sidebar{width:100%; min-width:0; height:auto; max-height:44vh;} .main{height:auto;} }
</style>
<div class="shell">
  <nav class="sidebar">
    <div class="sidebar__head">
      <h1>Amplificador Orthobullets</h1>
      <p id="contador">cargando catalogo...</p>
    </div>
    <button class="btn" id="btnNueva">+ Nueva ficha</button>
    <input class="search" type="search" id="buscador" placeholder="Buscar tema...">
    <div class="tree" id="arbol"></div>
  </nav>
  <main class="main">
    <div class="main__inner" id="contenido"></div>
  </main>
</div>

<div class="overlay hidden" id="overlay">
  <div class="modal">
    <h2>Generar una ficha nueva</h2>
    <p class="hint">Corre el pipeline real: busca el topic base, arma bibliografia verificada en PubMed y redacta con la API de Anthropic. Puede tardar uno o dos minutos.</p>
    <div id="formulario">
      <div class="field"><label>Tema clinico</label><input id="fTema" type="text" placeholder="fractura supracondilea de humero en ninos"></div>
      <div class="field"><label>Categoria (opcional)</label><input id="fCategoria" type="text" placeholder="Trauma/Extremidad superior"></div>
      <div class="field"><label>Consultas extra de PubMed (opcional, separadas por coma)</label><input id="fExtra" type="text" placeholder="pediatric MRI, Chile"></div>
      <div class="field"><label>Maximo de referencias</label><input id="fN" type="number" value="40" min="5" max="100"></div>
      <div class="modal__actions">
        <button class="btn" id="btnGenerar">Generar</button>
        <button class="btn btn--ghost" id="btnCancelar">Cancelar</button>
      </div>
      <div class="error hidden" id="errorForm"></div>
    </div>
    <div class="progreso hidden" id="progreso">
      <strong id="progresoTitulo">Generando...</strong>
      <pre id="progresoLog"></pre>
      <div class="modal__actions">
        <button class="btn btn--ghost" id="btnCerrarProgreso">Cerrar</button>
      </div>
    </div>
  </div>
</div>

<script>
let FICHAS = [];

async function cargarCatalogo(){
  const r = await fetch("/api/catalogo");
  const d = await r.json();
  FICHAS = d.fichas;
  document.getElementById("contador").textContent = FICHAS.length + " fichas en el catalogo";
  repintarArbol();
}

function agrupar(fichas){
  const raiz = {};
  for(const f of fichas){
    let nodo = raiz;
    const ruta = f.categoria && f.categoria.length ? f.categoria : ["Sin categoria"];
    for(const nivel of ruta){ nodo.hijos = nodo.hijos || {}; nodo.hijos[nivel] = nodo.hijos[nivel] || {}; nodo = nodo.hijos[nivel]; }
    nodo.temas = nodo.temas || []; nodo.temas.push(f);
  }
  return raiz;
}

function contieneCoincidencia(nodo, filtro){
  if(nodo.temas && nodo.temas.some(f => f.tema.toLowerCase().includes(filtro))) return true;
  if(nodo.hijos) return Object.values(nodo.hijos).some(h => contieneCoincidencia(h, filtro));
  return false;
}

function pintarNodo(nodo, contenedor, filtro){
  if(nodo.temas){
    const temas = nodo.temas.filter(f => !filtro || f.tema.toLowerCase().includes(filtro)).sort((a,b)=>a.tema.localeCompare(b.tema));
    for(const f of temas){
      const a = document.createElement("a");
      a.href = "#" + f.slug; a.className = "tree__item"; a.dataset.slug = f.slug;
      a.innerHTML = f.tema + '<span class="ver">v' + f.version + ' &middot; ' + f.actualizado.slice(0,10) + '</span>';
      a.addEventListener("click", (e) => { e.preventDefault(); mostrar(f.slug); });
      contenedor.appendChild(a);
    }
  }
  if(nodo.hijos){
    for(const clave of Object.keys(nodo.hijos).sort()){
      const hijo = nodo.hijos[clave];
      if(filtro && !contieneCoincidencia(hijo, filtro)) continue;
      const grupo = document.createElement("div");
      const etiqueta = document.createElement("div"); etiqueta.className = "tree__label"; etiqueta.textContent = clave;
      const hijos = document.createElement("div"); hijos.className = "tree__children";
      grupo.appendChild(etiqueta); grupo.appendChild(hijos); contenedor.appendChild(grupo);
      pintarNodo(hijo, hijos, filtro);
    }
  }
}

function repintarArbol(){
  const filtro = document.getElementById("buscador").value.trim().toLowerCase();
  const cont = document.getElementById("arbol"); cont.innerHTML = "";
  pintarNodo(agrupar(FICHAS), cont, filtro);
}

function chip(texto, variante){ return '<span class="chip' + (variante?' chip--'+variante:'') + '">' + texto + '</span>'; }

async function mostrar(slug){
  document.querySelectorAll(".tree__item").forEach(el => el.classList.toggle("active", el.dataset.slug === slug));
  const cont = document.getElementById("contenido");
  cont.innerHTML = '<div class="empty">Cargando...</div>';
  const r = await fetch("/api/ficha?slug=" + encodeURIComponent(slug));
  if(!r.ok){ cont.innerHTML = '<div class="empty">Ficha no encontrada.</div>'; return; }
  const f = await r.json();
  const chips = [
    chip((f.categoria && f.categoria.length ? f.categoria.join(" / ") : "Sin categoria")),
    chip("v" + f.version + " &middot; " + f.actualizado.slice(0,10)),
    chip((f.num_referencias || 0) + " referencias", "amber"),
  ];
  if(f.citas_inexistentes > 0) chips.push(chip(f.citas_inexistentes + " PMID inexistentes", "warn"));
  else if(f.citas_no_verificables > 0) chips.push(chip(f.citas_no_verificables + " PMID sin verificar (sin red)", "amber"));
  else chips.push(chip("citas verificadas", "good"));
  if(f.agregados > 0) chips.push(chip(f.agregados + " aportes [+]"));
  cont.innerHTML = '<div class="chips">' + chips.join("") + '</div><article>' + f.html + '</article>';
  window.location.hash = slug;
  cont.scrollTop = 0;
}

document.getElementById("buscador").addEventListener("input", repintarArbol);

const overlay = document.getElementById("overlay");
const formulario = document.getElementById("formulario");
const progreso = document.getElementById("progreso");
const progresoLog = document.getElementById("progresoLog");
const errorForm = document.getElementById("errorForm");

document.getElementById("btnNueva").addEventListener("click", () => {
  overlay.classList.remove("hidden");
  formulario.classList.remove("hidden");
  progreso.classList.add("hidden");
  errorForm.classList.add("hidden");
});
document.getElementById("btnCancelar").addEventListener("click", () => overlay.classList.add("hidden"));
document.getElementById("btnCerrarProgreso").addEventListener("click", () => { overlay.classList.add("hidden"); cargarCatalogo(); });

document.getElementById("btnGenerar").addEventListener("click", async () => {
  const tema = document.getElementById("fTema").value.trim();
  errorForm.classList.add("hidden");
  if(!tema){ errorForm.textContent = "Escribe un tema."; errorForm.classList.remove("hidden"); return; }
  const body = {
    tema, categoria: document.getElementById("fCategoria").value.trim(),
    extra: document.getElementById("fExtra").value.trim(),
    n: parseInt(document.getElementById("fN").value, 10) || 40,
  };
  const r = await fetch("/api/generar", { method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body) });
  const d = await r.json();
  if(!r.ok || d.error){ errorForm.textContent = d.error || "No se pudo iniciar la generacion."; errorForm.classList.remove("hidden"); return; }

  formulario.classList.add("hidden");
  progreso.classList.remove("hidden");
  document.getElementById("progresoTitulo").textContent = "Generando \\"" + tema + "\\"...";
  progresoLog.textContent = "";

  const poll = setInterval(async () => {
    const rr = await fetch("/api/estado?job=" + d.job_id);
    const dd = await rr.json();
    progresoLog.textContent = (dd.log || []).join("\\n");
    progresoLog.scrollTop = progresoLog.scrollHeight;
    if(dd.estado === "listo"){
      clearInterval(poll);
      document.getElementById("progresoTitulo").textContent = "Lista: " + tema;
      await cargarCatalogo();
      if(dd.entrada) mostrar(dd.entrada.slug);
    } else if(dd.estado === "error"){
      clearInterval(poll);
      document.getElementById("progresoTitulo").textContent = "Fallo la generacion";
      progresoLog.textContent += "\\n\\nERROR: " + dd.error;
    }
  }, 1500);
});

cargarCatalogo().then(() => {
  const inicial = window.location.hash.replace("#", "");
  if(inicial) mostrar(inicial);
  else document.getElementById("contenido").innerHTML = '<div class="empty">Elige un tema del panel izquierdo, o generá uno nuevo con "+ Nueva ficha".</div>';
});
</script>
"""


def ejecutar(raiz: Path, host: str = "127.0.0.1", puerto: int = 8420) -> None:
    servidor = ThreadingHTTPServer((host, puerto), _crear_handler(raiz))
    print(f"Amplificador Orthobullets sirviendo en http://{host}:{puerto}  (Ctrl+C para detener)",
          file=sys.stderr)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        servidor.server_close()
