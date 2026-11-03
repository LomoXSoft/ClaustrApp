"""«Depurador de condiciones» (planificador de referencia, diálogos 664 y 665; cadenas 879, 915, 33215).
Las condiciones seleccionadas no llegan al motor; el archivo no se modifica."""
from __future__ import annotations
from .textos import TX
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QCheckBox, QLabel,
                               QPushButton, QMessageBox)
from .motor import problema, flexibilizar as F

TITULO = "Depurador de condiciones"
CABECERA = ("Puede buscar soluciones evitando alguna de las condiciones estrictas inicialmente establecidas.\n"
            "De este modo podrá hacer pruebas para determinar aquellas que puedan impedir los resultados.")
PIE = ("  Si hay opciones deshabilitadas es porque las referidas condiciones no se encuentran\n"
       "  establecidas en la configuración o no de forma estricta.\n"
       "  Evitando estas condiciones estrictas no se alteran los datos configurados ni se ve\n"
       "  afectado el proceso de validación, sencillamente desde aquí no llegan al  motor.")
# (título de grupo, [(texto, clave o None)], columnas)
G664 = [
    ("Conmuta todas las posiciones prohibidas por posiciones no preferentes en las plantillas de:",
     [("Materias", "proh_materia"), ("Profesores", "proh_profesor"), ("Aulas", "proh_aula"), ("Tipos de tarea", "proh_tarea"),
      ("Sesiones lectivas", "proh_sesion"), ("Actividades complementarias", "proh_compl"), ("Guardias", "proh_guardia"),
      ("Reuniones", "proh_reunion")], 4),
    ("Conmuta todas las posiciones pefijadas por posiciones preferentes en las plantillas de:",
     [("Sesiones lectivas", "pref_sesion"), ("Actividades complementarias", "pref_compl"), ("Guardias", "pref_guardia"),
      ("Reuniones", "pref_reunion")], 4),
    ("Flexibilizar el uso de las aulas:",
     [("Ofrecer siempre aulas genéricas alternativas.", None), ("Incrementar el número de aulas si es necesario.", None),
      ("Las sesiones de cada asignatura pueden ocupar distinta aula.", "aula_distinta"),
      ("No considerar la capacidad de las aulas.", None)], 2),
    ("Para todos los profesores, eliminar o expresar como preferencias las siguientes restricciones:",
     [(TX("horas_libres_fuera_posiciones_fijadas"), None), ("Mañanas o tardes libres", "r_libres"),
      ("Periodos mutuamente excluyentes", "r_incompat"), ("Mínimo lectivo diario", "r_min"), ("Máximo lectivo diario", "r_max"),
      ("Máximo de lectivas seguidas", "r_seguidas"), (TX("permanencia_maxima_semana"), "r_perm_sem"), (TX("permanencia_maxima_dia"), "r_perm_dia"),
      ("Periodo de descanso antes o después de guardia de recreo.", None)], 3),
]
G665 = [
    ("Flexibilizar condiciones en grupos de alumnos:",
     [("Quitar tardes libres no prefijadas.", "g_tardes"), ("Quitar el límite de la ocupación máxima diaria de cada grupo.", "g_limite"),
      ("Permitir periodos libres que formen huecos en el horario del grupo.", "g_huecos"),
      ("Permitr que los periodos libres estén en las posiciones señaladas como no preferentes.", None),
      ("Conmuta todas las posiciones prohibidas por posiciones no preferentes en sus plantillas.", "proh_grupo")], 1),
    ("Eliminar las condiciones entre distintos bloques de sesiones lectivas:",
     [("En días distintos", "bl_distintos"), (TX("seguidas"), "bl_consecutivas"), (TX("no_seguidas"), None),
      ("No simultáneas", None), ("Previas o posteriores", None), ("Separadas -n- días", None)], 3),
    ("Eliminar las condiciones sobre las sesiones de cada bloque:",
     [("Permitir recreos entre las sesiones de duración múltiple.", None),
      (TX("recreos_ayudan_comprobar_condiciones_sesiones"), None),
      ("No obligar estrictamente a impartirse en días alternos.", "no_alternos"),
      ("No obligar estrictamente a impartirse en días consecutivos.", "no_consecutivos")], 1),
    ("Flexibilizar la distribución semanal de las sesiones lectivas:",
     [("Flexibilizar la carga diaria de las sesiones de cada asignatura.", None),
      (TX("aceptar_sesiones_partidas_dentro_mismo"), None)], 1),
    ("Flexibilizar la distribución semanal de las actividades complementarias:",
     [("Flexibilizar la carga diaria de las actividades.", None), (TX("aceptar_actividades_partidas_dentro_mismo"), None)], 1),
]


