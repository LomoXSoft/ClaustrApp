"""Editor de horarios sobre resultados .lphr.

Menús, menú contextual y diálogos con los textos de los recursos del editor de referencia; lo no
implementado aparece deshabilitado con la marca «Próximamente». La lógica está en editor_modelo.py.
"""
from __future__ import annotations
from .textos import TX
import copy, json, os
from collections import defaultdict
from PySide6.QtCore import Qt, QMimeData, QPoint, Signal
from PySide6.QtGui import QAction, QColor, QDrag, QFont, QKeySequence, QBrush, QIcon, QPixmap, QPainter, QPen
from PySide6.QtWidgets import (QMainWindow, QMdiArea, QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QToolButton,
                               QLabel, QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView, QMenu, QMessageBox,
                               QFileDialog, QDialog, QTreeWidgetItem, QColorDialog, QApplication, QCheckBox,
                               QPushButton, QListWidget, QListWidgetItem, QStyle, QAbstractItemView, QLineEdit,
                               QSpinBox, QDialogButtonBox, QPlainTextEdit)
from . import __version__, APP_NAME, APP_EDITOR, VENDOR, AJUSTES
from . import informes as INF, informes_ui as IU
from PySide6.QtPrintSupport import QPrinter, QPrintDialog, QPageSetupDialog
from .editor_modelo import Editor, ErrorEdicion, DIAS, VISTAS, ROJO
from .formrc import PaginaRC, fuente_dialogo, ajustar
from . import iconos, resultado as RES

APP_ED = APP_EDITOR
MIME = "application/x-horarios-item"
_DIR = os.path.join(os.path.dirname(__file__), "recursos")
from .textos import MENUS_EDITOR as MENUS   # paquete de textos activo
OMITIR = {32892, 33090}                 # servicios propios de la marca original (suscripción, app web)
RENOMBRAR = {57664: f"Acerca de {APP_ED}", 33038: f"Web de {APP_NAME}"}
PROX = "Próximamente"
VISTA_DE_TIPO = {"profesor": "Profesorado", "grupo": "Grupos", "aula": "Aulas"}


def _pon(w, v):
    w.setValue(int(v)) if isinstance(w, QSpinBox) else w.setText(str(v))


def _num(w):
    if isinstance(w, QSpinBox):
        return max(1, w.value())
    try:
        return max(1, int(w.text() or "1"))
    except ValueError:
        return 1


def _proximamente(parent, texto="Esta función"):
    QMessageBox.information(parent, APP_ED, f"{texto}: {PROX.lower()}.")


def _icono_estado(color):
    pm = QPixmap(14, 14); pm.fill(Qt.transparent); p = QPainter(pm); p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor(color)); p.setPen(QPen(QColor("#333"), 1)); p.drawEllipse(1, 1, 12, 12)
    if color == "#d33":
        p.setPen(QPen(QColor("white"), 2)); p.drawLine(4, 4, 10, 10); p.drawLine(10, 4, 4, 10)
    p.end(); return QIcon(pm)


def _icono_flex():
    """Marca violeta «P»: la sesión incumple una condición estricta flexibilizada en el Depurador."""
    pm = QPixmap(14, 14); pm.fill(QColor("#8a2be2")); p = QPainter(pm)
    p.setPen(QColor("white")); f = p.font(); f.setBold(True); f.setPixelSize(11); p.setFont(f)
    p.drawText(pm.rect(), Qt.AlignCenter, "P"); p.end(); return QIcon(pm)


# ====================================================================== rejilla
class TablaHorario(QTableWidget):
    def __init__(self, vista_w, vista, nombre):
        super().__init__()
        self.vw, self.vista, self.nombre = vista_w, vista, nombre
        self.celdas, self.pos = {}, {}
        self.setEditTriggers(QAbstractItemView.NoEditTriggers); self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setAcceptDrops(True); self.viewport().setAcceptDrops(True); self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setWordWrap(True); self.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.setStyleSheet("QTableWidget{background:#fffff0; gridline-color:#9a9a9a;}"
                           "QTableWidget::item:selected{border:2px solid #d00; color:black;}"
                           "QHeaderView::section{background:#ffffff; color:#1f8a8a; border:1px solid #c0c0c0;}")
        self._ini = None
        self.currentCellChanged.connect(lambda *_: self._senalar())

    def _estilo(self, inf):
        """Letreros y configuración: botones 3D en las cabeceras y colores de seguimiento (tracking)."""
        borde = "2px outset #d0d0d0" if inf.get("botones_3d") else "1px solid #c0c0c0"
        fondo = "#ececec" if inf.get("botones_3d") else "#ffffff"
        self.setStyleSheet("QTableWidget{background:#fffff0; gridline-color:%s;}"
                           "QTableWidget::item:selected{border:2px solid #d00; color:black;}"
                           "QHeaderView::section{background:%s; color:#1f8a8a; border:%s;}" % (inf["color_lineas"] if inf.get("color_lineas") not in (None, INF.OPC_DEF["color_lineas"]) else "#9a9a9a", fondo, borde))
        self.setShowGrid(bool(inf.get("lineas_v", True) or inf.get("lineas_h", True)))
        self._inf = inf

    def _senalar(self):
        """Señala fila/columna actual: pinta la cabecera de la celda actual con los colores Tracking."""
        inf = getattr(self, "_inf", {}) or {}
        r, c = self.currentRow(), self.currentColumn()
        for k in range(self.rowCount()):
            h = self.verticalHeaderItem(k)
            if h:
                on = inf.get("senala_fila") and k == r
                h.setBackground(QColor(inf.get("color_track_linea", "#d00000")) if on else QBrush())
                h.setForeground(QColor(inf.get("color_track_texto", "#ffffff")) if on else QBrush())
        for k in range(self.columnCount()):
            h = self.horizontalHeaderItem(k)
            if h:
                on = inf.get("senala_columna") and k == c
                h.setBackground(QColor(inf.get("color_track_linea", "#d00000")) if on else QBrush())
                h.setForeground(QColor(inf.get("color_track_texto", "#ffffff")) if on else QBrush())
        self.horizontalHeader().viewport().update(); self.verticalHeader().viewport().update()

    def pintar(self):
        ed = self.vw.ventana.ed; op = self.vw.ventana.opciones
        items = ed.items_de(self.vista, self.nombre)
        marcos = ed.marcos_de(self.vista, self.nombre, items)
        filas = [(m, t) for m in marcos for t in ed.p.marcos[m].filas()]
        ndias = max(len(ed.p.marcos[m].dias) for m in marcos)
        self.clear(); self.celdas, self.pos = {}, {}
        self.setRowCount(len(filas)); self.setColumnCount(ndias)
        inf = INF.opciones(ed.doc); self._estilo(inf)
        let = (ed.doc["editor"].get("informes") or {}).get("letreros") or {}
        dias = list(let.get("dias") or []) + list(DIAS[len(let.get("dias") or []):])
        self.setHorizontalHeaderLabels(dias[:ndias])
        cel_o = ed.celdas()
        def _cab(m, t):
            e, sa = ed.hora_tramo(m, t); cl = ed.clave_tramo(m, t)
            txt = (e if cel_o["solo_entrada"] else f"{e}\n{sa}") if t.tipo == "lectivo" else f"{e}-{sa}"
            return (f"{ed.nombre_marco(m)} " if len(marcos) > 1 else "") + (f"{cl}\n" if cl else "") + txt
        self.setVerticalHeaderLabels([_cab(m, t) for m, t in filas])
        fila_de = {(m, t.indice): i for i, (m, t) in enumerate(filas)}
        malos = ed.choques()
        for i, (m, t) in enumerate(filas):
            for d in range(ndias):
                it = QTableWidgetItem(""); it.setTextAlignment(Qt.AlignCenter)
                if t.tipo != "lectivo":
                    it.setBackground(QColor("#d8f3f3")); it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsDropEnabled)
                    if let.get("recreo") and getattr(t, "tipo", "") == "recreo":
                        it.setText(let["recreo"]); it.setForeground(QColor("#5aa"))
                self.setItem(i, d, it); self.pos[(i, d)] = (m, d, t.indice)
            self.setRowHidden(i, (t.tipo == "recreo" and ("recreos" in op or cel_o["ocultar_recreos"]))
                              or (t.tipo == "mediodia" and cel_o["ocultar_mediodia"]))
        for itm in items:
            for (m, d, idx) in ed.posiciones(itm):
                i = fila_de.get((m, idx))
                if i is None or d >= ndias:
                    continue
                self.celdas.setdefault((i, d), []).append(itm)
        if cel_o["ocultar_vacias"]:   # filas vacías al principio y al final del horario
            usadas = sorted({i for (i, _d) in self.celdas})
            for i in range(len(filas)):
                if not usadas or i < usadas[0] or i > usadas[-1]:
                    self.setRowHidden(i, True)
        con_col = ed.doc["editor"].get("con_colores", True)
        for (i, d), lst in self.celdas.items():
            cel = self.item(i, d)
            if self.vista == "Grupos" and len(lst) >= max(2, cel_o["desdobles"]):
                cel.setText(f"(*) [op.{len(lst)}]")   # optativas detalladas en la descripción de la celda
            else:
                cel.setText(("\n" if cel_o["ocultar_separacion"] else "\n— — —\n").join(ed.texto_celda(x, self.vista, op) for x in lst))
            if len(lst) > 1 or any(x in malos for x in lst):
                cel.setBackground(QColor(ROJO))
            elif con_col:
                cel.setBackground(QColor(ed.color(ed.clave_color(lst[0]))))
            tip = "\n".join(ed.descripcion(x) for x in lst)
            flex = [m for x in lst for m in (ed.doc.get("flexibilizadas") or {}).get(x, [])]
            if flex:
                cel.setIcon(_icono_flex()); tip += "\n\nCondición flexibilizada (Depurador):\n" + "\n".join(dict.fromkeys(flex))
            cel.setToolTip(tip)
        f = self.font(); f.setPointSizeF(max(5.0, 9.0 * self.vw.ventana.zoom)); self.setFont(f)
        self.resizeRowsToContents()
        self._min = {}
        for i, (m, t) in enumerate(filas):
            self._min[i] = 16 if t.tipo != "lectivo" else max(self.rowHeight(i), 46)
        self._estirar(); self._senalar()

    def _estirar(self):
        """Reparte la altura disponible entre las filas lectivas (las de recreo quedan finas)."""
        mins = getattr(self, "_min", {})
        vis = [i for i in mins if not self.isRowHidden(i)]
        if not vis:
            return
        lect = [i for i in vis if mins[i] > 16]
        libre = self.viewport().height() - 2 - sum(mins[i] for i in vis if i not in lect)
        alto = (libre - len(vis)) // len(lect) if lect else 0
        for i in vis:
            self.setRowHeight(i, max(mins[i], alto) if i in lect else mins[i])

    def resizeEvent(self, ev):
        super().resizeEvent(ev); self._estirar()

    def items_en(self, r, c):
        return list(self.celdas.get((r, c), []))

    # ---------------------------------------------------- arrastrar y soltar
    def mousePressEvent(self, ev):
        self._ini = ev.position().toPoint() if ev.button() == Qt.LeftButton else None
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        if self._ini is not None and (ev.position().toPoint() - self._ini).manhattanLength() >= QApplication.startDragDistance():
            ix = self.indexAt(self._ini); its = self.items_en(ix.row(), ix.column())
            self._ini = None
            if its:
                md = QMimeData(); md.setData(MIME, its[0].encode()); dr = QDrag(self); dr.setMimeData(md)
                dr.exec(Qt.MoveAction)
            return
        super().mouseMoveEvent(ev)

    def dragEnterEvent(self, ev):
        ev.acceptProposedAction() if ev.mimeData().hasFormat(MIME) else ev.ignore()

    def dragMoveEvent(self, ev):
        ev.acceptProposedAction() if ev.mimeData().hasFormat(MIME) else ev.ignore()

    def dropEvent(self, ev):
        if not ev.mimeData().hasFormat(MIME):
            return ev.ignore()
        ix = self.indexAt(ev.position().toPoint())
        if ix.isValid():
            item = bytes(ev.mimeData().data(MIME)).decode()
            ev.acceptProposedAction()
            self.vw.ventana.soltar(item, self.pos[(ix.row(), ix.column())])

    def contextMenuEvent(self, ev):
        ix = self.indexAt(ev.pos())
        if ix.isValid():
            self.setCurrentCell(ix.row(), ix.column())
            self.vw.ventana.menu_celda(self, ix.row(), ix.column()).exec(ev.globalPos())


