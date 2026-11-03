"""Prueba offscreen de «Pesos de los criterios de optimización» (persistencia en <criterios> y efecto en el motor).
Trabaja sobre copias temporales; los originales no se tocan (md5). Guarda captura en capturas/criterios.png."""
import sys, os, tempfile, shutil, hashlib, faulthandler
faulthandler.dump_traceback_later(60, exit=True)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import _rutas as _R
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QSettings
tmp = tempfile.mkdtemp()
QSettings.setDefaultFormat(QSettings.IniFormat); QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, tmp)
from horarios.ventana import Planificador
from horarios import criterios as CR, edicion as ED, xghc
from horarios.motor import problema, cpsat
app = QApplication.instance() or QApplication(sys.argv)
for f in ("question",): setattr(QMessageBox, f, staticmethod(lambda *a, **k: QMessageBox.Yes))
QMessageBox.information = staticmethod(lambda *a, **k: None); QMessageBox.warning = staticmethod(lambda *a, **k: None)
fallos = 0
def check(c, m):
    global fallos
    print(("OK   " if c else "FALLO") + " " + m); fallos += (not c)
CAP = os.environ.get("CAPTURAS", _R.CAPG)
ORIG = _R.disponibles(os.path.join(_R.R, "prueba1.xghc"), os.path.join(_R.R, "SINTETICO_grande.xghc"))
md5 = {p: hashlib.md5(open(p, "rb").read()).hexdigest() for p in ORIG}
for src in ORIG:
    nombre = os.path.basename(src); cp = os.path.join(tmp, nombre); shutil.copy(src, cp)
    w = Planificador(); w.abrir(cp)
    pes0 = problema.construir(w.proyecto)["pesos"]
    d = CR.DialogoCriterios(w); d.show(); app.processEvents()
    check(len(d.sl) == 20, f"{nombre}: 20 deslizadores")
    check(all(d.sl[k].value() == pes0.get(k, d.sl[k].value()) for k in d.sl), f"{nombre}: valores leídos = pesos del motor")
    if "SINT" in nombre:
        os.makedirs(CAP, exist_ok=True); d.grab().save(os.path.join(CAP, "criterios.png"))
    d.sl["masClasesEnUnDiaQueEnOtro"].setValue(7); d.sl["huecosEnGrupos"].setValue(9); d.sl["ordenProfesores"].setValue(0)
    nd = len(w.pila_deshacer); d.aceptar()
    check(len(w.pila_deshacer) == nd + 1, f"{nombre}: cambio deshacible")
    r = w.proyecto.doc.raiz
    check(ED.leer(r, "criterios/horarioDeProfesores/masClasesEnUnDiaQueEnOtro") == "7", f"{nombre}: etiqueta real escrita")
    g = cp[:-5] + "_g.xghc"; w._escribir(g); p2 = xghc.cargar(g); pes = problema.construir(p2)["pesos"]
    check(pes["masClasesEnUnDiaQueEnOtro"] == 7 and pes["huecosEnGrupos"] == 9 and pes["ordenProfesores"] == 0,
          f"{nombre}: ida y vuelta por archivo hasta pb['pesos']")
    d2 = CR.DialogoCriterios(w); d2.poner(CR.DEFECTO)
    check(d2.valores() == {k: CR.DEFECTO[k] for k in d2.sl}, f"{nombre}: valores por defecto")
    w.deshacer(); check(problema.construir(w.proyecto)["pesos"]["masClasesEnUnDiaQueEnOtro"] == pes0["masClasesEnUnDiaQueEnOtro"],
                        f"{nombre}: deshacer restaura")
    w.proyecto.modificado = False; w.close()
# efecto en el motor: equilibrio de carga diaria 0 frente a 10
p = xghc.cargar(ORIG[0]); cat = "carga_desigual"; res = {}
for v in (0, 10):
    pb = problema.construir(p); pb["pesos"]["masClasesEnUnDiaQueEnOtro"] = v
    e = cpsat.resolver(pb, segundos=15, hilos=4, semilla=1)["estadisticas"]; res[v] = e["resumen"].get(cat, 0)
check(res[0] == 0 and res[10] > 0, f"motor: categoría solo con peso>0 ({res})")
check(all(hashlib.md5(open(q, "rb").read()).hexdigest() == md5[q] for q in ORIG), "originales intactos")
print("FALLOS:", fallos); sys.exit(1 if fallos else 0)
