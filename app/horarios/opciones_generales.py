"""CONFIGURACIÓN > «Opciones generales, valores de partida y otras acciones» (cadena 273 del planificador de referencia).

Hoja de solapas construida con los diálogos del planificador de referencia (manda el recurso): 218 Opciones generales,
196 Sesiones, 667 Ocupación diaria, 195 Periodos libres, 373 Compactación, 252 Tareas iniciales, 445 Alumnos,
444 Anotaciones, 503 Operaciones y 938 Alejados.

Persistencia en el .xghc (etiquetas tomadas de las plantillas de escritura XML del planificador de referencia):
- otros/opciones/opcionesGenerales/{contarHuecosMediodia, desecharGuardias}   (solo se escriben con «true»)
- otros/opciones/valorInicialSesiones/*    (valores para las sesiones nuevas; «a toda la lista» los copia)
- otros/opciones/valorInicialProfesores/*  (valores para los profesores nuevos; ídem)
- tareas/{lectivaPorDefecto, reunionPorDefecto, guardiaPorDefecto}
- otros/notas
- otros/gruposAlejados/{opciones/{actualizarAlGenerar, evitarDobleDesp}, listaDeGrupos/grupo}
Los mensajes de confirmación y la «utilización como referencia» no tienen etiqueta en el formato: se guardan
como preferencias de la aplicación (QSettings).
"""
from __future__ import annotations
from .textos import TX
import copy
import xml.etree.ElementTree as ET
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (QDialog, QTabWidget, QVBoxLayout, QHBoxLayout, QPushButton, QMessageBox,
                               QListWidget, QAbstractItemView, QDialogButtonBox, QLabel, QPlainTextEdit, QLineEdit)
from . import edicion as ED
from .formrc import PaginaRC, NO_PERSISTIDO, fuente_dialogo
from .propiedades import (Enlace, Texto, CasillaD, Bandera, RadioBandera, NumeroD, RadiosD, TipoPeriodo,
                          PeriodoJornada, IconoEstricto, RADIOS_FRANJA, RADIOS_DIAS_SEGUIDOS, _cargar_combo,
                          _con_nombre_largo)

TITULO = TX("opciones_generales_valores_partida_otras")
PAGINAS = ["218", "196", "667", "195", "373", "252", "445", "444", "503", "938"]
from . import VENDOR as ORG, AJUSTES as APP

OG = "otros/opciones/opcionesGenerales/"
VS = "otros/opciones/valorInicialSesiones"
VP = "otros/opciones/valorInicialProfesores"

# Valores iniciales del planificador de referencia cuando el archivo no los trae (los de los archivos de ejemplo)
PLANTILLA_VS = """<valorInicialSesiones>
<penaSesionesAPrimera>true</penaSesionesAPrimera>
<penaSesionesAUltima>true</penaSesionesAUltima>
<penaSalirUltimaEntrarPrimera>true</penaSalirUltimaEntrarPrimera>
<penaSesionMismaHora>distinta</penaSesionMismaHora>
<penaCoincidanPorLaTarde>true</penaCoincidanPorLaTarde>
<penaCoincidanDespuesDelRecreo>true</penaCoincidanDespuesDelRecreo>
<noPermitirRecreosEntreSesiones>false</noPermitirRecreosEntreSesiones>
<recreosSeparanSesionesContinuas>false</recreosSeparanSesionesContinuas>
<permitirImpartanEnDiasSeguidos>preferiblemente</permitirImpartanEnDiasSeguidos>
<considerarLunesViernesSeguidos>false</considerarLunesViernesSeguidos>
</valorInicialSesiones>"""
PLANTILLA_VP = """<valorInicialProfesores>
<intervalosDePermanenciaSemanales estricto="true">40</intervalosDePermanenciaSemanales>
<intervalosDePermanenciaSemanales estricto="false">25</intervalosDePermanenciaSemanales>
<intervalosDePermanenciaDiarios estricto="true">50</intervalosDePermanenciaDiarios>
<intervalosDePermanenciaDiarios estricto="false">5</intervalosDePermanenciaDiarios>
<eliminarHuecos>true</eliminarHuecos>
<maximasHorasSeguidas>5</maximasHorasSeguidas>
<periodosLibres><cantidadDeDias>0</cantidadDeDias><tipoDePeriodo><diasCompletos>0</diasCompletos></tipoDePeriodo></periodosLibres>
<periodoLibreJornadaPartida><cantidad>0</cantidad><preferentes>0</preferentes><tipoDePeriodoLibre>indistintamente</tipoDePeriodoLibre></periodoLibreJornadaPartida>
<otrosPeriodosLibresJornadaPartida>
<periodoLibreJornadaPartida><cantidad>0</cantidad><preferentes>0</preferentes><tipoDePeriodoLibre>tardes</tipoDePeriodoLibre></periodoLibreJornadaPartida>
<periodoLibreJornadaPartida><cantidad>0</cantidad><preferentes>0</preferentes><tipoDePeriodoLibre>mañanas</tipoDePeriodoLibre></periodoLibreJornadaPartida>
</otrosPeriodosLibresJornadaPartida>
<incompatibilidadEntreSesiones>
<salirUltimaEntrarPrimera nIntervalos="1">false</salirUltimaEntrarPrimera>
<salirUltimaEntrarPrimeraLunes nIntervalos="1">false</salirUltimaEntrarPrimeraLunes>
<entrarPrimeraSalirUltima nIntervalos="1">false</entrarPrimeraSalirUltima>
<entrarPrimeraSalirUltimaTarde>false</entrarPrimeraSalirUltimaTarde>
<entrarPrimeraSalirUltimaManana>false</entrarPrimeraSalirUltimaManana>
<salirUltimaMananaEntrarPrimeraTarde>false</salirUltimaMananaEntrarPrimeraTarde>
<salirUltimaMananaTardeCompleta>false</salirUltimaMananaTardeCompleta>
<menosDeDosIntervalosLibres>false</menosDeDosIntervalosLibres>
<entrarPrimeraSalirTarde>false</entrarPrimeraSalirTarde>
</incompatibilidadEntreSesiones>
<considerarMaximasHorasDiariasSolamenteLectivas>optimizacionPreferente</considerarMaximasHorasDiariasSolamenteLectivas>
<valorMaximasHorasCalculadoSolamenteLectivas>automatico</valorMaximasHorasCalculadoSolamenteLectivas>
<considerarMinimasHorasDiariasSolamenteLectivas>optimizacionPreferente</considerarMinimasHorasDiariasSolamenteLectivas>
<valorMinimasHorasCalculadoSolamenteLectivas>automatico</valorMinimasHorasCalculadoSolamenteLectivas>
<considerarMaximasHorasDiarias>optimizacionPreferente</considerarMaximasHorasDiarias>
<valorMaximasHorasCalculado>automatico</valorMaximasHorasCalculado>
<considerarMinimasHorasDiarias>optimizacionPreferente</considerarMinimasHorasDiarias>
<valorMinimasHorasCalculado>automatico</valorMinimasHorasCalculado>
</valorInicialProfesores>"""

