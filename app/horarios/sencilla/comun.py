"""Piezas comunes de la versión sencilla."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QTableWidget,
                               QHeaderView, QAbstractItemView, QDialog, QListWidget, QListWidgetItem, QSpinBox,
                               QDialogButtonBox, QLineEdit, QCheckBox)


def lbl(texto, nombre=None, envolver=True):
    l = QLabel(texto); l.setWordWrap(envolver)
    if nombre:
        l.setObjectName(nombre)
    return l


def btn(texto, slot=None, primario=False, enlace=False, nombre=None):
    b = QPushButton(texto)
    if primario:
        b.setObjectName("primario")
    elif enlace:
        b.setObjectName("enlace"); b.setCursor(Qt.PointingHandCursor)
    if slot:
        b.clicked.connect(lambda _=False: slot())
    if nombre:
        b.setAccessibleName(nombre)
    return b


def tarjeta():
    f = QFrame(); f.setObjectName("tarjeta")
    v = QVBoxLayout(f); v.setContentsMargins(14, 12, 14, 12); v.setSpacing(8)
    return f, v


def tabla(cabeceras, estirar=0):
    t = QTableWidget(0, len(cabeceras)); t.setHorizontalHeaderLabels(cabeceras)
    t.verticalHeader().setVisible(False); t.setAlternatingRowColors(False)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    h = t.horizontalHeader(); h.setSectionResizeMode(QHeaderView.Interactive)
    if 0 <= estirar < len(cabeceras):
        h.setSectionResizeMode(estirar, QHeaderView.Stretch)
    return t


def fila_botones(*botones):
    h = QHBoxLayout(); h.setSpacing(8)
    for b in botones:
        if b is None:
            h.addStretch(1)
        else:
            h.addWidget(b)
    return h


def horas_de(tmp: str) -> int:
    return sum(int(c) for c in (tmp or "") if c.isdigit())


class ElegirProfesores(QDialog):
    """Lista de profesores con casillas (y, opcionalmente, nº de guardias de cada uno)."""
    def __init__(self, parent, titulo, profesores, marcados=(), con_numero=False, nombre=None):
        super().__init__(parent); self.setWindowTitle(titulo)
        v = QVBoxLayout(self)
        self.ed_nombre = None
        if nombre is not None:
            v.addWidget(QLabel("Nombre:")); self.ed_nombre = QLineEdit(nombre); v.addWidget(self.ed_nombre)
        v.addWidget(QLabel("Marque los profesores:"))
        self.lista = QListWidget(); v.addWidget(self.lista)
        for p in profesores:
            it = QListWidgetItem(p); it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if p in marcados else Qt.Unchecked); self.lista.addItem(it)
        self.sp = None
        if con_numero:
            h = QHBoxLayout(); h.addWidget(QLabel("Horas de guardia de cada uno:")); self.sp = QSpinBox()
            self.sp.setRange(1, 10); self.sp.setValue(1); h.addWidget(self.sp); v.addLayout(h)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); v.addWidget(bb)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)

    def marcar(self, nombres):
        for i in range(self.lista.count()):
            it = self.lista.item(i); it.setCheckState(Qt.Checked if it.text() in nombres else Qt.Unchecked)

    def elegidos(self):
        return [self.lista.item(i).text() for i in range(self.lista.count()) if self.lista.item(i).checkState() == Qt.Checked]
