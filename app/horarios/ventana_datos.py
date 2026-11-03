"""Datos del Planificador: perfil de aplicación (450), importar datos (257, lista de gestores), periodos del marco
(425/426/521/249), horario distinto cada día (448), varias semanas (622) y asignación semanal (625).
Todos los textos proceden del paquete de textos activo (ver textos.py)."""
from __future__ import annotations
from .textos import TX
from PySide6.QtCore import Qt, QSettings, QRectF
from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtWidgets import (QDialog, QMessageBox, QTreeWidgetItem, QWidget, QTabBar, QSpinBox, QLabel,
                               QAbstractItemView, QHBoxLayout, QPushButton, QVBoxLayout, QDialogButtonBox)
from . import APP_NAME, VENDOR, AJUSTES
from . import edicion as ED, periodos as PER, semanas as SEM
from .formrc import PaginaRC, fuente_dialogo

PROX = "Esta opción estará disponible próximamente."


def _no_modal(w):
    p = w
    while p is not None and not hasattr(p, "_no_modal"):
        p = p.parent()
    return bool(getattr(p, "_no_modal", False))


class DlgRC(QDialog):
    RID = ""; OCULTAR = ()

    def __init__(self, parent, titulo=None):
        super().__init__(parent)
        viejo = PaginaRC.OCULTAR; PaginaRC.OCULTAR = set(viejo) | set(self.OCULTAR)
        try:
            self.pg = PaginaRC(self.RID, self)
        finally:
            PaginaRC.OCULTAR = viejo
        self.setFixedSize(self.pg.size()); self.setFont(fuente_dialogo())
        self.setWindowTitle(titulo or self.pg.titulo or APP_NAME)
        self.c = self.pg.c
        if 1 in self.c:
            self.c[1].clicked.connect(self.accept)
        if 2 in self.c:
            self.c[2].clicked.connect(self.reject)
        if 57670 in self.c:
            self.c[57670].clicked.connect(lambda: QMessageBox.information(self, APP_NAME, "La ayuda: " + PROX.lower()))

    def ejecutar(self):
        return True if _no_modal(self.parent()) else self.exec() == QDialog.Accepted


# ---------------------------------------------------------------- 450 Perfil
PERFILES = {1043: ("basico", "primaria"), 1044: ("avanzado", "secundaria"), 1045: ("subgrupos", "secundaria"),
            1060: ("conservatorio", "conservatorio")}


class DialogoPerfil(DlgRC):
    """Asistente de perfil: «Seleccione la opción que mejor se adapte a su utilización…». El perfil elegido se
    guarda en QSettings (perfil de aplicación) y en otros/perfil del archivo (valores del XML-GHC)."""
    RID = "450"

    def __init__(self, parent, actual="avanzado"):
        super().__init__(parent, "Perfil")
        for cid, (k, _x) in PERFILES.items():
            self.c[cid].setChecked(k == actual)
        st = QSettings(VENDOR, AJUSTES)
        self.c[1074].setChecked(st.value("perfil/abrir_al_iniciar", "true") == "true")
        b = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        b.button(QDialogButtonBox.Ok).setText("Aceptar"); b.button(QDialogButtonBox.Cancel).setText("Cerrar")
        b.accepted.connect(self.accept); b.rejected.connect(self.reject)
        self.setFixedSize(self.width(), self.height() + 34); b.setGeometry(self.width() - 200, self.height() - 32, 190, 26)

    def eleccion(self):
        return next((k for cid, (k, _x) in PERFILES.items() if self.c[cid].isChecked()), "avanzado")


# ---------------------------------------------------------------- 257 Importar (lista de gestores)
class DialogoImportar(DlgRC):
    """Diálogo de importación desde programas de gestión académica: solo la lista de gestores (estructura). Ninguna importación está disponible todavía."""
    RID = "257"

    def __init__(self, parent):
        super().__init__(parent, TX("importar_datos_otro_programa"))
        self.radios = {cid: w for cid, w in self.c.items() if w.metaObject().className() == "QRadioButton"}
        self.pg.regrupar(list(self.radios))
        try:
            self.c[1].clicked.disconnect()
        except (RuntimeError, TypeError):
            pass
        self.c[1].clicked.connect(self.aceptar)
        self.elegido = None

    def gestores(self):
        return [w.text().replace("\n", " ") for _cid, w in sorted(self.radios.items(), key=lambda kv: (kv[1].x(), kv[1].y()))]

    def aceptar(self):
        sel = next((w for w in self.radios.values() if w.isChecked()), None)
        if sel is None:
            QMessageBox.information(self, self.windowTitle(), "Seleccione la aplicación de la que procede los datos."); return
        self.elegido = sel.text().replace("\n", " ")
        if not _no_modal(self):
            QMessageBox.information(self, self.windowTitle(), f"«{self.elegido}»\n\nLa importación desde esta aplicación "
                                    "estará disponible próximamente.")
        self.accept()


