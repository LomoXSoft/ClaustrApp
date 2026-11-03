"""Propiedades de las listas no lectivas: tipos de tarea, reuniones, guardias, integrantes de guardia y
otras actividades complementarias. Los diálogos se dibujan con la descripción del planificador de referencia (PaginaRC):
#251 Tipo de tarea, #198 Reunión, #199 Guardia, #200 Nº de guardias del profesor en el servicio,
#253 Más actividades complementarias, #621/#686 creación de reuniones. «Guardias hora a hora»
(#227) no tiene controles en la descripción: la rejilla se construye aquí.
"""
from __future__ import annotations
from .textos import TX
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget,
                               QListWidgetItem, QComboBox, QTableWidget, QSpinBox, QHeaderView, QMessageBox,
                               QDialogButtonBox, QRadioButton, QButtonGroup)
from . import edicion as ED, modelo as M, nolectivas as NL
from .formrc import PaginaRC, fuente_dialogo, NO_PERSISTIDO
from .propiedades import (VentanaSimple, Texto, Casilla, Radios, Numero, no_persistir, solo_lectura,
                          _cargar_combo, _con_nombre_largo, NO_PERSISTIDOS)

DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
MARCO_IDS = (1181, 1182, 1183, 1184)


def es_integrante(obj) -> bool:
    return isinstance(obj, M.Elemento) and obj.datos.get("_tipo") == "integrante"


def integrantes_de_guardias(p) -> list:
    """Filas hijas (integrante de un servicio de guardia) en el orden de la lista."""
    from .listas import filas_integrantes
    return [h for g in p.guardias for h in filas_integrantes(p, g, "guardias")]


class _Marcos:
    """Radios «Marco horario asignado» enlazados al atributo subMarco."""

    def preparar_marcos(self):
        c = self.p.c; marcos = list(self.win.proyecto.marcos.values())
        self.radios_marco = {}
        for k, rid in enumerate(MARCO_IDS):
            if rid not in c:
                continue
            if k < len(marcos):
                c[rid].setText(marcos[k].nombre or f"Marco {marcos[k].id}"); self.radios_marco[c[rid]] = marcos[k].id
            else:
                c[rid].setVisible(False)
        visible = len(marcos) > 1
        if 1179 in c:
            c[1179].setVisible(visible)
        for rb in self.radios_marco:
            rb.setVisible(visible)
        for cid in (1404, 1397, 1403):        # «En semanas»: horarios de varias semanas, no vistos en los ejemplos
            if cid in c:
                c[cid].setVisible(False)

    def cargar_marcos(self):
        self.marco0 = self.elemento_xml().get("subMarco")
        for rb, m in self.radios_marco.items():
            rb.setChecked(m == self.marco0)

    def guardar_marco(self, x):
        nuevo = next((m for rb, m in self.radios_marco.items() if rb.isChecked()), self.marco0)
        if self.marco0 is not None and nuevo != self.marco0:
            x.set("subMarco", nuevo); return True
        return False


class _BaseNL(VentanaSimple, _Marcos):
    def lista_fresca(self):
        return getattr(self.win.proyecto, self.LISTA)

    def aplicar(self):
        x = self.elemento_xml()

        def hacer(arbol):
            ch = [en.guardar(arbol, x) for en in self.enlaces]
            ch.append(self.guardar_marco(x) if hasattr(self, "radios_marco") else False)
            ch.append(self.aplicar_extra(arbol, x))
            return any(ch)
        self.win.editar(hacer, self.windowTitle(), refrescar=False)

    def aplicar_extra(self, arbol, x):
        return False

    def cargar(self):
        super().cargar()
        if hasattr(self, "radios_marco"):
            self.cargar_marcos()

    def mover(self, d):
        self.aplicar()
        self.elementos = self.lista_fresca()
        self.indice = max(0, min(len(self.elementos) - 1, self.indice + d)); self.cargar()

    def reabrir_tras_editar(self):
        """Tras una edición inmediata (añadir profesores...) el modelo se reconstruye: tomar el objeto nuevo."""
        self.elementos = self.lista_fresca(); self.indice = min(self.indice, len(self.elementos) - 1); self.cargar()


