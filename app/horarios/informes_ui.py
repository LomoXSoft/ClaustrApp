"""Diálogos de informes e impresión del Editor (textos del editor de referencia)."""
from __future__ import annotations
from .textos import TX
import copy, os
from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QLabel, QLineEdit,
                               QCheckBox, QPushButton, QDialogButtonBox, QComboBox, QSpinBox, QFileDialog,
                               QMessageBox, QRadioButton, QColorDialog, QPlainTextEdit, QFormLayout, QWidget)
from PySide6.QtPrintSupport import QPrinter, QPrintPreviewDialog, QPrintDialog, QPageSetupDialog
from . import informes as I, VENDOR, AJUSTES
from .formrc import PaginaRC, fuente_dialogo, px

PROX = "Próximamente"
IDENT = [TX("codigo"), "Nombre completo"]


def _prox(w):
    w.setEnabled(False); w.setToolTip(PROX)


def ajustes_por_defecto():
    s = QSettings(VENDOR, AJUSTES)
    import json
    try:
        return json.loads(s.value("informes/opciones", "{}") or "{}")
    except ValueError:
        return {}


def guardar_por_defecto(o):
    import json
    QSettings(VENDOR, AJUSTES).setValue("informes/opciones", json.dumps(o, ensure_ascii=False))


def opciones_editor(ed):
    return I.opciones(ed.doc, ajustes_por_defecto())


def fijar_opciones(ed, o, texto="opciones de presentación"):
    nuevo = ed._instantanea(); nuevo["editor"]["informes"] = copy.deepcopy(o); ed._confirmar(nuevo, texto)


class _RC(QDialog):
    RID = ""; OCULTAR = (1376, 1377, 1395)

    def __init__(self, parent, titulo=None):
        super().__init__(parent)
        viejo = getattr(PaginaRC, "OCULTAR", set()); PaginaRC.OCULTAR = set(self.OCULTAR)
        try:
            self.pg = PaginaRC(self.RID, self)
        finally:
            PaginaRC.OCULTAR = viejo
        self.setFixedSize(self.pg.size()); self.setFont(fuente_dialogo()); self.setWindowTitle(titulo or self.pg.titulo); self.c = self.pg.c
        if 57670 in self.c:
            self.c[57670].clicked.connect(lambda: QMessageBox.information(self, self.windowTitle(), f"La ayuda: {PROX.lower()}."))
        if 1 in self.c:
            self.c[1].clicked.connect(self.accept)
        if 2 in self.c:
            self.c[2].clicked.connect(self.reject)


