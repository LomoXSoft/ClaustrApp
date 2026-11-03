"""Informes nuevos del Editor: hojas de firmas (aula/alumnos/profesor), hojas de ausencias, equipos docentes por curso,
asignaciones en HTML indexado, alumnos y subgrupos, preferencias del profesorado, y en el diálogo 429 las opciones de
horario completo en una tabla y de reflejar prohibiciones y preferencias. Solo datos SINT-* y copias temporales."""
import sys, os, tempfile, shutil, hashlib, subprocess, re, faulthandler, signal
faulthandler.register(signal.SIGUSR1)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import _rutas as _R
from PySide6.QtWidgets import QApplication, QMessageBox, QFileDialog
from horarios import editor as E, informes as I, informes_ui as IU
from horarios.modelo import PROHIBIDO

app = QApplication.instance() or QApplication(sys.argv)
for n in ("question", "information", "warning"):
    setattr(QMessageBox, n, staticmethod(lambda *a, **k: QMessageBox.Yes))
IU.guardar_por_defecto({})
fallos = 0
def check(c, m):
    global fallos
    print(("OK   " if c else "FALLO") + " " + m); fallos += (not c)
paginas = lambda r: int(re.search(r"Pages:\s+(\d+)", subprocess.run(["pdfinfo", r], capture_output=True, text=True).stdout).group(1))
texto = lambda r: subprocess.run(["pdftotext", "-layout", r, "-"], capture_output=True, text=True).stdout
md5 = lambda r: hashlib.md5(open(r, "rb").read()).hexdigest()

RAIZ = _R.R; SAL = os.path.join(RAIZ, "informes_muestra")
orig = {f: md5(os.path.join(RAIZ, f)) for f in ("SINTETICO_grande.xghc", "SINTETICO_grande.lphr")}
E.VentanaEditor.abrir_planificador = staticmethod(lambda r: None)
tmp = tempfile.mkdtemp(); X = os.path.join(tmp, "S.xghc"); L = os.path.join(tmp, "S.lphr")
shutil.copy(os.path.join(RAIZ, "SINTETICO_grande.xghc"), X); shutil.copy(os.path.join(RAIZ, "SINTETICO_grande.lphr"), L)
w = E.VentanaEditor(L, X); w.show(); app.processEvents(); ed = w.ed; p = ed.p
o = I.opciones(ed.doc, {"centro": "IES SINTÉTICO", "localidad": "Villaprueba"})
dias = len(next(iter(p.marcos.values())).dias)

def pdf(tipo, tablas, nombre=None):
    r = os.path.join(SAL, nombre or f"SINTETICO_grande_{tipo}.pdf"); I.exportar_pdf(tablas, r, o, [X, L]); return r, paginas(r), texto(r)

# hojas de firmas
for tipo, vista in (("firmas_aula", "Aulas"), ("firmas_alumnos", "Grupos"), ("firmas_profesor", "Profesorado")):
    tb = I.tablas_de(ed, tipo, o)
    con = [n for n in ed.elementos(vista) if ed.items_de(vista, n)]
    r, n, tx = pdf(tipo, tb)
    check(tb and all(t.cols[-1] == "Firma" and t.rejilla_lista and t.alto_fila >= 10 for t in tb) and n >= len(tb)
          and "Firma" in tx and "Lunes" in tx, f"{tipo}: {len(tb)} impresos (elemento × día), {n} págs.")
    check(len({t.subtitulo.rsplit(' – ', 1)[0] for t in tb}) <= len(con) + 1, f"{tipo}: un impreso por elemento y día")