class TablaEspecial(TablaHorario):
    """VENTANAS > Tabla nueva en otra pestaña: tablas de consulta (sin arrastrar ni soltar).
    modo: lista (tabla con lista de integrantes) | columnas / filas (general) | recreo | cruce | aulas_libres | prof_libres."""
    NOMBRES = {"lista": "con lista", "columnas": TX("todos_columnas"), "filas": TX("todos_filas"), "recreo": "Guardias de recreo",
               "cruce": "Cruce profesores/alumnos", "aulas_libres": "Aulas libres", "prof_libres": "Profesores libres"}

    def __init__(self, vista_w, vista, nombre, modo):
        super().__init__(vista_w, vista, nombre); self.modo = modo
        self.setAcceptDrops(False); self.setDragDropMode(QAbstractItemView.NoDragDrop)

    def mouseMoveEvent(self, ev):
        QTableWidget.mouseMoveEvent(self, ev)

    def contextMenuEvent(self, ev):
        pass

    def _rellenar(self, cab_h, cab_v, datos):
        self.clear(); self.celdas, self.pos = {}, {}
        self.setRowCount(len(datos)); self.setColumnCount(len(cab_h))
        self.setHorizontalHeaderLabels(cab_h); self.setVerticalHeaderLabels(cab_v)
        for i, fila in enumerate(datos):
            for j, v in enumerate(fila):
                it = QTableWidgetItem(v); it.setTextAlignment(Qt.AlignCenter); it.setToolTip(v); self.setItem(i, j, it)
        self.resizeRowsToContents(); self._min = {}

    def _tabla_inf(self, tb):
        if tb.cols:
            return self._rellenar(tb.cols, [str(i + 1) for i in range(len(tb.datos))], tb.datos)
        datos = [["\n".join(l for c in tb.celdas.get((i, d), []) for l in c.lineas) for d in range(len(tb.dias))]
                 for i in range(len(tb.filas))]
        self._rellenar(tb.dias, [f"{a}-{b}" for a, b, _t in tb.filas], datos)

    def pintar(self):
        ed = self.vw.ventana.ed; o = INF.opciones(ed.doc); g = INF.Generador(ed, o); self._estilo(o)
        if self.modo == "lista":
            TablaHorario.pintar(self)
            filas = g.asignaciones_de(ed.items_de(self.vista, self.nombre))
            base = self.rowCount(); self.setRowCount(base + len(filas))
            for k, t in enumerate(filas):
                it = QTableWidgetItem(t); self.setItem(base + k, 0, it); self.setSpan(base + k, 0, 1, max(1, self.columnCount()))
                self.setVerticalHeaderItem(base + k, QTableWidgetItem("" if k else "Lista"))
            return
        if self.modo in ("columnas", "filas"):
            tipo = {"Grupos": "alumnos", "Profesorado": "profesores", "Aulas": "aulas"}.get(self.vista, "alumnos")
            tbs = g.completo(tipo)
            if not tbs:
                return self._rellenar([], [], [])
            tb = tbs[0]
            if self.modo == "columnas":
                return self._rellenar(tb.cols[1:], [r[0] for r in tb.datos], [r[1:] for r in tb.datos])
            return self._rellenar([r[0] for r in tb.datos], tb.cols[1:], [list(x) for x in zip(*[r[1:] for r in tb.datos])])
        if self.modo == "recreo":
            tbs = g.tablas("recreo")
            return self._tabla_inf(tbs[0]) if tbs else self._rellenar(["Guardias de recreo"], [""], [["No hay guardias de recreo."]])
        if self.modo in ("aulas_libres", "prof_libres"):
            tbs = g.libres("aulas" if self.modo == "aulas_libres" else "profesores")
            dias = tbs[0].dias if tbs else []
            datos = [[", ".join(l for c in tb.celdas.get((0, d), []) for l in c.lineas) for d in range(len(dias))] for tb in tbs]
            return self._rellenar(dias, [tb.subtitulo for tb in tbs], datos)
        if self.modo == "cruce":
            profs = ed.elementos("Profesorado"); grs = ed.elementos("Grupos"); n = defaultdict(int)
            for it in ed.items():
                if it[0] != "s":
                    continue
                rec = ed.recursos(it); np_ = len(ed.posiciones(it))
                for (tp, a) in rec:
                    if tp == "profesor":
                        for (tp2, b) in rec:
                            if tp2 == "grupo":
                                n[(a, b)] += np_
            usados = [g_ for g_ in grs if any(n[(p, g_)] for p in profs)]
            return self._rellenar(usados, profs, [[str(n[(p, g_)] or "") for g_ in usados] for p in profs])


class VistaHorario(QWidget):
    """Ventana MDI: selector de vista + elemento, título y solapas inferiores '[elemento] (vista)'."""
    def __init__(self, ventana, vista="Grupos", nombre=None):
        super().__init__()
        self.ventana = ventana
        L = QVBoxLayout(self); L.setContentsMargins(2, 2, 2, 2); L.setSpacing(2)
        h = QHBoxLayout(); L.addLayout(h)
        self.cb_vista = QComboBox(); self.cb_vista.addItems(VISTAS); self.cb_vista.setToolTip("Tipo de horario")
        self.b_ant = QToolButton(); self.b_ant.setText("<="); self.b_sig = QToolButton(); self.b_sig.setText("=>")
        self.cb_el = QComboBox(); self.cb_el.setMinimumWidth(220); self.cb_el.setToolTip("Elemento")
        for w in (self.cb_vista, self.b_ant, self.b_sig, self.cb_el):
            h.addWidget(w)
        h.addStretch()
        self.titulo = QLabel(); self.titulo.setAlignment(Qt.AlignCenter)
        self.titulo.setStyleSheet("font-style:italic; font-size:16px; color:#1f8a8a;")
        L.addWidget(self.titulo)
        self.tabs = QTabWidget(); self.tabs.setTabPosition(QTabWidget.South); self.tabs.setDocumentMode(True)
        L.addWidget(self.tabs, 1)
        self.cb_vista.currentTextChanged.connect(self._vista_cambiada)
        self.cb_el.currentTextChanged.connect(self._el_cambiado)
        self.b_ant.clicked.connect(lambda: self.mover(-1)); self.b_sig.clicked.connect(lambda: self.mover(1))
        self.tabs.currentChanged.connect(self._tab_cambiada)
        self.nueva_solapa(vista, nombre)

    def tabla(self) -> TablaHorario:
        return self.tabs.currentWidget()

    def nueva_solapa(self, vista, nombre=None, modo=None):
        els = self.ventana.ed.elementos(vista)
        nombre = nombre if nombre in els else (els[0] if els else "")
        t = TablaEspecial(self, vista, nombre, modo) if modo else TablaHorario(self, vista, nombre)
        self.tabs.addTab(t, ""); self.tabs.setCurrentWidget(t); self._tab_cambiada(); return t

    def _tab_cambiada(self, *_):
        t = self.tabla()
        if t is None:
            return
        for cb in (self.cb_vista, self.cb_el):
            cb.blockSignals(True)
        self.cb_vista.setCurrentText(t.vista)
        self.cb_el.clear(); self.cb_el.addItems(self.ventana.ed.elementos(t.vista)); self.cb_el.setCurrentText(t.nombre)
        for cb in (self.cb_vista, self.cb_el):
            cb.blockSignals(False)
        self.refrescar()

    def _vista_cambiada(self, v):
        t = self.tabla(); els = self.ventana.ed.elementos(v)
        t.vista, t.nombre = v, (els[0] if els else "")
        self._tab_cambiada()

    def _el_cambiado(self, n):
        t = self.tabla()
        if n and t is not None:
            t.nombre = n; self.refrescar()

    def mover(self, paso):
        n = self.cb_el.count()
        if n:
            self.cb_el.setCurrentIndex((self.cb_el.currentIndex() + paso) % n)

    def refrescar(self):
        for i in range(self.tabs.count()):
            t = self.tabs.widget(i); m = getattr(t, "modo", None)
            self.tabs.setTabText(i, f"[{t.nombre}] ({t.vista})" if m in (None, "lista") else
                                 (f"[{t.vista}] ({TablaEspecial.NOMBRES[m]})" if m in ("columnas", "filas") else f"({TablaEspecial.NOMBRES[m]})"))
        t = self.tabla()
        if t is not None:
            self.titulo.setText(self.ventana.ed.nombre_largo(t.vista, t.nombre)); t.pintar()
            sw = self.parent()
            if sw is not None and hasattr(sw, "setWindowTitle"):
                sw.setWindowTitle(f"{t.nombre} ({t.vista})")


# ====================================================================== diálogos
class _DlgRC(QDialog):
    RID = ""; OCULTAR = ()

    def __init__(self, parent, titulo=None):
        super().__init__(parent)
        PaginaRC.OCULTAR, viejo = set(self.OCULTAR), getattr(PaginaRC, "OCULTAR", set())
        try:
            self.pg = PaginaRC(self.RID, self)
        finally:
            PaginaRC.OCULTAR = viejo
        self.setFixedSize(self.pg.size()); self.setFont(fuente_dialogo())
        self.setWindowTitle(titulo or self.pg.titulo or APP_ED)
        self.c = self.pg.c
        if 57670 in self.c:
            self.c[57670].clicked.connect(lambda: _proximamente(self, "La ayuda"))


CAT_NOMBRES = {32824: ("profesores", "Profesores"), 32825: ("alumnos", "Alumnos"), 32827: ("aulas", "Aulas"),
               32828: ("materias", "Materias"), 32865: ("tareas", "Tareas"), 32979: ("cursos", "Cursos"),
               32981: ("departamentos", "Departamentos"), 32829: ("reuniones", "Reuniones"),
               32830: ("guardias", "Guardias"), 33030: ("guardiasRecreo", "Guardias de recreo")}


class DialogoNombres(_DlgRC):
    """Diálogo 209: «Cambiar nombres, códigos y códigos externos». Solo afecta a la presentación del editor e informes."""
    RID = "E209"

    def __init__(self, parent, ed, cat, titulo):
        super().__init__(parent, TX("cambiar_nombres_codigos_titulo", titulo=titulo))
        self.ed, self.cat = ed, cat
        self.lst = self.c[1055]; self.lst.setHeaderLabels([TX("codigo"), "Abreviatura", "Nombre completo"])
        self.lst.setSelectionMode(QAbstractItemView.ExtendedSelection)
        for b in (1141, 1138, 1144):
            self.c[b].setEnabled(False); self.c[b].setToolTip("Las altas, bajas y claves externas se gestionan en el planificador" if b != 1144 else PROX)
        self.c[1026].clicked.connect(self.modificar); self.c[2].clicked.connect(self.accept)
        self.lst.itemDoubleClicked.connect(lambda *_: self.modificar())
        self.llenar()

    def llenar(self):
        self.lst.clear(); self.filas = self.ed.nombres_de(self.cat)
        for o, i, a, c in self.filas:
            it = QTreeWidgetItem([i, a, c]); it.setData(0, Qt.UserRole, o); self.lst.addTopLevelItem(it)

    def modificar(self, no_modal=False):
        sel = [self.lst.indexOfTopLevelItem(it) for it in self.lst.selectedItems()] or ([0] if self.filas else [])
        if not sel:
            return None
        d = DialogoIdentificativo(self, self.ed, self.cat, self.filas, sorted(sel)[0]); self._dlg = d
        if no_modal:
            return d
        if d.exec():
            self.llenar()
        return d


class DialogoIdentificativo(_DlgRC):
    """Diálogo 210: «Añadir o cambiar códigos en las listas» con Anterior/Siguiente."""
    RID = "E210"
    OCULTAR = (1136, 1137, 1048, 1084, 1067, 1497, 1034, 1021, 1007, 1090, 1049, 1112, 1047, 1001, 1002, 1003, 1005,
               1138, 1139, 1165, 1498, 1499, 1055, 1533)

    def __init__(self, parent, ed, cat, filas, i):
        super().__init__(parent)
        from PySide6.QtWidgets import QGroupBox
        for wd in self.pg.findChildren(QLabel):
            if wd.text().startswith("(*)"):
                wd.hide()
        for wd in self.pg.findChildren(QGroupBox):
            wd.hide()
        self.ed, self.cat, self.filas, self.i = ed, cat, filas, i
        self.cambios = {}
        self.c[1].clicked.connect(self.aceptar); self.c[2].clicked.connect(self.reject)
        self.c[1053].clicked.connect(lambda: self.ir(-1)); self.c[1054].clicked.connect(lambda: self.ir(1))
        self.mostrar()

    def _guardar(self):
        o = self.filas[self.i][0]
        self.cambios[o] = {"nombre": self.c[1000].text().strip(), "abreviatura": self.c[1259].text().strip(),
                           "nombreCompleto": self.c[1018].text().strip()}

    def mostrar(self):
        o, i, a, c = self.filas[self.i]; v = self.cambios.get(o, {})
        self.c[1000].setText(v.get("nombre", i)); self.c[1259].setText(v.get("abreviatura", a)); self.c[1018].setText(v.get("nombreCompleto", c))
        self.c[1053].setEnabled(self.i > 0); self.c[1054].setEnabled(self.i < len(self.filas) - 1)

    def ir(self, paso):
        self._guardar(); self.i = max(0, min(len(self.filas) - 1, self.i + paso)); self.mostrar()

    def aceptar(self):
        self._guardar(); err = self.ed.fijar_nombres(self.cat, self.cambios)
        if err:
            self.error = err
            p = self.parent()
            while p is not None and not hasattr(p, "_no_modal"):
                p = p.parent()
            if not getattr(p, "_no_modal", False):
                QMessageBox.warning(self, APP_ED, err)
            return False
        self.accept(); return True


