"""Archivo > Nuevo: plantilla vacía, asistente (450 perfil + 425 periodos), deshacer limpio, Guardar como y
reapertura. Sin datos reales. --capturas guarda PNG."""
import sys, os, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import _rutas as _R
from PySide6.QtWidgets import QApplication, QMessageBox, QFileDialog
from PySide6.QtCore import QSettings
tmp = tempfile.mkdtemp()
QSettings.setDefaultFormat(QSettings.IniFormat); QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, tmp)
from horarios.ventana import Planificador
from horarios import xghc, validacion as VAL

app = QApplication.instance() or QApplication(sys.argv); app.setStyle("Fusion")
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
QMessageBox.information = staticmethod(lambda *a, **k: None)
QMessageBox.warning = staticmethod(lambda *a, **k: None)
destino = os.path.join(tmp, "SINT_nuevo.xghc")
QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (destino, ""))
fallos = 0
def check(c, m):
    global fallos
    print(("OK   " if c else "FALLO") + " " + m, flush=True); fallos += (not c)

w = Planificador(); w._no_modal = True; w.resize(1300, 800); w.show(); app.processEvents()
check(not w.a_nuevo.property("proximamente") and w.a_nuevo.shortcut().toString() == "Ctrl+N", "acción Nuevo activa (Ctrl+N)")
vistos = []
ok = w.nuevo(perfil="basico", operar_periodos=lambda d: vistos.append(len(d.filas)))
p = w.proyecto
check(ok and p is not None and p.ruta == "" and not p.modificado, "archivo nuevo sin título y sin modificar")
check(vistos and vistos[0] == 35, f"asistente: 425 con {vistos and vistos[0]} tramos (5 días x 7 periodos)")
check((p.doc.raiz.findtext("otros/perfil") or "") == "primaria", "asistente: perfil 450 aplicado al archivo")
check(not p.profesores and not p.grupos and not p.sesiones and len(p.marcos) >= 1 if hasattr(p, "marcos") else not p.profesores,
      "lista vacías con marco A")
check(not w.pila_deshacer, "sin puntos de deshacer tras el asistente")
check("Sin título" in w.windowTitle(), f"título: {w.windowTitle()}")
n = w.arbol.topLevelItemCount()
check(n == 3, "panel de validación rellenado")
# editar: un profesor
from horarios import edicion as ED
w.editar(lambda arbol: (ED.insertar_hijo(arbol, arbol.raiz.find("profesores"), ED.nuevo("profesor", hijos=[ED.nuevo("nombre", "SINT Profesor 1")])), True)[1]
         if hasattr(ED, "insertar_hijo") else False, "Insertar")
check(w.proyecto.modificado and len(w.proyecto.profesores) == 1, "edición tras Nuevo")
check(w.guardar() and os.path.exists(destino), "Guardar pide nombre y escribe el archivo")
q = xghc.cargar(destino)
check(len(q.profesores) == 1 and q.profesores[0].nombre == "SINT Profesor 1", "el archivo guardado se reabre")
# Ctrl+N con cambios pendientes pide confirmación (respuesta simulada: Sí -> guardar)
w.editar(lambda arbol: (ED.insertar_hijo(arbol, arbol.raiz.find("profesores"), ED.nuevo("profesor", hijos=[ED.nuevo("nombre", "SINT Profesor 2")])), True)[1], "Insertar")
w.a_nuevo.trigger(); app.processEvents()
check(len(xghc.cargar(destino).profesores) == 2 and not w.proyecto.profesores, "Nuevo con cambios: guarda y crea otro vacío")
w.abrir(os.path.join(_R.R, "SINTETICO_grande.xghc")); w.cambiar_lista("profesores")
pdf = w.imprimir_lista(os.path.join(tmp, "lista.pdf"))
check(pdf and open(pdf, "rb").read(5) == b"%PDF-" and os.path.getsize(pdf) > 5000, "Imprimir (Ctrl+P): lista a PDF")
check(not w.a_imprimir.property("proximamente"), "acción Imprimir activa")
if "--capturas" in sys.argv:
    w.grab().save(os.path.join(_R.CAP, "archivo_nuevo.png"))
print("FALLOS:", fallos)
