"""«Pesos de los criterios de optimización» (planificador de referencia, DIALOG 146; menú 32812).

20 deslizadores 0-10 persistidos en datosGHC/criterios con sus etiquetas reales (schema.txt). El motor
(motor/problema.py -> pb["pesos"]) los usa como pesos de penalización; ver SOPORTE para los que aún no aplica.
"""
from __future__ import annotations
from .textos import TX
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QLabel, QSlider,
                               QPushButton, QToolButton, QMessageBox, QDialogButtonBox)
from . import APP_NAME, edicion as ED

TITULO = TX("pesos_criterios_optimizacion")
# (grupo, [(etiqueta del recurso, ruta en datosGHC/criterios, ayuda)]) en el orden del recurso
GRUPOS = [
    ("Evitar los periodos desocupados en el horario:", [
        ("De los alumnos", "huecosEnHorario/huecosEnGrupos", "Penaliza cada periodo libre entre dos clases de un grupo."),
        ("De los profesores", "huecosEnHorario/huecosEnProfesores", "Penaliza cada periodo libre entre dos ocupaciones de un profesor."),
    ]),
    ("Observar o evitar en las sesiones de cada asignatura:", [
        ("Impartidas en días seguidos o alternos", "colocarSesionesLectivas/enDiasConsecutivos", "Penaliza las sesiones de una asignatura en días seguidos cuando se pide «preferiblemente» días no seguidos."),
        ("En el aula preferente", "colocarSesionesLectivas/enAulaNoPreferente", "Penaliza usar un aula alternativa en lugar de la asignada."),
        ("Sin cambios de aula", "colocarSesionesLectivas/conCambiosDeAula", "Penaliza que las sesiones de una asignatura usen aulas distintas."),
        ("Evitar que coincidan en los extremos", "colocarSesionesLectivas/enHorasExtremas", "Penaliza las sesiones marcadas a primera o última hora."),
        ("Evitar coincidan después del recreo", "colocarSesionesLectivas/coincidanPorLaTarde", "Penaliza que varias sesiones de una asignatura caigan tras el recreo/por la tarde."),
        ("Coincidentes en la misma franja", "colocarSesionesLectivas/coincidanALaMismaHora", "Penaliza que las sesiones de una asignatura se repitan a la misma hora."),
        ("Optativas solapadas", "colocarSesionesLectivas/optativaSolapada", "Penaliza el solapamiento de optativas."),
    ]),
    ("Evitar ocupar posiciones señaladas como no preferentes:", [
        ("A los alumnos", "posicionesNoPreferentes/enGrupos", "Peso de ocupar posiciones no preferentes de la plantilla de los grupos."),
        ("A los profesores", "posicionesNoPreferentes/enProfesores", "Peso de ocupar posiciones no preferentes de la plantilla de los profesores."),
        ("A las materias y tareas", "posicionesNoPreferentes/enMateriasYTareas", "Peso de ocupar posiciones no preferentes de materias y tipos de tarea."),
        ("A las sesiones lectivas", "posicionesNoPreferentes/enSesionesLectivas", "Peso de ocupar posiciones no preferentes de la plantilla de cada sesión."),
    ]),
    ("En el horario de los profesores", [
        ("Observar los periodos excluyentes", "horarioDeProfesores/horasExcluyentes", "Penaliza ocupar a la vez periodos mutuamente excluyentes."),
        ("Equilibrar la carga lectiva diaria", "horarioDeProfesores/masClasesEnUnDiaQueEnOtro", "Penaliza la diferencia entre el día con más y con menos clases de cada profesor."),
        ("Observar periodos de descanso", "horarioDeProfesores/horasDeClaseSeguidas", "Penaliza superar las horas de clase seguidas."),
        ("No exceder la permanencia máxima", "horarioDeProfesores/masPermanencia", "Penaliza la permanencia por encima de la preferente."),
        ("Evitar continuado con los mismos alumnos", "horarioDeProfesores/seguidoConElMismoGrupo", "Penaliza dar dos clases seguidas al mismo grupo con sesiones distintas."),
        ("Evitar guardias coincidentes", "horarioDeProfesores/guardiasEnExtremos", "Penaliza las guardias en horas extremas."),
        ("Prelación en el horario del profesor", "horarioDeProfesores/ordenProfesores", "Prioridad de los profesores según su orden en la lista."),
    ]),
]
# valores por defecto: los del archivo de ejemplo oficial del formato (ejemploDosMarcosHorarios.xghc.xml)
DEFECTO = {"huecosEnGrupos": 5, "huecosEnProfesores": 2, "enGrupos": 4, "enProfesores": 3, "enMateriasYTareas": 1,
           "enSesionesLectivas": 2, "enDiasConsecutivos": 1, "enAulaNoPreferente": 3, "enHorasExtremas": 2,
           "coincidanPorLaTarde": 1, "coincidanALaMismaHora": 0, "conCambiosDeAula": 1, "optativaSolapada": 1,
           "horasExcluyentes": 3, "masClasesEnUnDiaQueEnOtro": 3, "horasDeClaseSeguidas": 2, "masPermanencia": 2,
           "seguidoConElMismoGrupo": 1, "guardiasEnExtremos": 1, "ordenProfesores": 2}