class DialogoMarcos(QDialog):
    """EDICIÓN > Marcos horarios: horas de entrada y salida, clave de los periodos y nombres de los marcos (presentación)."""

    def __init__(self, parent, ed, que):
        super().__init__(parent); self.ed, self.que = ed, que
        self.setWindowTitle({"horas": "Horas de entrada y salida", "claves": TX("codigos_horas"),
                             "nombres": "Nombres de los marcos"}[que]); self.setFont(fuente_dialogo())
        lay = QVBoxLayout(self); self.cb = QComboBox(); self.cb.addItems(list(ed.p.marcos))
        self.tab = QTableWidget(); lay.addWidget(QLabel("Marco horario:")); lay.addWidget(self.cb); lay.addWidget(self.tab)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); lay.addWidget(bb)
        bb.accepted.connect(self.aceptar); bb.rejected.connect(self.reject)
        self.cb.currentTextChanged.connect(self.llenar); self.resize(460, 420); self.llenar()

    def llenar(self, *_):
        m = self.cb.currentText(); fil = self.ed.p.marcos[m].filas() if m else []
        if self.que == "nombres":
            ms = list(self.ed.p.marcos); self.tab.setRowCount(len(ms)); self.tab.setColumnCount(2)
            self.tab.setHorizontalHeaderLabels(["Marco", "Nombre a mostrar"])
            for r, k in enumerate(ms):
                a = QTableWidgetItem(k); a.setFlags(Qt.ItemIsEnabled); self.tab.setItem(r, 0, a)
                self.tab.setItem(r, 1, QTableWidgetItem(self.ed.nombre_marco(k)))
            self.cb.setEnabled(False); return
        cols = ["Periodo", "Entrada", "Salida"] if self.que == "horas" else ["Periodo", TX("codigo_2")]
        self.tab.setRowCount(len(fil)); self.tab.setColumnCount(len(cols)); self.tab.setHorizontalHeaderLabels(cols)
        for r, t in enumerate(fil):
            a = QTableWidgetItem(f"{t.indice} ({t.tipo})"); a.setFlags(Qt.ItemIsEnabled); a.setData(Qt.UserRole, t.indice); self.tab.setItem(r, 0, a)
            vals = list(self.ed.hora_tramo(m, t)) if self.que == "horas" else [self.ed.clave_tramo(m, t)]
            for c, v in enumerate(vals, 1):
                self.tab.setItem(r, c, QTableWidgetItem(v))

    def aceptar(self):
        m = self.cb.currentText()
        if self.que == "nombres":
            for r in range(self.tab.rowCount()):
                k = self.tab.item(r, 0).text(); v = self.tab.item(r, 1).text().strip()
                self.ed.fijar_marco(k, nombre=v if v and v != k else "")
        else:
            d = {}
            for r in range(self.tab.rowCount()):
                ix = str(self.tab.item(r, 0).data(Qt.UserRole))
                d[ix] = [self.tab.item(r, 1).text().strip(), self.tab.item(r, 2).text().strip()] if self.que == "horas" else self.tab.item(r, 1).text().strip()
            if self.que == "horas":
                import re
                if any(not re.fullmatch(r"\d{1,2}:\d{2}", x) for v in d.values() for x in v):
                    QMessageBox.warning(self, APP_ED, "Las horas deben tener el formato hh:mm."); return
            self.ed.fijar_marco(m, **{self.que: d})
        self.accept()


def _txt_pos(ed, pos, L=1):
    """(Día, HH:MM-HH:MM, Marco, Duración) de una posición (o «Sin hueco en el horario.»)."""
    if pos is None:
        return ("", "", "", "")
    m, d, i = pos; t = ed.tramos.get(pos)
    e, sa = ed.hora_tramo(m, t) if t else ("", "")
    if L > 1:
        t2 = ed.tramos.get((m, d, i + L - 1)); sa = ed.hora_tramo(m, t2)[1] if t2 else sa
    return (DIAS[d] if d < len(DIAS) else str(d), f"{e}-{sa}", ed.nombre_marco(m), f"{L} p.")


class DialogoListaMarcable(_DlgRC):
    """Diálogos 938/939/940: restricciones observadas, profesores y grupos movibles (lista con casillas)."""

    def __init__(self, parent, rid, columnas, filas, marcadas, b_todos=1104, b_ninguno=1068):
        self.RID = rid
        super().__init__(parent)
        self.lst = self.c[1055]; self.lst.setHeaderLabels(columnas); self.lst.setSortingEnabled(True)
        for f in filas:
            it = QTreeWidgetItem(list(f) if isinstance(f, (list, tuple)) else [f])
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable); it.setCheckState(0, Qt.Checked if (f[0] if isinstance(f, (list, tuple)) else f) in marcadas else Qt.Unchecked)
            self.lst.addTopLevelItem(it)
        self.c[b_todos].clicked.connect(lambda: self._todas(Qt.Checked)); self.c[b_ninguno].clicked.connect(lambda: self._todas(Qt.Unchecked))
        self.c[1].clicked.connect(self.accept); self.c[2].clicked.connect(self.reject)
        if 1067 in self.c:
            self.c[1067].setEnabled(False)

    def _todas(self, st):
        for i in range(self.lst.topLevelItemCount()):
            self.lst.topLevelItem(i).setCheckState(0, st)

    def marcadas(self):
        return {self.lst.topLevelItem(i).text(0) for i in range(self.lst.topLevelItemCount())
                if self.lst.topLevelItem(i).checkState(0) == Qt.Checked}


class DialogoRecombinador(_DlgRC):
    """Diálogo 754: «Asistente para recolocar»."""
    RID = "E754"

    def __init__(self, ventana, item, destino=None):
        super().__init__(ventana)
        self.v, self.ed, self.item, self.destino = ventana, ventana.ed, item, destino
        self.sols, self.parado = [], False
        ed = self.ed; o = ed.obj(item)
        self.lst = self.c[1055]; self.lst.setHeaderLabels(["Materia", "Grupo", "Profesorado", "Tmp", "Aula", "Aulas Alter."])
        fila = ed.descripcion_fuera(item) if item[0] == "n" else [ed.descripcion(item), "", "", str(len(ed.posiciones(item))), "", ""]
        self.lst.addTopLevelItem(QTreeWidgetItem(fila))
        L = ed._longitud(o) if item[0] == "n" and o.get("tipo") == "sesion" else max(1, len(ed.posiciones(item)))
        self.L = L
        desde = None if item[0] == "n" else ed.posiciones(item)[0]
        for cid, txt in zip((1489, 1132, 1491, 1493), _txt_pos(ed, desde, L)):
            self.c[cid].setText(txt)
        self.c[1517].setVisible(desde is None)
        for cid, txt in zip((1484, 1130, 1485, 1488), _txt_pos(ed, destino, L)):
            self.c[cid].setText(txt)
        self.c[1518].setVisible(destino is None)
        self.c[1395].setText("")
        self.observar = set(); self.prof_fijos, self.grupos_fijos = set(), set()
        self.c[1521].clicked.connect(self.ver_restricciones); self.c[1526].clicked.connect(self.ver_profesores)
        self.c[1527].clicked.connect(self.ver_alumnos)
        sp = self.c[1000]
        if hasattr(sp, "setRange"):
            sp.setRange(1, 6); sp.setValue(3)
        else:
            sp.setText("3")
        self.c[1511].clicked.connect(self.buscar); self.c[1512].clicked.connect(self.detener)
        self.c[3].clicked.connect(self.ver_solucion); self.c[2].clicked.connect(self.cerrar)
        for k in (1001, 1002, 1003, 1005):
            self.c[k].setEnabled(False); self.c[k].toggled.connect(self._resumen)
        self.c[1512].hide(); self.c[1522].hide()
        self._contadores(); self._resumen()

    def _contadores(self):
        cats = self.ed.categorias_restricciones()
        self.c[1523].setText(f"Hay {len(cats) - len(self.observar)} restricciones que se podrían ignorar")
        self.c[1528].setText(f"Hay {len(self.prof_fijos)} profesores con su horario inmovilizado")
        self.c[1529].setText(f"Hay {len(self.grupos_fijos)} grupos con su horario inmovilizado")

    def _modal(self, d):
        if getattr(self.v, "_no_modal", False):
            d.show(); self._sub = d; return False
        return d.exec()

    def ver_restricciones(self):
        d = DialogoListaMarcable(self, "E938", ["Restricción"], self.ed.categorias_restricciones(), self.observar)
        if self._modal(d):
            self.observar = d.marcadas(); self._contadores()
        return d

    def ver_profesores(self):
        todos = [e.nombre for e in self.ed.p.profesores]
        d = DialogoListaMarcable(self, "E939", ["Profesor"], todos, set(todos) - self.prof_fijos)
        if self._modal(d):
            self.prof_fijos = set(todos) - d.marcadas(); self._contadores()
        return d

    def ver_alumnos(self):
        todos = [e.nombre for e in self.ed.p.grupos]
        d = DialogoListaMarcable(self, "E940", ["Grupo"], todos, set(todos) - self.grupos_fijos, b_todos=1068, b_ninguno=1104)
        if self._modal(d):
            self.grupos_fijos = set(todos) - d.marcadas(); self._contadores()
        return d

    def max_mov(self):
        sp = self.c[1000]
        return sp.value() if hasattr(sp, "value") else int(sp.text() or 3)

    def detener(self):
        self.parado = True

    def buscar(self):
        import time
        self.parado = False; self.c[1511].hide(); self.c[1512].show(); self.c[1522].show()
        t0 = time.monotonic(); QApplication.processEvents()

        def parar():
            QApplication.processEvents(); self.c[1513].setText(f"{time.monotonic() - t0:.1f} s"); return self.parado
        self.sols = self.ed.recombinar(self.item, self.destino, self.max_mov(), self.prof_fijos, self.grupos_fijos,
                                       self.observar or None, parar=parar)
        self.c[1513].setText(f"{time.monotonic() - t0:.1f} s"); self.c[1520].setText("0 s")
        self.c[1511].show(); self.c[1512].hide(); self.c[1522].hide()
        self.c[1519].setText(str(len(self.sols)))
        for i, k in enumerate((1001, 1002, 1003, 1005)):
            self.c[k].setEnabled(i < len(self.sols))
        if self.sols:
            self.c[1001].setChecked(True); self.c[1532].setText("Hay soluciones")
        else:
            self.c[1532].setText(TX("no_hay_ninguna_solucion_estos_2"))
            if not getattr(self.v, "_no_modal", False):
                QMessageBox.information(self, APP_ED, TX("no_hay_ninguna_solucion_estos"))
        self._resumen(); return self.sols

    def elegida(self):
        for i, k in enumerate((1001, 1002, 1003, 1005)):
            if self.c[k].isChecked() and i < len(self.sols):
                return i
        return None

    def _resumen(self, *_):
        i = self.elegida(); self.c[3].setEnabled(i is not None)
        if i is None:
            self.c[1525].setText(TX("elija_solucion_verla_aplicarla") if self.sols else
                                 TX("guardaran_soluciones_menos_movimientos_menos")); return
        s = self.sols[i]
        self.c[1525].setText(f"La solución  {i + 1}  ha realizado  {len(s['movs'])}  movimiento(s), ignorando en total "
                             f"{s['restr']} restricciones y {s['avisos']} notificaciones")

    def ver_solucion(self):
        i = self.elegida()
        if i is None:
            return None
        d = DialogoSolucion(self, i); self._dlg_sol = d
        if getattr(self.v, "_no_modal", False):
            d.show(); return d
        if d.exec() == 1524:
            self.accept()
        return d

    def cerrar(self):
        if self.sols and not getattr(self.v, "_no_modal", False):
            if QMessageBox.question(self, APP_ED, TX("cerrar_asistente_sin_aplicar_ninguna")) != QMessageBox.Yes:
                return
        self.reject()


class DialogoSolucion(_DlgRC):
    """Diálogo 773: «Movimientos de la solución %d»."""
    RID = "E773"

    def __init__(self, asis, i):
        super().__init__(asis)
        from PySide6.QtWidgets import QTabBar
        self.a, self.i, self.sol, self.ed = asis, i, asis.sols[i], asis.ed
        self.setWindowTitle(f"Viendo los movimientos de la solución {i + 1}")
        g = self.c[1055].geometry(); self.tabs = QTabBar(self.pg)
        ky, kh = g.y() / 82, g.height() / 75          # escala de unidades de diálogo (1055 está en y=82, alto 75)
        self.tabs.setGeometry(g.x(), int(18 * ky), g.width(), max(20, int(18 * kh)))
        for k in range(len(self.sol["movs"])):
            self.tabs.addTab(f"Mov. {k + 1}")
        self.tabs.currentChanged.connect(self.mostrar)
        self.c[1055].setHeaderLabels(["Materia", "Grupo", "Profesorado", "Tmp", "Aula"])
        self.c[1056].setHeaderLabels(["Mensaje"])
        self.c[1529].clicked.connect(lambda: self._ver("Profesorado")); self.c[1530].clicked.connect(lambda: self._ver("Grupos"))
        self.c[1067].setEnabled(False)
        self.c[2].clicked.connect(self.reject); self.c[1524].clicked.connect(self.aplicar)
        self.mostrar(0)

    def mostrar(self, k):
        it, desde, hasta = self.sol["movs"][k]; ed = self.ed; L = self.a.L if k == 0 else len(ed.posiciones(it))
        self.c[1527].setText(f"Movimiento {k + 1} de la solución {self.i + 1}")
        for cid, txt in zip((1484, 1130, 1485, 1488), _txt_pos(ed, desde, L)):
            self.c[cid].setText(txt)
        self.c[1517].setVisible(desde is None)
        for cid, txt in zip((1489, 1132, 1491, 1493), _txt_pos(ed, hasta, L)):
            self.c[cid].setText(txt)
        self.c[1055].clear()
        fila = ed.descripcion_fuera(it) if it[0] == "n" else [ed.descripcion(it), "", "", str(len(ed.posiciones(it))), ""]
        self.c[1055].addTopLevelItem(QTreeWidgetItem(fila[:5]))
        self.c[1056].clear()
        for e in self.sol.get("errores", []) if k == len(self.sol["movs"]) - 1 else []:
            self.c[1056].addTopLevelItem(QTreeWidgetItem([f"{e[0]}: {e[1]}"]))
        self.mov = k

    def _ver(self, vista):
        it = self.sol["movs"][self.mov][0]
        rec = self.ed.recursos(it) if it[0] != "n" else self.ed.recursos(it)
        tp = "profesor" if vista == "Profesorado" else "grupo"
        n = next((nm for t, nm in sorted(rec) if t == tp), None)
        if n:
            self.a.v.ir_a(vista, n)

    def aplicar(self):
        if not getattr(self.a.v, "_no_modal", False):
            if QMessageBox.question(self, APP_ED, TX("aplicar_solucion_n", n=self.i + 1)) != QMessageBox.Yes:
                return False
        self.ed.aplicar_solucion(self.sol); self.a.v.refrescar(); self.done(1524); self.a.accept(); return True