class _OpcionesBase(_RC):
    """Vincula los controles comunes de los diálogos 429 y 690 con el diccionario de opciones."""
    CHECKS = {1100: "lista_asignaciones", 1409: "contadores", 1126: "ocultar_profesor", 1091: "ocultar_aula",
              1095: "ocultar_materia", 1171: "centrar", 1092: "colorear", 1410: "letreros_recreo", 1118: "prohibiciones",
              1411: "depto", 1099: "cab_usuario", 1093: "cab_localidad", 1152: "cab_titulo", 1170: "cab_semana",
              1153: "pie_fecha", 1154: "pie_pagina", 1155: "pie_marca", 1096: "mostrar_texto_pie"}
    IDENTS = {1004: "materias", 1007: "alumnos", 1008: "profesores", 1009: "aulas"}

    def __init__(self, parent, o, titulo=None):
        super().__init__(parent, titulo)
        self.o = copy.deepcopy(o)
        for cid, k in self.CHECKS.items():
            if cid in self.c:
                self.c[cid].setChecked(bool(self.o.get(k)))
        for cid, k in self.IDENTS.items():
            if cid in self.c:
                self.c[cid].addItems(IDENT); self.c[cid].setCurrentText(self.o["ident"].get(k, IDENT[0]))
        if 1000 in self.c:
            w = self.c[1000]
            (w.setValue if isinstance(w, QSpinBox) else lambda v: w.setText(str(v)))(int(self.o.get("desdobles", 3)))
        (self.c[1014] if self.o.get("solo_ocupada", True) else self.c[1094]).setChecked(True)
        {"tabla": self.c[1110], "regleta": self.c[1083], "celda": self.c[1227]}.get(self.o.get("horas"), self.c[1083]).setChecked(True)
        {"pequeno": self.c[1045], "normal": self.c[1042], "grande": self.c[1043]}.get(self.o.get("tam"), self.c[1042]).setChecked(True)
        (self.c[1241] if self.o.get("fuente") == "Century Gothic" else self.c[1128]).setChecked(True)
        self.pg.regrupar([1110, 1083, 1227], [1045, 1042, 1043], [1128, 1241], [1014, 1094])
        self.c[1118].setToolTip("Sombrea en los horarios de profesores las horas prohibidas y las preferencias de su plantilla")
        if 1147 in self.c:
            self.c[1147].setText(self.o.get("logo", "")); self.c[1147].setReadOnly(True)
            self.c[1059].clicked.connect(self._logo); self.c[1060].clicked.connect(lambda: self.c[1147].setText(""))
        self.c[1067].clicked.connect(self._texto_pie)
        self._rotulo_pie()
        if 1395 in self.c:
            self.c[1395].setText("")
        if 1533 in self.c:
            self.c[1533].hide()

    def _logo(self):
        r, _ = QFileDialog.getOpenFileName(self, "Escudo o logotipo del centro", "", "Imágenes (*.png *.jpg *.jpeg *.bmp)")
        if r:
            self.c[1147].setText(r)

    def _texto_pie(self):
        d = DialogoTextoPie(self, self.o.get("texto_pie", ""))
        if d.exec():
            self.o["texto_pie"] = d.texto(); self._rotulo_pie(); self.c[1096].setChecked(bool(self.o["texto_pie"]))

    def _rotulo_pie(self):
        t = (self.o.get("texto_pie") or "").replace("\n", " ")
        lb = self.c[1500]; lb.setText(t[:14])   # el recurso ya pone «...» detrás
        lb.setToolTip(t); lb.setStyleSheet("color:#555;")

    def opciones(self):
        o = self.o
        for cid, k in self.CHECKS.items():
            if cid in self.c:
                o[k] = self.c[cid].isChecked()
        for cid, k in self.IDENTS.items():
            if cid in self.c:
                o["ident"][k] = self.c[cid].currentText()
        if 1000 in self.c:
            w = self.c[1000]
            try:
                o["desdobles"] = w.value() if isinstance(w, QSpinBox) else int(w.text() or "3")
            except ValueError:
                pass
        o["solo_ocupada"] = self.c[1014].isChecked()
        o["horas"] = "tabla" if self.c[1110].isChecked() else ("celda" if self.c[1227].isChecked() else "regleta")
        o["tam"] = "pequeno" if self.c[1045].isChecked() else ("grande" if self.c[1043].isChecked() else "normal")
        o["fuente"] = "Century Gothic" if self.c[1241].isChecked() else "Nimbus Sans"
        if 1147 in self.c:
            o["logo"] = self.c[1147].text()
        return o

    def permanente(self):
        return 1111 in self.c and self.c[1111].isChecked()


class DialogoListadoPDF(_OpcionesBase):
    """Diálogo 429 «Horario completo en PDF - Opciones» (horario completo en PDF)."""
    RID = "E429"
    TIPO_RADIO = {1003: "alumnos", 1005: "profesores", 1006: "aulas", 1017: "guardias", 1018: "reuniones",
                  1086: "recreo", 1089: "prof_libres", 1088: "aulas_libres"}

    def __init__(self, parent, o):
        super().__init__(parent, o)
        # Materias (no figura en el recurso): radio propio bajo «Aulas libres»
        self.rb_mat = QRadioButton("Materias", self.pg); self.rb_mat.setGeometry(px(199, 118, 60, 8)); self.rb_mat.setFont(self.c[1088].font())
        self.c[9001] = self.rb_mat
        self.pg.regrupar(list(self.TIPO_RADIO) + [9001])
        tipo = self.o.get("tipo", "alumnos")
        for cid, t in self.TIPO_RADIO.items():
            self.c[cid].setChecked(t == tipo)
        self.rb_mat.setChecked(tipo == "materias")
        self.pg.regrupar([1013, 1015, 1113])
        {"distintos": self.c[1013], "completo": self.c[1113]}.get(self.o.get("presentacion"), self.c[1015]).setChecked(True)
        self.c[1016].setChecked(bool(self.o.get("varias_por_pagina")))
        self.c[1113].setToolTip("Una sola tabla: una fila por grupo, profesor o aula y una columna por día y periodo")

    def opciones(self):
        o = super().opciones()
        o["tipo"] = next((t for cid, t in self.TIPO_RADIO.items() if self.c[cid].isChecked()), "materias" if self.rb_mat.isChecked() else "alumnos")
        o["presentacion"] = "distintos" if self.c[1013].isChecked() else ("completo" if self.c[1113].isChecked() else "uno")
        o["varias_por_pagina"] = self.c[1016].isChecked()
        return o