# criterios que el motor aplica hoy (el resto se guardan y se documentan en ui_spec.md, Anexo O)
SOPORTE = {"huecosEnGrupos", "huecosEnProfesores", "enGrupos", "enProfesores", "enMateriasYTareas",
           "enSesionesLectivas", "enDiasConsecutivos", "enAulaNoPreferente", "enHorasExtremas", "guardiasEnExtremos",
           "masClasesEnUnDiaQueEnOtro", "conCambiosDeAula"}
ORDEN_XML = {"criterios": ["huecosEnHorario", "posicionesNoPreferentes", "colocarSesionesLectivas", "horarioDeProfesores"],
             "huecosEnHorario": ["huecosEnGrupos", "huecosEnProfesores"],
             "posicionesNoPreferentes": ["enGrupos", "enProfesores", "enMateriasYTareas", "enSesionesLectivas"],
             "colocarSesionesLectivas": ["enDiasConsecutivos", "enAulaNoPreferente", "enHorasExtremas", "coincidanPorLaTarde",
                                         "coincidanALaMismaHora", "conCambiosDeAula", "optativaSolapada"],
             "horarioDeProfesores": ["horasExcluyentes", "masClasesEnUnDiaQueEnOtro", "horasDeClaseSeguidas", "masPermanencia",
                                     "seguidoConElMismoGrupo", "guardiasEnExtremos", "ordenProfesores"]}
for _k, _v in ORDEN_XML.items():
    ED.ORDEN.setdefault(_k, _v)


def leer(raiz) -> dict:
    out = {}
    for _, items in GRUPOS:
        for _, ruta, _ in items:
            v = ED.leer(raiz, "criterios/" + ruta)
            tag = ruta.split("/")[-1]
            out[tag] = int(v) if v and v.lstrip("-").isdigit() else DEFECTO[tag]
    return out


def escribir(arbol, valores: dict) -> bool:
    cambio = False
    for _, items in GRUPOS:
        for _, ruta, _ in items:
            tag = ruta.split("/")[-1]
            cambio |= bool(ED.escribir(arbol, arbol.raiz, "criterios/" + ruta, str(int(valores[tag]))))
    return cambio


class DialogoCriterios(QDialog):
    def __init__(self, win, parent=None):
        super().__init__(parent or win)
        self.win = win; self.setWindowTitle(TITULO)
        L = QVBoxLayout(self); L.addWidget(QLabel("Indique el peso de los criterios:"))
        G = QGridLayout(); L.addLayout(G)
        self.sl = {}
        for i, (titulo, items) in enumerate(GRUPOS):
            gb = QGroupBox(titulo); g = QGridLayout(gb)
            g.addWidget(QLabel("0          5          10"), 0, 1)
            for j, (txt, ruta, ayuda) in enumerate(items, 1):
                tag = ruta.split("/")[-1]
                lb = QLabel(txt + ("" if tag in SOPORTE else " *"))
                s = QSlider(Qt.Horizontal); s.setRange(0, 10); s.setTickPosition(QSlider.TicksBelow); s.setTickInterval(1)
                s.setPageStep(1); s.setFixedWidth(140); s.setToolTip(ayuda)
                val = QLabel("0"); val.setFixedWidth(18); s.valueChanged.connect(lambda v, w=val: w.setText(str(v)))
                q = QToolButton(); q.setText("?"); q.clicked.connect(lambda _=False, t=txt, a=ayuda, k=tag: QMessageBox.information(
                    self, TITULO, f"{t}\n\n{a}" + ("" if k in SOPORTE else "\n\n(* El motor de este programa aún no aplica este criterio; se guarda en el archivo.)")))
                g.addWidget(lb, j, 0); g.addWidget(s, j, 1); g.addWidget(val, j, 2); g.addWidget(q, j, 3)
                self.sl[tag] = s
            G.addWidget(gb, (0, 1, 0, 1)[i], (0, 0, 1, 1)[i], Qt.AlignTop)
        L.addWidget(QLabel("* Criterio guardado en el archivo que el motor aún no aplica."))
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Aceptar"); bb.button(QDialogButtonBox.Cancel).setText("Cancelar")
        self.b_def = bb.addButton(TX("valores_partida"), QDialogButtonBox.ResetRole)
        self.b_def.clicked.connect(lambda: self.poner(DEFECTO))
        bb.accepted.connect(self.aceptar); bb.rejected.connect(self.reject); L.addWidget(bb)
        self.poner(leer(win.proyecto.doc.raiz))

    def poner(self, valores):
        for k, s in self.sl.items():
            s.setValue(int(valores.get(k, 0)))

    def valores(self):
        return {k: s.value() for k, s in self.sl.items()}

    def peso_total(self):
        return sum(self.valores().values())

    def aceptar(self):
        v = self.valores()
        self.win.editar(lambda arbol: escribir(arbol, v), TX("criterios_peso_2"), refrescar=False)
        self.accept()
