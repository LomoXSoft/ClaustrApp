"""Ventana del motor y visor sencillo de resultados (.lphr).

Muestra el progreso del cálculo (tiempo, peso, sesiones sin colocar, avisos), las pestañas de resultados y
el botón para abrir el resultado en el editor.
"""
from __future__ import annotations
from .textos import TX
from .motor import categorias as CAT
import os, time, datetime
from collections import defaultdict
from PySide6.QtCore import Qt, QTimer, QSettings
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit, QGroupBox,
                               QProgressBar, QPushButton, QTabWidget, QTreeWidget, QTreeWidgetItem, QWidget,
                               QPlainTextEdit, QFileDialog, QMessageBox, QComboBox, QTableWidget, QTableWidgetItem,
                               QHeaderView, QSpinBox, QStyle)
from . import APP_NAME, resultado as RES, comprobador
from .motor import problema

NIVELES = 20   # «Nivel de optimización rtdo. actual … de 20»


def _ro(ancho=70):
    e = QLineEdit(); e.setReadOnly(True); e.setFixedWidth(ancho); e.setAlignment(Qt.AlignRight)
    return e


def avisos_previos(p, pb) -> list[str]:
    """Avisos de precaución antes de generar (cargas imposibles, sesiones sin hueco posible)."""
    out = []
    lect = defaultdict(int)
    for s in pb["slots"]:
        if s["tipo"] == "lectivo":
            lect[s["marco"]] += 1
    carga_g, carga_p = defaultdict(int), defaultdict(int)
    for u in pb["unidades"]:
        n = u["variable"]["total"] if u.get("variable") else sum(u["piezas"])
        for g in u["grupos"]:
            carga_g[g] += n
        for pr in u["profesores"]:
            carga_p[pr] += n
    for g, n in carga_g.items():
        m = pb["marco_grupo"].get(g)
        if m in lect and n > lect[m]:
            out.append(f"El grupo {g} tiene {n} periodos y su marco solo {lect[m]} tramos lectivos.")
        elif m in lect and n == lect[m]:
            out.append(f"El grupo {g} ocupa todos los tramos lectivos de su marco ({n}).")
    for pr, n in carga_p.items():
        g = sum(it["n"] for gg in pb["guardias"] for it in gg["integrantes"] if it["profesor"] == pr and not gg["recreo"])
        m = pb["marco_prof"].get(pr)
        if m in lect and n + g > lect[m] + 5:
            out.append(f"Un profesor ({pr}) tiene {n} periodos lectivos y {g} guardias.")
    tmp = {x.id: x.tmp for x in p.sesiones}
    for u in pb["unidades"]:
        if len({tmp.get(i) for i in u["sesiones"]}) > 1:
            out.append(f"Las sesiones simultáneas {', '.join(u['sesiones'])} tienen distribuciones distintas; "
                       f"se usa la de la sesión {u['sesiones'][0]}.")
        if u["prohibidos"] and len(u["prohibidos"]) >= sum(1 for s in pb["slots"] if s["marco"] == u["marco"] and s["tipo"] == "lectivo"):
            out.append(f"Las sesiones {', '.join(u['sesiones'])} tienen todos los tramos prohibidos.")
    return out


