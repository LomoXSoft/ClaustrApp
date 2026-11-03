"""Guardar, edición de celdas, insertar/eliminar, deshacer y Propiedades para el Planificador."""
from __future__ import annotations
from .textos import TX
import os
from PySide6.QtCore import Qt, QEvent, QObject, QTimer
from PySide6.QtGui import QStandardItem
from PySide6.QtWidgets import (QStyledItemDelegate, QComboBox, QLineEdit, QMessageBox, QFileDialog, QInputDialog,
                               QAbstractItemView, QDialog)
from . import APP_NAME, xghc, edicion as ED, modelo as M
from .propiedades import VENTANAS

SUFIJO = "_lph.xghc"
MAX_DESHACER = 100

# columnas editables por lista: col -> (campo, tipo, origen de valores)
#   tipo: 'texto' | 'combo' ; campo: para elementos, ruta XML ('nombre' renombra en cascada)
EDITABLES = {
    "sesiones": {1: ("materia", "combo", "materias"), 2: ("grupo", "combo", "grupos"),
                 3: ("profesor", "combo", "profesores"), 4: ("tmp", "texto", None),
                 5: ("aula", "combo", "aulas"), 6: ("conjunto", "combo", "conjuntos"),
                 10: ("departamento", "combo", "departamentos"), 11: ("grupoMateria", "texto", None),
                 12: ("tarea", "combo", "tareas")},
    "profesores": {0: ("nombre", "texto", None), 1: ("abreviatura", "texto", None), 2: ("nombreCompleto", "texto", None),
                   3: ("departamento", "combo", "departamentos"), 9: ("claveDeExportacion", "texto", None),
                   10: ("prioridad", "texto", None)},
    "grupos": {0: ("nombre", "texto", None), 1: ("abreviatura", "texto", None),
               2: ("cursoPerteneciente", "combo", "cursos"), 3: ("profesorTutor", "combo", "profesores"),
               4: ("aula", "combo", "aulas")},
    "materias": {0: ("nombre", "texto", None), 1: ("abreviatura", "texto", None), 2: ("nombreCompleto", "texto", None),
                 3: ("departamento", "combo", "departamentos")},
    "aulas": {0: ("nombre", "texto", None), 1: ("abreviatura", "texto", None), 2: ("descripcion", "texto", None)},
    "cursos": {0: ("nombre", "texto", None), 1: ("nombreCompleto", "texto", None)},
    "departamentos": {0: ("nombre", "texto", None), 1: ("nombreCompleto", "texto", None)},
    "tareas": {0: ("nombre", "texto", None), 1: ("nombreCompleto", "texto", None), 2: ("claveDeExportacion", "texto", None)},
    "reuniones": {0: ("nombre", "texto", None), 1: ("numeroDeReuniones", "numero", None), 3: ("tipoDeTarea", "combo", "tareas")},
    "guardias": {0: ("nombre", "texto", None), 1: ("tipoDeTarea", "combo", "tareas"), 4: ("numeroDeGuardias", "numero", None)},
}
INSERTABLES = {"sesiones", "profesores", "grupos", "materias", "aulas", "cursos", "departamentos", "tareas",
               "reuniones", "guardias", "complementarias"}
NO_LECTIVAS = {"reuniones", "guardias", "complementarias"}


def tipo_campo(lista, campo):
    return next((t for c, t, _o in EDITABLES.get(lista, {}).values() if c == campo), None)