class DialogoTablaPDF(_OpcionesBase):
    """Diálogo 690 «Presentación de la tabla actual en PDF»."""
    RID = "E690"

    def __init__(self, parent, o):
        super().__init__(parent, o, TX("tabla_ahora_pdf_parte_opciones"))


class DialogoTextoPie(_RC):
    RID = "E752"

    def __init__(self, parent, texto=""):
        super().__init__(parent)
        w = self.c[1010]
        if isinstance(w, QLineEdit):    # el recurso es un EDIT multilínea
            g = w.geometry(); w.hide(); self.ed = QPlainTextEdit(self.pg); self.ed.setGeometry(g); self.ed.show()
        else:
            self.ed = w
        self.ed.setPlainText(texto)

    def texto(self):
        return self.ed.toPlainText().strip()


class DialogoImprimirListado(_RC):
    """Diálogo 139 «Imprimir horarios»."""
    RID = "E139"
    OPCIONES = [("alumnos", "Grupos de alumnos"), ("profesores", "Profesores"), ("individual", "Horario individual del profesor"),
                ("aulas", "Aulas"), ("materias", "Materias"), ("guardias", "Guardias"), ("recreo", "Guardias de recreo"),
                ("reuniones", "Reuniones"), ("prof_libres", "Profesores libres"), ("aulas_libres", "Aulas libres")] + \
               [(k, v) for k, v in I.LISTADOS.items()]

    def __init__(self, ventana, o):
        super().__init__(ventana)
        self.v, self.o = ventana, copy.deepcopy(o)
        self.c[1013].setChecked(True); self.c[1001].setChecked(True); self.c[1005].setChecked(True); self.c[1100].setChecked(True)
        _prox(self.c[1003])
        for k, t in self.OPCIONES:
            self.c[1004].addItem(t, k)
        self.c[1004].currentIndexChanged.connect(self._tipo)
        self.c[1045].toggled.connect(self._modo)
        self.c[57606].clicked.connect(lambda: self.v.configurar_impresora())
        self.c[32793].clicked.connect(lambda: self.v.configurar_pagina())
        self.c[32778].clicked.connect(self._cab)
        self.c[32818].clicked.connect(self._letreros)
        self.c[1].setText("Imprimir")
        self.b_prev = QPushButton(TX("vista_previa"), self.pg); g = self.c[1].geometry()
        self.b_prev.setGeometry(g.x(), g.y() + 3 * g.height() + 6, g.width(), g.height()); self.b_prev.hide()
        self._tipo(); self._modo()

    def _cab(self):
        d = DialogoCabeceras(self, self.o)
        if d.exec():
            self.o = d.opciones()

    def _letreros(self):
        d = DialogoLetreros(self, self.o)
        if d.exec():
            self.o = d.opciones()

    def _modo(self, *_):
        lst = self.c[1045].isChecked()
        for cid in (1001, 1004, 1005, 1015, 1002, 1007, 1008, 1009, 1100, 1101):
            self.c[cid].setEnabled(lst)

    def _tipo(self, *_):
        k = self.tipo(); ed = self.v.ed
        vista = {"alumnos": "Grupos", "profesores": "Profesorado", "individual": "Profesorado", "aulas": "Aulas",
                 "guardias": "Guardias", "recreo": "Guardias", "reuniones": "Reuniones"}.get(k)
        if k == "materias":
            els = [e.nombre for e in ed.p.materias]
        else:
            els = ed.elementos(vista) if vista else []
        for cid in (1007, 1008):
            self.c[cid].clear(); self.c[cid].addItems(els)
        if els:
            self.c[1008].setCurrentIndex(len(els) - 1)
        prof = vista == "Profesorado"
        self.c[1009].clear()
        if prof:
            self.c[1009].addItems(sorted({e.datos.get("departamento") or "" for e in ed.p.profesores} - {""}))
        self.c[1002].setEnabled(prof)
        for cid in (1100, 1101):
            self.c[cid].setEnabled(prof and self.c[1045].isChecked())
        for cid in (1015, 1007, 1008):
            self.c[cid].setEnabled(bool(els))

    def tipo(self):
        return self.c[1004].currentData()

    def nombres(self):
        k = self.tipo(); ed = self.v.ed
        if self.c[1015].isChecked() and self.c[1007].count():
            a, b = sorted((self.c[1007].currentIndex(), self.c[1008].currentIndex()))
            return [self.c[1007].itemText(i) for i in range(a, b + 1)]
        if self.c[1002].isChecked() and self.c[1002].isEnabled():
            dep = self.c[1009].currentText()
            return [e.nombre for e in ed.p.profesores if (e.datos.get("departamento") or "") == dep]
        if k in ("profesores", "individual") and self.c[1101].isChecked():
            return [e.nombre for e in sorted(ed.p.profesores, key=lambda e: e.datos.get("nombreCompleto") or e.nombre)]
        return None

    def tablas(self):
        if self.c[1013].isChecked():
            return self.v.tablas_actuales(self.o)
        return I.tablas_de(self.v.ed, self.tipo(), self.o, self.nombres())


