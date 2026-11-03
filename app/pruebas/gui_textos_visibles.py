"""Recorre ventanas, menús y todos los diálogos de recursos buscando textos vacíos o claves sin traducir."""
import os, re, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from PySide6.QtWidgets import QApplication, QAbstractButton, QGroupBox, QLabel, QMenu, QWidget
import _rutas as _R
from horarios import textos
from horarios.textos import DIALOGOS, MENUS_EDITOR

app = QApplication.instance() or QApplication(sys.argv)
fallos = []
CLAVE = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)+$")
claves = set(textos.cargar_paquete(textos.MODO).get("mensajes", {})) if hasattr(textos, "cargar_paquete") else set()


def mirar(t, donde):
    t = (t or "").replace("&", "").strip()
    if CLAVE.match(t) or textos.MODO == "publico" and "_" in t and " " not in t or "{" in t and "}" in t:
        fallos.append(f"{donde}: clave o campo sin formatear: {t!r}")


def recorrer(w: QWidget, donde):
    mirar(w.windowTitle(), donde + " título")
    for c in w.findChildren(QWidget):
        if isinstance(c, (QAbstractButton, QLabel)):
            mirar(c.text(), donde)
        elif isinstance(c, QGroupBox):
            mirar(c.title(), donde)
    for m in w.findChildren(QMenu):
        mirar(m.title(), donde + " menú")
        for a in m.actions():
            mirar(a.text(), donde + " acción")
            if not a.isSeparator() and not a.text().strip() and a.menu() is None and a.isVisible():
                fallos.append(f"{donde}: acción de menú vacía")


from horarios.formrc import PaginaRC
n = 0
for rid in DIALOGOS:
    try:
        p = PaginaRC(rid)
    except Exception as e:
        fallos.append(f"diálogo {rid}: {e}"); continue
    recorrer(p, f"diálogo {rid}"); p.deleteLater(); n += 1
from horarios.ventana import Planificador
w = Planificador()
if _R.hay(_R.R + "/SINTETICO_grande.xghc"):
    w.abrir(_R.R + "/SINTETICO_grande.xghc")
recorrer(w, "planificador")
from horarios.sencilla.ventana import VentanaSencilla
recorrer(VentanaSencilla(nucleo=w), "sencilla")
if _R.hay(_R.R + "/SINTETICO_grande.lphr"):
    from horarios.editor import VentanaEditor
    recorrer(VentanaEditor(_R.R + "/SINTETICO_grande.lphr"), "editor")
for f in fallos[:40]:
    print("FALLO", f)
print(f"modo {textos.MODO}: {n} diálogos recorridos")
print("FALLOS:", len(fallos))
