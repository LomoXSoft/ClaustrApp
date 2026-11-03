"""Ventana principal: PLANIFICADOR de horarios."""
from __future__ import annotations
from .textos import TX
import os
from PySide6.QtCore import Qt, QSize, QSortFilterProxyModel, QRectF, QPointF
from PySide6.QtGui import (QAction, QActionGroup, QKeySequence, QStandardItemModel, QStandardItem, QColor,
                           QPainter, QPen, QIcon)
from PySide6.QtWidgets import (QMainWindow, QTableView, QToolBar, QWidget, QSplitter, QDockWidget, QTreeWidget,
                               QTreeWidgetItem, QComboBox, QLabel, QToolButton, QMessageBox, QFileDialog,
                               QStyledItemDelegate, QAbstractItemView, QHeaderView, QMenu, QSizePolicy, QStyle, QApplication)
from . import __version__, APP_NAME, VENDOR
from .resultado import FILTRO_LPHR
from . import modelo as M, xghc, validacion
from .listas import LISTAS, POR_CLAVE
from .plantilla import PanelPlantilla
from .iconos import icono
from .ventana_edicion import EdicionMixin, DelegadoEdicion
from .ventana_nolectivas import NoLectivasMixin, ESTADOS as ESTADOS_NL
from .ventana_datos import DatosMixin

ROL_OBJ = Qt.UserRole + 1
ROL_BLOQUE = Qt.UserRole + 2   # (bloque, posición: 'unica'|'ini'|'med'|'fin')


class DelegadoSimultaneas(QStyledItemDelegate):
    """Dibuja en el margen izquierdo las líneas rojas que unen sesiones simultáneas."""
    def paint(self, p, opt, idx):
        super().paint(p, opt, idx)
        info = idx.data(ROL_BLOQUE)
        if not info:
            return
        pos = info
        r = opt.rect; x = r.left() + 8; cy = r.center().y()
        p.save(); p.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor("#d02020"), 2); p.setPen(pen)
        top = r.top() if pos in ("med", "fin") else cy
        bot = r.bottom() + 1 if pos in ("ini", "med") else cy
        p.drawLine(QPointF(x, top), QPointF(x, bot))
        p.drawLine(QPointF(x, cy), QPointF(x + 7, cy))
        p.setBrush(QColor("#d02020")); p.drawEllipse(QPointF(x, cy), 3, 3)
        p.restore()


class FiltroProxy(QSortFilterProxyModel):
    def __init__(self):
        super().__init__(); self.col = -1; self.valor = ""

    def filterAcceptsRow(self, row, parent):
        if self.col < 0 or not self.valor:
            return True
        txt = self.sourceModel().index(row, self.col, parent).data() or ""
        return self.valor in txt.split(" ") or txt == self.valor