INCOMPAT = [  # (casilla, botón icono, etiqueta, edición nIntervalos, botón aplicar)
    (1171, 1234, "entrarPrimeraSalirUltima", 1382, 1073), (1172, 1235, "entrarPrimeraSalirTarde", None, 1089),
    (1206, 1236, "entrarPrimeraSalirUltimaManana", None, 1084), (1218, 1237, "entrarPrimeraSalirUltimaTarde", None, 1088),
    (1150, 1238, "salirUltimaMananaEntrarPrimeraTarde", None, 1072),
    (1216, 1239, "salirUltimaMananaTardeCompleta", None, 1086), (1217, 1240, "menosDeDosIntervalosLibres", None, 1087),
    (1149, 1233, "salirUltimaEntrarPrimera", 1381, 1071), (1151, 1241, "salirUltimaEntrarPrimeraLunes", 1386, 1095)]

CATEGORIAS_REF = [("Materias", 1044, 1052, 1056), ("Alumnos", 1045, 1053, 1057), ("Profesores", 1046, 1054, 1058),
                  ("Aulas", 1047, 1055, 1059), ("Cursos", 1048, None, 1060), ("Departamentos", 1049, None, 1061),
                  ("Tareas", 1050, None, 1062)]


def preferencias():
    return QSettings(ORG, APP)


def confirmar_suprimir() -> bool:
    """«Pedir confirmación: Siempre que se borre algo de una lista» (preferencia de la aplicación)."""
    v = preferencias().value("opciones/confirmar_suprimir", True)
    return v not in (False, "false", 0, "0")


class TextoLargo(Enlace):
    def __init__(self, w: QPlainTextEdit, ruta):
        self.w, self.ruta, self.v0 = w, ruta, None

    def cargar(self, e):
        self.v0 = ED.leer(e, self.ruta, None); self.w.setPlainText(self.v0 or "")

    def guardar(self, arbol, e):
        v = self.w.toPlainText().strip()
        return v != (self.v0 or "") and ED.escribir(arbol, e, self.ruta, v)


class DobleDesplazamiento(Enlace):
    """otros/gruposAlejados/opciones/evitarDobleDesp: false = no es relevante; true = procurar evitar;
    true con prohibir="true" = prohibir estrictamente (cadena «prohibir» junto a <evitarDobleDesp%s>)."""
    RUTA = "otros/gruposAlejados/opciones/evitarDobleDesp"

    def __init__(self, no, evitar, prohibir):
        self.r = (no, evitar, prohibir); self.v0 = 0

    def cargar(self, e):
        n = ED.buscar(e, self.RUTA)
        self.v0 = 0 if n is None or (n.text or "").strip() != "true" else (2 if n.get("prohibir") == "true" else 1)
        self.r[self.v0].setChecked(True)

    def guardar(self, arbol, e):
        v = next(i for i, r in enumerate(self.r) if r.isChecked()) if any(r.isChecked() for r in self.r) else self.v0
        if v == self.v0:
            return False
        if v == 0 and ED.buscar(e, self.RUTA) is None:
            return False
        n = ED.asegurar(arbol, e, self.RUTA)
        n.text = "true" if v else "false"
        if v == 2:
            n.set("prohibir", "true")
        else:
            n.attrib.pop("prohibir", None)
        return True


