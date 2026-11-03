"""B3 GUI: asistente de exportación sincronizada a DELPHOS en el editor (211 -> 749 -> 144 -> 425 -> 689 -> 361 -> 205).
Copia SINT de SINTETICO_grande con claves SINT. --capturas guarda PNG de cada paso."""
import sys, os, tempfile, shutil
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import _rutas as _R
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt
from horarios import editor as E, xghc, edicion as ED, delphos as DL, delphos_salida as DS, editor_delphos as EDL

app = QApplication.instance() or QApplication(sys.argv); app.setStyle("Fusion")
for k in ("information", "warning"):
    setattr(QMessageBox, k, staticmethod(lambda *a, **kw: None))
CAPT = "--capturas" in sys.argv; CAP = _R.CAP
F = 0
def check(c, m):
    global F
    print(("OK   " if c else "FALLO"), m, flush=True); F += (not c)
def foto(w, n):
    if CAPT:
        w.show(); app.processEvents(); w.grab().save(f"{CAP}/{n}.png"); w.hide()

T = tempfile.mkdtemp()
for f in ("SINTETICO_grande.xghc", "SINTETICO_grande.lphr"):
    shutil.copy(f"{_R.R}/{f}", T)
X, R = os.path.join(T, "SINTETICO_grande.xghc"), os.path.join(T, "SINTETICO_grande.lphr")
p = xghc.cargar(X); a = ED.Arbol(p.doc.raiz); r = p.doc.raiz
for lista, tag, base in (("profesores", "profesor", 9000), ("grupos", "grupo", 3000), ("materias", "materia", 5000),
                         ("aulas", "aula", 7000), ("tareas", "tarea", 100)):
    for i, e in enumerate(r.find(lista).findall(tag)):
        ED.escribir(a, e, "claveDeExportacion", str(base + i))
        if tag == "profesor" and i:                 # al primero le falta la toma de posesión (mensaje en rojo)
            ED.escribir(a, e, "tomaDePosesion", "01/09/2020")
ED.escribir(a, ED.insertar_elemento(a, "tareas", "JD"), "claveDeExportacion", "199")
xghc.guardar(p, X)
w = E.VentanaEditor(R, X); w._no_modal = True; w.resize(1200, 800); w.show(); app.processEvents()
check(w.acc[32815].isEnabled() and w.acc[33017].isEnabled(), "menú: otros programas e importar códigos externos")
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "datos", "delphos_sintetico.xml")
check(w.importar_claves_externas(D) and len(w.catalogo_delphos["profesores"]) == 8, "importar claves externas (SINT)")
w.catalogo_delphos = None
primero = sorted(x.findtext("nombre") for x in r.find("profesores").findall("profesor"))[0]
estado = {}

def operar(i, d):
    if i == 0:
        check(d.c[EDL.GESTOR_DELPHOS].isChecked() and not d.c[1124].isEnabled() and d.c[1006].isChecked(),
              "211: DELPHOS elegido, el resto próximamente, clave externa")
        d.c[1010].setText(os.path.join(T, "Horario.xml")); foto(d, "delphos_exp_1_gestor")
    elif i == 1:
        check(d.c[1494].text().endswith("Sin comprobar"), "749: sin catálogo")
        d.a.cargar_catalogo(d, D); d.actualizar()
        check("Precaución" in d.c[1494].text() or "Errores" in d.c[1494].text(), f"749 con claves de otro centro: {d.c[1494].text()}")
        foto(d, "delphos_exp_2_semaforo"); d.a.tr.catalogo = {}
    elif i == 2:
        check(d.tm.count() >= 1 and d.td.count() == 5 and "=" in d.res.text(), "144: claves de periodos por marco y día")
        d.td.setCurrentIndex(1); foto(d, "delphos_exp_3_periodos"); d.c[1016].setChecked(False)
    elif i == 3:
        n = d.l.topLevelItemCount()
        check(n > 50, f"425: {n} profesores con horario")
        d.marcar(False); check(not d.validar(), "425: hay que elegir alguno"); d.marcar(True)
        foto(d, "delphos_exp_4_profesores")
    elif i == 4:
        check(d.sem == DS.ROJO and any(m.nombre == primero and "posesión" in m.texto for m in d.ms), "689: rojo por F_TOMAPOS")
        check(not d.validar(), "689: no deja continuar en rojo")
        foto(d, "delphos_exp_5_mensajes")
        # la toma de posesión se corrige en el planificador: aquí se simula en la configuración cargada
        d.a.tr.x["profesores"][primero].append(ED.nuevo("tomaDePosesion", "01/09/2021"))
        d.a.op.anno = "2026"; d.llenar()
        check(d.sem != DS.ROJO, f"689: sin rojos tras corregir ({d.sem})")
        estado["sem"] = d.sem
    elif i == 5:
        check(d.c[1000].text() == "L", "361: claves de los días del archivo"); foto(d, "delphos_exp_6_dias")
    elif i == 6:
        d.c[1011].setText("2026"); d.c[1115].setText("8/9/2026")
        check(not d.validar(), "205: valida DD/MM/AAAA"); d.c[1115].setText("08/09/2026"); d.c[1116].setText("22/06/2027")
        foto(d, "delphos_exp_7_fechas")

ruta = w.transferir_externa(operar)
check(ruta and os.path.exists(ruta), "Horario.xml escrito")
inc = DL.Incidencias(); x = DL.leer(ruta, inc)
check(not inc.lineas and int(x["secciones"]["EMP"] and len(x["secciones"]["EMP"])) > 0, "envoltorio coherente")
txt = open(ruta, encoding="iso-8859-1").read()
check('dato="C_ANNO">2026' in txt and 'F_INICIO">08/09/2026' in txt, "fechas en el archivo")
print("FALLOS:", F)