# ---------------------------------------------------------------- 493 DELPHOS: modo y archivos
class DialogoDelphos(DlgRC):
    """Basado en 493: el paso «1.-» elige el archivo descargado de DELPHOS (variante principal) y, opcionalmente, el de
    la variante KRONOWIN (para proponer las sesiones con N_HORAS/60); la conversión la hace la propia aplicación.
    Los tres modos del recurso: nuevos datos (1045), incremental sincronizada (1044) y claves externas (1046)."""
    RID = "493"
    MODOS = {1045: "nuevo", 1044: "actualizar", 1046: "claves"}

    def __init__(self, parent):
        super().__init__(parent, TX("importar_datos_delphos_castilla_mancha"))
        self.pg.regrupar(list(self.MODOS))
        self.c[1045].setChecked(True)
        self.c[1322].setText("1.- Elegir los archivos de DELPHOS")
        self.c[1322].clicked.connect(self.elegir)
        self.c[1011].setReadOnly(True)
        from PySide6.QtWidgets import QLabel as _L
        for lb in self.findChildren(_L):
            if lb.text().startswith("Use primero el proceso"):
                lb.setText("Elija el archivo XML descargado de DELPHOS con los datos para el horario y, si quiere que se "
                           "propongan las sesiones, el de la variante KRONOWIN.")
        self.b_kro = QPushButton("KRONOWIN (opcional)...", self)
        g = self.c[1322].geometry()
        self.b_kro.setGeometry(g.right() + 8, g.y(), 150, g.height()); self.b_kro.clicked.connect(lambda: self.elegir(True))
        self.c[1].setText("2.- Importar")
        try:
            self.c[1].clicked.disconnect()
        except (RuntimeError, TypeError):
            pass
        self.c[1].clicked.connect(self.aceptar)
        self.pen = self.kro = None
        self._estado()

    def elegir(self, kro=False):
        from PySide6.QtWidgets import QFileDialog
        f, _ = QFileDialog.getOpenFileName(self, "Archivo de DELPHOS" + (" (KRONOWIN)" if kro else ""), "",
                                           "Archivos XML (*.xml);;Todos (*)")
        if f:
            self.poner(f, kro)

    def poner(self, f, kro=False):
        if kro:
            self.kro = f
        else:
            self.pen = f
        self._estado()

    def _estado(self):
        import os
        self.c[1011].setText(os.path.basename(self.pen) if self.pen else "")
        self.c[1011].setFixedWidth(300)
        self.c[1242].setText(" Archivo principal: " + (os.path.basename(self.pen) if self.pen else "—") +
                             "\n KRONOWIN: " + (os.path.basename(self.kro) if self.kro else "(no)"))

    def modo(self):
        return next(m for cid, m in self.MODOS.items() if self.c[cid].isChecked())

    def aceptar(self):
        if not self.pen and not self.kro:
            QMessageBox.information(self, self.windowTitle(), "Elija primero el archivo descargado de DELPHOS."); return
        self.accept()


class DialogoInforme(QDialog):
    """Informe de incidencias de la importación (recuentos, avisos y errores)."""

    def __init__(self, parent, titulo, texto):
        super().__init__(parent)
        from PySide6.QtWidgets import QPlainTextEdit
        self.setWindowTitle(titulo); self.setFont(fuente_dialogo()); self.resize(640, 420)
        lay = QVBoxLayout(self)
        self.t = QPlainTextEdit(texto, self); self.t.setReadOnly(True); lay.addWidget(self.t)
        b = QDialogButtonBox(QDialogButtonBox.Ok, self); b.button(QDialogButtonBox.Ok).setText("Aceptar")
        b.accepted.connect(self.accept); lay.addWidget(b)