class DialogoAvisoOcultos(_DlgRC):
    """Diálogo 781: aviso de las opciones de presentación que ocultan información."""
    RID = "E781"

    def __init__(self, parent, lista):
        super().__init__(parent)
        self.c[1020].setText("\n".join(lista)); self.c[1020].setWordWrap(True) if hasattr(self.c[1020], "setWordWrap") else None
        self.c[1].clicked.connect(self.accept); self.c[2].clicked.connect(self.reject)
        self.c[1016].toggled.connect(lambda on: parent._fijar_ajuste("avisar_ocultos", not on))


class DialogoConflictos(_DlgRC):
    """Diálogo 177: mensajes al agregar/mover (Extraer, Continuar, Cancelar)."""
    RID = "E177"

    def __init__(self, parent, prop):
        super().__init__(parent, prop.titulo + "...")
        self.prop, self.extraer = prop, []
        self.lst = self.c[1055]; self.lst.setHeaderLabels(["Mensaje"]); self.lst.setSelectionMode(QAbstractItemView.SingleSelection)
        for txt, it in prop.mensajes:
            w = QTreeWidgetItem([txt]); w.setData(0, Qt.UserRole, it)
            w.setIcon(0, _icono_estado("#d33" if it else "#e6b800")); self.lst.addTopLevelItem(w)
        self.lst.currentItemChanged.connect(self._sel)
        self.c[1058].clicked.connect(self.extraer_sel)
        self.c[1].clicked.connect(self.accept); self.c[2].clicked.connect(self.reject)
        self.c[1501].setEnabled(False); self.c[1501].setToolTip(PROX)
        self.c[1067].clicked.connect(lambda: _proximamente(self, "La ayuda sobre el mensaje"))
        if self.lst.topLevelItemCount():
            self.lst.setCurrentItem(self.lst.topLevelItem(0))
        self._sel()

    def _sel(self, *_):
        w = self.lst.currentItem(); it = w.data(0, Qt.UserRole) if w else None
        self.c[1070].setText(self.parent().ed.descripcion(it, self.prop.doc) if it else "(el mensaje no corresponde a una sesión extraíble)")
        self.c[1058].setEnabled(bool(it))

    def extraer_sel(self):
        w = self.lst.currentItem(); it = w.data(0, Qt.UserRole) if w else None
        if not it:
            return
        self.extraer.append(it)
        for i in reversed(range(self.lst.topLevelItemCount())):
            if self.lst.topLevelItem(i).data(0, Qt.UserRole) == it:
                self.lst.takeTopLevelItem(i)
        self._sel()


class DialogoFuera(_DlgRC):
    """Diálogo 166: Sesiones sin hueco en el horario."""
    RID = "E166"; OCULTAR = (1401, 1405, 1172, 1168, 1540, 1007, 1067, 32776, 32777, 1533)

    def __init__(self, ventana):
        super().__init__(ventana)
        self.v = ventana; self.setModal(False)
        self.lst = self.c[1052]
        self.lst.setHeaderLabels(["Materia", "Grupo", "Profesorado", "Tmp", "Aula", "Aulas Alter."])
        self.lst.setSelectionMode(QAbstractItemView.SingleSelection)
        self.lst.setDragEnabled(True); self.lst.startDrag = self._arrastrar
        self.filtro = self.c[1004]; self.filtro.addItems(["Todas", "Lectivas", "Guardias", "Reuniones", "Complementarias"])
        self.filtro.currentIndexChanged.connect(self.refrescar)
        self.c[1135].clicked.connect(self.agregar_sobre_celda)
        self.c[1095].clicked.connect(self.separar); self.c[1094].clicked.connect(self.duplicar)
        self.c[1501].clicked.connect(self.asistente)
        self.c[1079].clicked.connect(lambda: self.v.menu_nuevas().exec(self.c[1079].mapToGlobal(QPoint(0, self.c[1079].height()))))
        self.c[1064].clicked.connect(self.modificar)
        self.c[1093].clicked.connect(self.eliminar)
        self.refrescar()

    def _arrastrar(self, acciones):
        it = self.actual()
        if it:
            md = QMimeData(); md.setData(MIME, it.encode()); d = QDrag(self.lst); d.setMimeData(md); d.exec(Qt.MoveAction)

    def refrescar(self):
        ed = self.v.ed; f = self.filtro.currentText()
        tipo = {"Lectivas": "sesion", "Guardias": "guardia", "Reuniones": "reunion", "Complementarias": "complementaria"}.get(f)
        sel = self.actual(); self.lst.clear()
        for i, nc in enumerate(ed.doc["no_colocadas"]):
            if tipo and nc.get("tipo") != tipo:
                continue
            w = QTreeWidgetItem(ed.descripcion_fuera(f"n:{i}")); w.setData(0, Qt.UserRole, f"n:{i}")
            self.lst.addTopLevelItem(w)
            if f"n:{i}" == sel:
                self.lst.setCurrentItem(w)
        for k in range(6):
            self.lst.resizeColumnToContents(k)

    def actual(self):
        w = self.lst.currentItem()
        return w.data(0, Qt.UserRole) if w else None

    def seleccionar(self, nitem):
        for i in range(self.lst.topLevelItemCount()):
            if self.lst.topLevelItem(i).data(0, Qt.UserRole) == nitem:
                self.lst.setCurrentItem(self.lst.topLevelItem(i)); return True
        return False

    def agregar_sobre_celda(self):
        it = self.actual(); pos = self.v.celda_actual()
        if not it or pos is None:
            QMessageBox.information(self, APP_ED, "Seleccione una línea de la lista y una celda del horario."); return
        self.v.soltar(it, pos)

    def modificar(self):
        it = self.actual()
        if it:
            nc = self.v.ed.obj(it)
            if nc.get("tipo") == "sesion":
                self.v.modificar_sesiones(nc["sesiones"])
            else:
                QMessageBox.information(self, APP_ED, TX("guardias_reuniones_complementarias_cambian_planificador"))

    def _pregunta(self, txt):
        return getattr(self.v, "_no_modal", False) or QMessageBox.question(self, APP_ED, txt + TX("seguir")) == QMessageBox.Yes

    def _aviso(self, txt):
        self.ultimo_aviso = txt
        if not getattr(self.v, "_no_modal", False):
            QMessageBox.information(self, APP_ED, txt)

    def separar(self):
        it = self.actual()
        if not it or not self._pregunta(TX("sesiones_sin_hueco_quedaran_separadas")):
            return None
        try:
            r = self.v.ed.separar_fuera(it)
        except ErrorEdicion as e:
            self._aviso(str(e)); return None
        self.v.refrescar(); return r

    def duplicar(self):
        it = self.actual()
        if not it or not self._pregunta(TX("duplicaran_sesiones_elegidas_estan_fuera")):
            return None
        r = self.v.ed.duplicar_fuera(it); self.v.refrescar(); return r

    def asistente(self):
        """Añadir al horario con el asistente: abre el Recombinador con la línea seleccionada."""
        it = self.actual()
        if not it:
            self._aviso("Seleccione una línea de la lista."); return None
        return self.v.recombinador(it)

    def eliminar(self):
        it = self.actual()
        if not it:
            return
        if QMessageBox.question(self, APP_ED, TX("borrara_siempre_linea_elegida_seguir")) != QMessageBox.Yes:
            return
        self.v.ed.eliminar_fuera(it); self.v.refrescar()


class DialogoPresentacionCeldas(_DlgRC):
    """Diálogo 196 «Aspecto de las celdas» (FORMATO > Qué se ve en las celdas)."""
    RID = "E196"; OCULTAR = (1146, 1536, 1533, 1534)
    CHECKS = {1091: "ocultar_aula", 1095: "ocultar_materia", 1097: "ocultar_profesor", 1098: "ocultar_grupo",
              1094: "duracion", 1092: "una_fila", 1096: "ocultar_separacion", 1017: "solo_entrada",
              1016: "ocultar_vacias", 1099: "ocultar_recreos", 1100: "ocultar_mediodia"}
    HORAS = {1013: "no", 1002: "distintas", 1003: "todas"}
    IDENT = {"materias": (1001, 1113, 1044), "alumnos": (1005, 1114, 1047), "profesores": (1006, 1004, 1058),
             "aulas": (1088, 1207, 1059), "cursos": (1048, None, 1060), "departamentos": (1018, None, 1228),
             "tareas": (1014, None, 1062)}

    def __init__(self, ventana):
        super().__init__(ventana)
        o = ventana.ed.celdas(); self.o = o
        for cid, k in self.CHECKS.items():
            self.c[cid].setChecked(bool(o[k]))
        self.pg.regrupar(list(self.HORAS), *[[x for x in t if x] for t in self.IDENT.values()])
        for cid, k in self.HORAS.items():
            self.c[cid].setChecked(o["horas"] == k)
        for cat, ids in self.IDENT.items():
            for cid, modo in zip(ids, ("id", "abrev", "completo")):
                if cid:
                    self.c[cid].setChecked(o["ident"].get(cat, "id") == modo)
        if isinstance(self.c[1000], QSpinBox):
            self.sp = self.c[1000]
        else:
            self.sp = QSpinBox(self.pg); self.sp.setGeometry(self.c[1000].geometry()); self.c[1000].hide()
        self.sp.setRange(1, 99); self.sp.setValue(int(o["desdobles"]))
        for cid, modo in ((1070, 0), (1067, 1), (1071, 2)):
            self.c[cid].clicked.connect(lambda _=False, m=modo: self.siempre(m))
        self.c[1].clicked.connect(self.accept); self.c[2].clicked.connect(self.reject)

    def siempre(self, n):
        """Siempre el código / abreviatura / nombre completo (si no hay abreviatura, identificativo)."""
        for ids in self.IDENT.values():
            cid = ids[n] or ids[0]
            self.c[cid].setChecked(True)

    def permanente(self):
        return self.c[1111].isChecked()

    def valores(self):
        o = copy.deepcopy(self.o)
        for cid, k in self.CHECKS.items():
            o[k] = self.c[cid].isChecked()
        o["horas"] = next(k for cid, k in self.HORAS.items() if self.c[cid].isChecked()) if any(
            self.c[c].isChecked() for c in self.HORAS) else "no"
        for cat, ids in self.IDENT.items():
            for cid, modo in zip(ids, ("id", "abrev", "completo")):
                if cid and self.c[cid].isChecked():
                    o["ident"][cat] = modo
        o["desdobles"] = self.sp.value()
        return o


