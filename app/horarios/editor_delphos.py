"""Asistente «Pasar el horario a > Otros programas» del editor, para DELPHOS (exportación
sincronizada). Pasos del editor de referencia: 211 (1/7) -> 749 (2/7, semáforo de claves) -> 144 (claves de los
periodos y guardias de recreo) -> 425 (profesores) -> 689 (mensajes de precaución) -> 361 (claves de los días) ->
205 (fechas del curso, 7/7). El archivo de salida sigue la hipótesis de delphos_salida (SIN CONFIRMAR)."""
from __future__ import annotations
from .textos import TX
import os, re
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import (QDialog, QMessageBox, QTreeWidgetItem, QTabBar, QLabel, QFileDialog, QInputDialog)
from .formrc import PaginaRC, fuente_dialogo, px
from . import delphos as DL, delphos_salida as DS

from . import APP_NAME
APP_ED = f"{APP_NAME} - Editor"
COLOR = {DS.VERDE: "#1e8c2e", DS.AMBAR: "#c98a00", DS.ROJO: "#c62828"}
TXT = {DS.VERDE: "Luz verde", DS.AMBAR: "Precaución", DS.ROJO: "Errores"}
GESTOR_DELPHOS = 1086


def _no_modal(w):
    p = w
    while p is not None and not hasattr(p, "_no_modal"):
        p = p.parent()
    return bool(getattr(p, "_no_modal", False))


def semaforo(lbl: QLabel, sem):
    lbl.setText(f"● {TXT[sem]}"); lbl.setStyleSheet(f"color:{COLOR[sem]}; font-weight:bold;")
    lbl.setToolTip(DS.SIN_CONFIRMAR)


class Paso(QDialog):
    RID = ""

    def __init__(self, asis, titulo=None):
        super().__init__(asis.parent)
        self.a = asis
        self.pg = PaginaRC(self.RID, self); self.setFixedSize(self.pg.size()); self.setFont(fuente_dialogo())
        self.setWindowTitle(titulo or self.pg.titulo); self.c = self.pg.c
        if 1 in self.c:
            self.c[1].clicked.connect(self.continuar)
        if 2 in self.c:
            self.c[2].clicked.connect(self.reject)
        if 57670 in self.c:
            self.c[57670].clicked.connect(lambda: QMessageBox.information(self, APP_ED, "La ayuda: próximamente."))

    def continuar(self):
        if self.validar():
            self.accept()

    def validar(self):
        return True

    def info(self, t):
        QMessageBox.information(self, self.windowTitle(), t)


class Paso1(Paso):
    """211: gestor (solo DELPHOS disponible), archivo, identificativo/clave externa, el botón de completar datos o
    cargar códigos (carga el catálogo desde un archivo de DELPHOS)."""
    RID = "E211"

    def __init__(self, asis):
        super().__init__(asis)
        self.radios = {cid: w for cid, w in self.c.items() if w.metaObject().className() == "QRadioButton"
                       and cid not in (1005, 1006)}
        self.pg.regrupar(list(self.radios), [1005, 1006])
        for cid, w in self.radios.items():
            if cid != GESTOR_DELPHOS:
                w.setEnabled(False); w.setToolTip("Próximamente")
        self.c[GESTOR_DELPHOS].setChecked(True)
        self.c[1006 if asis.op.usar_clave else 1005].setChecked(True)
        self.c[1010].setText(asis.ruta)
        self.c[1398].clicked.connect(self.cambiar_ruta)
        self.c[1144].clicked.connect(lambda: asis.cargar_catalogo(self))
        if 1017 in self.c:
            self.c[1017].setChecked(asis.op.subgrupos_con_grupo)
        for k in (1395, 1539):
            if k in self.c:
                self.c[k].setText("")
        self.c[1539].setText(f"{len(asis.catalogo_total())} claves")

    def cambiar_ruta(self):
        r, _ = QFileDialog.getSaveFileName(self, "Archivo de intercambio", self.c[1010].text(), "XML (*.xml)")
        if r:
            self.c[1010].setText(r)

    def validar(self):
        if not self.c[1010].text().strip():
            self.info("Indique el nombre y la ruta del archivo de intercambio."); return False
        self.a.ruta = self.c[1010].text().strip()
        self.a.op.usar_clave = self.c[1006].isChecked()
        self.a.op.subgrupos_con_grupo = self.c[1017].isChecked() if 1017 in self.c else False
        return True