# guardias y reuniones en las hojas de firmas del profesor
tb = I.tablas_de(ed, "firmas_profesor", o)
filas = [f for t in tb for f in t.datos]
ng = sum(1 for it in ed.items() if it[0] == "g")
nr = sum(len(ed.integrantes_reunion(ed.obj(it).get("reunion") or ed.obj(it).get("nombre") or "")) for it in ed.items() if it[0] == "r")
check(sum(1 for f in filas if f[1].startswith("GUARDIA")) == ng and ng > 0, f"firmas profesor: {ng} guardias identificadas «GUARDIA …»")
check(sum(1 for f in filas if f[1].startswith("REUNIÓN")) == nr and nr > 0, f"firmas profesor: {nr} asistencias a reuniones «REUNIÓN …»")
check(all(any(f[1] not in ("",) for f in t.datos) for t in tb), "firmas profesor: todas las filas identificadas")
r, n, tx = pdf("firmas_profesor", tb)
check("GUARDIA" in tx and "REUNIÓN" in tx, "firmas profesor (PDF): aparecen GUARDIA y REUNIÓN")
# ausencias
tb = I.tablas_de(ed, "ausencias", o); r, n, tx = pdf("ausencias", tb)
check(len(tb) == dias and "Profesorado de guardia" in tx and "Sustituye" in tx, f"ausencias: {len(tb)} hojas (una por día), {n} págs.")
check(any(f[1] for t in tb for f in t.datos), "ausencias: aparecen profesores de guardia")
# equipos por curso
tb = I.tablas_de(ed, "equipos_curso", o)[0]; r, n, tx = pdf("equipos_curso", [tb])
tot = sum(int(f[5]) for f in tb.datos)
check(tb.datos and "Curso" in tx and "Minutos/semana" in tx, f"equipos por curso: {len(tb.datos)} filas, {tot} min")
# alumnos y subgrupos
tb = I.tablas_de(ed, "alumnos_subgrupos", o)[0]; r, n, tx = pdf("alumnos_subgrupos", [tb])
check(len(tb.datos) == len(p.grupos) and "Nº alumnos" in tx, f"alumnos y subgrupos: {len(tb.datos)} grupos")
# preferencias
tb = I.tablas_de(ed, "preferencias", o)[0]; r, n, tx = pdf("preferencias", [tb])
check(tb.datos and all(int(f[7]) + int(f[8]) == int(f[1]) for f in tb.datos) and "% cumplido" in tx,
      f"preferencias: {len(tb.datos)} profesores, cumplidas+incumplidas = ocupados")
# HTML indexado
d = os.path.join(tmp, "html"); idx = w.asignaciones_html(d)
pags = [f for f in os.listdir(d) if f.startswith("asignaciones_")]
txt = open(idx, encoding="utf-8").read()
check(os.path.exists(idx) and len(pags) >= 1 and all(f"href='{f}'" in txt for f in pags), f"asignaciones HTML: índice y {len(pags)} páginas enlazadas")
QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: tmp)
check(w.asignaciones_html().startswith(os.path.join(tmp, "Asignaciones_HTML")), "asignaciones HTML desde el menú (carpeta propia)")
# menú: los identificadores ya no son «próximamente»
for mid in (33033, 33034, 33072, 33004, 33049, 33080, 33075, 32982):
    a = w.acc.get(mid)
    check(a is not None and a.isEnabled() and "Próximamente" not in a.text(), f"menú {mid} activo")
# 429: tabla completa
oc = dict(o); oc["presentacion"] = "completo"
for tipo in ("alumnos", "profesores", "aulas"):
    tb = I.tablas_de(ed, tipo, oc); r, n, tx = pdf("completo", tb, f"SINTETICO_grande_completo_{tipo}.pdf")
    check(len(tb) == len(p.marcos) and tb[0].cols[1].startswith(o["letreros"]["dias"][0][:2]) and n >= 1,
          f"horario completo {tipo}: {len(tb[0].datos)} filas × {len(tb[0].cols) - 1} periodos, {n} págs.")
d429 = IU.DialogoListadoPDF(w, o); d429.c[1113].setChecked(True); d429.c[1118].setChecked(True)
op = d429.opciones()
check(op["presentacion"] == "completo" and op["prohibiciones"] and d429.c[1113].isEnabled() and d429.c[1118].isEnabled(),
      "429: horario completo en una tabla y prohibiciones activos")
# 429: prohibiciones
op = dict(o); op["prohibiciones"] = True
prof = next((e for e in p.profesores if PROHIBIDO in e.plantilla.values()), None)
if prof is None:
    prof = p.profesores[0]; m0 = next(iter(p.marcos)); prof.plantilla[(m0, 0, p.marcos[m0].filas()[0].indice)] = PROHIBIDO
tb = I.tablas_de(ed, "profesores", op, [prof.nombre])[0]
r, n, tx = pdf("prohibiciones", [tb], "SINTETICO_grande_prohibiciones.pdf")
check(tb.marcas and "prohibido" in tx, f"prohibiciones: {len(tb.marcas)} celdas sombreadas y leyenda")
tb0 = I.tablas_de(ed, "profesores", o, [prof.nombre])[0]
check(not tb0.marcas, "sin la opción no se sombrea")
# combo del 139
d139 = IU.DialogoImprimirListado(w, o)
datos = [d139.c[1004].itemData(i) for i in range(d139.c[1004].count())]
check(all(k in datos for k in ("firmas_aula", "ausencias", "equipos_curso", "preferencias", "alumnos_subgrupos")), "139: nuevos listados en el combo")
w.ed.modificado = False; w._preguntar_proyeccion = False; w.close()
for f, h in orig.items():
    check(md5(os.path.join(RAIZ, f)) == h, f"original intacto: {f}")
print("FALLOS:", fallos); sys.exit(1 if fallos else 0)
