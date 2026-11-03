"""B1/B2 GUI: DELPHOS desde 257 -> 493 (modo y archivos), deshacer, informe de incidencias y «Cargar los códigos
externas» en las propiedades. Solo archivos SINT (las muestras anon no se abren aquí). --capturas guarda PNG."""
import sys, os, tempfile, shutil
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import _rutas as _R
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QSettings
tmp = tempfile.mkdtemp()
QSettings.setDefaultFormat(QSettings.IniFormat); QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, tmp)
from horarios.ventana import Planificador
from horarios import ventana_datos as VD, propiedades as PR

app = QApplication.instance() or QApplication(sys.argv); app.setStyle("Fusion")
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
QMessageBox.information = staticmethod(lambda *a, **k: None)
QMessageBox.warning = staticmethod(lambda *a, **k: None)
CAPT = "--capturas" in sys.argv; CAP = _R.CAP
fallos = 0
def check(c, m):
    global fallos
    print(("OK   " if c else "FALLO") + " " + m, flush=True); fallos += (not c)
def foto(wdg, nombre):
    if CAPT:
        wdg.show(); app.processEvents(); wdg.grab().save(f"{CAP}/{nombre}.png")

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "datos")
PEN, KRO = os.path.join(D, "delphos_sintetico.xml"), os.path.join(D, "delphos_sintetico_kronowin.xml")
cp = os.path.join(tmp, "SINTETICO_delphos.xghc"); shutil.copy(os.path.join(_R.R, "SINTETICO_grande.xghc"), cp)
w = Planificador(); w._no_modal = True; w.resize(1300, 800); w.abrir(cp); w.show(); app.processEvents()
ser0 = w.proyecto.doc.serializar()

# 493
d = VD.DialogoDelphos(w); d.poner(PEN); d.poner(KRO, True); foto(d, "delphos_493_modo")
check(d.modo() == "nuevo" and len(d.MODOS) == 3 and "Archivo principal" in d.c[1242].text(), "493: tres modos del recurso")

def op(modo, kro=True):
    def f(dlg):
        dlg.poner(PEN)
        if kro:
            dlg.poner(KRO, True)
        dlg.c[{"nuevo": 1045, "actualizar": 1044, "claves": 1046}[modo]].setChecked(True)
    return f

w.validar(silencioso=True)
from horarios import validacion as VAL
def panel():
    a = w.arbol
    return [a.topLevelItem(i).child(j).text(0) for i in range(a.topLevelItemCount()) for j in range(a.topLevelItem(i).childCount())]
def esperado():
    return [m[1] for t in (VAL.AVISO, VAL.ERROR, VAL.INFO) for m in VAL.validar(w.proyecto) if m[0] == t]
msgs0 = panel()
inc = w.importar_delphos(op("nuevo"))
check(w.proyecto.ruta == "" and open(cp, "rb").read() == open(os.path.join(_R.R, "SINTETICO_grande.xghc"), "rb").read(),
      "nuevo: usa Archivo > Nuevo (archivo sin título) y el abierto no se toca")
msgs1 = panel()
check(msgs1 == esperado() and msgs1 != msgs0, f"panel de validación refrescado tras importar ({len(msgs0)} -> {len(msgs1)} mensajes)")
check(inc is not None and not inc.errores and inc.cuentas.get("profesores") == 8, "nuevo: importado sin errores")
check(len(w.proyecto.grupos) == 4 and len(w.proyecto.sesiones) == 19, f"nuevo: {len(w.proyecto.grupos)} grupos, {len(w.proyecto.sesiones)} sesiones")
check("recreo" in w._informe.t.toPlainText(), "informe de incidencias con el recreo propuesto")
foto(w._informe, "delphos_informe")
w.lista_actual = "profesores" if hasattr(w, "lista_actual") else None
foto(w, "delphos_importado")
from horarios import nuevo as NV
w.deshacer()
check(w.proyecto.doc.serializar() == NV.crear().doc.serializar(), "deshacer vuelve al archivo nuevo vacío")
w.rehacer()
check(len(w.proyecto.profesores) == 8, "rehacer reimporta")
inc2 = w.importar_delphos(op("actualizar"))
check(len(w.proyecto.profesores) == 8 and len(w.proyecto.sesiones) == 19, "actualizar: sin duplicados")

# claves (B2)
antes = w.proyecto.doc.serializar()
inc3 = w.importar_delphos(op("claves", kro=False))
check(w.proyecto.doc.serializar() == antes and len(w.proyecto.claves_externas["profesores"]) == 8, "claves: catálogo sin cambiar el XML")
dp = PR.PropiedadesProfesor(w, w.proyecto.profesores, 0)
b = dp.p_id.c[1091]; cb = dp.p_id.c[1072]
check(b.isEnabled() and cb.count() == 9, f"1091 habilitado y combo con {cb.count() - 1} claves")
k = w.proyecto.profesores[0].datos["_xml"].findtext("claveDeExportacion")
check(cb.currentText().split("  ~ ")[0] == k, "la clave actual queda seleccionada")
foto(dp, "delphos_claves_profesor")
dg = PR.PropiedadesGrupo(w, w.proyecto.grupos, 0)
check(dg.p.c[1091].isEnabled() and dg.p.c[1071].count() == 5, "grupo: claves externas")
foto(dg, "delphos_claves_grupo")
w.proyecto.claves_externas = {}
dm = PR.PropiedadesMateria(w, w.proyecto.materias, 0)
check(dm.p.c[1091].isEnabled() and dm.cargar_claves() == 0, "sin catálogo: aviso y nada cargado")
print("FALLOS:", fallos)
