"""Datos y Planificador: perfil (450), importar (257), periodos (425/426/521/249), horario distinto cada día (448),
varias semanas (622) y asignación semanal (625). Copia temporal de SINTETICO_grande; capturas SINT en app/capturas
si se pasa --capturas."""
import sys, os, tempfile, shutil, hashlib
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import _rutas as _R
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QSettings, Qt
tmp = tempfile.mkdtemp()
QSettings.setDefaultFormat(QSettings.IniFormat); QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, tmp)
from horarios.ventana import Planificador
from horarios import ventana_datos as VD, semanas as SEM, periodos as PER, xghc

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

SRC = os.path.join(_R.R, "SINTETICO_grande.xghc"); h0 = hashlib.md5(open(SRC, "rb").read()).hexdigest()
cp = os.path.join(tmp, "SINTETICO_datos.xghc"); shutil.copy(SRC, cp)
w = Planificador(); w._no_modal = True; w.resize(1300, 800); w.abrir(cp); w.show(); app.processEvents()
raiz = lambda: w.proyecto.doc.raiz

# 1. perfil
d = VD.DialogoPerfil(w, "avanzado"); foto(d, "datos_450_perfil")
check(d.windowTitle() == "Perfil" and d.c[1044].isChecked() and d.c[1060].text().startswith("Conservatorios"), "450: perfil con 4 opciones")
k = w.perfil_aplicacion("basico")
check(k == "basico" and (raiz().findtext("otros/perfil") or "").strip() == "primaria", "perfil básico -> otros/perfil=primaria")
check(QSettings(VD.VENDOR, VD.APP_NAME).value("perfil/actual") == "basico", "perfil guardado en la configuración de la aplicación")
w.perfil_aplicacion("avanzado")

# 2. importar: lista de gestores
d = VD.DialogoImportar(w); foto(d, "datos_257_importar")
g = d.gestores()
check(len(g) == 39 and "RAÍCES - C. de Madrid" in g and "Texto con formato" in g, f"257: {len(g)} gestores del recurso")
ser = w.proyecto.doc.serializar()
check(w.importar_datos("SÉNECA - Andalucía") == "SÉNECA - Andalucía" and w.proyecto.doc.serializar() == ser,
      "importar: un gestor -> próximamente, sin tocar los datos")

# 3. periodos (425 / 426 / 249)
n0 = len(PER.filas(w.proyecto))
def op(dlg):
    foto(dlg, "datos_425_periodos")
    dlg.tabs.setCurrentIndex(1)                         # Lunes
    check(all(dlg.filas[i]["dia"] == 0 for i in dlg.visibles()), "425: pestaña Lunes filtra los periodos")
    dlg.lst.setCurrentItem(dlg.lst.topLevelItem(dlg.lst.topLevelItemCount() - 1))
    dlg.anadir()
    it = dlg.lst.topLevelItem(dlg.lst.topLevelItemCount() - 1); dlg.lst.clearSelection(); it.setSelected(True)
    pd = VD.DialogoPeriodo(dlg, dlg.filas[it.data(0, Qt.UserRole)]); foto(pd, "datos_426_modifica_periodo")
    dlg.modificar({1010: "SINT-P8", 1273: "16", 1274: "00"})
    gr = VD.DialogoRepresentacion(dlg, dlg.filas); foto(gr, "datos_249_representacion")
w.periodos_marco(op)
f2 = PER.filas(w.proyecto)
nuevo = [f for f in f2 if f["clave"] == "SINT-P8"]
check(len(f2) == n0 + 1 and nuevo and nuevo[0]["dia"] == 0 and nuevo[0]["salida"] == "16:00", "periodo añadido y modificado en el lunes")
check(PER.distinto_cada_dia(w.proyecto), "el lunes es ahora distinto")
w.deshacer(); check(len(PER.filas(w.proyecto)) == n0, "deshacer los periodos")

# 4. horario distinto cada día: copiar el lunes (con un periodo más) al martes
def op2(dlg):
    dlg.tabs.setCurrentIndex(1); dlg.anadir()
    dc = VD.DialogoCopiarPeriodos(dlg, "Origen: marco A, Lunes", ["A", "B", "C", "D"], 5); foto(dc, "datos_521_copiar")
    dlg.lst.clearSelection()
    dlg.copiar(destino=("A", [1]))
    dlg.tabs.setCurrentIndex(2); foto(dlg, "datos_448_distinto_martes")
d = VD.DialogoInfo(w, "448"); foto(d, "datos_448_aviso")
w.horario_distinto(op2)
m = w.proyecto.marcos["A"]
lun = sorted((t.entrada, t.salida) for t in m.tramos if t.dia == 0); mar = sorted((t.entrada, t.salida) for t in m.tramos if t.dia == 1)
mie = sorted((t.entrada, t.salida) for t in m.tramos if t.dia == 2)
check(lun == mar and len(mar) == len(mie) + 1, "copiar periodos del lunes al martes; miércoles sin cambios")
w.deshacer()

# 5. varias semanas y asignación semanal
d = VD.DialogoNumSemanas(w, 1); foto(d, "datos_622_semanas")
check(w.numero_semanas(3) == 3 and SEM.num_semanas(raiz()) == 3, "622: tres semanas")
w.cambiar_lista("marco"); app.processEvents(); foto(w, "datos_marco_3_semanas")
check(any(r[1].startswith("s3 ") for _o, r in __import__("horarios.listas", fromlist=["x"]).f_marco(w.proyecto)), "lista del marco con días de s3")
w.cambiar_lista("sesiones"); app.processEvents()
ses = w.proyecto.sesiones[:3]
noms = ["s1", "s2", "s3"]
d = VD.DialogoSemanas(w, noms, [noms, noms, ["s1"]], ["ignorar"] * 3, f"Asignación semanal de {ses[0].materia}")
foto(d, "datos_625_asignacion_semanal")
check(d.c[1074].checkState() == Qt.Checked and d.c[1075].checkState() == Qt.PartiallyChecked and not d.c[1077].isVisible(), "625: casillas sí / varía y solo 3 semanas")
check(w.asignacion_semanal(["s1", "s2"], "obligatorio", sesiones=ses), "asignación semanal aplicada")
xs = [s.xml for s in w.proyecto.sesiones[:3]]
check(all(SEM.de_sesion(x, noms) == (["s1", "s2"], "obligatorio") for x in xs), "enPeriodos s1 s2 + misma posición obligatoria")
col = w.modelo.columnCount() - 1 if hasattr(w, "modelo") else None
filas = __import__("horarios.listas", fromlist=["x"]).f_sesiones(w.proyecto)
check(filas[0][1][-1] == "s1 s2 -", "columna «En semanas»")
print("captura", flush=True); foto(w, "datos_sesiones_en_semanas"); print("ok captura", flush=True)
cp2 = os.path.join(tmp, "SINT_guardado.xghc"); xghc.guardar(w.proyecto, cp2)
if os.path.exists(cp2):
    p2 = xghc.cargar(cp2)
    check(SEM.num_semanas(p2.doc.raiz) == 3 and SEM.de_sesion(p2.sesiones[0].xml, noms)[1] == "obligatorio", "guardado y releído")
check(w.numero_semanas(1) == 1 and SEM.num_semanas(raiz()) == 1 and len(w.proyecto.marcos["A"].dias) == 5, "volver a una semana")
check(hashlib.md5(open(SRC, "rb").read()).hexdigest() == h0, "original intacto")
print(f"\n{fallos} fallos")