class Paso2(Paso):
    """749: cotejar las claves con un archivo de DELPHOS (semáforo) o continuar sin la comprobación."""
    RID = "E749"

    def __init__(self, asis):
        super().__init__(asis)
        try:
            self.c[1].clicked.disconnect()
            self.c[2].clicked.disconnect()
        except (RuntimeError, TypeError):
            pass
        self.c[1].clicked.connect(self.cargar); self.c[2].clicked.connect(self.accept)
        self.actualizar()

    def actualizar(self):
        semaforo(self.c[1494], self.a.tr.comprobar(self.a.op)[0] if self.a.tr.catalogo else DS.AMBAR)
        if not self.a.tr.catalogo:
            self.c[1494].setText("● Sin comprobar")

    def cargar(self):
        if self.a.cargar_catalogo(self):
            self.actualizar()
            if not _no_modal(self):
                self.accept()


class Paso3(Paso):
    """144: claves de los periodos (por marco y día) y guardias de recreo."""
    RID = "E144"

    def __init__(self, asis):
        super().__init__(asis)
        self.c[1016].setChecked(asis.op.guardias_recreo); self.c[1017].setChecked(asis.op.tarea_del_servicio)
        self.c[1139].clicked.connect(lambda: asis.cargar_catalogo(self) and self.pintar())
        self.marcos = sorted(asis.ed.p.marcos)
        self.tm = QTabBar(self); self.tm.setGeometry(px(35, 84, 228, 18))
        for m in self.marcos:
            self.tm.addTab(f"Marco {m}")
        self.td = QTabBar(self); self.td.setGeometry(px(34, 100, 199, 16))
        for d in ("L", "M", "X", "J", "V"):
            self.td.addTab(d)
        self.res = QLabel(self); self.res.setGeometry(px(35, 117, 260, 26)); self.res.setWordWrap(True)
        self.tm.currentChanged.connect(lambda *_: self.pintar()); self.td.currentChanged.connect(lambda *_: self.pintar())
        self.pintar()

    def pintar(self):
        m = self.a.ed.p.marcos[self.marcos[max(0, self.tm.currentIndex())]]
        d = max(0, self.td.currentIndex())
        cat = {k for k, _ in self.a.tr.catalogo.get("tramos", [])}
        ts = [t for t in m.tramos if t.dia == d]
        self.res.setText("  ".join(f"{t.entrada[:5]}={t.clave or '?'}{'*' if cat and t.clave not in cat else ''}"
                                   + ("(R)" if t.tipo == "recreo" else "") for t in ts))
        mal = [t for t in m.tramos if not t.clave or (cat and t.clave not in cat)]
        semaforo(self.c[1494], DS.ROJO if any(not t.clave for t in mal) else DS.AMBAR if mal else DS.VERDE)

    def validar(self):
        self.a.op.guardias_recreo = self.c[1016].isChecked(); self.a.op.tarea_del_servicio = self.c[1017].isChecked()
        return True