class ListaAlejados(Enlace):
    RUTA = "otros/gruposAlejados/listaDeGrupos"

    def __init__(self, lw: QListWidget):
        self.lw, self.v0 = lw, []

    def cargar(self, e):
        n = ED.buscar(e, self.RUTA)
        self.v0 = [(g.text or "").strip() for g in n.findall("grupo")] if n is not None else []
        self.lw.clear(); self.lw.addItems(self.v0)

    def valores(self):
        return [self.lw.item(i).text() for i in range(self.lw.count())]

    def guardar(self, arbol, e):
        v = self.valores()
        if v == self.v0:
            return False
        n = ED.asegurar(arbol, e, self.RUTA)
        for g in list(n):
            ED.quitar_hijo(arbol, n, g)
        for g in v:
            ED.insertar_hijo(arbol, n, ED.nuevo("grupo", g))
        return True


class SeleccionNombres(QDialog):
    def __init__(self, titulo, nombres, parent=None):
        super().__init__(parent); self.setWindowTitle(titulo); self.setFont(fuente_dialogo())
        lay = QVBoxLayout(self); self.lw = QListWidget(); self.lw.addItems(nombres)
        self.lw.setSelectionMode(QAbstractItemView.ExtendedSelection); lay.addWidget(self.lw)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Aceptar"); bb.button(QDialogButtonBox.Cancel).setText("Cancelar")
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject); lay.addWidget(bb)
        self.resize(300, 360)

    def seleccion(self):
        return [i.text() for i in self.lw.selectedItems()]