# ---------------------------------------------------------------- tipo de tarea
class PropiedadesTarea(_BaseNL):
    RID = "251"; LISTA = "tareas"

    def preparar(self, raiz):
        c = self.p.c
        self.enlazar(Texto(c[1010], "nombre", renombrar_lista="tareas"))
        self.enlazar(Texto(c[1061], "nombreCompleto"))
        c[1071].setEditable(True); self.enlazar(Texto(c[1071], "claveDeExportacion"))
        no_persistir(self.p, self.V, 1074, 1075, 1076, 1077, 1078, 1055)
        solo_lectura(self.p, 1059)

    def calcular(self):
        p = self.win.proyecto; t = self.elementos[self.indice].nombre
        n = sum(s.duracion for s in p.sesiones if s.tarea == t)
        n += sum(int(e.datos.get("numeroDeReuniones") or 1) * (2 if e.datos.get("dobleDuracion") == "true" else 1)
                 * len(NL.integrantes(e.datos["_xml"])) for e in p.reuniones if e.datos.get("tipoDeTarea") == t)
        n += sum(int((ix.findtext("numeroDeGuardias") or "0").strip() or 0)
                 for e in p.guardias if e.datos.get("tipoDeTarea") == t
                 for ix in e.datos["_xml"].iter("integrante"))
        n += sum(int(e.datos.get("intervalosSemanales") or 0) for e in p.complementarias if e.datos.get("tarea") == t)
        self.p.c[1059].setText(f"{n:g}")


# ---------------------------------------------------------------- reunión
class PropiedadesReunion(_BaseNL):
    RID = "198"; LISTA = "reuniones"

    def preparar(self, raiz):
        c = self.p.c
        self.enlazar(Texto(c[1010], "nombre"))
        _cargar_combo(c[1197], _con_nombre_largo(raiz, "tareas")); self.enlazar(Texto(c[1197], "tipoDeTarea"))
        self.enlazar(Casilla(c[1074], "lectiva"))
        c[1081].setRange(0, 99); self.enlazar(Numero(c[1081], "numeroDeReuniones"))
        self.enlazar(Radios({c[1044]: "false", c[1043]: "true"}, "dobleDuracion"))
        solo_lectura(self.p, 1061)
        self.preparar_marcos()
        c[1229].clicked.connect(self.anadir)

    def calcular(self):
        self.p.c[1061].setText(str(len(NL.integrantes(self.elemento_xml()))))

    def anadir(self):
        x = self.elemento_xml()
        dlg = DialogoAnadirProfesores(self, self.win.proyecto, set(NL.integrantes(x)))
        if dlg.exec() == QDialog.Accepted and dlg.elegidos():
            self.aplicar()
            x = self.lista_fresca()[self.indice].datos["_xml"]
            self.win.editar(lambda a: NL.anadir_profesores(a, x, dlg.elegidos()), "añadir profesores")
            self.reabrir_tras_editar()


