"""Diálogo del analizador de conflictos (conjunto mínimo de sesiones que no encajan juntas)."""
from __future__ import annotations
import threading
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QListWidget, QPushButton, QHBoxLayout
from .motor import analizador as AN

TITULO = "Busca conjuntos mínimos de sesiones que no encajan"


class DialogoAnalizador(QDialog):
    def __init__(self, win, pb, segundos=60.0, autoarranque=True):
        super().__init__(win); self.setWindowTitle(TITULO); self.pb = pb; self.segundos = segundos
        L = QVBoxLayout(self)
        self.lbl = QLabel("Buscando un conjunto mínimo de sesiones que no pueden colocarse a la vez…"); L.addWidget(self.lbl)
        self.lista = QListWidget(); self.lista.setMinimumSize(560, 220); L.addWidget(self.lista)
        h = QHBoxLayout(); h.addStretch(); self.b = QPushButton("Detener"); self.b.clicked.connect(self._boton); h.addWidget(self.b)
        L.addLayout(h)
        self.parar = threading.Event(); self.res = None; self.hilo = None
        self.t = QTimer(self); self.t.timeout.connect(self._mirar)
        if autoarranque:
            self.arrancar()

    def arrancar(self):
        self.hilo = threading.Thread(target=self._run, daemon=True); self.hilo.start(); self.t.start(200)

    def _run(self):
        self.res = AN.analizar(self.pb, self.segundos, parar=self.parar)

    def _mirar(self):
        if self.hilo and self.hilo.is_alive():
            return
        self.t.stop(); r = self.res or {}; self.b.setText("Cerrar")
        if r.get("estado") == "factible":
            self.lbl.setText("Todas las sesiones encajan a la vez: no hay conjuntos imposibles en las condiciones estrictas.")
        elif r.get("estado") == "infactible":
            n = len(r["conjunto"])
            self.lbl.setText(f"Conjunto {'mínimo' if r['minimo'] else 'reducido (no garantizado mínimo)'} de {n} "
                             f"sesiones que no encajan juntas (quitando cualquiera, el resto sí) — {r['tiempo']} s:")
            self.lista.addItems(AN.describir(self.pb, r["conjunto"]))
        else:
            self.lbl.setText("No se ha podido determinar en el tiempo disponible.")

    def _boton(self):
        if self.hilo and self.hilo.is_alive():
            self.parar.set()
        else:
            self.accept()

    def reject(self):
        self.parar.set(); super().reject()