class DialogoOpcionesGenerales(QDialog):
    def __init__(self, win, pagina_inicial: str | None = None, parent=None):
        super().__init__(parent or win)
        self.win = win; self.setWindowTitle(TITULO); self.setFont(fuente_dialogo())
        self.grupos: dict[str, tuple[str, list]] = {"": ("", []), VS: (PLANTILLA_VS, []), VP: (PLANTILLA_VP, [])}
        self.tabs = QTabWidget(); self.p = {}
        for rid in PAGINAS:
            pg = PaginaRC(rid, sin_botones=True); self.p[rid] = pg; self.tabs.addTab(pg, pg.titulo)
        lay = QVBoxLayout(self); lay.addWidget(self.tabs)
        bl = QHBoxLayout(); bl.addStretch(1)
        self.b_aceptar = QPushButton("Aceptar"); self.b_aceptar.setDefault(True)
        self.b_cancelar = QPushButton("Cancelar"); self.b_aplicar = QPushButton("Aplicar"); self.b_ayuda = QPushButton("Ayuda")
        for b in (self.b_aceptar, self.b_cancelar, self.b_aplicar, self.b_ayuda):
            b.setMinimumWidth(80); bl.addWidget(b)
        lay.addLayout(bl)
        self.b_aceptar.clicked.connect(self.aceptar); self.b_cancelar.clicked.connect(self.reject)
        self.b_aplicar.clicked.connect(self.aplicar)
        self.b_ayuda.clicked.connect(lambda: QMessageBox.information(self, TITULO, "La ayuda estará disponible próximamente."))
        raiz = self.raiz()
        self._general(); self._sesiones(); self._ocupacion(); self._periodos(); self._compactacion()
        self._tareas(raiz); self._alumnos(); self._anotaciones(); self._operaciones(); self._alejados()
        self.cargar()
        if pagina_inicial in self.p:
            self.tabs.setCurrentWidget(self.p[pagina_inicial])

    # ------------------------------------------------------------ utilidades
    def raiz(self):
        return self.win.proyecto.doc.raiz

    def enlazar(self, en, grupo=""):
        self.grupos[grupo][1].append(en); return en

    def enlaces(self):
        return [en for _, l in self.grupos.values() for en in l]

    def cargar(self):
        r = self.raiz()
        for en in self.enlaces():
            en.cargar(r)
        self._cargar_preferencias()
        pg = self.p["444"]
        pg.c[1078].setText((getattr(self.win.proyecto, "ruta_original", None) or getattr(self.win.proyecto, "ruta", "")) or "")
        pg.c[1479].setText(ED.leer(r, "otros/origenDatos", "") or "—")

    def _hacer(self, arbol):
        raiz = arbol.raiz
        prueba = copy.deepcopy(raiz); ap = ED.Arbol(prueba)
        cambio = False
        for ruta, (plantilla, lista) in self.grupos.items():
            if not lista:
                continue
            if plantilla and ED.buscar(raiz, ruta) is None:
                if not any([en.guardar(ap, prueba) for en in lista]):
                    continue
                padre, tag = ruta.rsplit("/", 1)
                nodo = ET.fromstring(plantilla)
                for x in nodo.iter():
                    if len(x) == 0:
                        x.text = (x.text or "").strip()
                ED.insertar_hijo(arbol, ED.asegurar(arbol, raiz, padre), nodo)
                cambio = True
            if any([en.guardar(arbol, raiz) for en in lista]):
                cambio = True
        return cambio

    def aplicar(self) -> bool:
        try:
            ok = self.win.editar(self._hacer, "Opciones generales", refrescar=False)
        except ValueError as ex:
            QMessageBox.warning(self, TITULO, str(ex)); return False
        self._guardar_preferencias()
        self.cargar()
        return True if ok is None else ok

    def aceptar(self):
        self.aplicar(); self.accept()

    def _editar(self, fn, descripcion):
        """Ejecuta una operación sobre el XML (deshacer disponible) tras aplicar lo pendiente del diálogo."""
        self.aplicar()
        hecho = self.win.editar(fn, descripcion)
        self.cargar()
        return hecho

    def _preguntar(self, texto) -> bool:
        return QMessageBox.question(self, TITULO, texto) == QMessageBox.Yes

    # ------------------------------------------------------------ 218 Opciones generales
    def _general(self):
        pg = self.p["218"]
        self.enlazar(Bandera(pg.c[1111], OG + "contarHuecosMediodia"))
        self.enlazar(Bandera(pg.c[1112], OG + "desecharGuardias"))
        pg.regrupar(*[[x for x in fila[1:] if x] for fila in CATEGORIAS_REF])
        for b, col in ((1070, 1), (1069, 2), (1071, 3)):
            pg.c[b].clicked.connect(lambda _=False, col=col: self._referencia_todas(col))
        for cid in (1296, 1297):
            pg.c[cid].setToolTip("Preferencia de la aplicación (no se guarda en el archivo)")

    def _referencia_todas(self, col):
        pg = self.p["218"]
        for fila in CATEGORIAS_REF:
            cid = fila[col] or fila[1 if col == 2 else 3]
            pg.c[cid].setChecked(True)

    def _cargar_preferencias(self):
        s = preferencias(); pg = self.p["218"]
        pg.c[1296].setChecked(confirmar_suprimir())
        pg.c[1297].setChecked(s.value("opciones/confirmar_cadena", True) not in (False, "false", 0, "0"))
        for fila in CATEGORIAS_REF:
            k = int(s.value(f"opciones/referencia/{fila[0]}", 0) or 0)
            cid = fila[1 + k] if 0 <= k <= 2 and fila[1 + k] else fila[1]
            pg.c[cid].setChecked(True)

    def _guardar_preferencias(self):
        s = preferencias(); pg = self.p["218"]
        s.setValue("opciones/confirmar_suprimir", pg.c[1296].isChecked())
        s.setValue("opciones/confirmar_cadena", pg.c[1297].isChecked())
        for fila in CATEGORIAS_REF:
            k = next((i for i, cid in enumerate(fila[1:]) if cid and pg.c[cid].isChecked()), 0)
            s.setValue(f"opciones/referencia/{fila[0]}", k)

    # ------------------------------------------------------------ «a toda la lista»
    def _boton_aplicar(self, pg, bid, cont, destinos, piezas, nombre):
        """piezas: [(ruta_padre, tag, pred)] relativas al contenedor de valores iniciales."""
        def pulsar():
            if not self._preguntar(f"¿Asignar «{nombre}» a todos los elementos de la lista?"):
                return

            def fn(arbol):
                origen = ED.buscar(arbol.raiz, cont)
                if origen is None:
                    return False
                ch = False
                for d, base in destinos(arbol.raiz):
                    for rp, tag, pred in piezas:
                        ruta = base + ("/" + rp if rp else "")
                        sp = ED.buscar(origen, rp) if rp else origen
                        if ED.copiar_nodo(arbol, sp, d, ruta, tag, pred):
                            ch = True
                return ch
            self._editar(fn, TX("toda_lista_nombre", nombre=nombre))
        pg.c[bid].clicked.connect(pulsar)

    @staticmethod
    def _sesiones_de(raiz):
        sl = raiz.find("sesionesLectivas")
        return [(s, "opciones") for s in (sl.findall("sesion") if sl is not None else [])]

    @staticmethod
    def _profesores_de(raiz):
        pr = raiz.find("profesores")
        return [(p, "opciones") for p in (pr.findall("profesor") if pr is not None else [])]

    # ------------------------------------------------------------ 196 Sesiones
    def _sesiones(self):
        pg = self.p["196"]; V = VS + "/"
        casillas = [(1154, "penaSesionesAPrimera", "true", 1082), (1155, "penaSesionesAUltima", "true", 1083),
                    (1149, "penaSalirUltimaEntrarPrimera", "true", 1086),
                    (1087, "penaCoincidanDespuesDelRecreo", "true", 1088),
                    (1157, "penaCoincidanPorLaTarde", "true", 1085),
                    (1076, "noPermitirRecreosEntreSesiones", "false", 1080),
                    (1079, "recreosSeparanSesionesContinuas", "false", 1081),
                    (1511, "sinCambioAula", "false", 1065)]
        for cid, tag, d, bid in casillas:
            self.enlazar(CasillaD(pg.c[cid], V + tag, d), VS)
            self._boton_aplicar(pg, bid, VS, self._sesiones_de, [("", tag, None)], pg.c[cid].text() or tag)
        self.enlazar(CasillaD(pg.c[1077], V + "considerarLunesViernesSeguidos", "false"), VS)
        self.enlazar(RadiosD(RADIOS_FRANJA(pg), V + "penaSesionMismaHora", "distinta"), VS)
        self._boton_aplicar(pg, 1084, VS, self._sesiones_de, [("", "penaSesionMismaHora", None)],
                            TX("franja_horaria"))
        self.enlazar(RadiosD(RADIOS_DIAS_SEGUIDOS(pg), V + "permitirImpartanEnDiasSeguidos", "preferiblemente"), VS)
        self._boton_aplicar(pg, 1064, VS, self._sesiones_de, [("", "permitirImpartanEnDiasSeguidos", None),
                                                              ("", "considerarLunesViernesSeguidos", None)],
                            "Días alternos / consecutivos")

    # ------------------------------------------------------------ 667 Ocupación diaria
    def _ocupacion(self):
        pg = self.p["667"]; V = VP + "/"
        pg.regrupar([1358, 1046])
        self.enlazar(RadioBandera(pg.c[1046], pg.c[1358], V + "minimizarDiasOcupados"), VP)
        self._boton_aplicar(pg, 1076, VP, self._profesores_de, [("", "minimizarDiasOcupados", None)], "Días libres")
        filas = [((1349, 1208, 1061), "considerarMinimasHorasDiariasSolamenteLectivas", 1072,
                  (1205, 1214, 1221), "valorMinimasHorasCalculadoSolamenteLectivas", 1073),
                 ((1207, 1357, 1060), "considerarMaximasHorasDiariasSolamenteLectivas", 1085,
                  (1206, 1215, 1222), "valorMaximasHorasCalculadoSolamenteLectivas", 1074),
                 ((1350, 1209, 1062), "considerarMinimasHorasDiarias", 1075,
                  (1210, 1216, 1223), "valorMinimasHorasCalculado", 1077),
                 ((1211, 1359, 1063), "considerarMaximasHorasDiarias", 1086,
                  (1212, 1217, 1224), "valorMaximasHorasCalculado", 1078)]
        for (e, p_, pd), tag, b1, (mas, eq, menos), tag2, b2 in filas:
            self.enlazar(RadiosD({pg.c[e]: "estricto", pg.c[p_]: "optimizacionPreferente", pg.c[pd]: "ponderable"},
                                    V + tag, "optimizacionPreferente"), VP)
            self.enlazar(RadiosD({pg.c[mas]: "unaHoraMas", pg.c[eq]: "automatico", pg.c[menos]: "unaHoraMenos"},
                                    V + tag2, "automatico"), VP)
            self._boton_aplicar(pg, b1, VP, self._profesores_de, [("", tag, None)], tag)
            self._boton_aplicar(pg, b2, VP, self._profesores_de, [("", tag2, None)], tag2)

    # ------------------------------------------------------------ 195 Periodos libres
    def _periodos(self):
        pg = self.p["195"]; V = VP + "/"
        self.enlazar(NumeroD(pg.c[1074], V + "periodosLibres/cantidadDeDias", 0), VP)
        self.enlazar(TipoPeriodo({pg.c[1045]: "diasCompletos", pg.c[1046]: "losPrimerosIntervalos",
                                  pg.c[1205]: "losUltimosIntervalos", pg.c[1214]: "intervalosSeguidos"}, pg.c[1077],
                                 ruta=V + "periodosLibres/tipoDePeriodo"), VP)
        self._boton_aplicar(pg, 1081, VP, self._profesores_de, [("periodosLibres", "cantidadDeDias", None)],
                            "Días libres")
        for b in (1082, 1083):
            self._boton_aplicar(pg, b, VP, self._profesores_de, [("periodosLibres", "tipoDePeriodo", None)],
                                "Tipo de periodos libres")
        tipo = lambda t: (lambda x: (x.findtext("tipoDePeriodoLibre") or "").strip() == t)
        for wc, wp, t, b in ((1065, 1066, "tardes", 1079), (1067, 1075, "mañanas", 1080),
                             (1091, 1093, "indistintamente", 1085)):
            self.enlazar(PeriodoJornada(pg.c[wc], pg.c[wp], t, base=VP), VP)
            rp = "" if t == "indistintamente" else "otrosPeriodosLibresJornadaPartida"
            self._boton_aplicar(pg, b, VP, self._profesores_de, [(rp, "periodoLibreJornadaPartida", tipo(t))],
                                TX("horas_libres_t", t=t))
        inc = V + "incompatibilidadEntreSesiones/"
        for chk, ico, tag, num, b in INCOMPAT:
            self.enlazar(CasillaD(pg.c[chk], inc + tag, "false"), VP)
            if num:
                self.enlazar(NumeroD(pg.c[num], inc + tag, 1, attr="nIntervalos"), VP)
            pg.c[ico].setEnabled(False)
            pg.c[ico].setToolTip("Estricto (chincheta) o preferente (cara): solo se muestra")
            self._boton_aplicar(pg, b, VP, self._profesores_de, [("incompatibilidadEntreSesiones", tag, None)],
                                pg.c[chk].text())
        self._iconos_tipo = {pg.c[ico]: inc + tag for _c, ico, tag, _n, _b in INCOMPAT}

    # ------------------------------------------------------------ 373 Compactación
    def _compactacion(self):
        pg = self.p["373"]; V = VP + "/"
        for cid, est, d, b, tag in ((1063, "true", 40, 1069, "intervalosDePermanenciaSemanales"),
                                    (1082, "false", 25, 1075, "intervalosDePermanenciaSemanales"),
                                    (1068, "true", 50, 1078, "intervalosDePermanenciaDiarios"),
                                    (1084, "false", 5, 1079, "intervalosDePermanenciaDiarios")):
            self.enlazar(NumeroD(pg.c[cid], f'{V}{tag}[@estricto="{est}"]', d), VP)
            self._boton_aplicar(pg, b, VP, self._profesores_de,
                                [("", tag, lambda x, est=est: x.get("estricto") == est)], f"{tag} ({est})")
        self.enlazar(NumeroD(pg.c[1064], V + "maximasHorasSeguidas", 5), VP)
        self.enlazar(IconoEstricto(pg.c[1509], V + "maximasHorasSeguidas"), VP)
        self._boton_aplicar(pg, 1070, VP, self._profesores_de, [("", "maximasHorasSeguidas", None)],
                            "Máximo de horas seguidas")
        self.enlazar(Bandera(pg.c[1080], V + "penalizarAlrededorGuardiaRecreo"), VP)
        self.enlazar(IconoEstricto(pg.c[1510], V + "penalizarAlrededorGuardiaRecreo"), VP)

        def penalizar(arbol):
            v = pg.c[1080].isChecked(); est = pg.c[1510].estricto; ch = False
            for p, _ in self._profesores_de(arbol.raiz):
                op = ED.asegurar(arbol, p, "opciones"); n = op.find("penalizarAlrededorGuardiaRecreo")
                if not v:
                    if n is not None:
                        ED.quitar_hijo(arbol, op, n); ch = True
                    continue
                if n is None:
                    n = ED.insertar_hijo(arbol, op, ED.nuevo("penalizarAlrededorGuardiaRecreo", "true")); ch = True
                if (n.get("estricto") == "true") != est:
                    n.set("estricto", "true") if est else n.attrib.pop("estricto", None); ch = True
            return ch
        pg.c[1081].clicked.connect(lambda: self._preguntar("¿Asignar esta condición a todos los profesores?")
                                   and self._editar(penalizar, TX("toda_lista_guardias_recreo")))
        pg.c[1065].setValue(1)
        pg.c[1065].setToolTip(TX("prioridad_no_tiene_valor_partida"))

        def prioridad(arbol):
            v = str(pg.c[1065].value())
            return any([ED.escribir(arbol, p, "prioridad", v) for p, _ in self._profesores_de(arbol.raiz)])
        pg.c[1071].clicked.connect(lambda: self._preguntar(
            f"¿Asignar el nivel de prioridad {pg.c[1065].value()} a todos los profesores?")
            and self._editar(prioridad, TX("toda_lista_prioridad")))

    # ------------------------------------------------------------ 252 Tareas iniciales
    def _tareas(self, raiz):
        pg = self.p["252"]
        tareas = _con_nombre_largo(raiz, "tareas")
        for cid, tag in ((1192, "lectivaPorDefecto"), (1193, "reunionPorDefecto"), (1191, "guardiaPorDefecto")):
            _cargar_combo(pg.c[cid], tareas)
            self.enlazar(Texto(pg.c[cid], "tareas/" + tag))

        def asignar(cid, lista, item, campo, nombre):
            def fn(arbol):
                v = pg.c[cid].currentText().split("  ~ ")[0].strip()
                c = arbol.raiz.find(lista)
                if not v or c is None:
                    return False
                return any([ED.escribir(arbol, x, campo, v) for x in c.findall(item)])
            pg.c[{1192: 1194, 1193: 1195, 1191: 1196}[cid]].clicked.connect(
                lambda: self._preguntar(f"¿Asignar este tipo de tarea a todas las {nombre}?") and self._editar(fn, f"tarea de las {nombre}"))
        asignar(1192, "sesionesLectivas", "sesion", "tarea", "sesiones lectivas")
        asignar(1193, "reuniones", "reunion", "tipoDeTarea", "reuniones")
        asignar(1191, "guardias", "guardia", "tipoDeTarea", "guardias")

    # ------------------------------------------------------------ 445 Alumnos (sin valores iniciales en el formato)
    def _alumnos(self):
        pg = self.p["445"]
        pg.c[1221].setChecked(True)
        pg.c[1205].setEnabled(False); pg.c[1205].setToolTip(NO_PERSISTIDO)
        grupos = lambda raiz: (raiz.find("grupos").findall("grupo") if raiz.find("grupos") is not None else [])

        def tutor(arbol):
            ch = False
            for g in grupos(arbol.raiz):
                t = g.find("profesorTutor")
                if t is None:
                    continue
                for cid, at in ((1077, "imparteTodosLosDias"), (1074, "imparteAPrimeras"), (1076, "imparteAUltimas")):
                    v = pg.c[cid].isChecked()
                    if (t.get(at) == "true") != v:
                        t.set(at, "true") if v else t.attrib.pop(at, None); ch = True
            return ch

        def escribir_todos(tag, valor):
            def fn(arbol):
                return any([ED.escribir(arbol, g, tag, valor()) for g in grupos(arbol.raiz)])
            return fn
        acciones = {1086: (tutor, "clases del tutor en su grupo"),
                    1082: (escribir_todos("eliminarHuecos", lambda: "true" if pg.c[1214].isChecked() else "false"),
                           "huecos del horario de los alumnos"),
                    1083: (escribir_todos("huecosEnNoPreferentes", lambda: "true" if pg.c[1075].isChecked() else "false"),
                           "periodos libres en zonas no preferentes"),
                    1084: (escribir_todos("limiteOcupacionDia", lambda: str(pg.c[1237].value())), "ocupación diaria máxima"),
                    1085: (escribir_todos("tardesLibres", lambda: str(pg.c[1235].value())), "tardes libres"),
                    1069: (escribir_todos("numeroAlumnos", lambda: "0"), "grupos con cero alumnos")}
        for bid, (fn, nombre) in acciones.items():
            pg.c[bid].clicked.connect(lambda _=False, fn=fn, nombre=nombre: self._preguntar(
                f"¿Asignar «{nombre}» a todos los grupos de alumnos?") and self._editar(fn, f"grupos: {nombre}"))

    # ------------------------------------------------------------ 444 Anotaciones
    def _anotaciones(self):
        pg = self.p["444"]
        self.enlazar(TextoLargo(pg.c[1293], "otros/notas"))

    # ------------------------------------------------------------ 503 Operaciones
    def _operaciones(self):
        pg = self.p["503"]
        ops = {1108: (self.op_quitar_profesores, "Se quitarán las asignaciones de profesor de TODAS las sesiones lectivas."),
               1103: (self.op_quitar_no_consecutivas, "Se eliminarán todas las condiciones de -no consecutivas-."),
               1104: (self.op_alternativas_general, "Se asignará el aula alternativa de tipo «general» a todas las "
                                                    "sesiones lectivas que no la tengan."),
               1106: (self.op_eliminar_no_usados, "Se eliminarán las materias y los cursos que no se estén usando."),
               1107: (self.op_generar_sesiones, "Se generarán las sesiones lectivas de cada grupo según las materias "
                                                "de su curso (solo las que falten)."),
               1105: (self.op_departamentos, "Se asignará a cada sesión lectiva el departamento de su materia.")}
        for bid, (fn, txt) in ops.items():
            pg.c[bid].clicked.connect(lambda _=False, fn=fn, txt=txt: self._preguntar(txt + "\n\n¿Continuar?")
                                      and self._operar(fn))
        pg.c[1378].setEnabled(False); pg.c[1378].setToolTip("Disponible próximamente")

    def _operar(self, fn):
        res = {}
        hecho = self._editar(lambda a: fn(a, res), "operación sobre la lista de sesiones")
        QMessageBox.information(self, TITULO, res.get("mensaje", "Hecho.") if hecho else res.get("mensaje", "No había nada que cambiar."))

    @staticmethod
    def _todas(raiz):
        sl = raiz.find("sesionesLectivas")
        return sl.findall("sesion") if sl is not None else []

    def op_quitar_profesores(self, arbol, res):
        n = sum(1 for s in self._todas(arbol.raiz) if ED.leer(s, "profesor", "") and ED.escribir(arbol, s, "profesor", ""))
        res["mensaje"] = TX("sesiones_sin_profesor_n", n=n)
        return n > 0

    def op_quitar_no_consecutivas(self, arbol, res):
        n = 0
        for s in self._todas(arbol.raiz):
            for x in list(s.findall("noConsecutivas")):
                ED.quitar_hijo(arbol, s, x); n += 1
        res["mensaje"] = f"Condiciones de -no consecutivas- eliminadas: {n}."
        return n > 0

    def op_alternativas_general(self, arbol, res):
        raiz = arbol.raiz
        conj = raiz.find("conjuntoDeAulas")
        nombre = next((c.get("nombre") for c in (conj if conj is not None else []) if (c.get("nombre") or "").lower() == "general"), None)
        if nombre is None:
            res["mensaje"] = "No hay ningún conjunto de aulas llamado «general»."; return False
        n = 0
        for s in self._todas(raiz):
            la = ED.asegurar(arbol, s, "listaDeAlternativas")
            if nombre not in [(x.text or "").strip() for x in la.findall("conjuntoAlternativo")]:
                ED.insertar_hijo(arbol, la, ED.nuevo("conjuntoAlternativo", nombre)); n += 1
        res["mensaje"] = f"Sesiones con el aula alternativa «{nombre}» añadida: {n}."
        return n > 0

    def op_eliminar_no_usados(self, arbol, res):
        raiz = arbol.raiz
        usados_cursos = {(g.findtext("cursoPerteneciente") or "").strip() for g in raiz.iter("grupo")}
        cursos = raiz.find("cursos"); quitados_c = []
        for c in (list(cursos.findall("curso")) if cursos is not None else []):
            nm = (c.findtext("nombre") or "").strip()
            if nm not in usados_cursos:
                ED.quitar_hijo(arbol, cursos, c); quitados_c.append(nm)
        usadas = {(s.findtext("materia") or "").strip() for s in self._todas(raiz)}
        for c in (cursos.findall("curso") if cursos is not None else []):
            usadas |= {(m.text or "").strip() for m in c.iter("materia")}
        for opt in raiz.iter("optativa"):
            usadas |= {(m.text or "").strip() for m in opt.iter("materia")}
        mats = raiz.find("materias"); quitadas_m = []
        for m in (list(mats.findall("materia")) if mats is not None else []):
            nm = (m.findtext("nombre") or "").strip()
            if nm not in usadas:
                ED.quitar_hijo(arbol, mats, m); quitadas_m.append(nm)
        res["mensaje"] = f"Cursos eliminados: {len(quitados_c)}. Materias eliminadas: {len(quitadas_m)}."
        return bool(quitados_c or quitadas_m)

    def op_generar_sesiones(self, arbol, res):
        raiz = arbol.raiz
        cursos = {(c.findtext("nombre") or "").strip(): c for c in raiz.iter("curso")}
        existentes = {((s.findtext("materia") or "").strip(), (s.findtext("grupo") or "").strip()) for s in self._todas(raiz)}
        tarea = ED.leer(raiz, "tareas/lectivaPorDefecto", None) or "LEC"
        n = 0
        for g in (raiz.find("grupos").findall("grupo") if raiz.find("grupos") is not None else []):
            gn = (g.findtext("nombre") or "").strip(); cu = cursos.get((g.findtext("cursoPerteneciente") or "").strip())
            mc = cu.find("materiasDelCurso") if cu is not None else None
            for m in (mc.findall("materia") if mc is not None else []):
                mn = (m.text or "").strip()
                if not mn or (mn, gn) in existentes:
                    continue
                s = ED.insertar_sesion(arbol, materia=mn, grupo=gn, tarea=tarea)
                try:
                    k = max(1, int(round(float(m.get("numSesiones", "1") or 1))))
                except ValueError:
                    k = 1
                ED.escribir(arbol, s, "duracionSemanal", f"{k:.2f}")
                df = s.find("distribucionSemanal/distribucionFija")
                for _ in range(k - 1):
                    ED.insertar_hijo(arbol, df, ED.nuevo("numSesiones", "1"))
                existentes.add((mn, gn)); n += 1
        res["mensaje"] = f"Sesiones lectivas generadas: {n}."
        return n > 0

    def op_departamentos(self, arbol, res):
        raiz = arbol.raiz
        dep = {(m.findtext("nombre") or "").strip(): (m.findtext("departamento") or "").strip() for m in raiz.iter("materia")
               if m.find("nombre") is not None}
        n = 0
        for s in self._todas(raiz):
            d = dep.get((s.findtext("materia") or "").strip(), "")
            if d and ED.leer(s, "departamento", "") != d:
                ED.set_campo_sesion(arbol, s, "departamento", d); n += 1
        res["mensaje"] = f"Sesiones con el departamento asignado: {n}."
        return n > 0

    # ------------------------------------------------------------ 938 Alejados
    def _alejados(self):
        pg = self.p["938"]
        self.lista_alejados = self.enlazar(ListaAlejados(pg.c[1099]))
        pg.c[1099].setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.enlazar(DobleDesplazamiento(pg.c[1215], pg.c[1216], pg.c[1217]))
        self.enlazar(CasillaD(pg.c[1102], "otros/gruposAlejados/opciones/actualizarAlGenerar", "false"))
        pg.c[1294].setEnabled(False); pg.c[1294].setToolTip("Disponible próximamente")

        def anadir():
            ya = set(self.lista_alejados.valores())
            nombres = [n for n in (ED.leer(g, "nombre", "") for g in self.raiz().iter("grupo") if g.find("nombre") is not None) if n and n not in ya]
            dlg = SeleccionNombres("Añadir grupos", nombres, self)
            if dlg.exec():
                pg.c[1099].addItems(dlg.seleccion())

        def quitar():
            for it in pg.c[1099].selectedItems():
                pg.c[1099].takeItem(pg.c[1099].row(it))
        pg.c[1368].clicked.connect(anadir); pg.c[1098].clicked.connect(quitar)