# ---------------------------------------------------------------- 425 / 426 / 521 / 249 periodos
TIPOS = [("lectivo", "Lectivo"), ("recreo", "Recreos")]


class DialogoPeriodo(DlgRC):
    """426 «Modifica periodo»: clave, marco A-D, día (o todos), lectivo/recreo, entrada y salida."""
    RID = "426"
    MARCOS = {1060: "A", 1061: "B", 1062: "C", 1063: "D"}
    DIAS = {1045: 0, 1046: 1, 1047: 2, 1048: 3, 1049: 4, 1051: 5}

    def __init__(self, parent, fila, base_dia=0, varios=False):
        super().__init__(parent)
        self.base = base_dia
        self.pg.regrupar(list(self.MARCOS), [1044] + list(self.DIAS), [1043, 1050])
        self.c[1010].setText(fila.get("clave", ""))
        for cid, m in self.MARCOS.items():
            self.c[cid].setChecked(m == fila["marco"])
        self.c[1044].setChecked(varios)
        for cid, d in self.DIAS.items():
            self.c[cid].setChecked(not varios and d == fila["dia"] - base_dia)
        self.c[1043 if fila["tipo"] == "lectivo" else 1050].setChecked(True)
        h1, m1 = (fila["entrada"] + ":00").split(":")[:2]; h2, m2 = (fila["salida"] + ":00").split(":")[:2]
        for cid, v in ((1271, h1), (1272, m1), (1273, h2), (1274, m2)):
            self.c[cid].setText(v)

    def valor(self, fila):
        g = dict(fila)
        g["clave"] = self.c[1010].text().strip()
        g["marco"] = next((m for cid, m in self.MARCOS.items() if self.c[cid].isChecked()), fila["marco"])
        g["tipo"] = "lectivo" if self.c[1043].isChecked() else "recreo"
        z = lambda cid: f"{int(self.c[cid].text() or 0):02d}"
        g["entrada"] = f"{z(1271)}:{z(1272)}"; g["salida"] = f"{z(1273)}:{z(1274)}"
        todos = self.c[1044].isChecked()
        dia = next((d for cid, d in self.DIAS.items() if self.c[cid].isChecked()), None)
        return g, (None if todos or dia is None else dia + self.base)


class DialogoCopiarPeriodos(DlgRC):
    """521 «Copiar las horas marcadas»: destino marco A-D y día (L-S)."""
    RID = "521"
    MARCOS = {1044: "A", 1043: "B", 1060: "C", 1045: "D"}
    DIAS = {1047: 0, 1048: 1, 1049: 2, 1050: 3, 1051: 4, 1052: 5}

    def __init__(self, parent, origen, marcos, dias):
        super().__init__(parent)
        self.pg.regrupar(list(self.MARCOS), list(self.DIAS))
        self.c[1500].setText(origen)
        for cid, m in self.MARCOS.items():
            self.c[cid].setEnabled(m in marcos); self.c[cid].setChecked(m == marcos[0])
        for cid, d in self.DIAS.items():
            self.c[cid].setEnabled(d < dias)
        # «Toda la semana» (vídeo avanzado 1/4): todos los días destino si no se marca ninguno
        self.c[1047].setChecked(False)

    def destino(self):
        m = next((m for cid, m in self.MARCOS.items() if self.c[cid].isChecked()), "A")
        ds = [d for cid, d in self.DIAS.items() if self.c[cid].isChecked()]
        return m, ds