class DialogoCabeceras(QDialog):
    """Cabeceras y pies (nombre del centro, localidad, curso y elementos del pie)."""
    def __init__(self, parent, o):
        super().__init__(parent)
        self.o = copy.deepcopy(o); self.setWindowTitle(TX("cabeceras_pies")); self.setFont(fuente_dialogo())
        L = QVBoxLayout(self); f = QFormLayout(); L.addLayout(f)
        self.e_centro = QLineEdit(self.o.get("centro", "")); self.e_loc = QLineEdit(self.o.get("localidad", ""))
        self.e_curso = QLineEdit(self.o.get("curso", ""))
        f.addRow("Nombre del centro:", self.e_centro); f.addRow("Localidad:", self.e_loc); f.addRow("Curso escolar:", self.e_curso)
        h = QHBoxLayout(); L.addLayout(h)
        g1 = QGroupBox(TX("cabecera")); v1 = QVBoxLayout(g1); g2 = QGroupBox(TX("pie")); v2 = QVBoxLayout(g2)
        self.cb = {}
        for k, t, v in (("cab_usuario", "Nombre del centro", v1), ("cab_localidad", "Localidad", v1), ("cab_titulo", "Título de la tabla", v1),
                        ("cab_semana", "Semana del horario", v1), ("pie_fecha", "Fecha y hora", v2), ("pie_pagina", "Número de página", v2),
                        ("pie_marca", TX("nombre_programa"), v2), ("mostrar_texto_pie", TX("texto_bajo_cada_tabla_2"), v2)):
            c = QCheckBox(t); c.setChecked(bool(self.o.get(k))); v.addWidget(c); self.cb[k] = c
        h.addWidget(g1); h.addWidget(g2)
        L.addWidget(QLabel(TX("texto_bajo_cada_tabla"))); self.e_pie = QPlainTextEdit(self.o.get("texto_pie", "")); self.e_pie.setFixedHeight(60)
        L.addWidget(self.e_pie)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Aceptar"); bb.button(QDialogButtonBox.Cancel).setText("Cancelar")
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject); L.addWidget(bb)

    def opciones(self):
        o = self.o
        o["centro"], o["localidad"], o["curso"] = self.e_centro.text().strip(), self.e_loc.text().strip(), self.e_curso.text().strip()
        for k, c in self.cb.items():
            o[k] = c.isChecked()
        o["texto_pie"] = self.e_pie.toPlainText().strip()
        return o