# ---------------------------------------------------------------- guardia
class PropiedadesGuardia(_BaseNL):
    RID = "199"; LISTA = "guardias"

    def preparar(self, raiz):
        c = self.p.c
        self.enlazar(Texto(c[1010], "nombre"))
        _cargar_combo(c[1197], _con_nombre_largo(raiz, "tareas")); self.enlazar(Texto(c[1197], "tipoDeTarea"))
        self.enlazar(Radios({c[1169]: "false", c[1043]: "true"}, "enRecreos"))
        self.enlazar(Casilla(c[1074], "lectiva"))
        c[1084].setRange(0, 99); self.enlazar(Numero(c[1084], "profesoresACadaHora/cantidad"))
        c[1085].setRange(0, 99); c[1085].setValue(1)
        solo_lectura(self.p, 1062, 1063, 1083)
        self.preparar_marcos()
        c[1228].clicked.connect(self.anadir)
        c[1153].clicked.connect(self.detallar)
        c[1415].clicked.connect(self.poner_todos)
        c[1507].toggled.connect(self._fijo_variable)
        self._detalle_nuevo = None

    def cargar(self):
        super().cargar()
        x = self.elemento_xml(); det = NL.detalle_posiciones(x)
        self._detalle_nuevo = None
        self.p.c[1060 if det else 1507].setChecked(True); self._fijo_variable()

    def _fijo_variable(self, *_):
        self.p.c[1153].setEnabled(self.p.c[1060].isChecked())

    def calcular(self):
        p = self.win.proyecto; x = self.elemento_xml()
        ints = x.find("integrantes")
        nums = [int((ix.findtext("numeroDeGuardias") or "0").strip() or 0) for ix in (ints.findall("integrante") if ints is not None else [])]
        self.p.c[1062].setText(str(NL.huecos_a_cubrir(p, x)))
        self.p.c[1063].setText(str(len(nums))); self.p.c[1083].setText(str(sum(nums)))
        self.p.c[1416].setText(f"{sum(nums) / len(nums):.2f}" if nums else "0")

    def aplicar_extra(self, arbol, x):
        if self.p.c[1507].isChecked() and NL.detalle_posiciones(x):
            return NL.fijar_detalle(arbol, x, None)
        if self._detalle_nuevo is not None and self.p.c[1060].isChecked():
            return NL.fijar_detalle(arbol, x, self._detalle_nuevo)
        return False

    def detallar(self):
        x = self.elemento_xml(); p = self.win.proyecto
        marco = next((m for rb, m in self.radios_marco.items() if rb.isChecked()), x.get("subMarco")) or next(iter(p.marcos))
        recreo = self.p.c[1043].isChecked()
        det = self._detalle_nuevo if self._detalle_nuevo is not None else NL.detalle_posiciones(x)
        dlg = GuardiasPorPosicion(self, p, marco, recreo, self.p.c[1084].value(), det, x)
        if dlg.exec() == QDialog.Accepted:
            self._detalle_nuevo = dlg.detalle()

    def poner_todos(self):
        n = self.p.c[1085].value()
        self.aplicar()
        x = self.lista_fresca()[self.indice].datos["_xml"]
        self.win.editar(lambda a: NL.poner_a_todos(a, x, n), "guardias a todos")
        self.reabrir_tras_editar()

    def anadir(self):
        x = self.elemento_xml()
        dlg = DialogoAnadirProfesores(self, self.win.proyecto, set(NL.integrantes(x)), con_guardias=True)
        if dlg.exec() == QDialog.Accepted and dlg.elegidos():
            self.aplicar()
            x = self.lista_fresca()[self.indice].datos["_xml"]
            self.win.editar(lambda a: NL.anadir_profesores(a, x, dlg.elegidos(), dlg.n_guardias()), "añadir profesores")
            self.reabrir_tras_editar()


class PropiedadesIntegranteGuardia(_BaseNL):
    """#200 «Horas de guardia a la semana en este servicio»."""
    RID = "200"; LISTA = "guardias"

    def lista_fresca(self):
        return integrantes_de_guardias(self.win.proyecto)

    def preparar(self, raiz):
        c = self.p.c
        c[1085].setRange(0, 99); self.enlazar(Numero(c[1085], "numeroDeGuardias"))
        solo_lectura(self.p, 1011, 1010, 1014, 1012, 1059, 1069, 1076, 1070)

    def cargar(self):
        super().cargar()
        e = self.elementos[self.indice]
        self.setWindowTitle(f"{self.V}: {e.datos['_servicio']}")

    def calcular(self):
        from .listas import _lectivas, _guardias_de, _integrantes
        p = self.win.proyecto; e = self.elementos[self.indice]; prof = e.nombre
        c = self.p.c
        c[1011].setText(e.datos["_servicio"]); c[1010].setText(prof)
        pe = next((x for x in p.profesores if x.nombre == prof), None)
        c[1014].setText(pe.datos.get("nombreCompleto", "") if pe else "")
        m = p.marcos.get(e.marco) or next(iter(p.marcos.values()), None)
        serv = e.datos["_padre"]
        from .xghc import leer_plantilla
        pls = [leer_plantilla(serv, e.marco), e.plantilla, pe.plantilla if pe else {}]
        recreo = (serv.findtext("enRecreos") or "").strip() == "true"
        libres = sum(1 for t in (m.tramos if m else []) if ((t.tipo == "recreo") if recreo else (t.tipo == "lectivo"))
                     and all(pl.get((m.id, t.dia, t.indice)) != M.PROHIBIDO for pl in pls))
        c[1012].setText(str(libres))
        c[1059].setText(_lectivas(p, "profesor", prof))
        c[1069].setText(str(sum(1 for r in p.reuniones if prof in _integrantes(r))))
        c[1076].setText(str(sum(1 for x in p.complementarias if x.datos.get("profesor") == prof)))
        c[1070].setText(_guardias_de(p, prof, False) or "0")