class DelegadoEdicion(QStyledItemDelegate):
    """Editor de celda: lista desplegable o texto según la columna."""

    def __init__(self, win, base=None):
        super().__init__(win.tabla); self.win = win; self.base = base

    def paint(self, p, opt, idx):
        (self.base.paint if self.base else super().paint)(p, opt, idx)

    def _def(self, idx):
        return EDITABLES.get(self.win.lista_actual, {}).get(idx.column())

    def createEditor(self, parent, opt, idx):
        d = self._def(idx)
        if d is None:
            return None
        campo, tipo, origen = d
        if tipo == "combo":
            cb = QComboBox(parent); cb.addItem("")
            raiz = self.win.proyecto.doc.raiz
            if origen == "conjuntos":
                c = raiz.find("conjuntoDeAulas")
                cb.addItems([x.get("nombre") for x in c if x.get("nombre")] if c is not None else [])
            else:
                cb.addItems(ED.nombres(raiz, origen))
            cb.setMaxVisibleItems(20)
            return cb
        return QLineEdit(parent)

    def setEditorData(self, ed, idx):
        v = idx.data() or ""
        if isinstance(ed, QComboBox):
            v = v.split(" ")[0] if self._def(idx)[0] in ("aula", "conjunto") else v
            i = ed.findText(v); ed.setCurrentIndex(max(i, 0))
            QTimer.singleShot(0, ed.showPopup)
        else:
            ed.setText(v); ed.selectAll()

    def setModelData(self, ed, model, idx):
        v = ed.currentText() if isinstance(ed, QComboBox) else ed.text().strip()
        obj = idx.data(M_ROL_OBJ)
        campo = self._def(idx)[0]
        QTimer.singleShot(0, lambda: self.win.editar_celda(obj, campo, v))


M_ROL_OBJ = Qt.UserRole + 1


class FiltroTeclas(QObject):
    """Intro edita la celda; Tab abre Propiedades (como en el original)."""

    def __init__(self, win):
        super().__init__(win); self.win = win

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.KeyPress and self.win.tabla.state() != QAbstractItemView.EditingState:
            if ev.key() == Qt.Key_Tab and not ev.modifiers():
                self.win.propiedades(); return True
            if ev.key() in (Qt.Key_Return, Qt.Key_Enter):
                idx = self.win.tabla.currentIndex()
                if idx.isValid():
                    self.win.tabla.edit(idx)
                return True
        return False