class DialogoCambiarAula(_DlgRC):
    """Diálogo 208: Cambiar el aula (origen/destino; Cambiar el aula por otra / Pasar al aula libre)."""
    RID = "E208"; OCULTAR = (1040, 1143, 1144, 1145, 1146, 1395, 1536, 1131, 1150)

    def __init__(self, ventana, item):
        self.v, self.item = ventana, item
        ed = ventana.ed; m, d, i = ed.posiciones(item)[0]; t = ed.tramos[(m, d, i)]
        super().__init__(ventana, f"Cambiar el aula, {DIAS[d]}, {t.entrada}-{t.salida}")
        self.pos = (m, d, i)
        self.c[1484].setText(DIAS[d]); self.c[1130].setText(f"{t.entrada}-{t.salida}"); self.c[1485].setText(str(getattr(ed.p.marcos[m], 'nombre', m)))
        self.c[1033].setHeaderLabels(["Aula", "Sesión"]); self.c[1032].setHeaderLabels(["Aula", "Sesión"])
        self.c[1031].setHeaderLabels(["Aula", "Estado"])
        for cid in (1033, 1032, 1031):
            self.c[cid].setSelectionMode(QAbstractItemView.SingleSelection)
        self.c[1033].currentItemChanged.connect(self._origen); self.c[1031].currentItemChanged.connect(self._destino)
        self.c[1039].clicked.connect(self.aplicar); self.c[2].clicked.connect(self.accept)
        self.cargar()

    def cargar(self):
        ed = self.v.ed; o = ed.obj(self.item)
        self.c[1033].clear()
        for a in o.get("aulas", []):
            self.c[1033].addTopLevelItem(QTreeWidgetItem([a, ed.descripcion(self.item)]))
        if self.c[1033].topLevelItemCount():
            self.c[1033].setCurrentItem(self.c[1033].topLevelItem(0))
        est = ed.estado_aulas(*self.pos, excluir=self.item)
        col = {"libre": "#2e9e4a", "ocupada": "#d33", "prohibida": "#888"}
        self.c[1031].clear()
        for a, e in est.items():
            w = QTreeWidgetItem([a, {"libre": "Aula libre", "ocupada": TX("aula_clase"), "prohibida": TX("hora_prohibida_plantilla_aula")}[e]])
            w.setIcon(0, _icono_estado(col[e])); self.c[1031].addTopLevelItem(w)
        for cid in (1031, 1033):
            self.c[cid].resizeColumnToContents(0)
        self._origen(); self._destino()

    def origen(self):
        w = self.c[1033].currentItem(); return w.text(0) if w else ""

    def destino(self):
        w = self.c[1031].currentItem(); return w.text(0) if w else ""

    def _origen(self, *_):
        self.c[1035].setText(" " + self.origen())

    def _destino(self, *_):
        ed = self.v.ed; dst = self.destino(); self.c[1036].setText(" " + dst); self.c[1032].clear()
        ocup = ed.ocupantes_aula(dst, *self.pos, excluir=self.item) if dst else []
        for it in ocup:
            self.c[1032].addTopLevelItem(QTreeWidgetItem([dst, ed.descripcion(it)]))
        self.c[1037].setText(TX("sesion") if ocup else "")
        self.c[1039].setText(TX("cambiar_aula_otra") if ocup else TX("pasar_aula_libre")); ajustar(self.c[1039])
        self.c[1039].setEnabled(bool(dst and self.origen() and dst != self.origen()))

    def aplicar(self):
        ed = self.v.ed; antes = len(ed.comprobar().errores)
        try:
            ed.cambiar_aula(self.item, self.origen(), self.destino())
        except ErrorEdicion as e:
            QMessageBox.warning(self, APP_ED, str(e)); return
        inf = ed.comprobar()
        if len(inf.errores) > antes:
            QMessageBox.warning(self, APP_ED, "El cambio introduce incidencias (puede deshacerlo con Ctrl+Z):\n" +
                                "\n".join(f"{a}: {b}" for a, b in inf.errores[:6]))
        self.v.refrescar(); self.cargar()


class DialogoLibres(QDialog):
    def __init__(self, ventana, tipo, pos):
        super().__init__(ventana)
        m, d, i = pos; t = ventana.ed.tramos[pos]
        self.setWindowTitle(f"{'Profesores' if tipo == 'profesores' else 'Aulas'} libres - {DIAS[d]}, {t.entrada}-{t.salida}")
        L = QVBoxLayout(self); self.lst = QListWidget(); L.addWidget(self.lst)
        for n, proh in ventana.ed.libres(tipo, *pos):
            w = QListWidgetItem(n + ("   (posición no permitida en su plantilla)" if proh else ""))
            w.setIcon(_icono_estado("#888" if proh else "#2e9e4a")); self.lst.addItem(w)
        L.addWidget(QLabel(f"{self.lst.count()} libres")); b = QPushButton("Cerrar"); b.clicked.connect(self.accept)
        L.addWidget(b, 0, Qt.AlignRight); self.resize(380, 420)


class DialogoLectiva(_DlgRC):
    """Diálogo 225: Nuevas sesiones lectivas (también simultáneas y modificar)."""
    RID = "E225"; OCULTAR = (1016, 1174, 1001, 1002, 1003, 1004, 1005, 1006, 1168, 1169, 1123, 1125, 1127, 1029)

    def __init__(self, ventana, titulo=None, valores=None, fijos=()):
        super().__init__(ventana, titulo)
        p = ventana.ed.p; self.mas = False
        for cid, lista in ((1137, p.materias), (1138, p.grupos), (1139, p.profesores), (1191, p.aulas), (1190, p.tareas)):
            cb = self.c[cid]; cb.setEditable(False); cb.addItems([""] + [e.nombre for e in lista] if cid in (1191,) else [e.nombre for e in lista])
        _pon(self.c[1140], 1)
        for k, v in (valores or {}).items():
            w = self.c[{"materia": 1137, "grupo": 1138, "profesor": 1139, "aula": 1191, "tarea": 1190, "periodos": 1140}[k]]
            w.setCurrentText(v) if isinstance(w, QComboBox) else _pon(w, v)
        for k in fijos:
            self.c[{"materia": 1137, "grupo": 1138, "periodos": 1140}[k]].setEnabled(False)
        self.c[1].clicked.connect(self.accept); self.c[2].clicked.connect(self.reject)
        self.c[1537].clicked.connect(lambda: (setattr(self, "mas", True), self.accept()))

    def valores(self):
        n = _num(self.c[1140])
        return {"materia": self.c[1137].currentText(), "grupo": self.c[1138].currentText(),
                "profesor": self.c[1139].currentText(), "aula": self.c[1191].currentText(),
                "tarea": self.c[1190].currentText(), "periodos": n}


class DialogoComplementaria(_DlgRC):
    RID = "E224"; OCULTAR = (1174, 1001, 1002, 1003, 1004, 1005, 1006, 1168, 1169, 1179, 1181, 1182, 1183, 1184, 1055, 1533, 1077, 1072, 1488)

    def __init__(self, ventana):
        super().__init__(ventana)
        p = ventana.ed.p
        self.c[1075].addItems([e.nombre for e in p.profesores]); self.c[1076].addItems([e.nombre for e in p.tareas])
        _pon(self.c[1000], 1)
        self.c[1].clicked.connect(self.accept); self.c[2].clicked.connect(self.reject); self.c[1537].setEnabled(False)

    def valores(self):
        n = _num(self.c[1000])
        return {"profesor": self.c[1075].currentText(), "tarea": self.c[1076].currentText(), "periodos": n}


class DialogoGuardia(_DlgRC):
    RID = "E191"; OCULTAR = (1395, 1082)

    def __init__(self, ventana):
        super().__init__(ventana)
        p = ventana.ed.p
        self.c[1080].addItems([e.nombre for e in p.guardias]); self.c[1075].addItems([e.nombre for e in p.profesores])
        _pon(self.c[1081], 1)
        self.c[1066].clicked.connect(self.accept); self.c[2].clicked.connect(self.reject); self.c[1537].setEnabled(False)

    def valores(self):
        n = _num(self.c[1081])
        return {"servicio": self.c[1080].currentText(), "profesor": self.c[1075].currentText(), "n": n}


class DialogoReunion(_DlgRC):
    RID = "E184"; OCULTAR = (1179, 1181, 1182, 1183, 1184, 1168, 1169, 1055, 1533, 1145, 1073, 1072)

    def __init__(self, ventana):
        super().__init__(ventana)
        self.v = ventana; self.ints = []
        self.c[1190].addItems([e.nombre for e in ventana.ed.p.tareas]); _pon(self.c[1081], 1)
        self.c[1001].setChecked(True); self.c[1064].setReadOnly(True) if isinstance(self.c[1064], QLineEdit) else None
        self.c[1059].clicked.connect(self.anadir); self.c[1063].clicked.connect(self.quitar)
        self.c[1].clicked.connect(self.accept); self._act()

    def anadir(self):
        from .propiedades_nl import DialogoAnadirProfesores
        d = DialogoAnadirProfesores(self, self.v.ed.p, set(self.ints))
        if d.exec():
            self.ints += list(d.elegidos())
            self.ints = list(dict.fromkeys(self.ints)); self._act()

    def quitar(self):
        n = self.c[1062].currentText()
        if n in self.ints:
            self.ints.remove(n); self._act()

    def _act(self):
        self.c[1062].clear(); self.c[1062].addItems(self.ints); _pon(self.c[1064], len(self.ints))

    def valores(self):
        n = _num(self.c[1081])
        return {"nombre": self.c[1061].text().strip(), "profesores": list(self.ints), "n": n, "doble": self.c[1002].isChecked()}


class DialogoAbrirPlan(_DlgRC):
    RID = "E934"


class DialogoProyectar(QDialog):
    def __init__(self, parent, destino):
        super().__init__(parent)
        self.setWindowTitle(TX("abrir_resultado_planificador")); self.setFont(fuente_dialogo())
        L = QVBoxLayout(self)
        L.addWidget(QLabel("Prefijar sobre la configuración (chinchetas):"))
        self.cb_lect = QCheckBox("La posición de todas las sesiones lectivas, reuniones y complementarias"); self.cb_lect.setChecked(True)
        self.cb_guard = QCheckBox("La posición de las sesiones de guardia"); self.cb_guard.setChecked(True)
        L.addWidget(self.cb_lect); L.addWidget(self.cb_guard)
        L.addWidget(QLabel(TX("archivo_datos_nuevo_no_toca")))
        self.ed_dest = QLineEdit(destino); L.addWidget(self.ed_dest)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); bb.button(QDialogButtonBox.Ok).setText("Aceptar")
        bb.button(QDialogButtonBox.Cancel).setText("Cancelar"); bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        L.addWidget(bb); self.resize(520, 200)