# ---------------------------------------------------------------- complementaria
class PropiedadesComplementaria(_BaseNL):
    RID = "253"; LISTA = "complementarias"

    def preparar(self, raiz):
        c = self.p.c
        _cargar_combo(c[1198], _con_nombre_largo(raiz, "tareas")); self.enlazar(Texto(c[1198], "tarea"))
        _cargar_combo(c[1199], ED.nombres(raiz, "profesores")); self.enlazar(Texto(c[1199], "profesor"))
        n = max((sum(1 for t in m.tramos if t.tipo == "lectivo" and t.dia == m.dias[0]) for m in self.win.proyecto.marcos.values()
                 if m.dias), default=8)
        _cargar_combo(c[1161], [str(i) for i in range(1, n + 1)], vacio=False)
        self.enlazar(Texto(c[1161], "maxIntervalosDiarios"))
        _cargar_combo(c[1162], [str(i) for i in range(0, n + 1)], vacio=False)
        no_persistir(self.p, self.V, 1162)
        c[1200].setRange(0, 99); self.enlazar(Numero(c[1200], "intervalosSemanales"))
        self.enlazar(Casilla(c[1202], "noConsecutivos"))
        self.enlazar(Casilla(c[1074], "lectiva"))
        c[1496].setVisible(False)
        self.preparar_marcos()
        c[1200].valueChanged.connect(self.calcular)

    def cargar(self):
        super().cargar()
        e = self.elementos[self.indice]
        self.setWindowTitle(f"{self.V}: {e.datos.get('tarea', '')} ({e.nombre})")

    def calcular(self, *_):
        c = self.p.c
        c[1503].setText(str(c[1200].value()))


# ---------------------------------------------------------------- auxiliares
class DialogoAnadirProfesores(QDialog):
    """Elegir profesores (filtro por departamento) para añadir a una reunión o servicio de guardia."""

    def __init__(self, parent, p, ya: set, con_guardias=False):
        super().__init__(parent); self.setWindowTitle("Añadir profesores"); self.setFont(fuente_dialogo())
        self.p, self.ya = p, ya
        lay = QVBoxLayout(self)
        fila = QHBoxLayout(); fila.addWidget(QLabel("Departamento:"))
        self.cb = QComboBox(); self.cb.addItem("(todos)"); self.cb.addItems([d.nombre for d in p.departamentos])
        self.cb.currentIndexChanged.connect(self._rellenar); fila.addWidget(self.cb, 1); lay.addLayout(fila)
        self.lw = QListWidget(); self.lw.setMinimumSize(320, 300); lay.addWidget(self.lw)
        self.sp = None
        if con_guardias:
            f2 = QHBoxLayout(); f2.addWidget(QLabel("Número de guardias semanales de cada uno:"))
            self.sp = QSpinBox(); self.sp.setRange(0, 99); self.sp.setValue(1); f2.addWidget(self.sp); lay.addLayout(f2)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Aceptar"); bb.button(QDialogButtonBox.Cancel).setText("Cancelar")
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject); lay.addWidget(bb)
        self._rellenar()

    def _rellenar(self):
        dep = self.cb.currentText() if self.cb.currentIndex() > 0 else None
        marcados = set(self.elegidos()) if self.lw.count() else set()
        self.lw.clear()
        for e in self.p.profesores:
            if e.nombre in self.ya or dep and e.datos.get("departamento") != dep:
                continue
            it = QListWidgetItem(e.nombre); it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if e.nombre in marcados else Qt.Unchecked); self.lw.addItem(it)

    def elegidos(self):
        return [self.lw.item(i).text() for i in range(self.lw.count()) if self.lw.item(i).checkState() == Qt.Checked]

    def n_guardias(self):
        return self.sp.value() if self.sp else 1