class Paso4(Paso):
    """425: profesores cuyo horario se transfiere; «Cambiar el código» solo para esta transferencia."""
    RID = "E425"

    def __init__(self, asis):
        super().__init__(asis)
        self.l = self.c[1055]; self.l.setHeaderLabels(["Profesor", TX("codigo_2"), "Toma de posesión", "Tramos"])
        sel = asis.op.profesores
        for n, k, f, c in asis.tr.profesores(asis.op):
            it = QTreeWidgetItem([n, asis.claves_prof.get(n, k), f, str(c)])
            it.setCheckState(0, Qt.Checked if sel is None or n in sel else Qt.Unchecked); self.l.addTopLevelItem(it)
        for i in range(4):
            self.l.resizeColumnToContents(i)
        self.c[1068].clicked.connect(lambda: self.marcar(False)); self.c[1104].clicked.connect(lambda: self.marcar(True))
        self.c[1270].clicked.connect(self.modificar)

    def items(self):
        return [self.l.topLevelItem(i) for i in range(self.l.topLevelItemCount())]

    def marcar(self, v):
        for it in self.items():
            it.setCheckState(0, Qt.Checked if v else Qt.Unchecked)

    def modificar(self, valor=None):
        it = self.l.currentItem()
        if it is None:
            self.info("Seleccione un profesor."); return
        if valor is None:
            valor, ok = QInputDialog.getText(self, TX("cambiar_codigo"), it.text(0), text=it.text(1))
            if not ok:
                return
        it.setText(1, valor.strip()); self.a.claves_prof[it.text(0)] = valor.strip()

    def validar(self):
        sel = {it.text(0) for it in self.items() if it.checkState(0) == Qt.Checked}
        if not sel:
            self.info("Seleccione al menos un profesor."); return False
        self.a.op.profesores = None if len(sel) == len(self.items()) else sel
        return True


class Paso5(Paso):
    """689: mensajes de precaución con semáforo; no se puede continuar con mensajes en rojo."""
    RID = "E689"

    def __init__(self, asis):
        super().__init__(asis)
        self.l = self.c[1055]; self.l.setHeaderLabels(["", "Lista", "Elemento", "Mensaje"])
        self.c[1067].clicked.connect(self.modificar); self.l.itemDoubleClicked.connect(lambda *_: self.modificar())
        self.llenar()

    def llenar(self):
        self.sem, self.ms = self.a.comprobar()
        self.l.clear()
        for m in self.ms:
            it = QTreeWidgetItem(["●", m.lista, m.nombre, m.texto]); it.setForeground(0, QBrush(QColor(COLOR[m.nivel])))
            self.l.addTopLevelItem(it)
        for i in range(4):
            self.l.resizeColumnToContents(i)
        semaforo(self.c[1494], self.sem)

    def modificar(self, valor=None):
        it = self.l.currentItem()
        if it is None:
            self.info("Seleccione un mensaje."); return
        m = self.ms[self.l.indexOfTopLevelItem(it)]
        if m.lista == "profesores" and "clave" in m.texto:
            if valor is None:
                valor, ok = QInputDialog.getText(self, TX("codigo_externo"), m.nombre)
                if not ok:
                    return
            self.a.claves_prof[m.nombre] = valor.strip(); self.llenar()
        else:
            self.info("Corrija este dato en el planificador (propiedades del elemento) y vuelva a generar el horario "
                      "o recárguelo en el editor.")

    def validar(self):
        if self.sem == DS.ROJO:
            self.info("Hay mensajes en rojo: corríjalos antes de transferir el horario."); return False
        return True


class Paso6(Paso):
    """361: claves de los días."""
    RID = "E361"
    EDITS = (1000, 1018, 1021, 1041, 1019, 1020)

    def __init__(self, asis):
        super().__init__(asis)
        for d, cid in enumerate(self.EDITS):
            self.c[cid].setText(asis.op.dias.get(d) or asis.tr.dias_xml.get(d) or (str(d + 1) if d < 5 else ""))

    def validar(self):
        v = [self.c[cid].text().strip() for cid in self.EDITS[:5]]
        if len(set(v)) < 5 or "" in v:
            self.info("Las claves de lunes a viernes deben ser distintas y no vacías."); return False
        self.a.op.dias = {d: self.c[cid].text().strip() for d, cid in enumerate(self.EDITS) if self.c[cid].text().strip()}
        return True