# ====================================================================== ventana principal
class VentanaEditor(QMainWindow):
    abrir_planificador = None        # callable(ruta_xghc) -> ventana; por defecto abre un Planificador

    def __init__(self, ruta_lphr=None, ruta_xghc=None):
        super().__init__()
        self.ed = None; self.opciones = set(); self.zoom = 1.0; self.fuera = None; self._preguntar_proyeccion = True
        self.acc = {}
        self.mdi = QMdiArea(); self.mdi.setViewMode(QMdiArea.SubWindowView); self.setCentralWidget(self.mdi)
        self.mdi.setBackground(QBrush(QColor("#e8e8e8")))
        self._menus(); self._toolbar(); self._barras(); self.statusBar()
        self.lbl_estado = QLabel(); self.statusBar().addPermanentWidget(self.lbl_estado)
        self.resize(1200, 760)
        if ruta_lphr:
            self.abrir(ruta_lphr, ruta_xghc)
        else:
            self._titulo()

    # ---------------------------------------------------- menús
    def _accion(self, cid, texto, atajo=None):
        texto = RENOMBRAR.get(cid, texto)
        a = QAction(texto, self)
        if atajo:
            a.setShortcut(QKeySequence(atajo.replace("RePág", "PgUp").replace("AvPág", "PgDown")))
        f = self._comandos().get(cid)
        if f:
            a.triggered.connect(lambda *_, f=f: f())
        else:
            a.setText(f"{texto}\t{PROX}"); a.setEnabled(False); a.setStatusTip(PROX)
        if cid in (33081, 33086):
            a.setCheckable(True); a.setChecked(self._ajuste({33081: "confirmar_cadena", 33086: "avisar_ocultos"}[cid]))
        self.acc[cid] = a
        return a

    def _poblar(self, menu, items):
        for it in items:
            if it == "-":
                menu.addSeparator(); continue
            if "sub" in it:
                self._poblar(menu.addMenu(it["t"]), it["sub"]); continue
            if it["id"] in OMITIR:
                continue
            menu.addAction(self._accion(it["id"], it["t"], it.get("k")))

    def _menus(self):
        mb = self.menuBar()
        self.a_deshacer = QAction("Deshacer", self, shortcut=QKeySequence("Ctrl+Z"), triggered=self.deshacer)
        self.a_rehacer = QAction("Rehacer", self, shortcut=QKeySequence("Ctrl+Y"), triggered=self.rehacer)
        for tope in MENUS["129"]:
            m = mb.addMenu(tope["t"])
            if tope["t"] == "EDICIÓN":
                m.addAction(self.a_deshacer); m.addAction(self.a_rehacer); m.addSeparator()
            self._poblar(m, tope["sub"])
        # FORMATO > Qué se ve en las celdas: conmutadores del menú 158
        self.a_ocultar = {}
        for clave, cid in (("aula", 32928), ("materia", 32930), ("recreos", 32931)):
            a = QAction(next(x["t"] for x in MENUS["158"] if x != "-" and x["id"] == cid), self, checkable=True)
            a.toggled.connect(lambda on, k=clave: self._ocultar(k, on)); self.a_ocultar[clave] = a

    def _comandos(self):
        return {
            57601: self.dlg_abrir, 57602: self.close, 32808: self.abrir_en_planificador, 57603: self.guardar,
            57604: self.guardar_como, 32983: self.recuperar_copia, 32834: self.recargar, 57665: self.close,
            32851: self.extraer_celda, 32993: self.extraer_asignatura, 32852: self.agregar_al_horario,
            32883: self.crear_nuevas, 32871: self.modificar_celda, 32835: self.cambiar_aula_celda,
            57634: self.copiar, 32817: self.nueva_ventana_actual, 32897: self.menu_opciones_celdas,
            32843: self.poner_quitar_colores, 32916: self.cambiar_color_celda, 32923: self.recuperar_paleta,
            32798: self.altura_optima, 32807: self.informe_motor, 32860: self.sesiones_sin_colocar,
            32804: lambda: self.set_zoom(self.zoom * 1.15), 32805: lambda: self.set_zoom(self.zoom / 1.15),
            32806: lambda: self.set_zoom(1.0), 32776: lambda: self._vista_actual() and self._vista_actual().mover(-1),
            32777: lambda: self._vista_actual() and self._vista_actual().mover(1), 32792: self.nueva_solapa,
            32957: lambda: self._solapa(-1), 32958: lambda: self._solapa(1), 32791: self.elimina_solapa,
            32809: self.nueva_ventana_actual, 57650: self.mdi.cascadeSubWindows, 57652: self.mosaico_vertical,
            57651: self.mosaico_horizontal, 57664: self.acerca, 59392: lambda: self.tb.setVisible(not self.tb.isVisible()),
            59393: lambda: self.statusBar().setVisible(not self.statusBar().isVisible()),
            32955: self.abrir_relacionado_ventana, 32956: self.abrir_relacionado_solapa,
            32997: lambda: self.ver_libres("profesores"), 32998: lambda: self.ver_libres("aulas"),
            32879: self.nueva_lectiva, 32874: self.nueva_simultanea, 32880: self.nueva_complementaria,
            57609: self.presentacion_preliminar, 57607: self.imprimir_actual, 32802: self.imprimir_listado,
            32793: self.configurar_pagina, 57606: self.configurar_impresora, 32778: self.cabeceras_pies,
            32815: self.transferir_externa, 33017: self.importar_claves_externas,
            32977: self.guardar_tabla_pdf, 32978: self.transferir_pdf, 32818: self.letreros, 33096: self.idioma_letreros,
            33002: lambda: self.listado_pdf("asignaciones"), 33001: lambda: self.listado_pdf("equipos"),
            33028: lambda: self.listado_pdf("tutores_alumnos"), 33027: lambda: self.listado_pdf("tutores_tutor"),
            33033: lambda: self.listado_pdf("firmas_aula"), 33034: lambda: self.listado_pdf("firmas_alumnos"),
            33072: lambda: self.listado_pdf("firmas_profesor"), 33004: lambda: self.listado_pdf("ausencias"),
            33049: lambda: self.listado_pdf("equipos_curso"), 33075: lambda: self.listado_pdf("alumnos_subgrupos"),
            32982: lambda: self.listado_pdf("preferencias"), 33080: self.asignaciones_html,
            32799: lambda: self.nueva_solapa_modo("lista"), 32846: lambda: self.nueva_solapa_modo("columnas"),
            32772: lambda: self.nueva_solapa_modo("filas"), 32840: lambda: self.nueva_solapa_modo("recreo"),
            32932: lambda: self.nueva_solapa_modo("cruce"), 32908: lambda: self.nueva_solapa_modo("aulas_libres"),
            32810: lambda: self.nueva_solapa_modo("prof_libres"),
            32948: lambda: self.tb_edicion.setVisible(not self.tb_edicion.isVisible()),
            32790: self.barra_seleccion,
            33037: self.notificaciones, 33081: self.opcion_cadena_aula, 33086: self.opcion_avisar_ocultos,
            **{cid: (lambda cid=cid: self.cambiar_nombres(cid)) for cid in CAT_NOMBRES},
            32842: lambda: self.marcos_horarios("horas"), 33008: lambda: self.marcos_horarios("claves"),
            33015: lambda: self.marcos_horarios("nombres"),
            57649: self.coloca_iconos, 57636: self.buscar, 32823: self.seleccionar_todo,
            32845: self.anotacion, 32889: self.nueva_guardia, 32888: self.nuevo_servicio, 32877: self.nueva_reunion,
        }

    def _toolbar(self):
        tb = self.tb = self.addToolBar("Barra de herramientas"); tb.setMovable(False)
        st = self.style()
        def add(icon, txt, f):
            a = QAction(icon, txt, self); a.triggered.connect(f); tb.addAction(a); return a
        add(iconos.icono("abrir"), "Abrir", self.dlg_abrir); add(iconos.icono("guardar"), "Guardar (F2)", self.guardar)
        add(iconos.icono("imprimir"), TX("imprimir_tabla_ahora_ctrl_i"), self.imprimir_actual)
        tb.addSeparator()
        self.a_deshacer.setIcon(st.standardIcon(QStyle.SP_ArrowBack)); self.a_rehacer.setIcon(st.standardIcon(QStyle.SP_ArrowForward))
        tb.addAction(self.a_deshacer); tb.addAction(self.a_rehacer); tb.addSeparator()
        add(st.standardIcon(QStyle.SP_FileDialogNewFolder), TX("tabla_nueva_otra_pestana"), self.nueva_solapa)
        add(st.standardIcon(QStyle.SP_TitleBarNormalButton), "Nueva ventana", self.nueva_ventana_actual)
        add(st.standardIcon(QStyle.SP_ToolBarHorizontalExtensionButton), TX("mosaico_vertical"), self.mosaico_vertical)
        add(st.standardIcon(QStyle.SP_ToolBarVerticalExtensionButton), TX("mosaico_horizontal"), self.mosaico_horizontal)
        tb.addSeparator()
        add(st.standardIcon(QStyle.SP_FileDialogDetailedView), "Sesiones sin colocar", self.sesiones_sin_colocar)
        add(iconos.icono("validar"), "Comprobar el horario", self.mostrar_comprobacion)
        add(iconos.icono("editor"), "Abrir en el planificador", self.abrir_en_planificador)
        add(iconos.icono("ayuda"), "Ayuda", lambda: _proximamente(self, "La ayuda"))

    # ---------------------------------------------------- archivo
    def abrir(self, ruta, ruta_xghc=None):
        self.ed = Editor(ruta, ruta_xghc)
        from PySide6.QtCore import QSettings
        try:
            self.ed.celdas_base = json.loads(QSettings(VENDOR, AJUSTES).value("editor/celdas", "{}") or "{}")
        except (ValueError, TypeError):
            self.ed.celdas_base = {}
        for sw in self.mdi.subWindowList():
            sw.close()
        self.nueva_ventana("Grupos")
        self.refrescar()
        if self._ajuste("avisar_ocultos") and not getattr(self, "_no_modal", False):
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, self.aviso_ocultos)

    def dlg_abrir(self):
        if not self._descartar():
            return
        r, _ = QFileDialog.getOpenFileName(self, "Abrir", os.path.dirname(self.ed.ruta) if self.ed else "",
                                           RES.FILTRO_LPHR)
        if r:
            try:
                self.abrir(r)
            except Exception as e:  # noqa: BLE001
                QMessageBox.critical(self, APP_ED, f"No se pudo abrir el resultado:\n{e}")

    def _titulo(self):
        n = os.path.basename(self.ed.ruta) if self.ed else ""
        self.setWindowTitle(f"{APP_ED} - [{n}]" + (" *" if self.ed and self.ed.modificado else ""))

    def guardar(self):
        r = self.ed.guardar(); self.statusBar().showMessage(f"Guardado {r} (copia de seguridad previa .bak)", 5000)
        self._titulo(); return r

    def guardar_como(self):
        r, _ = QFileDialog.getSaveFileName(self, "Guardar como", self.ed.ruta, RES.FILTRO_LPHR)
        if r:
            self.ed.guardar(r); self._titulo()

    def recuperar_copia(self):
        try:
            self.ed.recuperar_copia()
        except ErrorEdicion as e:
            QMessageBox.information(self, APP_ED, str(e)); return
        self.refrescar()

    def recargar(self):
        if self.ed.modificado and QMessageBox.question(self, APP_ED, "Se perderán los cambios no guardados. ¿Continuar?") != QMessageBox.Yes:
            return
        self.abrir(self.ed.ruta, self.ed.ruta_xghc)

    def _descartar(self):
        if not self.ed or not self.ed.modificado:
            return True
        r = QMessageBox.question(self, APP_ED, "¿Quiere guardar los cambios del horario?",
                                 QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
        if r == QMessageBox.Cancel:
            return False
        if r == QMessageBox.Yes:
            self.guardar()
        return True

    def closeEvent(self, ev):
        if not self._descartar():
            ev.ignore(); return
        if self.ed and self._preguntar_proyeccion:
            if QMessageBox.question(self, APP_ED, TX("abrira_planificador_llevar_este_resultado")) == QMessageBox.Yes:
                self.proyectar()
        if self.fuera:
            self.fuera.close()
        ev.accept()

    def transferir_externa(self, operar=None):
        """Pasar el horario a > Otros programas: asistente de exportación sincronizada (DELPHOS)."""
        from .editor_delphos import AsistenteDelphos
        if not self.ed:
            return None
        self.asis_delphos = AsistenteDelphos(self, self.ed, getattr(self, "catalogo_delphos", None))
        r = self.asis_delphos.ejecutar(operar)
        if r:
            self.statusBar().showMessage(f"Horario transferido: {r}", 6000)
        return r

    def importar_claves_externas(self, ruta=None):
        """Importar códigos externos: catálogo de DELPHOS para el semáforo de la transferencia."""
        from .editor_delphos import AsistenteDelphos
        if not self.ed:
            return False
        a = AsistenteDelphos(self, self.ed)
        if a.cargar_catalogo(self, ruta):
            self.catalogo_delphos = a.tr.catalogo
            self.statusBar().showMessage(f"Claves externas cargadas: {len(a.catalogo_total())}", 6000)
            return True
        return False

    def abrir_en_planificador(self):
        d = DialogoAbrirPlan(self)
        d.c[1018].setText(self.ed.ruta_xghc); d.c[1069].setVisible(not os.path.exists(self.ed.ruta_xghc))
        d.c[1002].setChecked(True); d.c[1].clicked.connect(d.accept); d.c[2].clicked.connect(d.reject)
        if not d.exec():
            return
        if d.c[1001].isChecked():
            self._abrir_plan(self.ed.ruta_xghc)
        else:
            self.proyectar()

    def proyectar(self, destino=None, lectivas=True, guardias=True, preguntar=True):
        base = os.path.splitext(self.ed.ruta_xghc)[0]
        destino = destino or base + "_proyectado.xghc"
        if preguntar:
            dp = DialogoProyectar(self, destino)
            if not dp.exec():
                return None
            destino, lectivas, guardias = dp.ed_dest.text(), dp.cb_lect.isChecked(), dp.cb_guard.isChecked()
        try:
            n = self.ed.proyectar(destino, lectivas, guardias)
        except ErrorEdicion as e:
            QMessageBox.warning(self, APP_ED, str(e)); return None
        self.statusBar().showMessage(f"Proyectado sobre {destino}: {n} plantillas con posiciones prefijadas", 8000)
        self._abrir_plan(destino)
        return destino

    def _abrir_plan(self, ruta):
        f = type(self).abrir_planificador
        if f is None:
            from .ventana import Planificador
            w = Planificador(); w.abrir(ruta); w.show(); self._plan = w; return w
        return f(ruta)

    # ---------------------------------------------------- ventanas y solapas
    def nueva_ventana(self, vista="Grupos", nombre=None):
        v = VistaHorario(self, vista, nombre)
        sw = self.mdi.addSubWindow(v); sw.resize(760, 560); sw.show(); v.refrescar()
        self.mdi.setActiveSubWindow(sw)
        return v

    def _vista_actual(self) -> VistaHorario | None:
        sw = self.mdi.activeSubWindow() or (self.mdi.subWindowList() or [None])[0]
        return sw.widget() if sw else None

    def nueva_ventana_actual(self):
        v = self._vista_actual(); t = v.tabla() if v else None
        return self.nueva_ventana(t.vista if t else "Grupos", t.nombre if t else None)

    def nueva_solapa(self):
        v = self._vista_actual(); t = v.tabla()
        return v.nueva_solapa(t.vista, t.nombre)

    def nueva_solapa_modo(self, modo):
        """VENTANAS > Tabla nueva en otra pestaña > (con lista, general, guardias de recreo, cruce, libres)."""
        v = self._vista_actual()
        if v is None:
            v = self.nueva_ventana()
        t = v.tabla(); vista = t.vista if t is not None else "Grupos"
        if modo in ("columnas", "filas") and vista not in ("Grupos", "Profesorado", "Aulas"):
            vista = "Grupos"
        if modo in ("cruce", "prof_libres"):
            vista = "Profesorado"
        if modo == "aulas_libres":
            vista = "Aulas"
        if modo == "recreo":
            vista = "Guardias"
        return v.nueva_solapa(vista, t.nombre if t is not None and t.vista == vista else None, modo)

    # ---------------------------------------------------- VENTANAS: barras, notificaciones y opciones
    def _ajuste(self, clave, defecto=False):
        from PySide6.QtCore import QSettings
        v = QSettings(VENDOR, AJUSTES).value(f"editor/{clave}", defecto)
        return v in (True, "true", "1", 1)

    def _fijar_ajuste(self, clave, valor):
        from PySide6.QtCore import QSettings
        QSettings(VENDOR, AJUSTES).setValue(f"editor/{clave}", bool(valor))

    def _barras(self):
        st = self.style()
        self.tb_edicion = self.addToolBar("Barra de edición"); self.tb_edicion.setObjectName("barra_edicion")
        for txt, f, ic in ((TX("sacar_lo_hay_celda"), self.extraer_celda, QStyle.SP_DialogDiscardButton),
                           (TX("anadir_horario"), self.agregar_al_horario, QStyle.SP_ArrowDown),
                           (TX("cambiar_sesiones_2"), self.modificar_celda, QStyle.SP_FileDialogContentsView),
                           ("Cambiar el aula", self.cambiar_aula_celda, QStyle.SP_DirLinkIcon),
                           ("Buscar", self.buscar, QStyle.SP_FileDialogContentsView)):
            a = QAction(st.standardIcon(ic), txt, self); a.triggered.connect(lambda *_, f=f: f()); self.tb_edicion.addAction(a)
        self.tb_edicion.hide()
        self.tb_seleccion = self.addToolBar("Barra de selección"); self.tb_seleccion.setObjectName("barra_seleccion")
        self.sel_vista = QComboBox(); self.sel_vista.addItems(VISTAS); self.sel_el = QComboBox(); self.sel_el.setMinimumWidth(200)
        self.tb_seleccion.addWidget(QLabel(" Horario: ")); self.tb_seleccion.addWidget(self.sel_vista); self.tb_seleccion.addWidget(self.sel_el)
        self.sel_vista.currentTextChanged.connect(lambda v: (self.sel_el.clear(), self.sel_el.addItems(self.ed.elementos(v) if self.ed else [])))
        self.sel_el.activated.connect(lambda *_: self.ir_a(self.sel_vista.currentText(), self.sel_el.currentText()))
        self.tb_seleccion.hide()

    def barra_seleccion(self):
        vis = not self.tb_seleccion.isVisible()
        if vis and self.ed is not None:
            self.sel_el.clear(); self.sel_el.addItems(self.ed.elementos(self.sel_vista.currentText()))
        self.tb_seleccion.setVisible(vis)

    def ir_a(self, vista, nombre):
        v = self._vista_actual() or self.nueva_ventana(vista, nombre)
        t = v.tabla()
        if t is not None and not getattr(t, "modo", None):
            v.cb_vista.setCurrentText(vista); v.cb_el.setCurrentText(nombre)
        else:
            v.nueva_solapa(vista, nombre)
        return v

    def notificaciones(self):
        """VENTANAS > Ver > Notificaciones: mensajes del comprobador independiente en un panel acoplable."""
        from PySide6.QtWidgets import QDockWidget
        if getattr(self, "dock_notif", None) is None:
            self.dock_notif = QDockWidget(TX("avisos"), self); self.dock_notif.setObjectName("notificaciones")
            self.lst_notif = QListWidget(); self.dock_notif.setWidget(self.lst_notif)
            self.addDockWidget(Qt.BottomDockWidgetArea, self.dock_notif)
        elif self.dock_notif.isVisible():
            self.dock_notif.hide(); return self.dock_notif
        self.lst_notif.clear(); inf = self.ed.comprobar()
        for cat, det in inf.errores:
            QListWidgetItem(f"Error · {cat}: {det}", self.lst_notif).setForeground(QColor("#b00000"))
        for cat, det in getattr(inf, "avisos", []):
            QListWidgetItem(f"Aviso · {cat}: {det}", self.lst_notif)
        if not self.lst_notif.count():
            QListWidgetItem("Sin notificaciones: el horario es válido.", self.lst_notif)
        self.dock_notif.show(); return self.dock_notif

    def opcion_cadena_aula(self, on=None):
        """33081: pedir confirmación al cambiar la materia o el tipo de tarea en sesiones simultáneas en la misma aula."""
        on = (not self._ajuste("confirmar_cadena")) if on is None else on
        self._fijar_ajuste("confirmar_cadena", on); self.acc[33081].setChecked(on); return on

    def opcion_avisar_ocultos(self, on=None):
        """33086: al abrir el editor avisa de los elementos que se han ocultado en la presentación de las tablas."""
        on = (not self._ajuste("avisar_ocultos")) if on is None else on
        self._fijar_ajuste("avisar_ocultos", on); self.acc[33086].setChecked(on); return on

    def ocultos(self):
        c = self.ed.celdas(); txt = []
        for k, t in (("ocultar_aula", TX("no_mostrar_aula")), ("ocultar_materia", TX("no_mostrar_materia")), ("ocultar_profesor", TX("no_mostrar_profesor")),
                     ("ocultar_grupo", TX("no_mostrar_grupo_subgrupo")), ("ocultar_vacias", "Ocultar las filas vacías"),
                     ("ocultar_recreos", "Ocultar las filas de recreo"), ("ocultar_mediodia", "Ocultar la fila de mediodía")):
            if c.get(k):
                txt.append("- " + t)
        txt += ["- " + {"aula": TX("no_mostrar_aula"), "materia": TX("no_mostrar_materia"), "recreos": "Ocultar las filas de recreo"}[k]
                for k in sorted(self.opciones) if k in ("aula", "materia", "recreos")]
        return list(dict.fromkeys(txt))

    def aviso_ocultos(self):
        """Diálogo 781 «Aviso: hay opciones que esconden datos»."""
        lst = self.ocultos()
        if not lst:
            return None
        d = DialogoAvisoOcultos(self, lst); self._dlg_ocultos = d
        if not getattr(self, "_no_modal", False):
            if d.exec():
                self.menu_opciones_celdas()
        else:
            d.show()
        return d

    def cambiar_nombres(self, cid):
        cat, tit = CAT_NOMBRES[cid]
        d = DialogoNombres(self, self.ed, cat, tit); self._dlg_nombres = d
        if getattr(self, "_no_modal", False):
            d.show(); return d
        d.exec(); self.refrescar(); return d

    def marcos_horarios(self, que):
        d = DialogoMarcos(self, self.ed, que); self._dlg_marcos = d
        if getattr(self, "_no_modal", False):
            d.show(); return d
        if d.exec():
            self.refrescar()
        return d

    def recombinador(self, item=None, destino="celda"):
        """Asistente para recolocar (754): coloca `item` moviendo otros elementos que chocan."""
        if item is None:
            its = self._requiere_item()
            if not its:
                return None
            item = its[0]
        if destino == "celda":
            pos = self.celda_actual() if item[0] == "n" else None
            destino = pos if pos is not None and pos in self.ed.tramos else None
        d = DialogoRecombinador(self, item, destino); self._dlg_recomb = d
        if getattr(self, "_no_modal", False):
            d.show(); return d
        d.exec(); self.refrescar(); return d

    def coloca_iconos(self):
        for sw in self.mdi.subWindowList():
            sw.showMinimized()

    # ---------------------------------------------------- EDICIÓN: buscar y seleccionar todo
    def buscar(self, texto=None):
        """EDICIÓN > Buscar (F3): busca un profesor, grupo, aula, tarea, reunión o servicio por su nombre."""
        from PySide6.QtWidgets import QInputDialog
        if texto is None:
            texto, ok = QInputDialog.getText(self, "Buscar", "Texto a buscar (identificativo o nombre completo):", text=getattr(self, "_ult_busqueda", ""))
            if not ok or not texto.strip():
                return None
        self._ult_busqueda = texto = texto.strip(); t = texto.lower()
        for vista in VISTAS:
            for n in self.ed.elementos(vista):
                cat = {"Profesorado": "profesores", "Grupos": "alumnos", "Aulas": "aulas"}.get(vista)
                vis = self.ed.ident(cat, n, "id") if cat else n
                if t in n.lower() or t in vis.lower() or t in self.ed.nombre_largo(vista, n).lower():
                    self.ir_a(vista, n); self.statusBar().showMessage(f"Encontrado: {n} ({vista})", 4000)
                    return (vista, n)
        if not getattr(self, "_no_modal", False):
            QMessageBox.information(self, APP_ED, f"No se ha encontrado «{texto}».")
        return None

    def seleccionar_todo(self):
        v = self._vista_actual(); t = v.tabla() if v else None
        if t is not None:
            t.setSelectionMode(QAbstractItemView.ExtendedSelection); t.selectAll()

    def _solapa(self, paso):
        v = self._vista_actual(); v.tabs.setCurrentIndex((v.tabs.currentIndex() + paso) % v.tabs.count())

    def elimina_solapa(self):
        v = self._vista_actual()
        if v.tabs.count() > 1:
            v.tabs.removeTab(v.tabs.currentIndex())

    def mosaico_vertical(self):
        sws = self.mdi.subWindowList(); W = self.mdi.width(); H = self.mdi.height()
        for i, sw in enumerate(sws):
            sw.setGeometry(i * W // len(sws), 0, W // len(sws), H)

    def mosaico_horizontal(self):
        sws = self.mdi.subWindowList(); W = self.mdi.width(); H = self.mdi.height()
        for i, sw in enumerate(sws):
            sw.setGeometry(0, i * H // len(sws), W, H // len(sws))

    def set_zoom(self, z):
        self.zoom = max(0.5, min(2.5, z)); self.refrescar()

    def refrescar(self):
        for sw in self.mdi.subWindowList():
            sw.widget().refrescar()
        if self.fuera:
            self.fuera.refrescar()
        self.a_deshacer.setEnabled(bool(self.ed and self.ed.pila_deshacer))
        self.a_rehacer.setEnabled(bool(self.ed and self.ed.pila_rehacer))
        if self.ed:
            inf = self.ed.comprobar(); nf = len(self.ed.doc["no_colocadas"])
            self.lbl_estado.setText(("Horario válido" if inf.valido else f"{len(inf.errores)} incidencias") +
                                    f" · {nf} líneas fuera del horario · {len(self.ed.choques())} elementos en conflicto")
        self._titulo()

    # ---------------------------------------------------- celda actual
    def celda_actual(self):
        v = self._vista_actual(); t = v.tabla() if v else None
        if t is None or t.currentRow() < 0:
            return None
        return t.pos.get((t.currentRow(), t.currentColumn()))

    def items_actuales(self):
        v = self._vista_actual(); t = v.tabla() if v else None
        return t.items_en(t.currentRow(), t.currentColumn()) if t is not None and t.currentRow() >= 0 else []

    def _requiere_item(self, solo_s=False):
        its = [i for i in self.items_actuales() if not solo_s or i[0] == "s"]
        if not its:
            QMessageBox.information(self, APP_ED, "Seleccione una celda ocupada" + (" por una sesión lectiva." if solo_s else "."))
        return its

    def menu_celda(self, tabla, r, c):
        m = QMenu(self)
        for it in MENUS["153"]:
            if it == "-":
                m.addSeparator()
            else:
                m.addAction(self.acc[it["id"]] if it["id"] in self.acc and it["id"] not in (32851,) else self._accion(it["id"], it["t"], it.get("k")))
        return m

    def menu_nuevas(self):
        m = QMenu(self); self._poblar(m, MENUS["189"]); return m

    def menu_opciones_celdas(self):
        """FORMATO > Qué se ve en las celdas: diálogo 196."""
        d = self._dlg_celdas = DialogoPresentacionCeldas(self)
        if getattr(self, "_no_modal", False):
            d.show(); return d
        if d.exec():
            if d.permanente():
                from PySide6.QtCore import QSettings
                QSettings(VENDOR, AJUSTES).setValue("editor/celdas", json.dumps(d.valores(), ensure_ascii=False))
            if self.ed.fijar_celdas(d.valores()):
                self.refrescar()
        return d

    def menu_ocultar_rapido(self):
        m = QMenu(self)
        for a in self.a_ocultar.values():
            m.addAction(a)
        m.exec(self.cursor().pos())

    def _ocultar(self, k, on):
        (self.opciones.add if on else self.opciones.discard)(k); self.refrescar()

    # ---------------------------------------------------- soltar / mover / agregar
    def soltar(self, item, pos):
        m, d, i = pos
        prop = self.ed.proponer_agregar(item, m, d, i) if item.startswith("n:") else self.ed.proponer_mover(item, m, d, i)
        if prop.invalida:
            QMessageBox.warning(self, prop.titulo, prop.invalida); return False
        extraer = []
        if prop.mensajes:
            dlg = DialogoConflictos(self, prop)
            if not dlg.exec():
                return False
            extraer = dlg.extraer
        self.ed.confirmar(prop, extraer, prop.titulo.lower())
        self.refrescar(); return True

    def extraer_celda(self):
        its = self._requiere_item()
        if its:
            self.ed.extraer(its); self.refrescar()

    def extraer_asignatura(self):
        its = self._requiere_item(True)
        if its:
            self.ed.extraer_asignatura(its[0]); self.refrescar()

    def sesiones_sin_colocar(self):
        if self.fuera is None:
            self.fuera = DialogoFuera(self)
        self.fuera.refrescar(); self.fuera.show(); self.fuera.raise_()
        return self.fuera

    def agregar_al_horario(self):
        self.sesiones_sin_colocar()

    def crear_nuevas(self):
        f = self.sesiones_sin_colocar(); self.menu_nuevas().exec(f.mapToGlobal(QPoint(40, 40)))

    def cambiar_aula_celda(self):
        its = self._requiere_item(True)
        if its:
            DialogoCambiarAula(self, its[0]).exec()

    def ver_libres(self, tipo):
        pos = self.celda_actual()
        if pos:
            DialogoLibres(self, tipo, pos).exec()

    def modificar_celda(self):
        its = self._requiere_item(True)
        if its:
            self.modificar_sesiones(self.ed.obj(its[0])["sesiones"])

    def modificar_sesiones(self, sids):
        s = self.ed.ses[sids[0]]
        d = DialogoLectiva(self, TX("cambiar_sesiones"), {"materia": s.materia, "grupo": s.grupo, "profesor": s.profesor,
                           "aula": (s.aulas or [""])[0], "tarea": s.tarea}, fijos=("materia", "grupo", "periodos"))
        if d.exec():
            v = d.valores()
            if v["tarea"] != s.tarea and self._ajuste("confirmar_cadena") and self._en_cadena(sids[0]):
                if QMessageBox.question(self, APP_ED, "Esta sesión es simultánea con otras en la misma aula.\n"
                                        "¿Quiere cambiar el tipo de tarea?") != QMessageBox.Yes:
                    v["tarea"] = s.tarea
            for campo in ("profesor", "aula", "tarea"):
                self.ed.modificar_sesion(s.id, campo, v[campo])
            self.refrescar()

    def _en_cadena(self, sid):
        """¿La sesión comparte pieza (simultánea) con otras que usan su misma aula?"""
        for it in self.ed.items():
            if it[0] == "s":
                o = self.ed.obj(it)
                if sid in o.get("sesiones", []) and len(o["sesiones"]) > 1:
                    return True
        return False

    def cambiar_color_celda(self):
        its = self._requiere_item()
        if its:
            clave = self.ed.clave_color(its[0])
            c = QColorDialog.getColor(QColor(self.ed.color(clave)), self, TX("cambiar_color_materia_clave", clave=clave))
            if c.isValid():
                self.ed.cambiar_color(clave, c.name()); self.refrescar()

    def poner_quitar_colores(self):
        self.ed.poner_quitar_colores(); self.refrescar()

    def recuperar_paleta(self):
        self.ed.recuperar_paleta(); self.refrescar()

    def altura_optima(self):
        t = self._vista_actual().tabla(); t.resizeRowsToContents()

    def abrir_relacionado(self, solapa):
        its = self.items_actuales(); v = self._vista_actual(); t = v.tabla()
        destino = None
        if its:
            orden = {"Grupos": ["profesor", "aula"], "Profesorado": ["grupo", "aula"], "Aulas": ["grupo", "profesor"]}.get(t.vista, ["profesor", "grupo"])
            rec = self.ed.recursos(its[0])
            for tp in orden:
                n = next((nm for tt, nm in sorted(rec) if tt == tp), None)
                if n:
                    destino = (VISTA_DE_TIPO[tp], n); break
        destino = destino or (t.vista, t.nombre)
        return v.nueva_solapa(*destino) if solapa else self.nueva_ventana(*destino)

    def abrir_relacionado_ventana(self):
        return self.abrir_relacionado(False)

    def abrir_relacionado_solapa(self):
        return self.abrir_relacionado(True)

    def copiar(self):
        """Copia al portapapeles la tabla (o el rango seleccionado si hay varias celdas) en texto tabulado."""
        t = self._vista_actual().tabla()
        rg = t.selectedRanges()
        if len(rg) == 1 and (rg[0].rowCount() > 1 or rg[0].columnCount() > 1):
            rows = range(rg[0].topRow(), rg[0].bottomRow() + 1); cols = range(rg[0].leftColumn(), rg[0].rightColumn() + 1)
        else:
            rows, cols = range(t.rowCount()), range(t.columnCount())
        hh = lambda c: t.horizontalHeaderItem(c).text() if t.horizontalHeaderItem(c) else ""
        vh = lambda r: t.verticalHeaderItem(r).text().replace("\n", " ") if t.verticalHeaderItem(r) else ""
        cel = lambda r, c: t.item(r, c).text().replace("\n", " / ") if t.item(r, c) else ""
        filas = ["\t".join([""] + [hh(c) for c in cols])]
        for r in rows:
            filas.append("\t".join([vh(r)] + [cel(r, c) for c in cols]))
        QApplication.clipboard().setText("\n".join(filas))
        t.setSelectionMode(QAbstractItemView.SingleSelection)

    # ---------------------------------------------------- nuevas
    def nueva_lectiva(self):
        d = DialogoLectiva(self, TX("nuevas_sesiones_lectivas"))
        while d.exec():
            v = d.valores()
            if not (v["materia"] and v["grupo"]):
                QMessageBox.warning(self, APP_ED, "Indique materia y alumnos."); continue
            self.ed.nueva_lectiva(v["materia"], v["grupo"], v["profesor"], v["periodos"], v["aula"], v["tarea"] or "LEC")
            self.refrescar()
            if not d.mas:
                break
            d.mas = False

    def nueva_simultanea(self):
        its = [i for i in self.items_actuales() if i[0] == "s"]
        if not its:
            QMessageBox.information(self, APP_ED, "Seleccione en el horario la sesión con la que será simultánea."); return
        s = self.ed.ses[self.ed.obj(its[0])["sesiones"][0]]
        d = DialogoLectiva(self, "Nuevas simultáneas en otra aula", {"grupo": s.grupo, "periodos": len(self.ed.posiciones(its[0]))}, fijos=("periodos",))
        if d.exec():
            v = d.valores()
            try:
                self.ed.nueva_simultanea(its[0], v["materia"], v["grupo"], v["profesor"], v["aula"], v["tarea"] or "LEC")
            except ErrorEdicion as e:
                QMessageBox.warning(self, APP_ED, str(e))
            self.refrescar()

    def nueva_complementaria(self):
        d = DialogoComplementaria(self)
        if d.exec():
            v = d.valores(); self.ed.nueva_complementaria(v["profesor"], v["tarea"], v["periodos"]); self.refrescar()

    def nueva_guardia(self):
        if not self.ed.p.guardias:
            QMessageBox.information(self, APP_ED, "No hay servicios de guardia en la configuración."); return
        d = DialogoGuardia(self)
        if d.exec():
            v = d.valores(); self.ed.nueva_guardia(v["servicio"], v["profesor"], v["n"]); self.refrescar()

    def nuevo_servicio(self):
        from PySide6.QtWidgets import QInputDialog
        n, ok = QInputDialog.getText(self, "Nuevo servicio de guardias", "Identificador del servicio:")
        if ok and n.strip():
            try:
                self.ed.nuevo_servicio(n.strip())
            except ErrorEdicion as e:
                QMessageBox.warning(self, APP_ED, str(e))
            self.refrescar()

    def nueva_reunion(self):
        d = DialogoReunion(self)
        if d.exec():
            v = d.valores()
            try:
                self.ed.nueva_reunion(v["nombre"], v["profesores"], v["n"], v["doble"])
            except ErrorEdicion as e:
                QMessageBox.warning(self, APP_ED, str(e))
            self.refrescar()

    # ---------------------------------------------------- deshacer / informes
    def deshacer(self):
        if self.ed.deshacer() is not None:
            self.refrescar()

    def rehacer(self):
        if self.ed.rehacer() is not None:
            self.refrescar()

    # ---------------------------------------------------- informes e impresión
    def _opc(self):
        return IU.opciones_editor(self.ed)

    def _fijar_opc(self, o, permanente=False):
        if o != self._opc():
            IU.fijar_opciones(self.ed, o); self.refrescar()
        if permanente:
            IU.guardar_por_defecto({k: v for k, v in o.items() if k not in ("centro", "localidad", "curso")})

    def _impresora(self):
        if getattr(self, "_printer", None) is None:
            self._printer = QPrinter(QPrinter.HighResolution); INF.configurar_pagina(self._printer)
        return self._printer

    def tablas_actuales(self, o=None):
        v = self._vista_actual(); t = v.tabla() if v else None
        if t is None:
            return []
        return INF.tablas_actual(self.ed, t.vista, t.nombre, o or self._opc())

    def _sin_tablas(self, tablas):
        if not tablas:
            QMessageBox.information(self, APP_ED, "No hay ninguna tabla que presentar.")
        return not tablas

    def presentacion_preliminar(self, tablas=None, o=None):
        o = o or self._opc(); tablas = tablas if tablas is not None else self.tablas_actuales(o)
        if self._sin_tablas(tablas):
            return None
        d = IU.vista_previa(self, tablas, o, self._impresora())
        if not getattr(self, "_no_modal", False):
            d.exec()
        return d

    def _imprimir(self, tablas, o):
        if self._sin_tablas(tablas):
            return
        pr = self._impresora(); d = QPrintDialog(pr, self)
        if d.exec():
            INF.Pintor(o).render(pr, tablas)

    def imprimir_actual(self):
        self._imprimir(self.tablas_actuales(), self._opc())

    def imprimir_listado(self):
        d = IU.DialogoImprimirListado(self, self._opc())
        if d.exec():
            self._fijar_opc(d.o); self._imprimir(d.tablas(), d.o)

    def configurar_pagina(self):
        QPageSetupDialog(self._impresora(), self).exec()

    def configurar_impresora(self):
        QPrintDialog(self._impresora(), self).exec()

    def cabeceras_pies(self):
        d = IU.DialogoCabeceras(self, self._opc())
        if d.exec():
            self._fijar_opc(d.opciones())

    def anotacion(self):
        """«Anotación» (editor de referencia, diálogo 377): notas propias del resultado; el motor escribe aquí las condiciones
        flexibilizadas desde el Depurador."""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPlainTextEdit, QDialogButtonBox
        d = QDialog(self); d.setWindowTitle(TX("nota")); L = QVBoxLayout(d)
        L.addWidget(QLabel("Aquí puede dejar alguna anotación relacionada con este resultado."))
        L.addWidget(QLabel(os.path.basename(getattr(self.ed, "ruta", "") or "")))
        txt = QPlainTextEdit("\n".join(self.ed.doc.get("anotacion") or [])); txt.setMinimumSize(520, 260); L.addWidget(txt)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Aceptar"); bb.button(QDialogButtonBox.Cancel).setText("Cancelar")
        bb.accepted.connect(d.accept); bb.rejected.connect(d.reject); L.addWidget(bb)
        self._dlg_anotacion = d
        if d.exec():
            lineas = txt.toPlainText().split("\n") if txt.toPlainText() else []
            if lineas != list(self.ed.doc.get("anotacion") or []):
                nuevo = self.ed._instantanea(); nuevo["anotacion"] = lineas; self.ed._confirmar(nuevo, "anotación")
                self.refrescar()

    def letreros(self):
        d = IU.DialogoLetreros(self, self._opc())
        if d.exec():
            self._fijar_opc(d.opciones())

    def idioma_letreros(self):
        d = IU.DialogoIdiomaLetreros(self)
        if d.exec():
            if d.c[1013].isChecked():
                return self.letreros()
            o = self._opc(); o["letreros"] = copy.deepcopy(INF.OPC_DEF["letreros"]); self._fijar_opc(o)

    def _ruta_pdf(self, sugerido):
        base = os.path.dirname(self.ed.ruta) if getattr(self.ed, "ruta", None) else os.path.expanduser("~")
        r, _ = QFileDialog.getSaveFileName(self, "Guardar en PDF", os.path.join(base, sugerido), "Documentos PDF (*.pdf)")
        if r and not r.lower().endswith(".pdf"):
            r += ".pdf"
        return r

    def _evitar(self):
        return [x for x in (getattr(self.ed, "ruta", None), getattr(self.ed, "ruta_xghc", None)) if x]

    def _exportar(self, tablas, o, sugerido):
        if self._sin_tablas(tablas):
            return None
        r = self._ruta_pdf(sugerido)
        if not r:
            return None
        try:
            INF.exportar_pdf(tablas, r, o, self._evitar())
        except (OSError, ValueError) as e:
            QMessageBox.warning(self, APP_ED, str(e)); return None
        self.statusBar().showMessage(f"Guardado {r}", 5000)
        return r

    def guardar_tabla_pdf(self):
        d = IU.DialogoTablaPDF(self, self._opc())
        if d.exec():
            o = d.opciones(); self._fijar_opc(o, d.permanente())
            v = self._vista_actual(); t = v.tabla() if v else None
            return self._exportar(self.tablas_actuales(o), o, f"{t.nombre if t else 'tabla'}.pdf")

    def transferir_pdf(self):
        d = IU.DialogoListadoPDF(self, self._opc())
        if not d.exec():
            return None
        o = d.opciones(); self._fijar_opc(o, d.permanente())
        tablas = INF.tablas_de(self.ed, o["tipo"], o)
        if o.get("presentacion") == "distintos":
            if self._sin_tablas(tablas):
                return None
            c = QFileDialog.getExistingDirectory(self, "Carpeta para los documentos PDF")
            if not c:
                return None
            r = INF.exportar_distintos(tablas, c, o)
            self.statusBar().showMessage(f"{len(tablas)} documentos en {c}", 5000); return r
        return self._exportar(tablas, o, f"Horario_{o['tipo']}.pdf")

    def listado_pdf(self, tipo):
        o = self._opc(); tablas = INF.tablas_de(self.ed, tipo, o)
        return self._exportar(tablas, o, f"{INF.LISTADOS[tipo].replace(' ', '_')}.pdf")

    def asignaciones_html(self, carpeta=None):
        """INFORMES > Asignaciones del profesorado > Páginas HTML con índice."""
        if carpeta is None:
            base = QFileDialog.getExistingDirectory(self, "Carpeta para las páginas HTML")
            if not base:
                return None
            carpeta = os.path.join(base, "Asignaciones_HTML")
        n = INF.exportar_asignaciones_html(self.ed, carpeta, self._opc())
        self.statusBar().showMessage(f"{n} páginas de profesores en {carpeta}", 5000)
        return os.path.join(carpeta, "index.html")

    def informe_motor(self):
        d = QDialog(self); d.setWindowTitle("Resumen"); L = QVBoxLayout(d)
        t = QPlainTextEdit(RES.resumen_texto(self.ed.doc)); t.setReadOnly(True); L.addWidget(t)
        b = QPushButton("Aceptar"); b.clicked.connect(d.accept); L.addWidget(b, 0, Qt.AlignRight); d.resize(560, 380); d.exec()

    def mostrar_comprobacion(self):
        inf = self.ed.comprobar()
        txt = "El horario es válido." if inf.valido else "\n".join(f"{a}: {b}" for a, b in inf.errores[:40])
        QMessageBox.information(self, "Comprobador independiente", txt)

    def acerca(self):
        QMessageBox.about(self, f"Acerca de {APP_ED}", f"<b>{APP_ED}</b> — {APP_NAME} {__version__}<br>"
                          f"Editor de horarios para centros de enseñanza. Software libre ({VENDOR}).")