class GuardiasPorPosicion(QDialog):
    """Nº máximo de profesores de guardia en cada posición del marco (número variable)."""

    def __init__(self, parent, p, marco, recreo, cantidad, detalle: dict, servicio_xml=None):
        super().__init__(parent); self.setWindowTitle(TX("guardias_hora_hora")); self.setFont(fuente_dialogo())
        self.marco = p.marcos[marco]; self.celdas = {}
        from .xghc import leer_plantilla
        pl = leer_plantilla(servicio_xml, marco) if servicio_xml is not None else {}
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Número máximo de profesores de guardia a cada hora (las posiciones prohibidas en la "
                             "plantilla del servicio aparecen deshabilitadas):", wordWrap=True))
        indices = sorted({t.indice for t in self.marco.tramos if ((t.tipo == "recreo") if recreo else (t.tipo == "lectivo"))})
        dias = self.marco.dias
        tw = QTableWidget(len(indices), len(dias)); self.tabla = tw
        tw.setHorizontalHeaderLabels([DIAS[d] if d < 7 else str(d) for d in dias])
        horas = {}
        for t in self.marco.tramos:
            horas.setdefault(t.indice, f"{t.entrada}-{t.salida}")
        tw.setVerticalHeaderLabels([horas.get(i, str(i)) for i in indices])
        existe = {(t.dia, t.indice) for t in self.marco.tramos if ((t.tipo == "recreo") if recreo else (t.tipo == "lectivo"))}
        for r, i in enumerate(indices):
            for j, d in enumerate(dias):
                if (d, i) not in existe:
                    continue
                sp = QSpinBox(); sp.setRange(0, 99); sp.setAlignment(Qt.AlignCenter)
                k = (self.marco.id, d, i)
                sp.setValue(detalle.get(k, cantidad))
                if pl.get(k) == M.PROHIBIDO:
                    sp.setEnabled(False); sp.setToolTip("Posición prohibida en la plantilla del servicio")
                tw.setCellWidget(r, j, sp); self.celdas[k] = sp
        tw.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        tw.setMinimumSize(70 + 80 * len(dias), 40 + 30 * len(indices))
        lay.addWidget(tw)
        fila = QHBoxLayout(); fila.addWidget(QLabel("Poner en todas:"))
        self.sp_todas = QSpinBox(); self.sp_todas.setRange(0, 99); self.sp_todas.setValue(cantidad); fila.addWidget(self.sp_todas)
        b = QPushButton("Aplicar a todas"); b.clicked.connect(lambda: [s.setValue(self.sp_todas.value()) for s in self.celdas.values() if s.isEnabled()])
        fila.addWidget(b); fila.addStretch(1)
        self.total = QLabel(); fila.addWidget(self.total); lay.addLayout(fila)
        for s in self.celdas.values():
            s.valueChanged.connect(self._total)
        self._total()
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Aceptar"); bb.button(QDialogButtonBox.Cancel).setText("Cancelar")
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject); lay.addWidget(bb)

    def _total(self, *_):
        self.total.setText(f"Nº total de huecos a cubrir: {sum(s.value() for s in self.celdas.values() if s.isEnabled())}")

    def detalle(self) -> dict:
        return {k: s.value() for k, s in self.celdas.items() if s.isEnabled()}


class DialogoCrearReuniones(QDialog):
    """#621 «Crear reuniones de departamento» / #686 «… de equipos pedagógicos»."""

    def __init__(self, parent, p, por_grupo=False):
        super().__init__(parent)
        self.pg = PaginaRC("686" if por_grupo else "621", self); self.setFixedSize(self.pg.size())
        self.setWindowTitle(self.pg.titulo); self.setFont(fuente_dialogo())
        c = self.pg.c; self.por_grupo = por_grupo
        self.combo = c[1474 if por_grupo else 1170]
        _cargar_combo(self.combo, [e.nombre for e in (p.grupos if por_grupo else p.departamentos)], vacio=False)
        c[1044].setChecked(True); c[1060].setChecked(True)
        c[1].clicked.connect(self.accept); c[2].clicked.connect(self.reject)
        c[57670].clicked.connect(lambda: QMessageBox.information(self, self.windowTitle(), "La ayuda estará disponible próximamente."))

    def opciones(self):
        c = self.pg.c
        return (self.combo.currentText() if c[1043].isChecked() else None, c[1045].isChecked())


VENTANAS_NL = {"tareas": PropiedadesTarea, "reuniones": PropiedadesReunion, "guardias": PropiedadesGuardia,
               "complementarias": PropiedadesComplementaria}