class VentanaMotor(QDialog):
    def __init__(self, proyecto, parent=None, segundos=None, hilos=None, autoarranque=True, autoguardar=None,
                 pb=None, anotacion=None, pb_original=None, parcial=False):
        super().__init__(parent)
        self.p = proyecto
        st = QSettings()
        self.segundos = int(segundos or st.value("motor/segundos", 60))
        self.hilos = int(hilos or st.value("motor/hilos", max(1, min(8, os.cpu_count() or 4))))
        self.setWindowTitle(f"{APP_NAME} - Motor de horarios - {os.path.basename(proyecto.ruta)}")
        # autoguardado de cada resultado como <nombre>R1.lphr, R2... junto al archivo
        self.autoguardar = (st.value("motor/autoguardar", "true") in (True, "true")) if autoguardar is None else autoguardar
        self.n_res = 0; self.guardados = []
        self.pb_original = pb_original; self.parcial = parcial
        self.anotacion = list(anotacion or [])   # condiciones estrictas deshabilitadas (Depurador)
        self.setMinimumSize(760, 640)
        self.motor = None; self.doc = None; self.t_inicio = None; self.t_mejor = None
        self.pausa_ini = None; self.pausado_total = 0.0; self.ultimo = {}
        self._construir()
        self.pb = pb if pb is not None else problema.construir(proyecto)
        self.precauciones = avisos_previos(proyecto, self.pb)
        self._rellenar_precaucion()
        self.ed_origen.setText(os.path.basename(proyecto.ruta))
        self.lbl_archivo.setText(TX("archivo_datos") + proyecto.ruta)
        self._rellenar_rechazos()
        self.timer = QTimer(self); self.timer.timeout.connect(self._sondear)
        if autoarranque:
            QTimer.singleShot(0, self.iniciar)

    # ------------------------------------------------------------------ interfaz
    def _construir(self):
        L = QVBoxLayout(self)
        self.lbl_archivo = QLabel(""); self.lbl_archivo.setWordWrap(True); L.addWidget(self.lbl_archivo)
        cab = QLabel(TX("calculando")); f = cab.font(); f.setBold(True); cab.setFont(f)
        self.lbl_cab = cab; L.addWidget(cab)
        self.ed_estado = QLineEdit(); self.ed_estado.setReadOnly(True)
        self.ed_estado.setMinimumHeight(30); fe = self.ed_estado.font(); fe.setPointSize(fe.pointSize() + 2); self.ed_estado.setFont(fe)
        L.addWidget(self.ed_estado)
        fila = QHBoxLayout(); L.addLayout(fila)
        g = QGridLayout(); fila.addLayout(g)
        self.ed = {}
        for i, (k, txt) in enumerate([("tiempo", "Tiempo total de proceso:"), ("inicio", "Hora de inicio:"),
                                      ("mejor", "Hora del mejor resultado:"), ("avisos", "Avisos:"),
                                      ("peso", "Peso de optimización:"), ("nc", TX("sin_colocar_2")),
                                      ("pnc", "Peso de no colocadas:")]):
            g.addWidget(QLabel(txt), i, 0); self.ed[k] = _ro(); g.addWidget(self.ed[k], i, 1)
        self.lbl_prec = QLabel("Hay avisos de precaución")
        self.ico_prec = QLabel(); self.ico_prec.setPixmap(self.style().standardIcon(QStyle.SP_MessageBoxWarning).pixmap(16, 16))
        hp = QHBoxLayout(); hp.addWidget(self.ico_prec); hp.addWidget(self.lbl_prec); hp.addStretch()
        g.addLayout(hp, 7, 0, 1, 2)
        fila.addSpacing(20)
        caja = QGroupBox(); fila.addWidget(caja, 1)
        cg = QGridLayout(caja)
        self.ed_completos = _ro(50); self.ed_intentos = _ro(50)
        h1 = QHBoxLayout(); h1.addWidget(self.ed_completos); h1.addWidget(QLabel("Resultados completos encontrados")); h1.addStretch()
        h2 = QHBoxLayout(); h2.addWidget(QLabel("en ")); h2.addWidget(self.ed_intentos); h2.addWidget(QLabel("intentos")); h2.addStretch()
        cg.addLayout(h1, 0, 0, 1, 3); cg.addLayout(h2, 1, 0, 1, 3)
        self.lbl_fase = QLabel("Buscando resultado"); self.lbl_fase.setWordWrap(True)
        cg.addWidget(self.lbl_fase, 2, 0, 1, 3)
        self.lbl_pct = QLabel("0%"); self.barra = QProgressBar(); self.barra.setRange(0, 100); self.barra.setTextVisible(False)
        cg.addWidget(self.lbl_pct, 3, 0); cg.addWidget(self.barra, 3, 1, 1, 2)
        hl = QHBoxLayout(); hl.addWidget(QLabel("Tiempo máximo (s):"))
        self.sp_seg = QSpinBox(); self.sp_seg.setRange(5, 36000); self.sp_seg.setValue(self.segundos); hl.addWidget(self.sp_seg); hl.addStretch()
        cg.addLayout(hl, 4, 0, 1, 3)
        hb = QHBoxLayout()
        self.b_iniciar = QPushButton("Iniciar"); self.b_pausa = QPushButton("Pausa"); self.b_parar = QPushButton("Detener")
        self.b_ver = QPushButton("Ver el resultado"); self.b_guardar = QPushButton("Guardar resultado..."); self.b_cerrar = QPushButton("Cerrar")
        self.b_parar.setToolTip(TX("motor_sin_terminar"))
        self.b_cerrar.setToolTip(TX("termina_cierra_motor"))
        for b in (self.b_iniciar, self.b_pausa, self.b_parar):
            hb.addWidget(b)
        cg.addLayout(hb, 5, 0, 1, 3)
        hb2 = QHBoxLayout()
        for b in (self.b_ver, self.b_guardar, self.b_cerrar):
            hb2.addWidget(b)
        cg.addLayout(hb2, 6, 0, 1, 3)
        self.b_iniciar.clicked.connect(self.iniciar); self.b_pausa.clicked.connect(self.pausa)
        self.b_parar.clicked.connect(self.parar); self.b_ver.clicked.connect(self.ver_resultado)
        self.b_guardar.clicked.connect(self.guardar); self.b_cerrar.clicked.connect(self.close)
        # pestañas
        self.tabs = QTabWidget(); L.addWidget(self.tabs, 1)
        self.t_nc = QTreeWidget(); self.t_nc.setHeaderLabels(["Elemento", "Periodos", "Detalle"])
        self.t_prec = QTreeWidget(); self.t_prec.setHeaderLabels(["Precaución"])
        self.t_res = QPlainTextEdit(); self.t_res.setReadOnly(True)
        opt = QWidget(); og = QGridLayout(opt)
        og.addWidget(QLabel("En el resultado..."), 0, 0, 1, 2)
        hn = QHBoxLayout(); hn.addWidget(QLabel("Nivel de optimización rtdo. actual")); self.ed_nivel = _ro(30)
        hn.addWidget(self.ed_nivel); hn.addWidget(QLabel("de 20")); hn.addStretch()
        og.addLayout(hn, 0, 2, 1, 2)
        self.barra_nivel = QProgressBar(); self.barra_nivel.setRange(0, NIVELES); self.barra_nivel.setTextVisible(False)
        og.addWidget(self.barra_nivel, 1, 0, 1, 4)
        self.opt = {}
        # Claves: códigos internos (motor/categorias) o claves propias de la ventana; el texto se traduce al mostrar
        izq = ["no_colocadas", "peso_no_colocadas", "huecos_alumnos", "huecos_profes", "dias_consecutivos", "horas_extremas"]
        der = ["aula_no_preferente", "ocupaciones_no_pref", "guardias_extremas", "sueltas_variable", "peso_provisional", "cota"]
        rot = {"no_colocadas": "Sesiones no colocadas", "peso_no_colocadas": TX("peso_lo_no_colocado"),
               "peso_provisional": "Peso provisional:", "cota": "Cota inferior"}
        for col, lista in ((0, izq), (2, der)):
            for i, t in enumerate(lista):
                og.addWidget(QLabel(rot.get(t) or CAT.nombre(t)), 2 + i, col); self.opt[t] = _ro(60)
                og.addWidget(self.opt[t], 2 + i, col + 1)
        og.addWidget(QLabel(TX("datos_partida")), 9, 0); self.ed_origen = QLineEdit(); self.ed_origen.setReadOnly(True)
        og.addWidget(self.ed_origen, 9, 1, 1, 3); og.setRowStretch(10, 1)
        self.tabs.addTab(self.t_nc, TX("sin_colocar")); self.tabs.addTab(self.t_prec, "Precaución")
        self.tabs.addTab(self.t_res, "Resumen"); self.tabs.addTab(opt, TX("optimizacion_curso"))
        self.t_rech = QTreeWidget(); self.t_rech.setHeaderLabels(["Alumnos / profesor", "Tramos rechazados"])
        self.t_rint = QTreeWidget(); self.t_rint.setHeaderLabels(["Sesión no colocada / tramo", ""])
        self.t_mas = QTreeWidget(); self.t_mas.setHeaderLabels(["Sesión", "Rechazados", "% del marco"])
        self.tabs.addTab(self.t_rech, TX("rechazos_alumnado_profesorado"))
        self.tabs.addTab(self.t_rint, TX("rechazos_este_intento"))
        self.tabs.addTab(self.t_mas, TX("sesiones_mas_rechazadas"))
        self._botones()

    def _botones(self):
        corriendo = self.motor is not None and self.motor.vivo() and self.doc is None
        self.b_iniciar.setEnabled(not corriendo); self.sp_seg.setEnabled(not corriendo)
        self.b_pausa.setEnabled(corriendo); self.b_parar.setEnabled(corriendo)
        self.b_ver.setEnabled(self.doc is not None); self.b_guardar.setEnabled(self.doc is not None)
        self.b_pausa.setText("Continuar" if self.motor and self.motor.pausado else "Pausa")
        if corriendo:
            self.lbl_cab.setText(TX("pausa_no_salen_resultados_completos") if self.motor.pausado and not self.ultimo
                                 else TX("calculando"))

    def _rellenar_rechazos(self):
        from .motor import mensajes
        el, ses = mensajes.rechazos(self.pb)
        self.t_rech.clear(); self.t_mas.clear()
        for t, n, c in el:
            self.t_rech.addTopLevelItem(QTreeWidgetItem([("Alumnos de " if t == "grupo" else "Profesor ") + n, str(c)]))
        if not el:
            self.t_rech.addTopLevelItem(QTreeWidgetItem(["No hay rechazos por plantilla"]))
        for et, sesiones, r, tot in ses:
            self.t_mas.addTopLevelItem(QTreeWidgetItem([f"{et} [{', '.join(sesiones)}]", str(r), f"{100 * r // max(1, tot)}%"]))

    def _rellenar_precaucion(self, extra=()):
        self.t_prec.clear()
        lista = list(self.precauciones) + list(extra)
        for t in lista:
            it = QTreeWidgetItem([t]); it.setIcon(0, self.style().standardIcon(QStyle.SP_MessageBoxWarning)); self.t_prec.addTopLevelItem(it)
        if not lista:
            self.t_prec.addTopLevelItem(QTreeWidgetItem([TX("sin_avisos")]))
        self.lbl_prec.setVisible(bool(lista)); self.ico_prec.setVisible(bool(lista))
        self.ed["avisos"].setText(str(len(lista)))

    # ------------------------------------------------------------------ control
    def iniciar(self):
        from .motor.proceso import MotorEnProceso
        self.segundos = self.sp_seg.value(); QSettings().setValue("motor/segundos", self.segundos)
        self.doc = None; self.ultimo = {}; self.pausado_total = 0.0; self.t_mejor = None
        self.t_nc.clear(); self.t_res.clear()
        self.motor = MotorEnProceso(self.pb, segundos=self.segundos, hilos=self.hilos)
        self.motor.iniciar()
        self.t_inicio = time.time()
        self.ed["inicio"].setText(datetime.datetime.now().strftime("%H:%M:%S"))
        self.ed_estado.setText("Buscando un resultado..."); self.lbl_fase.setText("Buscando resultado")
        self.timer.start(200); self._botones()

    def pausa(self):
        if not self.motor:
            return
        if self.motor.pausado:
            self.motor.reanudar(); self.pausado_total += time.time() - self.pausa_ini
            self.lbl_fase.setText(self._fase_txt)
        else:
            self.motor.pausar(); self.pausa_ini = time.time()
            self._fase_txt = self.lbl_fase.text(); self.lbl_fase.setText("Pausado")
        self._botones()

    def parar(self):
        if self.motor and self.motor.vivo():
            self.motor.parar(); self.lbl_fase.setText("Deteniendo el motor...")

    def _activo(self):
        if not self.t_inicio:
            return 0.0
        fin = self.pausa_ini if self.motor and self.motor.pausado else time.time()
        return fin - self.t_inicio - self.pausado_total

    def _sondear(self):
        if not self.motor:
            return
        for e in self.motor.eventos():
            ev = e.get("evento")
            if ev == "fase":
                self.lbl_fase.setText(e["texto"])
            elif ev == "solucion":
                self.ultimo = e; self.t_mejor = datetime.datetime.now().strftime("%H:%M:%S")
                self._mostrar_solucion(e)
            elif ev == "peso_provisional" and self.ultimo is not None:
                # peso real (modelo completo) del resultado de la fase 1, antes de empezar a optimizar
                self.ultimo = dict(self.ultimo, peso=e["peso"], provisional=True)
                self._mostrar_solucion(self.ultimo)
            elif ev == "fin":
                self._terminado(e["resultado"])
            elif ev == "error":
                self.timer.stop(); self._botones()
                QMessageBox.critical(self, APP_NAME, "Error en el motor:\n\n" + e["texto"][-1500:])
        t = self._activo()
        if self.doc is None:
            self.ed["tiempo"].setText(f"{int(t) // 60}:{int(t) % 60:02d}")
            pct = min(100, int(100 * t / max(1, self.segundos)))
            self.barra.setValue(pct); self.lbl_pct.setText(f"{pct}%")
        if self.doc is None and not self.motor.vivo() and self.motor.resultado is None:
            self.motor.eventos()
        self._botones()

    def _mostrar_solucion(self, e):
        self.ed_completos.setText(str(e["completos"])); self.ed_intentos.setText(str(e["n"]))
        self.ed["mejor"].setText(self.t_mejor or "")
        peso = "—" if e.get("peso") is None else e["peso"]
        self.ed["peso"].setText(str(peso)); self.ed["nc"].setText(str(e["no_colocadas"]))
        nc = e["no_colocadas"]
        self.ed_estado.setText(("Resultado completo: " if nc == 0 else "Resultado incompleto: ")
                               + (("sin optimizar todavía" if e.get("peso") is None else
                                  f"peso {peso} (sin optimizar todavía)" if e.get("provisional") else f"peso {peso}"))
                               + ("" if nc == 0 else f", {nc} no colocadas"))
        self.opt["peso_provisional"].setText(str(peso))
        cota = e.get("cota")
        if nc == 0 and e["peso"] and cota is not None:
            cota_p = max(0.0, min(float(e["peso"]), float(cota)))
            nivel = int(round(NIVELES * cota_p / e["peso"])) if e["peso"] else NIVELES
            self.ed_nivel.setText(str(nivel)); self.barra_nivel.setValue(nivel)
            self.opt["cota"].setText(f"{cota_p:.0f}")

    def _terminado(self, r):
        self.timer.stop()
        e = r.get("estadisticas", {})
        self.doc = RES.crear(r, self.p.ruta, {"nombre": "cpsat", "segundos": self.segundos, "hilos": self.hilos})
        if self.parcial and self.pb and self.pb.get("parcial"):
            self.doc["parcial"] = self.pb["parcial"]
        if not r.get("sesiones") and r.get("estado") not in ("OPTIMAL", "FEASIBLE"):
            self.ed_estado.setText("No se ha encontrado ningún resultado"); self.doc = None; self._botones(); return
        try:
            self.informe = comprobador.comprobar(self.p, self.doc)
        except Exception as ex:  # noqa: BLE001
            self.informe = None; self.precauciones.append(f"No se pudo comprobar el resultado: {ex}")
        nc = e.get("no_colocadas", 0) + e.get("guardias_no_colocadas", 0)
        if e.get("parado"):
            fase = "Motor detenido"
        elif e.get("sin_optimizar"):
            fase = "Resultado sin optimizar"
        elif e.get("optimo"):
            fase = "Resultado optimizado"
        else:
            fase = "Resultado completo" if nc == 0 else "Resultado incompleto"
        self.lbl_fase.setText(fase)
        self.ed_estado.setText(("Resultado completo: " if nc == 0 else "Resultado incompleto: ") +
                               f"peso {e.get('peso')}, tiempo {e.get('tiempo')} s")
        self.lbl_cab.setText("  Resultado completo:  " if nc == 0 else "  Resultado incompleto:  ")
        self.n_res += 1
        if self.anotacion:
            cab = TX("cuidado_resultado_parcial") if self.parcial else TX("cuidado_resultado_calculado_condiciones_obligatorias")
            self.doc["anotacion"] = ([] if self.anotacion[0].startswith("¡Atención!") else [cab]) + self.anotacion
            if self.pb_original is not None:
                from .motor.flexibilizar import violaciones
                self.doc["flexibilizadas"] = violaciones(self.pb_original, self.doc)
        self._autoguardar()
        self.barra.setValue(100); self.lbl_pct.setText("100%")
        t = e.get("tiempo", 0) or 0
        self.ed["tiempo"].setText(f"{int(t) // 60}:{int(t) % 60:02d}")
        self.ed["peso"].setText(str(e.get("peso", ""))); self.ed["nc"].setText(str(e.get("no_colocadas", "")))
        self.ed["pnc"].setText(str(e.get("peso_no_colocadas", "")))
        self.ed_completos.setText(str(e.get("completos", ""))); self.ed_intentos.setText(str(e.get("resultados", "")))
        res = CAT.normalizar(e.get("resumen", {}))
        for k, w in self.opt.items():
            if k in res:
                w.setText(str(res[k]))
        self.opt["no_colocadas"].setText(str(e.get("no_colocadas", 0)))
        self.opt["peso_no_colocadas"].setText(str(e.get("peso_no_colocadas", 0)))
        for k in ("huecos_alumnos", "huecos_profes", "aula_no_preferente"):
            self.opt[k].setText(str(res.get(k, 0)))
        if e.get("peso") and nc == 0 and (e.get("cota") is not None or e.get("optimo")):
            cota = max(0.0, min(float(e["peso"]), float(e.get("cota") or 0)))
            nivel = NIVELES if e.get("optimo") else int(round(NIVELES * cota / e["peso"]))
            self.ed_nivel.setText(str(nivel)); self.barra_nivel.setValue(nivel)
        # no colocadas
        for n in self.doc["no_colocadas"]:
            if n["tipo"] == "sesion":
                it = QTreeWidgetItem([f"Sesiones {', '.join(n['sesiones'])}", str(n.get("periodos", "")), n.get("etiqueta", "")])
            else:
                it = QTreeWidgetItem([f"{n['tipo'].capitalize()} {n['nombre']}", str(n.get("cantidad", "")), n.get("profesor", "")])
            self.t_nc.addTopLevelItem(it)
        if not self.doc["no_colocadas"]:
            self.t_nc.addTopLevelItem(QTreeWidgetItem(["Todas las sesiones, guardias y reuniones están colocadas"]))
        extra = [f"{c}: {t}" for c, t in (self.informe.avisos if self.informe else [])]
        if self.informe and not self.informe.valido:
            extra = [f"ERROR de comprobación — {c}: {t}" for c, t in self.informe.errores] + extra
        from .motor import mensajes
        extra = mensajes.mensajes_resultado(self.pb, self.doc, self.n_res) + extra
        if self.anotacion:
            extra = [f"(R{self.n_res}) " + x for x in self.doc.get("anotacion", [])] + extra
        if self.guardados:
            extra.append(TX("archivo_creado_r", n=self.n_res, ruta=self.guardados[-1]))
        self.t_rint.clear()
        for et, mot in mensajes.rechazos_intento(self.pb, self.doc):
            it = QTreeWidgetItem([et, f"{len(mot)} tramos"]); self.t_rint.addTopLevelItem(it)
            for m in mot:
                it.addChild(QTreeWidgetItem([m]))
        if self.t_rint.topLevelItemCount() == 0:
            self.t_rint.addTopLevelItem(QTreeWidgetItem([f"(R{self.n_res}) Todas las sesiones lectivas están colocadas"]))
        self._rellenar_precaucion(extra)
        self.t_res.setPlainText(RES.resumen_texto(self.doc) + "\n\nComprobador independiente: " +
                                (("válido" if self.informe.valido else f"{len(self.informe.errores)} errores")
                                 if self.informe else "no disponible"))
        self.tabs.setCurrentIndex(2)
        self._botones()

    def _autoguardar(self):
        if not self.autoguardar or not self.doc or not self.p.ruta:
            return
        base = os.path.splitext(self.p.ruta)[0]
        k = self.n_res
        while os.path.exists(f"{base}R{k}{RES.EXTENSION}"):      # nunca sobrescribe otro resultado
            k += 1
        ruta = f"{base}R{k}{RES.EXTENSION}"
        try:
            RES.guardar(self.doc, ruta); self.guardados.append(ruta)
        except OSError as ex:
            self.precauciones.append(f"No se pudo guardar el resultado: {ex}")

    def guardar(self):
        if not self.doc:
            return
        base = os.path.splitext(self.p.ruta)[0] + RES.EXTENSION
        ruta, _ = QFileDialog.getSaveFileName(self, "Guardar resultado", base, RES.FILTRO_LPHR)
        if ruta:
            RES.guardar(self.doc, ruta)

    def ver_resultado(self):
        if self.doc:
            VisorResultado(self.p, self.doc, self).exec()

    def closeEvent(self, ev):
        if self.motor and self.motor.vivo():
            if QMessageBox.question(self, APP_NAME, TX("motor_va_cerrar_seguir")) != QMessageBox.Yes:
                ev.ignore(); return
            self.motor.terminar()
        self.timer.stop()
        ev.accept()