class Representacion(QWidget):
    """249 «Dibujo de las horas»: columnas por marco y día, bloques por hora."""

    def __init__(self, filas, parent=None):
        super().__init__(parent); self.filas = [f for f in filas if f["activo"]]

    def paintEvent(self, _ev):
        p = QPainter(self); p.fillRect(self.rect(), QColor("white"))
        if not self.filas:
            return
        cols = sorted({(f["marco"], f["dia"]) for f in self.filas})
        t0 = min(PER._min(f["entrada"]) for f in self.filas); t1 = max(PER._min(f["salida"]) for f in self.filas)
        W, H = self.width() - 50, self.height() - 24
        cw = W / max(1, len(cols)); esc = H / max(1, t1 - t0)
        p.setPen(QColor("#888"))
        for h in range(t0 // 60, t1 // 60 + 1):
            y = 20 + (h * 60 - t0) * esc
            if 20 <= y <= self.height():
                p.drawText(2, int(y) + 4, f"{h:02d}:00"); p.drawLine(44, int(y), self.width(), int(y))
        for i, (mc, d) in enumerate(cols):
            x = 48 + i * cw
            p.setPen(QColor("#000")); p.drawText(QRectF(x, 2, cw, 16), Qt.AlignCenter, f"{mc} {PER.DIAS_C[d % 7]}{'' if d < 7 else d // 7 + 1}")
            for f in self.filas:
                if (f["marco"], f["dia"]) != (mc, d):
                    continue
                y = 20 + (PER._min(f["entrada"]) - t0) * esc; h = (PER._min(f["salida"]) - PER._min(f["entrada"])) * esc
                p.setBrush(QColor("#9fc5e8" if f["tipo"] == "lectivo" else "#ffe599")); p.setPen(QPen(QColor("#555")))
                p.drawRect(QRectF(x + 2, y, cw - 4, max(2, h)))


class DialogoRepresentacion(DlgRC):
    RID = "249"
    OCULTAR = (1395,)

    def __init__(self, parent, filas):
        super().__init__(parent)
        self.vista = Representacion(filas, self); self.vista.setGeometry(10, 34, self.width() - 20, self.height() - 44)


class DialogoPeriodos(DlgRC):
    """425 «Revise y marque las horas que quiere cargar», con pestañas por día (horario distinto cada día)."""
    RID = "425"
    COLS = ["Mar", "Día", "Entrada", "Salida", TX("codigo_2"), "Tipo", "Activo"]

    def __init__(self, parent, proyecto):
        super().__init__(parent, "Modifique y añada los periodos que desee cargar")
        self.p = proyecto; self.filas = PER.filas(proyecto)
        self.ndias = max([len(m.dias) for m in proyecto.marcos.values()] + [5])
        self.marcos = sorted(proyecto.marcos) or ["A"]
        self.c[1074].setChecked(True)
        self.lst = self.c[1055]; self.lst.setHeaderLabels(self.COLS)
        self.lst.setSelectionMode(QAbstractItemView.ExtendedSelection)
        g = self.lst.geometry()
        self.tabs = QTabBar(self); self.tabs.addTab("Todos")
        for d in range(min(self.ndias, 7)):
            self.tabs.addTab(PER.DIAS[d])
        self.tabs.setGeometry(g.x(), g.y() - 2, g.width(), 22); self.tabs.setDrawBase(False)
        self.lst.setGeometry(g.x(), g.y() + 20, g.width(), g.height() - 20)
        self.tabs.currentChanged.connect(lambda *_: self.llenar())
        self.c[1270].clicked.connect(self.modificar); self.c[1271].clicked.connect(self.duplicar)
        self.lst.itemDoubleClicked.connect(lambda *_: self.modificar())
        # botones añadidos (vídeo avanzado 1/4): Añadir, Borrar, Copiar los periodos, Representación gráfica
        x = self.c[1270].x(); w = self.c[1270].width(); y = self.c[1271].y() + self.c[1271].height() + 6
        self.b_anadir = QPushButton("Añadir un periodo", self); self.b_borrar = QPushButton("Borrar", self)
        self.b_copiar = QPushButton("Copiar los periodos...", self); self.b_graf = QPushButton("Representación gráfica", self)
        for i, b in enumerate((self.b_anadir, self.b_borrar, self.b_copiar, self.b_graf)):
            b.setGeometry(x, y + 64 + i * 26, w, 24); b.setFont(fuente_dialogo())
        self.c[1504].move(self.c[1504].x(), y)
        self.b_anadir.clicked.connect(self.anadir); self.b_borrar.clicked.connect(self.borrar)
        self.b_copiar.clicked.connect(self.copiar); self.b_graf.clicked.connect(self.grafica)
        self.c[1].clicked.disconnect(); self.c[1].clicked.connect(self.continuar)
        self.llenar()

    # -- lista
    def dia_tab(self):
        i = self.tabs.currentIndex(); return None if i <= 0 else i - 1

    def visibles(self):
        d = self.dia_tab()
        return [i for i, f in enumerate(self.filas) if d is None or f["dia"] % 7 == d]

    def llenar(self):
        self.lst.clear()
        for i in self.visibles():
            f = self.filas[i]
            it = QTreeWidgetItem([f["marco"], PER.DIAS[f["dia"] % 7] + ("" if f["dia"] < 7 else f" ({f['dia'] // 7 + 1})"),
                                  f["entrada"], f["salida"], f["clave"], dict(TIPOS).get(f["tipo"], f["tipo"]), ""])
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(6, Qt.Checked if f["activo"] else Qt.Unchecked); it.setData(0, Qt.UserRole, i)
            self.lst.addTopLevelItem(it)
        self.lst.itemChanged.connect(self._marcar) if not getattr(self, "_conectado", False) else None
        self._conectado = True
        cortos = PER.cortos(self.filas)
        self.c[1503].setVisible(bool(cortos))

    def _marcar(self, it, col):
        if col == 6:
            self.filas[it.data(0, Qt.UserRole)]["activo"] = it.checkState(6) == Qt.Checked

    def seleccion(self):
        return sorted(it.data(0, Qt.UserRole) for it in self.lst.selectedItems())

    def modificar(self, valores=None):
        sel = self.seleccion()
        if not sel:
            return
        f = self.filas[sel[0]]
        d = DialogoPeriodo(self, f, varios=len(sel) > 1)
        if valores:
            for cid, v in valores.items():
                w = d.c[cid]; w.setText(v) if hasattr(w, "setText") and not hasattr(w, "setChecked") else w.setChecked(bool(v))
        if not d.ejecutar():
            return
        g, dia = d.valor(f)
        for i in sel:
            h = dict(self.filas[i]); h.update({k: g[k] for k in ("clave", "marco", "tipo", "entrada", "salida")} if len(sel) == 1
                                             else {k: g[k] for k in ("marco", "tipo")})
            if dia is not None and len(sel) == 1:
                h["dia"] = dia
            self.filas[i] = h
        self.llenar()

    def anadir(self):
        d = self.dia_tab() or 0
        mias = [f for f in self.filas if f["dia"] == d and f["marco"] == self.marcos[0]]
        ult = max(mias, key=lambda f: PER._min(f["salida"]), default=None)
        ini = ult["salida"] if ult else "08:00"
        fin_m = PER._min(ini) + 55
        self.filas.append({"marco": self.marcos[0], "dia": d, "entrada": ini, "salida": f"{fin_m // 60:02d}:{fin_m % 60:02d}",
                           "tipo": "lectivo", "clave": "", "activo": True})
        self.llenar()

    def borrar(self):
        for i in reversed(self.seleccion()):
            del self.filas[i]
        self.llenar()

    def duplicar(self):
        """1271 «Copiar una hora a otro marco»: copia los seleccionados al siguiente marco (crea B si no hay)."""
        sel = self.seleccion()
        if not sel:
            return
        letras = "ABCD"
        for i in sel:
            f = dict(self.filas[i]); j = letras.index(f["marco"]) if f["marco"] in letras else 0
            f["marco"] = letras[min(3, j + 1)]; self.filas.append(f)
        self.llenar()

    def copiar(self, destino=None):
        sel = [self.filas[i] for i in self.seleccion()]
        if not sel:
            d = self.dia_tab() or 0
            sel = [f for f in self.filas if f["dia"] == d and f["marco"] == self.marcos[0]]
        if not sel:
            return
        d0 = sel[0]
        dlg = DialogoCopiarPeriodos(self, f"Origen: marco {d0['marco']}, {PER.DIAS[d0['dia'] % 7]} ({len(sel)} periodos)",
                                    sorted(set(self.marcos) | {"A", "B", "C", "D"}), self.ndias)
        if destino is not None:
            m, ds = destino
        else:
            if not dlg.ejecutar():
                return
            m, ds = dlg.destino()
        if not ds:
            ds = [d for d in range(self.ndias) if not (m == d0["marco"] and d == d0["dia"])]   # toda la semana
        self.filas = PER.copiar(self.filas, sel, m, ds)
        self.llenar()

    def grafica(self):
        d = DialogoRepresentacion(self, self.filas); self.ultima_grafica = d
        d.ejecutar()

    def continuar(self):
        av = PER.validar(self.filas)
        if av and not _no_modal(self):
            if QMessageBox.question(self, self.windowTitle(), "Hay periodos incorrectos:\n\n" + "\n".join(av[:10]) +
                                    TX("seguir_todas_formas")) != QMessageBox.Yes:
                return
        self.avisos = av
        self.accept()


# ---------------------------------------------------------------- 448 / 622 / 625
class DialogoInfo(DlgRC):
    def __init__(self, parent, rid):
        self.RID = rid; super().__init__(parent)


class DialogoNumSemanas(DlgRC):
    """622 «Varias semanas» + selector del «Número de semanas» (1-6, vídeo varias_semanas)."""
    RID = "622"

    def __init__(self, parent, n):
        super().__init__(parent)
        self.setFixedSize(self.width(), self.height() + 30)
        QLabel("Número de semanas:", self).setGeometry(30, self.height() - 26, 130, 22)
        self.sp = QSpinBox(self); self.sp.setRange(1, 6); self.sp.setValue(n); self.sp.setGeometry(160, self.height() - 26, 60, 22)
        self.c[1].setText("Aceptar")
        b = QPushButton("Cancelar", self); b.setGeometry(self.c[1].x(), self.height() - 28, self.c[1].width(), 24)
        b.clicked.connect(self.reject)


class DialogoSemanas(DlgRC):
    """625 «Semanas» (Asignación semanal de las sesiones seleccionadas)."""
    RID = "625"
    CASILLAS = [1074, 1075, 1076, 1077, 1078, 1079]
    ESTADOS = [1116, 1176, 1242, 1237, 1238, 1374]
    MODOS = {1044: "ignorar", 1045: "preferente", 1046: "obligatorio", 1047: "procuraEvitar", 1048: "prohibido"}

    def __init__(self, parent, nombres, refs_por_sesion, modos, titulo):
        super().__init__(parent, titulo)
        self.nombres = nombres
        self.pg.regrupar(list(self.MODOS))
        b = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        b.button(QDialogButtonBox.Ok).setText("Aceptar"); b.button(QDialogButtonBox.Cancel).setText("Cancelar")
        b.accepted.connect(self.accept); b.rejected.connect(self.reject)
        b.setGeometry(self.width() - 190, self.height() - 30, 180, 26)
        self.c[1069].setVisible(False)
        for i, cid in enumerate(self.CASILLAS):
            vis = i < len(nombres)
            self.c[cid].setVisible(vis); self.c[self.ESTADOS[i]].setVisible(vis)
            if vis:
                n = sum(1 for r in refs_por_sesion if nombres[i] in r)
                self.c[cid].setTristate(0 < n < len(refs_por_sesion))
                self.c[cid].setCheckState(Qt.Checked if n == len(refs_por_sesion) else Qt.Unchecked if n == 0 else Qt.PartiallyChecked)
                self.c[self.ESTADOS[i]].setText("sí" if n == len(refs_por_sesion) else "no" if n == 0 else "varía")
                self.c[cid].stateChanged.connect(lambda st, k=i: self.c[self.ESTADOS[k]].setText(
                    "sí" if st == Qt.Checked.value else "no" if st == Qt.Unchecked.value else "varía"))
        self.c[1406].setVisible(len(set(modos)) > 1)
        m0 = modos[0] if len(set(modos)) == 1 else None
        for cid, m in self.MODOS.items():
            self.c[cid].setChecked(m == m0)
        self.setWindowTitle(f"{self.windowTitle()} - {len(refs_por_sesion)} sesión(es)")

    def valor(self):
        """(refs o None si alguna casilla queda indeterminada, modo o None si no se elige)."""
        refs = []
        for i, n in enumerate(self.nombres):
            st = self.c[self.CASILLAS[i]].checkState()
            if st == Qt.PartiallyChecked:
                return None, self._modo()
            if st == Qt.Checked:
                refs.append(n)
        return refs, self._modo()

    def _modo(self):
        return next((m for cid, m in self.MODOS.items() if self.c[cid].isChecked()), None)


# ---------------------------------------------------------------- mixin del Planificador
class DatosMixin:
    def _abierto(self):
        if not self.proyecto:
            QMessageBox.information(self, APP_NAME, "No hay ningún archivo abierto."); return False
        return True

    def nuevo(self, asistente=True, perfil=None, operar_periodos=None):
        """Archivo > Nuevo: archivo .xghc vacío (plantilla con marco A de 7 periodos, tareas LEC/G/RDP,
        criterios y opciones por defecto). Con asistente: perfil (450) y periodos del marco (425).
        perfil/operar_periodos permiten a las pruebas recorrer el asistente sin diálogos modales."""
        from . import nuevo as NV
        if not self.confirmar_cierre():
            return False
        st = QSettings(VENDOR, AJUSTES)
        self.proyecto = NV.crear(perfil or st.value("perfil/actual", "avanzado"))
        self.pila_deshacer.clear(); self.pila_rehacer.clear(); self._actualizar_deshacer()
        self.panel.set_proyecto(self.proyecto)
        self._titulo(); self.cambiar_lista(self.lista_actual)
        if asistente:
            self.perfil_aplicacion(perfil)          # 450 (si se cancela, queda el perfil por defecto)
            self.periodos_marco(operar_periodos)    # 425 periodos del marco A
            self.pila_deshacer.clear(); self.pila_rehacer.clear(); self._actualizar_deshacer()
            self.proyecto.modificado = False
        self._titulo(); self.validar(silencioso=True)
        self.statusBar().showMessage("Archivo nuevo", 4000)
        return True

    def perfil_aplicacion(self, eleccion=None):
        st = QSettings(VENDOR, AJUSTES)
        d = DialogoPerfil(self, st.value("perfil/actual", "avanzado")); self._ultimo_dialogo = d
        if eleccion is not None:
            for cid, (k, _x) in PERFILES.items():
                d.c[cid].setChecked(k == eleccion)
        if not d.ejecutar():
            return None
        k = d.eleccion()
        st.setValue("perfil/actual", k); st.setValue("perfil/abrir_al_iniciar", "true" if d.c[1074].isChecked() else "false")
        self.statusBar().showMessage(TX("perfil_uso_k", k=k), 4000)
        if self.proyecto:
            xml = next(x for (kk, x) in PERFILES.values() if kk == k)
            def fn(arbol):
                raiz = arbol.raiz; otros = raiz.find("otros")
                if otros is None:
                    otros = ED.insertar_hijo(arbol, raiz, ED.nuevo("otros"))
                if (otros.findtext("perfil") or "").strip() == xml:
                    return False
                ED.escribir(arbol, otros, "perfil", xml); return True
            self.editar(fn, TX("perfil_uso_2"))
        return k

    def importar_datos(self, gestor=None):
        d = DialogoImportar(self); self._ultimo_dialogo = d
        if gestor is not None:
            for w in d.radios.values():
                w.setChecked(w.text().replace("\n", " ") == gestor)
            d.aceptar()
        elif not d.ejecutar():
            return None
        if d.elegido and d.elegido.startswith("DELPHOS"):
            return self.importar_delphos()
        return d.elegido

    def importar_delphos(self, operar=None):
        """DELPHOS: 493 (modo y archivos) -> importación con deshacer -> informe de incidencias.
        operar(dlg) permite a las pruebas fijar archivos y modo. Devuelve las Incidencias (o None)."""
        from . import delphos as DL
        if not self.proyecto and not self.nuevo(asistente=False):
            return None
        d = DialogoDelphos(self); self._ultimo_dialogo = d
        if operar is not None:
            operar(d); d.aceptar()
        elif not d.ejecutar():
            return None
        if d.result() != QDialog.Accepted and operar is None:
            return None
        inc = DL.Incidencias()
        try:
            pen = DL.leer(d.pen, inc) if d.pen else None
            kro = DL.leer(d.kro, inc) if d.kro else None
        except (DL.ErrorDelphos, OSError) as e:
            QMessageBox.warning(self, d.windowTitle(), f"No se puede leer el archivo:\n{e}"); return None
        if pen is None:
            pen, kro = kro, None
        modo = d.modo()
        if modo == "claves":
            DL.importar(None, pen, ED, None, "claves", kro=kro, inc=inc)
        else:
            if modo == "nuevo" and (self.proyecto.ruta or self.proyecto.modificado):
                # «datos nuevos»: se parte de un archivo nuevo (Archivo > Nuevo); el actual no se toca
                if not self.nuevo(asistente=False):
                    return None
            self.editar(lambda arbol: (DL.importar(arbol.raiz, pen, ED, arbol, modo, kro=kro, inc=inc), True)[1],
                        "Importar datos desde DELPHOS")
        self.proyecto.claves_externas = inc.claves
        self.validar(silencioso=True)          # el panel de validación refleja los datos importados
        self._informe = DialogoInforme(self, "Importación desde DELPHOS: informe de incidencias", inc.texto())
        self._ultimo_dialogo = self._informe
        if _no_modal(self):
            self._informe.show()
        else:
            self._informe.exec()
        self.statusBar().showMessage(f"DELPHOS: {len(inc.errores)} errores, {len(inc.lineas) - len(inc.errores)} avisos", 6000)
        return inc

    def periodos_marco(self, operar=None):
        """425: modificar y añadir periodos. operar(dlg) permite a las pruebas manipular el diálogo."""
        if not self._abierto():
            return False
        d = DialogoPeriodos(self, self.proyecto); self._ultimo_dialogo = d
        if operar is not None:
            operar(d); d.continuar()
        elif not d.ejecutar():
            return False
        if not d.c[1074].isChecked():
            return False
        filas = d.filas
        ok = self.editar(lambda arbol: PER.aplicar(self.proyecto, filas, ED, arbol), "Modificar los periodos")
        if ok:
            self.statusBar().showMessage("Periodos del marco actualizados", 4000)
        return ok

    def horario_distinto(self, operar=None):
        """448 «Un horario distinto para cada día» (aviso) y edición de los periodos por día."""
        if not self._abierto():
            return False
        DialogoInfo(self, "448").ejecutar()
        return self.periodos_marco(operar)

    def numero_semanas(self, n=None):
        if not self._abierto():
            return None
        actual = SEM.num_semanas(self.proyecto.doc.raiz)
        d = DialogoNumSemanas(self, actual); self._ultimo_dialogo = d
        if n is not None:
            d.sp.setValue(n)
        if not d.ejecutar():
            return None
        n = d.sp.value()
        if n == actual:
            return n
        self.editar(lambda arbol: SEM.fijar_num_semanas(self.proyecto, n, ED) or True, "Número de semanas")
        return n

    def asignacion_semanal(self, refs=None, modo=None, sesiones=None):
        """625: semanas en que se imparten las sesiones seleccionadas y posición entre semanas."""
        if not self._abierto():
            return False
        p = self.proyecto; raiz = p.doc.raiz
        if SEM.num_semanas(raiz) < 2:
            QMessageBox.information(self, APP_NAME, "El horario tiene una sola semana. Indique antes el número de "
                                    "semanas en el menú del marco horario."); return False
        if sesiones is None:
            from .ventana_edicion import M_ROL_OBJ
            sesiones = []
            for idx in self.tabla.selectionModel().selectedIndexes():
                o = idx.data(M_ROL_OBJ)
                if o is not None and o not in sesiones and hasattr(o, "materia"):
                    sesiones.append(o)
        if not sesiones:
            return False
        # el bloque de simultáneas se coloca junto: la asignación se extiende a todas sus sesiones
        bl = {s.bloque for s in sesiones if s.bloque is not None}
        sesiones = list(sesiones) + [s for s in p.sesiones if s.bloque in bl and s not in sesiones]
        noms = [n for n, _ in SEM.periodos(raiz, next(iter(p.marcos.values())).dias)]
        actuales = [SEM.de_sesion(s.xml, noms) for s in sesiones]
        titulo = f"Asignación semanal de {sesiones[0].materia}" if len({s.materia for s in sesiones}) == 1 else "Asignación semanal"
        d = DialogoSemanas(self, noms, [a[0] for a in actuales], [a[1] for a in actuales], titulo); self._ultimo_dialogo = d
        if refs is not None:
            for i, cid in enumerate(d.CASILLAS[:len(noms)]):
                d.c[cid].setCheckState(Qt.Checked if noms[i] in refs else Qt.Unchecked)
        if modo is not None:
            for cid, m in d.MODOS.items():
                d.c[cid].setChecked(m == modo)
        if not d.ejecutar():
            return False
        r, m = d.valor()
        if r is not None and not r:
            QMessageBox.warning(self, APP_NAME, "Debe señalar al menos una semana."); return False
        def fn(arbol):
            cambio = False
            for x in raiz.iter("sesion"):
                if any(x is s.xml for s in sesiones):
                    r0, m0 = SEM.de_sesion(x, noms)
                    r1, m1 = (r if r is not None else r0), (m or m0)
                    if (r1, m1) != (r0, m0):
                        SEM.fijar_sesion(x, r1, m1, ED, arbol, noms); cambio = True
            return cambio
        return self.editar(fn, "Asignación semanal")