class _Muestra(QWidget):
    def __init__(self, dlg):
        super().__init__(); self.dlg = dlg; self.setMinimumSize(260, 120)

    def paintEvent(self, ev):
        o = self.dlg.opciones(); p = QPainter(self); r = self.rect().adjusted(4, 4, -4, -4)
        p.fillRect(r, QColor(o["color_fondo"])); dias = o["letreros"]["dias"][:3]
        cw = (r.width() - 40) / 3; rh = (r.height() - 20) / 3
        p.setPen(QColor("#155e5e"))
        for i, d in enumerate(dias):
            p.drawText(int(r.x() + 40 + i * cw), r.y(), int(cw), 18, Qt.AlignCenter, d)
        filas = ["08:30", o["letreros"]["recreo"], "09:25"]
        for j, t in enumerate(filas):
            y = r.y() + 20 + j * rh
            if j == 1:
                p.fillRect(int(r.x() + 40), int(y), int(3 * cw), int(rh), QColor("#eaf6f6"))
            p.setPen(QColor(o["color_texto"])); p.drawText(int(r.x()), int(y), 38, int(rh), Qt.AlignRight | Qt.AlignVCenter, t if j != 1 else "")
            if j == 1 and o.get("letreros_recreo", True):
                p.drawText(int(r.x() + 40), int(y), int(3 * cw), int(rh), Qt.AlignCenter, t)
        p.setPen(QColor(o["color_lineas"]))
        if o["lineas_h"]:
            for j in range(4):
                y = r.y() + 20 + j * rh; p.drawLine(int(r.x() + 40), int(y), r.right(), int(y))
        if o["lineas_v"]:
            for i in range(4):
                x = r.x() + 40 + i * cw; p.drawLine(int(x), r.y() + 20, int(x), r.bottom())
        p.end()