class EdicionMixin:
    # ------------------------------------------------------------ preparación
    def _preparar_edicion(self):
        self.pila_deshacer: list[tuple[bytes, str]] = []
        self.pila_rehacer: list[tuple[bytes, str]] = []
        self._clave_pintado = None
        self.tabla.setEditTriggers(QAbstractItemView.SelectedClicked | QAbstractItemView.EditKeyPressed)
        self.tabla.setTabKeyNavigation(False)
        self.tabla.installEventFilter(FiltroTeclas(self))
        self.tabla.doubleClicked.connect(lambda _i: self.propiedades())
        self.panel.cambiada.disconnect(); self.panel.cambiada.connect(self._plantilla_pintada)
        self._actualizar_deshacer()

    # ------------------------------------------------------------ guardar
    def es_original(self, ruta):
        return not ruta.lower().endswith(SUFIJO)

    def guardar(self):
        p = self.proyecto
        if not p:
            return False
        destino = getattr(p, "ruta_guardado", None)
        if destino is None:
            return self.guardar_como(primera=True)
        return self._escribir(destino)

    def guardar_como(self, primera=False):
        p = self.proyecto
        if not p:
            return False
        base = p.ruta or "Sin título.xghc"
        sugerido = base if not self.es_original(base) else os.path.splitext(base)[0] + SUFIJO
        if not p.ruta:  # archivo nuevo (Archivo > Nuevo): sin original que conservar
            sugerido = "Sin título.xghc"
        elif primera and self.es_original(base):
            QMessageBox.information(self, APP_NAME,
                                    "El archivo abierto se conservará sin cambios.\n"
                                    f"Los datos se guardarán en una copia (sufijo «{SUFIJO}»).")
        ruta, _ = QFileDialog.getSaveFileName(self, "Guardar como", sugerido,
                                              "Configuración de horarios (*.xghc)")
        if not ruta:
            return False
        if not ruta.lower().endswith(".xghc"):
            ruta += ".xghc"
        return self._escribir(ruta)

    def _escribir(self, ruta):
        p = self.proyecto
        orig = getattr(p, "ruta_original", None)
        if orig and os.path.abspath(ruta) == os.path.abspath(orig) and self.es_original(orig):
            QMessageBox.warning(self, APP_NAME, "No se sobrescribe el archivo original abierto.\n"
                                                f"Elija otro nombre (p. ej. con el sufijo «{SUFIJO}»).")
            return self.guardar_como()
        try:
            xghc.guardar(p, ruta)
        except OSError as e:
            QMessageBox.critical(self, APP_NAME, f"No se pudo guardar el archivo:\n{ruta}\n\n{e}")
            return False
        p.ruta = ruta; p.ruta_guardado = ruta; p.modificado = False
        self._titulo(); self.statusBar().showMessage(f"Guardado: {ruta}", 5000)
        return True

    def confirmar_cierre(self):
        """True si se puede cerrar/abrir otro archivo."""
        p = self.proyecto
        if not p or not p.modificado:
            return True
        nombre = os.path.basename(getattr(p, "ruta_guardado", None) or p.ruta or "Sin título")
        r = QMessageBox.question(self, APP_NAME, f"¿Desea guardar los datos actuales en {nombre}?",
                                 QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
        if r == QMessageBox.Cancel:
            return False
        if r == QMessageBox.Yes:
            return self.guardar()
        return True

    # ------------------------------------------------------------ núcleo de edición
    def editar(self, fn, descripcion="", refrescar=True):
        """Ejecuta fn(arbol) sobre el XML; si devuelve True se guarda un punto de deshacer y se refresca."""
        p = self.proyecto
        if not p:
            return False
        antes = p.doc.serializar()
        arbol = ED.Arbol(p.doc.raiz)
        try:
            cambio = fn(arbol)
        except Exception:
            self._restaurar(antes); raise
        if not cambio:
            return False
        self.pila_deshacer.append((antes, descripcion)); del self.pila_deshacer[:-MAX_DESHACER]
        self.pila_rehacer.clear(); self._clave_pintado = None
        self._reconstruir(modificado=True)
        return True

    def _reconstruir(self, modificado=True, doc=None):
        viejo = self.proyecto
        nuevo = xghc.construir(doc or viejo.doc, viejo.ruta)
        for k in ("contenedor", "ruta_guardado", "ruta_original", "claves_externas"):
            setattr(nuevo, k, getattr(viejo, k, None))
        nuevo.modificado = modificado or viejo.modificado
        self.proyecto = nuevo
        fila = self.tabla.currentIndex().row(); col = self.tabla.currentIndex().column()
        self.panel.set_proyecto(nuevo)
        self.cambiar_lista(self.lista_actual, historial=False)
        if 0 <= fila < self.proxy.rowCount():
            self.tabla.setCurrentIndex(self.proxy.index(fila, max(col, 0)))
        self._titulo(); self._actualizar_deshacer()

    def _restaurar(self, datos: bytes):
        self.proyecto.doc = xghc.Documento(datos)
        self._reconstruir(modificado=True, doc=self.proyecto.doc)

    def deshacer(self):
        if not self.pila_deshacer:
            return
        datos, desc = self.pila_deshacer.pop()
        self.pila_rehacer.append((self.proyecto.doc.serializar(), desc))
        self._clave_pintado = None
        self._restaurar(datos)
        self.statusBar().showMessage(f"Deshecho: {desc}", 4000)

    def rehacer(self):
        if not self.pila_rehacer:
            return
        datos, desc = self.pila_rehacer.pop()
        self.pila_deshacer.append((self.proyecto.doc.serializar(), desc))
        self._clave_pintado = None
        self._restaurar(datos)

    def _actualizar_deshacer(self):
        if hasattr(self, "a_deshacer"):
            self.a_deshacer.setEnabled(bool(getattr(self, "pila_deshacer", [])))
            self.a_rehacer.setEnabled(bool(getattr(self, "pila_rehacer", [])))
            d = self.pila_deshacer[-1][1] if getattr(self, "pila_deshacer", []) else ""
            self.a_deshacer.setText(f"Deshacer {d}".strip())

    # ------------------------------------------------------------ plantillas
    def _plantilla_pintada(self):
        p = self.proyecto
        idx = self.tabla.currentIndex()
        obj = idx.data(M_ROL_OBJ) if idx.isValid() else None
        if p is None or obj is None:
            return
        if isinstance(obj, M.Sesion):
            owner, plantilla, marco = obj.xml_plantilla, obj.plantilla, obj.marco
        else:
            owner, plantilla, marco = obj.datos.get("_xml"), obj.plantilla, obj.marco
        if owner is None:
            return
        antes = p.doc.serializar()
        if ED.volcar_plantilla(ED.Arbol(p.doc.raiz), owner, plantilla, marco):
            clave = (self.lista_actual, id(owner))
            if clave != self._clave_pintado:      # un solo punto de deshacer por elemento pintado seguido
                self.pila_deshacer.append((antes, "pintar plantilla")); self.pila_rehacer.clear()
                self._clave_pintado = clave
            p.modificado = True; self._titulo(); self._actualizar_deshacer()

    # ------------------------------------------------------------ celdas
    def editar_celda(self, obj, campo, valor):
        if obj is None:
            return
        try:
            if isinstance(obj, M.Sesion):
                ok = self.editar(lambda a: ED.set_campo_sesion(a, obj.xml, campo, valor), f"{campo}")
            else:
                x = obj.datos["_xml"]
                if campo == "nombre":
                    if not valor:
                        return
                    if valor != obj.nombre and valor in ED.nombres(self.proyecto.doc.raiz, self.lista_actual):
                        QMessageBox.warning(self, APP_NAME, f"Ya existe «{valor}» en la lista."); return
                    ok = self.editar(lambda a: ED.renombrar(a, self.lista_actual, x, valor), "cambiar nombre")
                elif campo == "aula" and self.lista_actual == "grupos":
                    ok = self.editar(lambda a: ED.escribir(a, x, "aula", valor), "aula del grupo")
                else:
                    if tipo_campo(self.lista_actual, campo) == "numero":
                        if not valor.strip().isdigit():
                            QMessageBox.warning(self, APP_NAME, f"Valor numérico no válido: «{valor}»"); return
                        valor = str(int(valor))
                    ok = self.editar(lambda a: (ED.leer(x, campo, None) or "") != valor and ED.escribir(a, x, campo, valor), campo)
        except ValueError as e:
            QMessageBox.warning(self, APP_NAME, str(e)); return

    def preparar_items(self, items, clave):
        """Marca como editables solo las columnas con editor."""
        ed = EDITABLES.get(clave, {})
        for j, it in enumerate(items):
            if j in ed:
                it.setFlags(it.flags() | Qt.ItemIsEditable)
            else:
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)
        if clave in ("reuniones", "guardias"):
            from .propiedades_nl import es_integrante
            hijo = es_integrante(items[0].data(M_ROL_OBJ))
            if not hijo and clave == "guardias":      # «asignadas / huecos» es calculado
                items[4].setFlags(items[4].flags() & ~Qt.ItemIsEditable)
            self.preparar_items_nl(items, clave)

    # ------------------------------------------------------------ insertar / eliminar
    def insertar(self):
        p = self.proyecto; clave = self.lista_actual
        if not p or clave not in INSERTABLES:
            self.proximamente(TX("nuevo")); return
        idx = self.tabla.currentIndex(); obj = idx.data(M_ROL_OBJ) if idx.isValid() else None
        if clave in NO_LECTIVAS:
            return self.insertar_nl(clave)
        if clave == "sesiones":
            ref = obj.xml if isinstance(obj, M.Sesion) else None
            grupo = obj.grupo if isinstance(obj, M.Sesion) else ""
            tarea = ED.leer(p.doc.raiz, "tareas/lectivaPorDefecto", None) or (obj.tarea if isinstance(obj, M.Sesion) else "")
            nueva = []
            self.editar(lambda a: nueva.append(ED.insertar_sesion(a, ref, "", grupo, "", tarea)) or True, "insertar sesión")
            nid = nueva[0].get("id") if nueva else None
            col = 1
        else:
            existentes = set(ED.nombres(p.doc.raiz, clave))
            nombre, ok = QInputDialog.getText(self, TX("nuevo"), TX("codigo_3"))
            nombre = (nombre or "").strip()
            if not ok or not nombre:
                return
            if nombre in existentes:
                QMessageBox.warning(self, APP_NAME, f"Ya existe «{nombre}» en la lista."); return
            ref = obj.datos.get("_xml") if isinstance(obj, M.Elemento) else None
            self.editar(lambda a: ED.insertar_elemento(a, clave, nombre, ref) is not None, "insertar")
            nid = nombre; col = 0
        for r in range(self.proxy.rowCount()):
            o = self.proxy.index(r, 0).data(M_ROL_OBJ)
            if getattr(o, "id", None) == nid or getattr(o, "nombre", None) == nid:
                self.tabla.setCurrentIndex(self.proxy.index(r, col)); self.tabla.selectRow(r)
                if clave == "sesiones":
                    self.tabla.setCurrentIndex(self.proxy.index(r, col)); self.tabla.edit(self.proxy.index(r, col))
                break

    def eliminar(self):
        p = self.proyecto; clave = self.lista_actual
        if not p or clave not in INSERTABLES:
            self.proximamente("Eliminar"); return
        if clave in NO_LECTIVAS:
            return self.eliminar_nl(clave)
        objs = []
        for idx in self.tabla.selectionModel().selectedRows():
            o = idx.data(M_ROL_OBJ)
            if o is not None and o not in objs:
                objs.append(o)
        if not objs:
            return
        msg = TX("borrar_elemento_elegido") if len(objs) == 1 else \
            f"¿Quiere suprimir {len(objs)} elemento(s) seleccionado(s)?"
        if clave != "sesiones":
            refs = [o.nombre for o in objs if any(o.nombre in (s.materia, s.grupo, s.profesor) or o.nombre in s.aulas
                                                  for s in p.sesiones)]
            if refs:
                msg += "\n\nAlgunos están asignados a sesiones lectivas; esas referencias quedarán vacías."
        from .opciones_generales import confirmar_suprimir
        if confirmar_suprimir() and QMessageBox.question(self, "Suprimir", msg) != QMessageBox.Yes:
            return
        if clave == "sesiones":
            self.editar(lambda a: [ED.eliminar_sesion(a, o.xml) for o in objs] and True, "suprimir")
        else:
            self.editar(lambda a: [ED.eliminar_elemento(a, clave, o.datos["_xml"]) for o in objs] and True, "suprimir")

    # ------------------------------------------------------------ propiedades
    def propiedades(self):
        p = self.proyecto; clave = self.lista_actual
        if p and (clave in NO_LECTIVAS or clave == "tareas"):
            idx = self.tabla.currentIndex()
            if idx.isValid():
                self.propiedades_nl(clave, idx.data(M_ROL_OBJ))
            return
        cls = VENTANAS.get(clave)
        if not p or cls is None:
            self.proximamente("Propiedades"); return
        idx = self.tabla.currentIndex()
        if not idx.isValid():
            return
        obj = idx.data(M_ROL_OBJ)
        elementos = [self.proxy.index(r, 0).data(M_ROL_OBJ) for r in range(self.proxy.rowCount())]
        dlg = cls(self, elementos, elementos.index(obj))
        self._dlg_propiedades = dlg
        dlg.exec()
        self._dlg_propiedades = None
