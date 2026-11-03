"""Ventana de la versión sencilla. Comparte el núcleo (Planificador) con la versión clásica: mismo proyecto,
misma pila de deshacer y mismo archivo; alternar es mostrar una ventana u otra, sin convertir nada."""
import os
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QAction
from PySide6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QListWidget, QListWidgetItem,
                               QStackedWidget, QMessageBox, QFileDialog, QLabel)
from .. import APP_NAME, __version__
from . import textos as T
from .estilo import CSS
from .comun import btn, fila_botones
from .pasos_datos import PasoCentro, PasoProfesorado, PasoGrupos, PasoMaterias, PasoPreferencias, PasoGuardias
from .pasos_horario import PasoGenerar, PasoRevisar, PasoInformes, ruta_resultado
from . import selector

CLASES = [PasoCentro, PasoProfesorado, PasoGrupos, PasoMaterias, PasoPreferencias, PasoGuardias,
          PasoGenerar, PasoRevisar, PasoInformes]


class VentanaSencilla(QMainWindow):
    def __init__(self, nucleo=None):
        super().__init__()
        if nucleo is None:
            from ..ventana import Planificador
            nucleo = Planificador()
        self.nucleo = nucleo; nucleo.sencilla = self
        self.editor = None
        self.setObjectName("sencilla"); self.setStyleSheet(CSS); self.resize(1200, 780)
        cen = QWidget(); cen.setObjectName("sencilla"); self.setCentralWidget(cen)
        h = QHBoxLayout(cen); h.setContentsMargins(0, 0, 0, 0); h.setSpacing(0)
        self.lst = QListWidget(); self.lst.setObjectName("pasos"); self.lst.setFixedWidth(250); h.addWidget(self.lst)
        der = QWidget(); dv = QVBoxLayout(der); dv.setContentsMargins(0, 0, 0, 10); h.addWidget(der, 1)
        self.pila = QStackedWidget(); dv.addWidget(self.pila, 1)
        self.pasos = []
        for i, C in enumerate(CLASES):
            w = C(self); self.pasos.append(w); self.pila.addWidget(w)
            self.lst.addItem(QListWidgetItem(f"{i + 1}. {T.PASOS[i][1]}"))
        self.b_mas = btn("Más opciones…", lambda: self.paso_actual().mas_opciones(), enlace=True)
        self.b_ant = btn("← Anterior", lambda: self.ir(self.lst.currentRow() - 1))
        self.b_sig = btn("Siguiente →", lambda: self.ir(self.lst.currentRow() + 1), primario=True)
        bar = fila_botones(self.b_mas, None, self.b_ant, self.b_sig); bar.setContentsMargins(24, 0, 24, 0); dv.addLayout(bar)
        self.lst.currentRowChanged.connect(self._cambio_paso)
        self._menus()
        self.lst.setCurrentRow(0)
        self.titulo()

    # ------------------------------------------------------------------ menús
    def _menus(self):
        mb = self.menuBar()
        A = lambda t, f, k=None: self._acc(t, f, k)
        m = mb.addMenu("&Archivo")
        for a in (A("&Nuevo", lambda: self.nuevo(), "Ctrl+N"), A("&Abrir…", lambda: self.abrir(), "Ctrl+O"),
                  A("&Guardar", lambda: self.guardar(), "Ctrl+S"), A("Guardar &como…", lambda: self.guardar_como()), None,
                  A("&Salir", self.close)):
            m.addSeparator() if a is None else m.addAction(a)
        m = mb.addMenu("&Editar")
        self.a_desh = A("&Deshacer", lambda: self.deshacer(), "Ctrl+Z"); self.a_reh = A("&Rehacer", lambda: self.rehacer(), "Ctrl+Y")
        m.addAction(self.a_desh); m.addAction(self.a_reh)
        m = mb.addMenu("&Ver"); mv = m.addMenu("Versión")
        self.a_ver_sencilla = mv.addAction("Versión sencilla"); self.a_ver_sencilla.setCheckable(True); self.a_ver_sencilla.setChecked(True)
        self.a_ver_clasica = mv.addAction("Versión clásica", lambda: self.cambiar_version("clasica"))
        m = mb.addMenu("A&yuda")
        m.addAction(A("Glosario", lambda: QMessageBox.information(self, "Glosario", "\n\n".join(f"{k}: {v}" for k, v in T.GLOSARIO.items()))))
        m.addAction(A("Acerca de…", lambda: QMessageBox.about(self, APP_NAME, f"{APP_NAME} {__version__}\nVersión sencilla")))

    def _acc(self, t, f, k=None):
        a = QAction(t, self); a.triggered.connect(lambda _=False: f())
        if k:
            a.setShortcut(QKeySequence(k))
        return a

    # ------------------------------------------------------------------ núcleo
    @property
    def p(self):
        return self.nucleo.proyecto

    def editar(self, fn, desc=""):
        if self.p is None:
            self.nucleo.nuevo(asistente=False)
        ok = self.nucleo.editar(fn, desc)
        self.refrescar(); self.titulo()
        return ok

    def deshacer(self):
        if self.lst.currentRow() == 7 and self.editor:
            return self.pasos[7].deshacer()
        self.nucleo.deshacer(); self.refrescar(); self.titulo()

    def rehacer(self):
        if self.lst.currentRow() == 7 and self.editor:
            return self.pasos[7].rehacer()
        self.nucleo.rehacer(); self.refrescar(); self.titulo()

    def estado(self, t):
        self.statusBar().showMessage(t, 6000)

    def titulo(self):
        p = self.p
        nombre = os.path.basename(getattr(p, "ruta_guardado", None) or (p.ruta if p else "") or "Sin título") if p else "Sin archivo"
        self.setWindowTitle(f"{nombre}{' *' if p and p.modificado else ''} — {APP_NAME} (versión sencilla)")

    def paso_actual(self):
        return self.pasos[self.lst.currentRow()]

    def ir(self, i):
        if 0 <= i < len(self.pasos):
            self.lst.setCurrentRow(i)

    def _cambio_paso(self, i):
        if i < 0:
            return
        self.pila.setCurrentIndex(i); self.b_ant.setEnabled(i > 0); self.b_sig.setEnabled(i < len(self.pasos) - 1)
        if self.p is None and i < 6:
            self.nucleo.nuevo(asistente=False)
        self.pasos[i].cargar()

    def refrescar(self):
        self.paso_actual().cargar(); self.titulo()

    # ------------------------------------------------------------------ archivo
    def nuevo(self):
        if not self._cerrar_editor():
            return False
        ok = self.nucleo.nuevo(asistente=False)
        self.editor = None; self.ir(0); self.refrescar()
        return ok

    def abrir(self, ruta=None):
        if ruta is None:
            ruta, _ = QFileDialog.getOpenFileName(self, "Abrir", "", "Configuración de horarios (*.xghc)")
            if not ruta:
                return False
        if not self._cerrar_editor() or not self.nucleo.confirmar_cierre():
            return False
        self.nucleo.abrir(ruta); self.editor = None
        L = ruta_resultado(ruta)
        if os.path.exists(L):
            try:
                self.cargar_resultado(L)
            except Exception:  # noqa: BLE001 — el resultado no corresponde: se ignora
                self.editor = None
        self.refrescar()
        return self.p is not None

    def guardar(self):
        ok = self.nucleo.guardar(); self.titulo(); return ok

    def guardar_como(self):
        ok = self.nucleo.guardar_como(); self.titulo(); return ok

    def cargar_resultado(self, L):
        from ..editor_modelo import Editor
        p = self.p
        self.editor = Editor(L, getattr(p, "ruta_guardado", None) or p.ruta)
        return self.editor

    def _cerrar_editor(self):
        ed = self.editor
        if ed and ed.modificado:
            r = QMessageBox.question(self, APP_NAME, "¿Guardar los cambios hechos en el horario?",
                                     QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
            if r == QMessageBox.Cancel:
                return False
            if r == QMessageBox.Yes:
                ed.guardar(); ed.modificado = False
        return True

    # ------------------------------------------------------------------ «Más opciones…» → diálogos de la clásica
    def propiedades_clasicas(self, lista, nombre=None):
        n = self.nucleo
        n.cambiar_lista(lista)
        if nombre is not None:
            if lista in ("guardias", "reuniones", "complementarias"):
                n._seleccionar_nombre(nombre)
            else:
                self._seleccionar_en_nucleo(lista, nombre)
        if nombre is None:
            n.opciones_generales()
        else:
            n.propiedades()
        self.refrescar()

    def _seleccionar_en_nucleo(self, lista, nombre):
        from ..ventana import ROL_OBJ as ROL
        n = self.nucleo
        for r in range(n.proxy.rowCount()):
            o = n.proxy.index(r, 0).data(ROL)
            if o is not None and (getattr(o, "nombre", None) == nombre or getattr(o, "id", None) == nombre):
                n.tabla.selectRow(r); n.tabla.setCurrentIndex(n.proxy.index(r, 0)); return True
        return False

    def importar_delphos(self, operar=None):
        r = self.nucleo.importar_delphos(operar); self.refrescar(); return r

    def abrir_editor_clasico(self):
        if not self.editor:
            QMessageBox.information(self, APP_NAME, "Primero genere el horario."); return None
        from ..editor import VentanaEditor
        if self.editor.modificado:
            self.editor.guardar(); self.editor.modificado = False
        self.ved = VentanaEditor(self.editor.ruta, self.editor.ruta_xghc); self.ved.show()
        return self.ved

    # ------------------------------------------------------------------ alternar versión
    def cambiar_version(self, version):
        if version != "clasica":
            return self
        n = self.nucleo
        n.setGeometry(self.geometry()); n.cambiar_lista(n.lista_actual); n._titulo()
        self.hide(); n.show(); n.raise_()
        selector.ajustes().setValue(selector.CLAVE_VERSION, "clasica")
        return n

    def mostrar_desde_nucleo(self):
        p = self.p
        if self.editor and p is not None and os.path.abspath(self.editor.ruta_xghc) != os.path.abspath(getattr(p, "ruta_guardado", None) or p.ruta or ""):
            self.editor = None
        if self.editor is None and p is not None and (getattr(p, "ruta_guardado", None) or p.ruta):
            L = ruta_resultado(getattr(p, "ruta_guardado", None) or p.ruta)
            if os.path.exists(L):
                try:
                    self.cargar_resultado(L)
                except Exception:  # noqa: BLE001
                    self.editor = None
        self.refrescar(); self.show(); self.raise_()
        selector.ajustes().setValue(selector.CLAVE_VERSION, "sencilla")

    def closeEvent(self, ev):
        if not self._cerrar_editor() or not self.nucleo.confirmar_cierre():
            ev.ignore(); return
        if self.nucleo.proyecto is not None:
            self.nucleo.proyecto.modificado = False   # ya confirmado: el núcleo oculto no vuelve a preguntar
        ev.accept()