def _grupos(L, grupos, disp, cajas):
    for titulo, items, cols in grupos:
        gb = QGroupBox(); g = QGridLayout(gb); g.addWidget(QLabel(titulo), 0, 0, 1, cols)
        for i, (txt, clave) in enumerate(items):
            c = QCheckBox(txt); c.setEnabled(clave in disp)
            g.addWidget(c, 1 + i // cols, i % cols)
            if clave:
                cajas[clave] = c
        L.addWidget(gb)


class DialogoOtras(QDialog):
    """Diálogo 665 «Flexibilizar otras condiciones»."""
    def __init__(self, parent, disp, valores):
        super().__init__(parent); self.setWindowTitle("Flexibilizar otras condiciones"); self.cajas = {}
        L = QVBoxLayout(self)
        L.addWidget(QLabel("Flexibilizar otras condiciones que pudieran impedir las soluciones completas:"))
        _grupos(L, G665, disp, self.cajas)
        for k, c in self.cajas.items():
            c.setChecked(bool(valores.get(k)) and c.isEnabled())
        h = QHBoxLayout(); h.addWidget(QLabel(PIE)); h.addStretch()
        ok = QPushButton("Aceptar"); ok.setDefault(True); ok.clicked.connect(self.accept)
        no = QPushButton("Cancelar"); no.clicked.connect(self.reject); h.addWidget(ok); h.addWidget(no); L.addLayout(h)

    def valores(self):
        return {k: c.isChecked() for k, c in self.cajas.items()}


class DialogoDepurador(QDialog):
    """Diálogo 664 «Depurador de condiciones»."""
    def __init__(self, win):
        super().__init__(win); self.win = win; self.setWindowTitle(TITULO)
        self.pb = problema.construir(win.proyecto); self.disp = F.disponibles(self.pb)
        self.cajas = {}; self.otras = {}
        L = QVBoxLayout(self); L.addWidget(QLabel(CABECERA))
        L.addWidget(QLabel("Flexibilizar las condiciones que más comunmente impiden los resultados completos:"))
        _grupos(L, G664, self.disp, self.cajas)
        h = QHBoxLayout()
        self.b_otras = QPushButton("Flexibilizar otras condiciones que pueden impedir resultados completos")
        self.b_otras.clicked.connect(self.abrir_otras); h.addWidget(self.b_otras); h.addStretch()
        v = QVBoxLayout()
        self.b_lanzar = QPushButton(TX("calcular_sin_condiciones_marcadas")); self.b_lanzar.setDefault(True)
        self.b_lanzar.clicked.connect(self.lanzar)
        self.b_conj = QPushButton("Busca conjuntos mínimos de sesiones que no encajan"); self.b_conj.clicked.connect(self.analizar)
        self.b_filtr = QPushButton(TX("calcular_sin_condiciones_marcadas_ni"))
        self.b_filtr.clicked.connect(self.lanzar_filtrado)
        for b in (self.b_lanzar, self.b_conj, self.b_filtr):
            v.addWidget(b)
        h.addLayout(v); v2 = QVBoxLayout(); bc = QPushButton("Cancelar"); bc.clicked.connect(self.reject); v2.addWidget(bc)
        v2.addStretch(); h.addLayout(v2); L.addLayout(h); L.addWidget(QLabel(PIE))

    def abrir_otras(self):
        d = DialogoOtras(self, self.disp, self.otras)
        if d.exec():
            self.otras = d.valores()

    def flex(self):
        f = {k: c.isChecked() for k, c in self.cajas.items()}; f.update(self.otras); return f

    def preparar(self):
        return F.aplicar(self.pb, self.flex())

    def lanzar(self):
        q, notas = self.preparar()
        if not notas:
            QMessageBox.information(self, TITULO, "No ha seleccionado ninguna condición."); return
        from .ventana_motor import VentanaMotor
        self.win.ventana_motor = VentanaMotor(self.win.proyecto, self.win, pb=q, anotacion=notas, pb_original=self.pb)
        self.win.ventana_motor.show(); self.accept()

    def lanzar_filtrado(self):
        """Botón id=4: condiciones seleccionadas + elementos filtrados (diálogo 690 en modo filtro)."""
        from .parcial import DialogoParcial
        from .motor import parcial as PA
        dp = DialogoParcial(self.win, self.pb, modo="filtro")
        if not dp.exec():
            return
        base = dp.filtrar(); q, notas = F.aplicar(base, self.flex())
        q["parcial"] = base["parcial"]
        if notas:
            notas = [TX("cuidado_resultado_calculado_condiciones_obligatorias")] + notas
        notas += PA.anotacion(self.pb, base)
        from .ventana_motor import VentanaMotor
        self.win.ventana_motor = VentanaMotor(self.win.proyecto, self.win, pb=q, anotacion=notas, pb_original=self.pb,
                                              parcial=True)
        self.win.ventana_motor.show(); self.accept()

    def analizar(self):
        from .analizador import DialogoAnalizador
        DialogoAnalizador(self.win, self.pb).exec()
