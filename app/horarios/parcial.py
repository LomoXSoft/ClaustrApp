"""Diálogo 690 «¿Qué elementos quiere incluir en la búsqueda de resultados?» (Calcular un horario parcial)."""
from __future__ import annotations
from .textos import TX
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QGridLayout, QVBoxLayout, QHBoxLayout, QGroupBox, QListWidget, QListWidgetItem,
                               QPushButton, QCheckBox, QLabel)
from .motor import problema, parcial as PA

TITULO = "¿Qué elementos quiere incluir en la búsqueda de resultados?"


def _lista(nombres):
    w = QListWidget()
    for n in nombres:
        it = QListWidgetItem(n); it.setFlags(it.flags() | Qt.ItemIsUserCheckable); it.setCheckState(Qt.Checked); w.addItem(it)
    return w


def _marcar(w, on):
    for i in range(w.count()):
        w.item(i).setCheckState(Qt.Checked if on else Qt.Unchecked)


class DialogoParcial(QDialog):
    """modo «motor»: botones «Calcular un horario parcial» y «Análisis parcial»; modo «filtro»: solo Aceptar (Depurador)."""
    def __init__(self, win, pb=None, modo="motor"):
        super().__init__(win); self.win = win; self.setWindowTitle(TITULO); self.accion = None
        self.pb = pb if pb is not None else problema.construir(win.proyecto)
        L = QGridLayout(self)
        L.addWidget(QLabel("Se buscará un horario solamente para los elementos señalados.\n"
                           "La búsqueda de resultados parciales puede ayudar a analizar las condiciones imposibles."), 0, 0, 1, 3)
        self.l_gr = _lista(sorted({g for u in self.pb["unidades"] for g in u["grupos"]}))
        self.l_re = _lista([r["nombre"] for r in self.pb["reuniones"]])
        for col, (tit, lw, a, b) in enumerate((("Incluir los grupos de alumnos:", self.l_gr, "Marcar todos", "Desmarcar todos"),
                                               ("Incluir las reuniones:", self.l_re, "Marcar todas", "Desmarcar todas"))):
            gb = QGroupBox(tit); v = QVBoxLayout(gb); v.addWidget(lw); h = QHBoxLayout()
            for txt, on in ((a, True), (b, False)):
                bt = QPushButton(txt); bt.clicked.connect(lambda _=False, w=lw, o=on: _marcar(w, o)); h.addWidget(bt)
            v.addLayout(h); L.addWidget(gb, 1, col)
        gb = QGroupBox("Incluir además:"); v = QVBoxLayout(gb)
        self.c_gua = QCheckBox("Las guardias del profesorado en horario lectivo."); self.c_gua.setChecked(True)
        self.c_com = QCheckBox("Todas las actividades complementarias."); self.c_com.setChecked(True)
        self.c_gua.setEnabled(bool(self.pb["guardias"])); self.c_com.setEnabled(bool(self.pb["complementarias"]))
        v.addWidget(self.c_gua); v.addWidget(self.c_com); v.addStretch()
        self.b_gen = QPushButton(TX("calcular_horario_parcial_2") if modo == "motor" else "Aceptar"); self.b_gen.setDefault(True)
        self.b_ana = QPushButton("Análisis parcial"); self.b_ana.setVisible(modo == "motor")
        bc = QPushButton("Cancelar")
        self.b_gen.clicked.connect(lambda: self._fin("generar")); self.b_ana.clicked.connect(lambda: self._fin("analizar"))
        bc.clicked.connect(self.reject)
        for b in (self.b_gen, self.b_ana, bc):
            v.addWidget(b)
        L.addWidget(gb, 1, 2)

    def _marcados(self, w):
        return [w.item(i).text() for i in range(w.count()) if w.item(i).checkState() == Qt.Checked]

    def seleccion(self):
        return {"grupos": self._marcados(self.l_gr), "reuniones": self._marcados(self.l_re),
                "guardias": self.c_gua.isChecked() and self.c_gua.isEnabled(),
                "complementarias": self.c_com.isChecked() and self.c_com.isEnabled()}

    def filtrar(self, pb=None):
        return PA.filtrar(pb if pb is not None else self.pb, **self.seleccion())

    def _fin(self, accion):
        self.accion = accion; self.accept()


def generar_parcial(win):
    d = DialogoParcial(win)
    if not d.exec():
        return None
    q = d.filtrar()
    if d.accion == "analizar":
        from .analizador import DialogoAnalizador
        DialogoAnalizador(win, q).exec(); return q
    from .ventana_motor import VentanaMotor
    win.ventana_motor = VentanaMotor(win.proyecto, win, pb=q, anotacion=PA.anotacion(d.pb, q)[1:], parcial=True)
    win.ventana_motor.show(); return q
