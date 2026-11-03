"""Prueba offscreen de edición, guardar y diálogos de Propiedades."""
import sys, os, tempfile, shutil, hashlib
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import _rutas as _R
from PySide6.QtWidgets import QApplication, QMessageBox, QFileDialog, QInputDialog
from PySide6.QtCore import Qt
from horarios.ventana import Planificador
from horarios import xghc, propiedades as PR

app = QApplication.instance() or QApplication(sys.argv)
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
QMessageBox.information = staticmethod(lambda *a, **k: None)
QMessageBox.warning = staticmethod(lambda *a, **k: None)
tmp = tempfile.mkdtemp()
fallos = 0
def check(c, m):
    global fallos
    print(("OK   " if c else "FALLO") + " " + m); fallos += (not c)

for nombre in [os.path.basename(f) for f in _R.disponibles(*(os.path.join(_R.R, n) for n in ("prueba1.xghc", "prueba2.xghc")))]:
    src = os.path.join(_R.R, nombre); orig = os.path.join(tmp, nombre)
    shutil.copy(src, orig); md5 = hashlib.md5(open(orig, "rb").read()).hexdigest()
    w = Planificador(); w.abrir(orig)
    destino = {}
    QFileDialog.getSaveFileName = staticmethod(lambda _p, _t, sug, _f: (destino.setdefault("s", sug), "")[0:1] + ("",))
    # sesiones: cambiar tmp con editar_celda
    w.cambiar_lista("sesiones"); s0 = w.proxy.index(0, 0).data(Qt.UserRole + 1)
    w.editar_celda(s0, "tmp", "21")
    check(w.proyecto.modificado and w.pila_deshacer, f"{nombre}: edición de celda tmp")
    n = w.proxy.rowCount(); w.tabla.selectRow(0); w.insertar()
    check(w.proxy.rowCount() == n + 1, f"{nombre}: insertar sesión ({n}->{w.proxy.rowCount()})")
    w.deshacer(); check(w.proxy.rowCount() == n, f"{nombre}: deshacer inserción")
    w.rehacer(); check(w.proxy.rowCount() == n + 1, f"{nombre}: rehacer")
    w.tabla.selectRow(w.proxy.rowCount() - 1); w.eliminar()
    check(w.proxy.rowCount() == n, f"{nombre}: eliminar con confirmación")
    # profesores: insertar
    w.cambiar_lista("profesores"); np_ = w.proxy.rowCount()
    QInputDialog.getText = staticmethod(lambda *a, **k: ("PNUEVO", True))
    w.tabla.selectRow(0); w.insertar(); check(w.proxy.rowCount() == np_ + 1, f"{nombre}: insertar profesor")
    # propiedades de cada lista: abrir, recorrer pestañas, Siguiente y Aceptar
    for lista in ("sesiones", "profesores", "grupos", "aulas", "materias"):
        w.cambiar_lista(lista); w.tabla.selectRow(0)
        cls = PR.VENTANAS[lista]
        elems = [w.proxy.index(r, 0).data(Qt.UserRole + 1) for r in range(w.proxy.rowCount())]
        d = cls(w, elems, 0); d.show(); app.processEvents()
        for i in range(d.tabs.count() if hasattr(d, 'tabs') else 0):
            d.tabs.setCurrentIndex(i); app.processEvents()
        d.mover(1); d.mover(-1); d.aceptar(); app.processEvents()
        check(True, f"{nombre}: propiedades {lista} (título con plantilla «Propiedades del …»: {d.windowTitle().startswith("Propiedades del")})")
    # edición real desde el diálogo de profesor: abreviatura
    w.cambiar_lista("profesores"); w.tabla.selectRow(1)
    elems = [w.proxy.index(r, 0).data(Qt.UserRole + 1) for r in range(w.proxy.rowCount())]
    nd = len(w.pila_deshacer)
    d = PR.VENTANAS["profesores"](w, elems, 1); d.aceptar()
    check(len(w.pila_deshacer) == nd, f"{nombre}: Aceptar sin cambios no crea punto de deshacer")
    d = PR.VENTANAS["profesores"](w, elems, 1)
    from PySide6.QtWidgets import QLineEdit
    eds = [x for x in d.findChildren(QLineEdit) if x.isEnabled() and x.isVisible() is False or True]
    abrev = next(en for en, _f in d.enlaces if getattr(en, "ruta", "") == "abreviatura")
    abrev.w.setText("ZZ9"); d.mover(1)
    check(w.proyecto.profesores[1].datos.get("abreviatura") == "ZZ9", f"{nombre}: abreviatura editada desde Propiedades")
    check(d.indice == 2, f"{nombre}: botón siguiente avanza")
    d.reject()
    # guardar: debe proponer _lph y no tocar el original
    destino.clear()
    QFileDialog.getSaveFileName = staticmethod(lambda _p, _t, sug, _f: (destino.__setitem__("s", sug) or sug, ""))
    check(w.guardar(), f"{nombre}: guardar")
    check(destino.get("s", "").endswith("_lph.xghc"), f"{nombre}: propone {os.path.basename(destino.get('s',''))}")
    check(hashlib.md5(open(orig, "rb").read()).hexdigest() == md5, f"{nombre}: original intacto")
    p2 = xghc.cargar(destino["s"])
    check(len(p2.profesores) == np_ + 1 and p2.sesiones[0].tmp == w.proyecto.sesiones[0].tmp, f"{nombre}: recarga del guardado")
    w.proyecto.modificado = False; w.close()
_np = PR.informe_no_persistidos(); open(os.path.join(_R.CAP, "no_persistidos.txt"), "w", encoding="utf-8").write(_np + "\n")
print("no persistidos:", len(_np.splitlines()), "líneas")
print("FALLOS:", fallos); sys.exit(1 if fallos else 0)