class VisorResultado(QDialog):
    """Resumen y rejilla semanal por grupo, profesor o aula de un resultado .lphr."""
    def __init__(self, p, doc, parent=None):
        super().__init__(parent)
        self.p, self.doc = p, doc
        self.setWindowTitle(f"Resultado - {doc.get('configuracion', {}).get('archivo', '')}")
        self.resize(900, 620)
        L = QVBoxLayout(self)
        self.txt = QLabel(RES.resumen_texto(doc).split("\n\n")[0].replace("\n", "   ·   ")); self.txt.setWordWrap(True)
        L.addWidget(self.txt)
        if p is not None and doc.get("configuracion", {}).get("sha256") and not RES.corresponde(doc, p.ruta):
            w = QLabel("Atención: el resultado se generó con otra versión de la configuración."); w.setStyleSheet("color:#a00")
            L.addWidget(w)
        h = QHBoxLayout(); L.addLayout(h)
        self.cb_tipo = QComboBox(); self.cb_tipo.addItems(["Grupos", "Profesores", "Aulas"])
        self.cb_el = QComboBox(); self.cb_el.setMinimumWidth(240)
        h.addWidget(QLabel("Ver:")); h.addWidget(self.cb_tipo); h.addWidget(self.cb_el); h.addStretch()
        self.tabla = QTableWidget(); L.addWidget(self.tabla, 1)
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tabla.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.tabla.setWordWrap(True); self.tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        b = QPushButton("Cerrar"); b.clicked.connect(self.accept); L.addWidget(b, 0, Qt.AlignRight)
        self._indexar()
        self.cb_tipo.currentIndexChanged.connect(self._lista); self.cb_el.currentIndexChanged.connect(self._pintar)
        self._lista()

    def _indexar(self):
        ses = {s.id: s for s in self.p.sesiones}
        self.ocup = {"Grupos": defaultdict(list), "Profesores": defaultdict(list), "Aulas": defaultdict(list)}
        for pz in self.doc["sesiones"]:
            for sid in pz["sesiones"]:
                s = ses.get(sid)
                if not s:
                    continue
                txt = f"{s.materia}\n{s.grupo}" + (f"\n{', '.join(pz['aulas'])}" if pz["aulas"] else "")
                for t in pz["tramos"]:
                    for g in [s.grupo] + s.otros_grupos:
                        self.ocup["Grupos"][g].append((pz["marco"], pz["dia"], t, f"{s.materia}\n{s.profesor}"))
                    if s.profesor:
                        self.ocup["Profesores"][s.profesor].append((pz["marco"], pz["dia"], t, txt))
            for a in pz["aulas"]:
                for t in pz["tramos"]:
                    self.ocup["Aulas"][a].append((pz["marco"], pz["dia"], t, ", ".join(pz["sesiones"])))
        for g in self.doc["guardias"]:
            self.ocup["Profesores"][g["profesor"]].append((g["marco"], g["dia"], g["tramo"], f"Guardia\n{g['servicio']}"))
        for c in self.doc["complementarias"]:
            self.ocup["Profesores"][c["profesor"]].append((c["marco"], c["dia"], c["tramo"], c["tarea"]))
        integ = {}
        rx = self.p.doc.raiz.find("reuniones")
        for r in (rx.findall("reunion") if rx is not None else []):
            n = r.find("nombre"); ints = r.find("integrantes")
            integ[(n.text or "").strip() if n is not None else ""] = [((i.text or "").strip()) for i in (ints.findall("integrante") if ints is not None else [])]
        for r in self.doc["reuniones"]:
            for pr in integ.get(r["reunion"], []):
                for t in r["tramos"]:
                    self.ocup["Profesores"][pr].append((r["marco"], r["dia"], t, f"Reunión\n{r['reunion']}"))

    def _lista(self):
        self.cb_el.blockSignals(True); self.cb_el.clear()
        self.cb_el.addItems(sorted(self.ocup[self.cb_tipo.currentText()]))
        self.cb_el.blockSignals(False); self._pintar()

    def _pintar(self):
        lst = self.ocup[self.cb_tipo.currentText()].get(self.cb_el.currentText(), [])
        marcos = sorted({m for m, *_ in lst}) or list(self.p.marcos)[:1]
        dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
        filas = []
        for mid in marcos:
            filas += [(mid, t) for t in self.p.marcos[mid].filas()]
        ndias = max(len(self.p.marcos[m].dias) for m in marcos)
        self.tabla.clear(); self.tabla.setRowCount(len(filas)); self.tabla.setColumnCount(ndias)
        self.tabla.setHorizontalHeaderLabels(dias[:ndias])
        self.tabla.setVerticalHeaderLabels([(f"{m} " if len(marcos) > 1 else "") + f"{t.entrada}-{t.salida}" for m, t in filas])
        pos = {(m, t.indice): i for i, (m, t) in enumerate(filas)}
        for i, (m, t) in enumerate(filas):
            if t.tipo != "lectivo":
                for d in range(ndias):
                    it = QTableWidgetItem(""); it.setBackground(QColor(235, 235, 235)); self.tabla.setItem(i, d, it)
        for m, d, t, txt in lst:
            i = pos.get((m, t))
            if i is None or d >= ndias:
                continue
            prev = self.tabla.item(i, d)
            texto = (prev.text() + "\n" if prev and prev.text() else "") + txt
            it = QTableWidgetItem(texto); it.setTextAlignment(Qt.AlignCenter)
            it.setBackground(QColor(255, 236, 200) if txt.startswith(("Guardia", "Reunión")) else QColor(214, 230, 250))
            self.tabla.setItem(i, d, it)