class DialogoLetreros(QDialog):
    """«Letreros y configuración»: letreros de las tablas, líneas, colores y vista previa."""
    CLAVES = [("dias", i, d) for i, d in enumerate(I.DIAS5[:5])] + [(k, None, t) for k, t in (
        ("recreo", "Recreo"), ("mediodia", "Mediodía"), ("profesor", "Profesor"), ("aula", "Aula"), ("materia", "Materia"),
        ("grupo", "Grupo"), ("guardia", "Guardia"), ("reunion", "Reunión"))]

    def __init__(self, parent, o):
        super().__init__(parent)
        self.o = copy.deepcopy(o); self.setWindowTitle("Letreros y configuración"); self.setFont(fuente_dialogo())
        L = QHBoxLayout(self); izq = QVBoxLayout(); L.addLayout(izq); der = QVBoxLayout(); L.addLayout(der)
        g = QGroupBox("Cambiar letreros en tablas"); f = QFormLayout(g); izq.addWidget(g); self.ed = {}
        for k, i, t in self.CLAVES:
            v = self.o["letreros"][k][i] if i is not None else self.o["letreros"].get(k, t)
            e = QLineEdit(v); e.textChanged.connect(lambda *_: self.muestra.update()); f.addRow(t + ":", e); self.ed[(k, i)] = e
        g2 = QGroupBox("Opciones"); v2 = QVBoxLayout(g2); izq.addWidget(g2)
        self.cb_v = QCheckBox("Líneas Verticales"); self.cb_h = QCheckBox("Líneas Horizontales")
        self.cb_v.setChecked(self.o["lineas_v"]); self.cb_h.setChecked(self.o["lineas_h"])
        self.cb_rec = QCheckBox(TX("rotulos_recreo_mediodia")); self.cb_rec.setChecked(self.o.get("letreros_recreo", True))
        for c in (self.cb_v, self.cb_h, self.cb_rec):
            c.toggled.connect(lambda *_: self.muestra.update()); v2.addWidget(c)
        self.cb_extra = {}
        for k, t in (("botones_3d", "Botones 3D"), ("senala_fila", "Señala Fila actual"), ("senala_columna", "Señala Columna actual")):
            c = QCheckBox(t); c.setChecked(bool(self.o.get(k))); c.toggled.connect(lambda *_: self.muestra.update())
            v2.addWidget(c); self.cb_extra[k] = c
        g3 = QGroupBox("Color de las líneas"); v3 = QGridLayout(g3); der.addWidget(g3); self.colores = {}
        for n, (k, t) in enumerate((("color_lineas", "Grid"), ("color_texto", "Text"), ("color_fondo", "Background"))):
            b = QPushButton(); b.setFixedWidth(60); self._pinta(b, self.o[k]); b.clicked.connect(lambda _=False, k=k, b=b: self._color(k, b))
            v3.addWidget(QLabel(t), n, 0); v3.addWidget(b, n, 1); self.colores[k] = b
        for n, (k, t) in enumerate((("color_track_linea", "Tracking Line"), ("color_track_texto", "Tracking Text")), 3):
            b = QPushButton(); b.setFixedWidth(60); self._pinta(b, self.o.get(k) or I.OPC_DEF[k])
            b.clicked.connect(lambda _=False, k=k, b=b: self._color(k, b))
            v3.addWidget(QLabel(t), n, 0); v3.addWidget(b, n, 1); self.colores[k] = b
        gp = QGroupBox("Vista previa"); vp = QVBoxLayout(gp); self.muestra = _Muestra(self); vp.addWidget(self.muestra); der.addWidget(gp)
        der.addStretch()
        self.b_def = QPushButton("Todas de defecto"); self.b_def.clicked.connect(self.por_defecto); der.addWidget(self.b_def)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Aceptar"); bb.button(QDialogButtonBox.Cancel).setText("Cancelar")
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject); der.addWidget(bb)

    def por_defecto(self):
        """Recupera todos los letreros, líneas y colores iniciales."""
        D = I.OPC_DEF
        for (k, i), e in self.ed.items():
            e.setText(D["letreros"][k][i] if i is not None else D["letreros"].get(k, ""))
        self.cb_v.setChecked(D["lineas_v"]); self.cb_h.setChecked(D["lineas_h"]); self.cb_rec.setChecked(D["letreros_recreo"])
        for k, c in self.cb_extra.items():
            c.setChecked(D[k])
        for k, b in self.colores.items():
            self._pinta(b, D[k])
        self.muestra.update()

    def _pinta(self, b, c):
        b.setStyleSheet(f"background:{c}; border:1px solid #777;"); b.setProperty("color", c)

    def _color(self, k, b):
        c = QColorDialog.getColor(QColor(b.property("color")), self)
        if c.isValid():
            self._pinta(b, c.name()); self.muestra.update()

    def opciones(self):
        o = self.o
        dias = list(o["letreros"]["dias"])
        for (k, i), e in self.ed.items():
            if i is not None:
                dias[i] = e.text().strip() or I.DIAS5[i]
            else:
                o["letreros"][k] = e.text().strip()
        o["letreros"]["dias"] = dias
        o["lineas_v"], o["lineas_h"], o["letreros_recreo"] = self.cb_v.isChecked(), self.cb_h.isChecked(), self.cb_rec.isChecked()
        for k, b in self.colores.items():
            o[k] = b.property("color")
        for k, c in self.cb_extra.items():
            o[k] = c.isChecked()
        return o


class DialogoIdiomaLetreros(_RC):
    """Diálogo 784: modificar letreros o volver a los iniciales (solo castellano por ahora)."""
    RID = "E784"

    def __init__(self, parent):
        super().__init__(parent)
        self.c[1013].setChecked(True); self.c[1001].setChecked(True)
        self.pg.regrupar([1013, 1043])
        from .formrc import ajustar
        tope = self.c[1].x() - 6
        for cid in (1013, 1043):   # no deben quedar bajo los botones
            r = self.c[cid]; r.setFixedWidth(tope - r.x()); ajustar(r)
        for cid in (1015, 1002, 1003, 1017, 1005, 1006, 1042):
            _prox(self.c[cid])


def vista_previa(parent, tablas, opc, impresora=None):
    """Vista previa (A4 apaisado) con Imprimir, páginas, acercar/alejar."""
    pr = impresora or QPrinter(QPrinter.HighResolution)
    if impresora is None:
        I.configurar_pagina(pr)
    dlg = QPrintPreviewDialog(pr, parent); dlg.setWindowTitle(TX("vista_previa"))
    dlg.paintRequested.connect(lambda printer: I.Pintor(opc).render(printer, tablas))
    dlg.resize(1100, 780)
    return dlg