class Planificador(DatosMixin, NoLectivasMixin, EdicionMixin, QMainWindow):
    def __init__(self):
        super().__init__()
        self.proyecto: M.Proyecto | None = None
        self.lista_actual = "sesiones"
        self.setWindowIcon(QIcon(os.path.join(os.path.dirname(__file__), "recursos", "icon.png")))
        self.resize(1180, 720)
        self._crear_acciones(); self._crear_menus(); self._crear_barras(); self._crear_centro()
        self.statusBar().showMessage(TX("pulse_f1_ver_ayuda"))
        self.lbl_lin = QLabel(" Lin 0/ 0 "); self.statusBar().addPermanentWidget(self.lbl_lin)
        self._preparar_edicion()
        self.cambiar_lista("sesiones")
        self._titulo()

    # ------------------------------------------------------------------ acciones
    def _accion(self, texto, slot=None, atajo=None, ico=None, tip=None, proximamente=False):
        a = QAction(texto, self)
        if ico:
            a.setIcon(icono(ico))
        if atajo:
            a.setShortcut(QKeySequence(atajo))
        a.setStatusTip(tip or texto.replace("&", "").replace("...", ""))
        a.setToolTip(tip or texto.replace("&", "").replace("...", ""))
        if proximamente:
            a.triggered.connect(lambda _=False, t=texto: self.proximamente(t))
        elif slot:
            a.triggered.connect(slot)
        return a

    def depurar(self):
        if not self.proyecto:
            QMessageBox.information(self, APP_NAME, "No hay ningún archivo abierto."); return
        from .depurador import DialogoDepurador
        DialogoDepurador(self).exec()

    def fundir_archivos(self, ruta=None):
        """«Fundir archivos...»: prevalecen el marco y las opciones del horario actual. Devuelve las incidencias."""
        if not self.proyecto:
            QMessageBox.information(self, APP_NAME, "No hay ningún archivo abierto."); return None
        from . import fundir as FU, xghc as XG
        if ruta is None:
            if QMessageBox.information(self, FU.TITULO, FU.TEXTO, QMessageBox.Ok | QMessageBox.Cancel) != QMessageBox.Ok:
                return None
            ruta, _ = QFileDialog.getOpenFileName(self, "Abrir", os.path.dirname(self.proyecto.ruta or ""),
                                                  "Configuración de horarios (*.xghc);;Todos los archivos (*)")
            if not ruta:
                return None
        try:
            otra = XG.cargar(ruta).doc.raiz
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, APP_NAME, f"No se pudo abrir el archivo:\n{ruta}\n\n{e}"); return None
        inc = []
        def fn(arbol):
            inc.extend(FU.fundir(arbol, otra)); return True
        self.editar(fn, TX("juntar_archivos_2"))
        texto = FU.SIN_INCIDENCIAS if not inc else "Incidencias de la fusión:\n\n" + "\n".join(inc[:40]) + \
            (f"\n… y {len(inc) - 40} más." if len(inc) > 40 else "")
        QMessageBox.information(self, FU.TITULO, texto)
        return inc

    def imprimir_lista(self, ruta=None):
        """Imprime la lista visible a PDF (tabla con las columnas de la vista). Devuelve la ruta o None."""
        from PySide6.QtGui import QTextDocument, QPageLayout, QPageSize
        from PySide6.QtPrintSupport import QPrinter
        import html as H
        m = self.tabla.model() if self.proyecto else None
        if m is None:
            QMessageBox.information(self, APP_NAME, "No hay ningún archivo abierto."); return None
        if ruta is None:
            base = os.path.splitext(self.proyecto.ruta or "Sin título")[0] + f"_{self.lista_actual}.pdf"
            ruta, _ = QFileDialog.getSaveFileName(self, "Imprimir a PDF", base, "PDF (*.pdf)")
            if not ruta:
                return None
        cab = "".join(f"<th>{H.escape(str(m.headerData(c, Qt.Horizontal) or ''))}</th>" for c in range(m.columnCount()))
        filas = "".join("<tr>" + "".join(f"<td>{H.escape(str(m.index(r, c).data() or ''))}</td>" for c in range(m.columnCount()))
                        + "</tr>" for r in range(m.rowCount()))
        titulo = H.escape(f"{os.path.basename(self.proyecto.ruta) or 'Sin título'} - {self.lista_actual}")
        doc = QTextDocument()
        doc.setHtml(f"<h3>{titulo}</h3><table border='1' cellspacing='0' cellpadding='2' style='font-size:8pt'>"
                    f"<tr>{cab}</tr>{filas}</table>")
        pr = QPrinter(QPrinter.HighResolution); pr.setOutputFormat(QPrinter.PdfFormat); pr.setOutputFileName(ruta)
        pr.setPageLayout(QPageLayout(QPageSize(QPageSize.A4), QPageLayout.Landscape, pr.pageLayout().margins()))
        doc.print_(pr)
        self.statusBar().showMessage(f"Impreso en {ruta}", 5000)
        return ruta

    def criterios_ponderables(self):
        if not self.proyecto:
            return
        from .criterios import DialogoCriterios
        DialogoCriterios(self).exec()

    def opciones_generales(self, pagina=None):
        if not self.proyecto:
            return
        from .opciones_generales import DialogoOpcionesGenerales
        DialogoOpcionesGenerales(self, pagina).exec()

    # ------------------------------------------------------------------ pegar / leer listado (profesores, grupos, materias)
    def _aplicar_listado(self, filas, origen):
        from . import pegar as PG
        clave = self.lista_actual
        if clave not in PG.LISTAS:
            QMessageBox.information(self, APP_NAME, "Pegar y leer listados está disponible en las listas de profesores, "
                                    "grupos de alumnos y materias."); return None
        if not filas:
            QMessageBox.information(self, APP_NAME, f"No hay datos que leer en {origen}."); return None
        res = {}
        self.editar(lambda a: res.update(PG.aplicar(a, clave, filas)) or bool(res["nuevos"] or res["actualizados"]),
                    "pegar listado")
        self.statusBar().showMessage(f"{res.get('nuevos', 0)} nuevos, {res.get('actualizados', 0)} actualizados", 6000)
        return res

    def pegar_listado(self, texto=None):
        from . import pegar as PG
        if texto is None:
            texto = QApplication.clipboard().text()
        return self._aplicar_listado(PG.filas_de_texto(texto), "el portapapeles")

    def leer_listado(self, ruta=None):
        from . import pegar as PG
        if ruta is None:
            ruta, _ = QFileDialog.getOpenFileName(self, TX("leer_lista_fuera_2"), "", "Listados (*.csv *.txt *.tsv);;Todos (*)")
            if not ruta:
                return None
        return self._aplicar_listado(PG.leer_archivo(ruta), ruta)

    def cambiar_version(self, version):
        """Ver › Versión: alterna en caliente con la versión sencilla (mismo núcleo, mismo archivo)."""
        from .sencilla.ventana import VentanaSencilla
        vs = getattr(self, "sencilla", None)
        if vs is None:
            vs = self.sencilla = VentanaSencilla(nucleo=self)
        vs.setGeometry(self.geometry()); self.hide(); vs.mostrar_desde_nucleo()
        return vs

    def proximamente(self, que):
        que = que.replace("&", "").replace("...", "")
        self.statusBar().showMessage(f"{que}: próximamente", 4000)
        QMessageBox.information(self, APP_NAME, f"«{que}»\n\nEsta opción estará disponible próximamente.")

    def _crear_acciones(self):
        A = self._accion
        self.a_nuevo = A("&Nuevo", lambda: self.nuevo(), "Ctrl+N", "nuevo", "Crear un archivo de configuración nuevo")
        self.a_abrir = A("&Abrir", self.abrir_dialogo, "Ctrl+F", "abrir", "Abrir un archivo de configuración (.xghc)")
        self.a_abrir.setShortcuts([QKeySequence("Ctrl+F"), QKeySequence("Ctrl+O")])
        self.a_guardar = A("&Guardar", self.guardar, "F2", "guardar", "Guardar los datos de configuración")
        self.a_guardar.setShortcuts([QKeySequence("F2"), QKeySequence("Ctrl+S")])
        self.a_guardar_copia = A("Guardar &como", lambda: self.guardar_como())
        self.a_deshacer = A("Deshacer", self.deshacer, "Ctrl+Z")
        self.a_rehacer = A("Rehacer", self.rehacer, "Ctrl+Y")
        self.addAction(self.a_deshacer); self.addAction(self.a_rehacer)
        self.a_importar = A("&Importar datos...", lambda: self.importar_datos(), ico="importar",
                            tip=TX("cargar_actualizar_todas_listas_desde"))
        self.a_exportar = A("&Exportar datos...", proximamente=True)
        self.a_fundir = A(TX("juntar_archivos"), self.fundir_archivos,
                          tip=TX("anade_archivo_abierto_datos_otro"))
        self.a_imprimir = A("&Imprimir...", lambda: self.imprimir_lista(), "Ctrl+P", "imprimir", "Imprimir la lista actual (PDF)")
        self.a_salir = A("&Salir", self.close, "Alt+F4")
        self.a_atras = A("Atrás", self.nav_atras, "Alt+Left", "atras", "Volver a la lista anterior")
        self.a_adelante = A("Adelante", self.nav_adelante, "Alt+Right", "adelante", "Ir a la lista siguiente")
        self.a_insertar = A(TX("nuevo"), self.insertar, "Insert", "insertar", TX("anade_elemento_nuevo_lista"))
        self.a_insertar.setShortcuts([QKeySequence("Insert"), QKeySequence("+")])
        self.a_leer = A(TX("leer_lista_fuera"), lambda: self.leer_listado(), atajo="Alt+Insert", ico="leer_csv")
        self.a_pegar = A("Pegar", lambda: self.pegar_listado(), atajo="Ctrl+V", ico="pegar")
        self.a_propiedades = A("Propiedades...\tTab", self.propiedades, tip=TX("propiedades_elemento_elegido"))
        self.a_eliminar = A("Eliminar", self.eliminar, "Del", tip=TX("borra_elemento_elegido"))
        self.a_eliminar.setShortcutContext(Qt.WidgetWithChildrenShortcut)
        self.a_opciones = A("Opciones generales...", self.opciones_generales, ico="opciones",
                            tip=TX("opciones_generales_valores_partida_otras"))
        self.a_criterios = A(TX("criterios_peso"), self.criterios_ponderables,
                             tip=TX("pesos_criterios_optimizacion"))
        self.a_limpiar = A(TX("vaciar_plantillas"), ico="limpiar", proximamente=True)
        self.a_validar = A("Validar...", self.validar, "F9", "validar", "Validar los datos de configuración")
        self.a_generar = A(TX("calcular_horario"), self.generar, "F5", "generar", TX("calcular_horario_abre_motor"))
        self.a_parcial = A(TX("calcular_horario_parcial"), self.generar_parcial, ico="filtro",
                           tip=TX("calcular_horario_solo_elementos_elegidos"))
        self.a_abrir_res = A("Abrir un resultado (.lphr)...", self.abrir_resultado)
        self.a_depurador = A("Depurar condiciones...", self.depurar,
                             tip=TX("buscar_condiciones_impiden_encontrar_resultados"))
        self.a_ayuda = A(TX("ayuda"), atajo="F1", ico="ayuda", proximamente=True)
        self.a_acerca = A(f"Acerca de {APP_NAME}...", self.acerca)
        # acciones de listas (barra vertical)
        self.grupo_listas = QActionGroup(self); self.grupo_listas.setExclusive(True)
        self.acc_listas = {}
        for d in LISTAS:
            a = QAction(icono(d.icono), d.titulo, self); a.setCheckable(True); a.setToolTip(d.titulo)
            a.setStatusTip(f"Ver la lista: {d.titulo}")
            a.triggered.connect(lambda _=False, c=d.clave: self.cambiar_lista(c))
            self.grupo_listas.addAction(a); self.acc_listas[d.clave] = a
        self.historial, self.hist_pos = [], -1

    def _crear_menus(self):
        mb = self.menuBar()
        m = mb.addMenu("ARCHIVO")
        for a in (self.a_nuevo, self.a_abrir, self.a_guardar, self.a_guardar_copia, None, self.a_importar,
                  self.a_exportar, self.a_fundir, None, self.a_imprimir, None, self.a_salir):
            m.addSeparator() if a is None else m.addAction(a)
        self.m_ver = mb.addMenu("VER")
        m = mb.addMenu("CONFIGURACIÓN")
        m.addAction(self.a_opciones); m.addAction(self.a_criterios)
        sm = m.addMenu("Plantillas"); sm.addAction(self.a_limpiar)
        m.addAction(self._accion(TX("perfil_uso"), lambda: self.perfil_aplicacion()))
        sm = m.addMenu("Perfil")
        g = QActionGroup(self)
        for t in ("Perfil básico", "Perfil avanzado"):
            a = sm.addAction(t); a.setCheckable(True); a.setChecked(t == "Perfil avanzado"); g.addAction(a)
        self.m_lista = mb.addMenu(TX("menu_sesiones"))
        m = mb.addMenu("DESIDERATAS")
        m.addAction(self._accion("Criterios de optimización...", self.criterios_ponderables))
        m.addAction(self._accion("Captura de desideratas...", proximamente=True))
        m = mb.addMenu("RESULTADOS")
        for a in (self.a_validar, self.a_generar, self.a_parcial, None, self.a_abrir_res, self.a_depurador):
            m.addSeparator() if a is None else m.addAction(a)
        m = mb.addMenu("AYUDA")
        m.addAction(self.a_ayuda); m.addSeparator(); m.addAction(self.a_acerca)

    def _rellenar_menu_lista(self):
        d = POR_CLAVE[self.lista_actual]
        self.m_lista.setTitle(d.menu); self.m_lista.clear()
        for a in self._acciones_lista():
            self.m_lista.addSeparator() if a is None else (self.m_lista.addMenu(a) if isinstance(a, QMenu) else self.m_lista.addAction(a))

    def _acciones_lista(self):
        nl = self.acciones_nl(self.lista_actual)
        if nl:
            return nl
        if self.lista_actual == "marco":
            A = self._accion
            return [A("Modificar y añadir los periodos...", lambda: self.periodos_marco()),
                    A("Horario distinto para cada día...", lambda: self.horario_distinto()),
                    A("Número de semanas...", lambda: self.numero_semanas()), None,
                    self.a_propiedades, None, self.a_deshacer, self.a_rehacer]
        if self.lista_actual == "sesiones":
            A = self._accion
            sim = QMenu(TX("anadir_simultaneas"), self)
            for t, k in (("Simultáneas en otra aula", "F7"), ("Otro grupo en el aula", "F8"),
                         ("Otro profesor en el aula", "F9"), ("Otra aula al profesor", "F10"),
                         ("Otra materia en el aula", "F11")):
                a = A(t, proximamente=True); a.setShortcut(QKeySequence(k)); a.setShortcutContext(Qt.WidgetShortcut); sim.addAction(a)
            return [self.a_insertar, sim,
                    A("Duplicar líneas de sesiones", proximamente=True), A(TX("cancelar_esc"), proximamente=True),
                    None, A(TX("quitar_simultaneas"), proximamente=True), A(TX("poner_simultaneas"), proximamente=True), None,
                    A("Modificar\tIntro o Clic", lambda: self.tabla.edit(self.tabla.currentIndex())), A("Ir a su lista\tCtrl+Clic", proximamente=True),
                    A(TX("ver_codigos_abreviaturas_may_clic"), proximamente=True), None,
                    A(TX("leer_lista_fuera"), proximamente=True), A("Pegar", proximamente=True), None,
                    self.a_eliminar, None, A("Asignación semanal...", lambda: self.asignacion_semanal()),
                    self.a_propiedades, self.a_limpiar, None, self.a_deshacer, self.a_rehacer]
        return [self.a_insertar, self.a_leer, self.a_pegar, None, self.a_eliminar, None, self.a_propiedades, self.a_limpiar,
                None, self.a_deshacer, self.a_rehacer]

    def _crear_barras(self):
        tb = QToolBar("Archivo"); tb.setIconSize(QSize(28, 28)); tb.setMovable(False); self.addToolBar(tb)
        for a in (self.a_nuevo, self.a_abrir, self.a_guardar, None, self.a_atras, self.a_adelante, None,
                  self.a_importar, self.a_imprimir, None, self.a_validar, self.a_ayuda):
            tb.addSeparator() if a is None else tb.addAction(a)
        esp = QWidget(); esp.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred); tb.addWidget(esp)
        self.cb_perfil = QComboBox(); self.cb_perfil.addItems(["Perfil básico", "Perfil avanzado"])
        self.cb_perfil.setCurrentIndex(1); self.cb_perfil.setToolTip("Perfil de uso"); tb.addWidget(self.cb_perfil)
        self.addToolBarBreak()
        tb2 = QToolBar("Edición"); tb2.setIconSize(QSize(28, 28)); tb2.setMovable(False); self.addToolBar(tb2)
        for a in (self.a_insertar, self.a_leer, self.a_pegar, None, self.a_opciones):
            tb2.addSeparator() if a is None else tb2.addAction(a)
        b = QToolButton(); b.setIcon(icono("referencia")); b.setIconSize(QSize(28, 28)); b.setPopupMode(QToolButton.MenuButtonPopup)
        b.setToolTip("Utilizar como referencia: identificativo, abreviatura o nombre completo")
        mr = QMenu(b); g = QActionGroup(mr)
        for t in (TX("codigo"), "Abreviatura", "Nombre completo"):
            a = mr.addAction(t); a.setCheckable(True); a.setChecked(t == TX("codigo")); g.addAction(a)
        b.setMenu(mr); tb2.addWidget(b)
        tb2.addSeparator(); tb2.addAction(self.a_limpiar); tb2.addSeparator(); tb2.addAction(self.a_generar); tb2.addAction(self.a_parcial)
        # barra de filtro rápido
        tf = QToolBar("Filtro rápido"); tf.setMovable(False); tf.setIconSize(QSize(22, 22)); self.addToolBar(tf)
        lb = QLabel(); lb.setPixmap(icono("filtro").pixmap(22, 22)); lb.setToolTip("Filtro rápido"); tf.addWidget(lb)
        self.cb_tipo = QComboBox(); self.cb_tipo.addItems(["Grupo", "Profesorado", "Materia", "Aula"])
        self.cb_tipo.setToolTip("Tipo de elemento por el que filtrar"); tf.addWidget(self.cb_tipo)
        self.b_ant = QToolButton(); self.b_ant.setText("<"); self.b_ant.setToolTip("Elemento anterior"); tf.addWidget(self.b_ant)
        self.b_sig = QToolButton(); self.b_sig.setText(">"); self.b_sig.setToolTip("Elemento siguiente"); tf.addWidget(self.b_sig)
        self.b_igual = QToolButton(); self.b_igual.setText("="); self.b_igual.setToolTip("Filtrar por el elemento de la fila actual"); tf.addWidget(self.b_igual)
        self.cb_valor = QComboBox(); self.cb_valor.setMinimumWidth(180); self.cb_valor.setToolTip("Valor del filtro"); tf.addWidget(self.cb_valor)
        self.b_quitar = QToolButton(); self.b_quitar.setIcon(icono("quitar_filtro")); self.b_quitar.setToolTip("Quitar el filtro"); tf.addWidget(self.b_quitar)
        self.cb_tipo.currentIndexChanged.connect(self._rellenar_valores)
        self.cb_valor.currentIndexChanged.connect(self._aplicar_filtro)
        self.b_ant.clicked.connect(lambda: self._mover_valor(-1)); self.b_sig.clicked.connect(lambda: self._mover_valor(1))
        self.b_quitar.clicked.connect(lambda: self.cb_valor.setCurrentIndex(0))
        self.b_igual.clicked.connect(self._filtro_fila_actual)
        # barra vertical derecha de listas
        tl = QToolBar("Listas"); tl.setOrientation(Qt.Vertical); tl.setIconSize(QSize(30, 30)); tl.setMovable(False)
        grupos = [["marco"], ["materias", "grupos", "profesores"], ["aulas"], ["cursos", "departamentos", "tareas"],
                  ["sesiones"], ["reuniones", "guardias", "complementarias"]]
        for i, g in enumerate(grupos):
            if i:
                tl.addSeparator()
            for c in g:
                tl.addAction(self.acc_listas[c])
        self.addToolBar(Qt.RightToolBarArea, tl)
        # menú VER
        mv = self.m_ver
        for t in (tb, tb2, tf, tl):
            mv.addAction(t.toggleViewAction())
        mv.addSeparator()
        for d in LISTAS:
            mv.addAction(self.acc_listas[d.clave])

    def _crear_centro(self):
        self.tabla = QTableView(); self.tabla.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabla.setSelectionMode(QAbstractItemView.ExtendedSelection); self.tabla.setAlternatingRowColors(False)
        self.tabla.verticalHeader().setVisible(False); self.tabla.verticalHeader().setDefaultSectionSize(21)
        self.tabla.setEditTriggers(QAbstractItemView.NoEditTriggers); self.tabla.setShowGrid(False)
        self.tabla.horizontalHeader().setHighlightSections(False); self.tabla.horizontalHeader().setStretchLastSection(True)
        self.tabla.setSortingEnabled(False); self.tabla.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tabla.customContextMenuRequested.connect(self._menu_contextual)
        self.tabla.setStyleSheet("QTableView{background:white; selection-background-color:#0078d7;}"
                                 "QHeaderView::section{background:#f3f3f3; border:0; border-right:1px solid #ccc;"
                                 "border-bottom:1px solid #ccc; padding:3px;}")
        self.modelo = QStandardItemModel(); self.proxy = FiltroProxy(); self.proxy.setSourceModel(self.modelo)
        self.tabla.setModel(self.proxy)
        self.tabla.selectionModel().currentRowChanged.connect(self._fila_cambiada)
        self.delegado = DelegadoSimultaneas(self.tabla)
        self.del_edicion = DelegadoEdicion(self); self.tabla.setItemDelegate(self.del_edicion)
        self.panel = PanelPlantilla(); self.panel.setMinimumWidth(250); self.panel.cambiada.connect(self._marcar_modificado)
        sp = QSplitter(); sp.addWidget(self.tabla); sp.addWidget(self.panel)
        sp.setStretchFactor(0, 1); sp.setStretchFactor(1, 0); sp.setSizes([820, 270])
        self.setCentralWidget(sp)
        # dock de mensajes de validación
        self.dock = QDockWidget(TX("avisos_validacion"), self); self.dock.setObjectName("mensajes")
        self.arbol = QTreeWidget(); self.arbol.setHeaderHidden(True); self.arbol.itemDoubleClicked.connect(self._ir_mensaje)
        self.dock.setWidget(self.arbol); self.addDockWidget(Qt.LeftDockWidgetArea, self.dock)
        self.resizeDocks([self.dock], [230], Qt.Horizontal)
        self.m_ver.addSeparator(); self.m_ver.addAction(self.dock.toggleViewAction())
        self.m_ver.addSeparator()
        mver = self.m_ver.addMenu("Versión")
        self.a_ver_sencilla = mver.addAction("Versión sencilla", lambda: self.cambiar_version("sencilla"))
        self.a_ver_clasica = mver.addAction("Versión clásica"); self.a_ver_clasica.setCheckable(True); self.a_ver_clasica.setChecked(True)
        self._rellenar_mensajes([])

    # ------------------------------------------------------------------ datos
    def _titulo(self):
        nombre = (os.path.basename(self.proyecto.ruta) or "Sin título") if self.proyecto else "Sin título"
        mod = "*" if self.proyecto and self.proyecto.modificado else ""
        self.setWindowTitle(f"{nombre}{mod} - PLANIFICADOR de horarios")

    def abrir_dialogo(self):
        ruta, _ = QFileDialog.getOpenFileName(self, "Abrir", "", "Configuración de horarios (*.xghc);;Todos los archivos (*)")
        if ruta:
            self.abrir(ruta)

    def abrir(self, ruta):
        if not self.confirmar_cierre():
            return False
        try:
            self.proyecto = xghc.cargar(ruta)
            self.proyecto.ruta_original = ruta
            self.proyecto.ruta_guardado = None if self.es_original(ruta) else ruta
            self.pila_deshacer.clear(); self.pila_rehacer.clear(); self._actualizar_deshacer()
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, APP_NAME, f"No se pudo abrir el archivo:\n{ruta}\n\n{e}")
            return False
        self.panel.set_proyecto(self.proyecto)
        self._titulo(); self.cambiar_lista(self.lista_actual); self.validar(silencioso=True)
        self.statusBar().showMessage(f"Abierto: {ruta}", 5000)
        return True

    def cambiar_lista(self, clave, historial=True):
        if historial and (not self.historial or self.historial[self.hist_pos] != clave):
            self.historial = self.historial[:self.hist_pos + 1] + [clave]; self.hist_pos = len(self.historial) - 1
        self.lista_actual = clave; d = POR_CLAVE[clave]
        self.acc_listas[clave].setChecked(True)
        self._rellenar_menu_lista()
        self.modelo.clear(); self.modelo.setHorizontalHeaderLabels(d.columnas)
        filas = d.filas(self.proyecto) if self.proyecto else []
        for i, (obj, vals) in enumerate(filas):
            items = []
            for j, v in enumerate(vals):
                it = QStandardItem(str(v)); it.setData(obj, ROL_OBJ); items.append(it)
            self.preparar_items(items, clave)
            ic_col = 1 if clave == "sesiones" else 0
            items[ic_col].setIcon(icono(d.icono, 16))
            if clave == "sesiones" and obj.bloque is not None:
                prev = filas[i - 1][0] if i else None; nxt = filas[i + 1][0] if i + 1 < len(filas) else None
                a = getattr(prev, "bloque", None) == obj.bloque; b = getattr(nxt, "bloque", None) == obj.bloque
                items[0].setData("med" if a and b else "fin" if a else "ini" if b else "unica", ROL_BLOQUE)
            if clave == "marco" and getattr(obj, "tipo", "") != "lectivo":
                for it in items:
                    it.setBackground(QColor("#e6f6fa"))
            self.modelo.appendRow(items)
        self.tabla.setItemDelegateForColumn(0, self.delegado if clave == "sesiones" else self.del_edicion)
        hh = self.tabla.horizontalHeader()
        for j in range(len(d.columnas)):
            hh.setSectionResizeMode(j, QHeaderView.Interactive)
        self.tabla.resizeColumnsToContents()
        if clave == "sesiones":
            self.tabla.setColumnWidth(0, 22)
        for j in range(len(d.columnas)):
            self.tabla.setColumnWidth(j, min(self.tabla.columnWidth(j), 190))
        self.a_atras.setEnabled(self.hist_pos > 0); self.a_adelante.setEnabled(self.hist_pos < len(self.historial) - 1)
        self.panel.setVisible(d.con_plantilla)
        self._rellenar_valores()
        if self.proxy.rowCount():
            self.tabla.selectRow(0)
        else:
            self.panel.mostrar(None, "", None)
        self._actualizar_lin()

    def nav_atras(self):
        if self.hist_pos > 0:
            self.hist_pos -= 1; self.cambiar_lista(self.historial[self.hist_pos], False)

    def nav_adelante(self):
        if self.hist_pos < len(self.historial) - 1:
            self.hist_pos += 1; self.cambiar_lista(self.historial[self.hist_pos], False)

    def _fila_cambiada(self, cur, _prev=None):
        self._actualizar_lin()
        if not cur.isValid() or not self.proyecto:
            return
        obj = cur.data(ROL_OBJ); p = self.proyecto
        self.panel.set_estados(ESTADOS_NL.get(self.lista_actual))
        if self.lista_actual in ("reuniones", "guardias", "complementarias") and isinstance(obj, M.Elemento) \
                and self.mostrar_plantilla_nl(obj):
            return
        if isinstance(obj, M.Sesion):
            her = {}
            for lst, nom in ((p.profesores, obj.profesor), (p.grupos, obj.grupo), (p.materias, obj.materia)):
                for e in lst:
                    if e.nombre == nom:
                        for k, v in e.plantilla.items():
                            if v == M.PROHIBIDO:
                                her[k] = v
            self.panel.mostrar(obj.plantilla, f"{obj.materia}  ·  {obj.grupo}  ·  {obj.profesor}", obj.marco, her)
        elif isinstance(obj, M.Elemento):
            marco = obj.marco
            if self.lista_actual == "profesores":  # marco del primer grupo al que da clase
                g = next((s.grupo for s in p.sesiones if s.profesor == obj.nombre), None)
                marco = p.marco_de_grupo(g) if g else marco
            self.panel.mostrar(obj.plantilla, obj.datos.get("nombreCompleto") or obj.nombre, marco)

    def _actualizar_lin(self):
        r = self.tabla.currentIndex().row()
        self.lbl_lin.setText(f" Lin {r + 1 if r >= 0 else 0}/ {self.proxy.rowCount()} ")

    def _marcar_modificado(self):
        if self.proyecto:
            self.proyecto.modificado = True; self._titulo()

    # ------------------------------------------------------------------ filtro rápido
    _COL_FILTRO = {"sesiones": {"Grupo": 2, "Profesorado": 3, "Materia": 1, "Aula": 5},
                   "profesores": {"Profesorado": 0}, "grupos": {"Grupo": 0}, "materias": {"Materia": 0}, "aulas": {"Aula": 0}}

    def _rellenar_valores(self):
        self.cb_valor.blockSignals(True); self.cb_valor.clear(); self.cb_valor.addItem("")
        p = self.proyecto; t = self.cb_tipo.currentText()
        if p:
            src = {"Grupo": p.grupos, "Profesorado": p.profesores, "Materia": p.materias, "Aula": p.aulas}[t]
            self.cb_valor.addItems([e.nombre for e in src])
        self.cb_valor.blockSignals(False); self._aplicar_filtro()

    def _aplicar_filtro(self):
        col = self._COL_FILTRO.get(self.lista_actual, {}).get(self.cb_tipo.currentText(), -1)
        self.proxy.col = col; self.proxy.valor = self.cb_valor.currentText(); self.proxy.invalidateFilter()
        self.b_quitar.setEnabled(bool(self.proxy.valor)); self._actualizar_lin()

    def _mover_valor(self, d):
        n = self.cb_valor.count()
        if n > 1:
            i = self.cb_valor.currentIndex() + d
            self.cb_valor.setCurrentIndex(1 + (i - 1) % (n - 1))

    def _filtro_fila_actual(self):
        idx = self.tabla.currentIndex(); col = self._COL_FILTRO.get(self.lista_actual, {}).get(self.cb_tipo.currentText(), -1)
        if idx.isValid() and col >= 0:
            v = self.proxy.index(idx.row(), col).data().split(" ")[0]
            i = self.cb_valor.findText(v)
            if i >= 0:
                self.cb_valor.setCurrentIndex(i)

    # ------------------------------------------------------------------ menús contextuales y validación
    def _menu_contextual(self, pos):
        m = QMenu(self)
        for a in self._acciones_lista():
            m.addSeparator() if a is None else (m.addMenu(a) if isinstance(a, QMenu) else m.addAction(a))
        m.exec(self.tabla.viewport().mapToGlobal(pos))

    def validar(self, silencioso=False):
        if not self.proyecto:
            if not silencioso:
                QMessageBox.information(self, APP_NAME, "No hay ningún archivo abierto.")
            return
        self._rellenar_mensajes(validacion.validar(self.proyecto))
        self.dock.show()

    def _rellenar_mensajes(self, msgs):
        self.arbol.clear()
        st = self.style()
        iconos = {validacion.AVISO: st.standardIcon(QStyle.SP_MessageBoxWarning),
                  validacion.ERROR: st.standardIcon(QStyle.SP_MessageBoxCritical),
                  validacion.INFO: st.standardIcon(QStyle.SP_MessageBoxInformation)}
        for tipo in (validacion.AVISO, validacion.ERROR, validacion.INFO):
            sub = [m for m in msgs if m[0] == tipo]
            raiz = QTreeWidgetItem([f"{tipo} ({len(sub)})"]); raiz.setIcon(0, iconos[tipo])
            for _, txt, ref in sub:
                it = QTreeWidgetItem([txt]); it.setIcon(0, iconos[tipo]); it.setData(0, Qt.UserRole, ref); it.setToolTip(0, txt)
                raiz.addChild(it)
            self.arbol.addTopLevelItem(raiz); raiz.setExpanded(True)

    def _ir_mensaje(self, it, _col):
        ref = it.data(0, Qt.UserRole)
        if not ref:
            return
        lista, nombre = ref; self.cb_valor.setCurrentIndex(0); self.cambiar_lista(lista)
        for r in range(self.proxy.rowCount()):
            o = self.proxy.index(r, 0).data(ROL_OBJ)
            if getattr(o, "nombre", None) == nombre or getattr(o, "id", None) == nombre:
                self.tabla.selectRow(r); break

    def generar(self):
        if not self.proyecto:
            QMessageBox.information(self, APP_NAME, "No hay ningún archivo abierto."); return
        msgs = validacion.validar(self.proyecto)
        errores = [m for m in msgs if m[0] == validacion.ERROR]
        if errores and QMessageBox.question(self, APP_NAME, f"La validación encuentra {len(errores)} errores. "
                                            "¿Generar el horario de todos modos?") != QMessageBox.Yes:
            self._rellenar_mensajes(msgs); self.dock.show(); return
        from .ventana_motor import VentanaMotor
        self.ventana_motor = VentanaMotor(self.proyecto, self)
        self.ventana_motor.show()

    def generar_parcial(self):
        if not self.proyecto:
            QMessageBox.information(self, APP_NAME, "No hay ningún archivo abierto."); return
        from .parcial import generar_parcial
        generar_parcial(self)

    def abrir_resultado(self):
        if not self.proyecto:
            QMessageBox.information(self, APP_NAME, "Abra primero el archivo de configuración del resultado."); return
        ruta, _ = QFileDialog.getOpenFileName(self, "Abrir un resultado", os.path.dirname(self.proyecto.ruta),
                                              FILTRO_LPHR)
        if not ruta:
            return
        from .editor import VentanaEditor
        try:
            self.editor = VentanaEditor(ruta, self.proyecto.ruta)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, APP_NAME, f"No se pudo abrir el resultado:\n{e}"); return
        self.editor.show()

    def acerca(self):
        QMessageBox.about(self, f"Acerca de {APP_NAME}",
                          f"<h2>{APP_NAME}</h2><p>Versión {__version__}</p><p><b>{VENDOR}</b></p>"
                          "<p>Planificador de horarios para centros de enseñanza.<br>Software libre.</p>")

    def closeEvent(self, ev):
        if not self.confirmar_cierre():
            ev.ignore(); return
        ev.accept()