class Paso7(Paso):
    """205: año de inicio del curso y fechas DD/MM/AAAA."""
    RID = "E205"

    def __init__(self, asis):
        super().__init__(asis)
        self.c[1011].setText(asis.op.anno); self.c[1115].setText(asis.op.inicio); self.c[1116].setText(asis.op.fin)

    def validar(self):
        a, i, f = (self.c[k].text().strip() for k in (1011, 1115, 1116))
        if not re.fullmatch(r"\d{4}", a):
            self.info("Indique el año de inicio del curso (AAAA)."); return False
        for x in (i, f):
            if x and not re.fullmatch(r"\d{2}/\d{2}/\d{4}", x):
                self.info("Formato de fecha DD/MM/AAAA."); return False
        self.a.op.anno, self.a.op.inicio, self.a.op.fin = a, i, f
        return True


PASOS = (Paso1, Paso2, Paso3, Paso4, Paso5, Paso6, Paso7)


class AsistenteDelphos:
    def __init__(self, parent, ed, catalogo=None):
        self.parent, self.ed = parent, ed
        self.tr = DS.Transferencia(ed, catalogo)
        self.op = DS.Opciones()
        self.claves_prof = {}
        self.ruta = os.path.join(os.path.dirname(os.path.abspath(ed.ruta)), "Horario.xml")
        self.dialogos = []

    def catalogo_total(self):
        return [k for v in self.tr.catalogo.values() for k in v]

    def cargar_catalogo(self, dlg, ruta=None):
        if ruta is None:
            ruta, _ = QFileDialog.getOpenFileName(dlg, "Archivo de DELPHOS con las claves", "", "XML (*.xml)")
            if not ruta:
                return False
        inc = DL.Incidencias()
        try:
            datos = DL.leer(ruta, inc)
        except (DL.ErrorDelphos, OSError) as e:
            QMessageBox.warning(dlg, dlg.windowTitle(), f"No se puede leer el archivo:\n{e}"); return False
        self.tr.catalogo = DL.catalogo(datos if datos["variante"] != "KRONOWIN" else None,
                                       datos if datos["variante"] == "KRONOWIN" else None)
        return True

    def comprobar(self):
        """Semáforo con las claves modificadas en esta transferencia (425/689)."""
        self._aplicar_claves()
        try:
            return self.tr.comprobar(self.op)
        finally:
            self._quitar_claves()

    def _aplicar_claves(self):
        self._guardadas = {}
        for n, k in self.claves_prof.items():
            x = self.tr.x["profesores"].get(n)
            if x is None:
                continue
            e = x.find("claveDeExportacion")
            self._guardadas[n] = None if e is None else e.text
            if e is None:
                from xml.etree.ElementTree import SubElement
                e = SubElement(x, "claveDeExportacion")
            e.text = k

    def _quitar_claves(self):
        for n, v in self._guardadas.items():
            x = self.tr.x["profesores"][n]; e = x.find("claveDeExportacion")
            if v is None:
                x.remove(e)
            else:
                e.text = v

    def ejecutar(self, operar=None):
        """Recorre los 7 pasos. operar(i, dlg) permite a las pruebas manipular cada paso (sin modales).
        Devuelve la ruta escrita o None."""
        for i, P in enumerate(PASOS):
            d = P(self); self.dialogos.append(d)
            if operar is not None:
                operar(i, d)
                if not d.validar():
                    return None
            elif d.exec() != QDialog.Accepted:
                return None
        self._aplicar_claves()
        try:
            self.tr.exportar(self.ruta, self.op)
        finally:
            self._quitar_claves()
        if operar is None:
            QMessageBox.information(self.parent, APP_ED, f"Horario transferido a {self.ruta}.\n\n{DS.SIN_CONFIRMAR} "
                                    "Compruebe la importación en DELPHOS.")
        return self.ruta
