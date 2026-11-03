"""Widget reutilizable de plantilla de disponibilidad (días x tramos)."""
from __future__ import annotations
from .textos import TX
from PySide6.QtCore import Qt, Signal, QRectF, QSize
from PySide6.QtGui import QPainter, QColor, QPen, QFont
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QToolButton, QButtonGroup,
                               QFrame, QSizePolicy, QGroupBox, QScrollArea)
from . import modelo as M
from .iconos import pintar_estado, icono_estado, icono

DIAS = ["L", "M", "X", "J", "V", "S", "D"]


class RejillaPlantilla(QWidget):
    """Rejilla dibujada: cabecera # L M X J V y filas de tramos (recreos finos)."""
    cambiada = Signal()

    CW, CH, RH, HDR, NUMW = 30, 28, 7, 24, 26

    def __init__(self, parent=None):
        super().__init__(parent)
        self.marco: M.Marco | None = None
        self.plantilla: dict | None = None
        self.heredada: dict = {}
        self.ocupadas: set = set()
        self.estado_pincel = M.PROHIBIDO
        self.editable = True
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    def set_datos(self, marco, plantilla, heredada=None):
        self.marco, self.plantilla, self.heredada = marco, plantilla, heredada or {}
        self.resize(self.sizeHint()); self.updateGeometry(); self.update()

    def _filas(self):
        return self.marco.filas() if self.marco else []

    def sizeHint(self):
        filas = self._filas()
        h = self.HDR + 4 + sum(self.RH if t.tipo != "lectivo" else self.CH + 2 for t in filas)
        n = len(self.marco.dias) if self.marco else 5
        return QSize(self.NUMW + 4 + n * (self.CW + 2), max(h, 60))

    def _geometria(self):
        """Lista de (rect, dia, indice) y filas con su y."""
        celdas, filas = [], []
        y = self.HDR + 4
        dias = self.marco.dias if self.marco else []
        n = 0
        for t in self._filas():
            if t.tipo != "lectivo":
                filas.append((t, y, self.RH, None)); y += self.RH; continue
            n += 1
            filas.append((t, y, self.CH, n))
            for j, d in enumerate(dias):
                celdas.append((QRectF(self.NUMW + 4 + j * (self.CW + 2), y, self.CW, self.CH), d, t.indice))
            y += self.CH + 2
        return celdas, filas

    def paintEvent(self, ev):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        if not self.marco:
            p.setPen(QColor("#777")); p.drawText(self.rect(), Qt.AlignCenter, "(sin marco horario)"); return
        f = QFont("DejaVu Sans"); f.setPixelSize(12); f.setBold(True); p.setFont(f)
        dias = self.marco.dias
        def boton(r, txt):
            p.setPen(QColor("#9aa0b0")); p.setBrush(QColor("#f4f4f4")); p.drawRoundedRect(r, 3, 3)
            p.setPen(QColor("#202020")); p.drawText(r, Qt.AlignCenter, txt)
        boton(QRectF(0, 0, self.NUMW, self.HDR), "#")
        for j, d in enumerate(dias):
            boton(QRectF(self.NUMW + 4 + j * (self.CW + 2), 0, self.CW, self.HDR), DIAS[d] if d < 7 else str(d))
        celdas, filas = self._geometria()
        for t, y, h, n in filas:
            if n is None:
                continue
            boton(QRectF(0, y, self.NUMW, h), str(n))
        for r, d, i in celdas:
            k = (self.marco.id, d, i)
            est = (self.plantilla or {}).get(k, M.INDIFERENTE)
            fondo = "#e8f4e8"
            if k in self.ocupadas:
                fondo = "#1f7a33"
            elif self.heredada.get(k) == M.PROHIBIDO and est != M.PROHIBIDO:
                fondo = "#f2a3a3"
            p.setPen(QPen(QColor("#5a8a5a"), 1)); p.setBrush(QColor(fondo)); p.drawRect(r)
            pintar_estado(p, r, est)
        p.end()

    def mousePressEvent(self, ev):
        if not (self.editable and self.marco and self.plantilla is not None):
            return
        for r, d, i in self._geometria()[0]:
            if r.contains(ev.position()):
                k = (self.marco.id, d, i)
                actual = self.plantilla.get(k, M.INDIFERENTE)
                nuevo = M.INDIFERENTE if actual == self.estado_pincel else self.estado_pincel
                if nuevo == M.INDIFERENTE:
                    self.plantilla.pop(k, None)
                else:
                    self.plantilla[k] = nuevo
                self.update(); self.cambiada.emit()
                return

    def mouseMoveEvent(self, ev):
        for r, d, i in self._geometria()[0]:
            if r.contains(ev.position()):
                t = next((x for x in self.marco.tramos if x.dia == d and x.indice == i), None)
                if t:
                    self.setToolTip(f"{['Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo'][d]}  {t.entrada}-{t.salida}")
                return
        self.setToolTip("")


class PanelPlantilla(QWidget):
    """Panel derecho: filtros, marcos, nombre, selector de estado y rejilla."""
    cambiada = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.proyecto = None
        lay = QVBoxLayout(self); lay.setContentsMargins(6, 6, 6, 6); lay.setSpacing(6)
        # filtros Curso / Departamento (restringen desplegables; próximamente)
        fil = QHBoxLayout()
        for txt in ("Curso", "Departamento"):
            b = QToolButton(); b.setText(txt); b.setIcon(icono("filtro", 16)); b.setCheckable(True)
            b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon); b.setEnabled(False)
            b.setToolTip(f"Filtro de {txt.lower()} para las listas desplegables (próximamente)")
            fil.addWidget(b)
        fil.addStretch(); lay.addLayout(fil)
        # marcos
        gb = QGroupBox(TX("marco_horario_ve")); self.lay_marcos = QHBoxLayout(gb); self.lay_marcos.setContentsMargins(6, 2, 6, 4)
        self.grupo_marcos = QButtonGroup(self); self.grupo_marcos.setExclusive(True)
        self.grupo_marcos.idClicked.connect(self._cambiar_marco)
        lay.addWidget(gb)
        # nombre
        fila = QHBoxLayout()
        bx = QToolButton(); bx.setText("!"); bx.setToolTip("Mensajes del elemento"); fila.addWidget(bx)
        self.nombre = QLabel(""); self.nombre.setAlignment(Qt.AlignCenter); self.nombre.setFrameShape(QFrame.StyledPanel)
        self.nombre.setMinimumHeight(30); self.nombre.setWordWrap(True); self.nombre.setStyleSheet("background:white; font-size:13px;")
        fila.addWidget(self.nombre, 1)
        bq = QToolButton(); bq.setText("?"); bq.setToolTip("Ayuda sobre la plantilla"); fila.addWidget(bq)
        lay.addLayout(fila)
        # selector de estado (pincel)
        sel = QHBoxLayout(); sel.setSpacing(2)
        self.grupo_estados = QButtonGroup(self)
        for n, est in enumerate([M.PREFERENTE, M.INDIFERENTE, M.PROHIBIDO, M.NO_PREF1, M.NO_PREF2, M.PREFIJADO]):
            b = QToolButton(); b.setIcon(icono_estado(est, 22)); b.setIconSize(QSize(22, 22)); b.setCheckable(True)
            b.setToolTip(f"Pintar: {M.NOMBRE_ESTADO[est]}"); b.setAutoRaise(True)
            self.grupo_estados.addButton(b, n); sel.addWidget(b)
            if est == M.PROHIBIDO:
                b.setChecked(True)
        self._estados = [M.PREFERENTE, M.INDIFERENTE, M.PROHIBIDO, M.NO_PREF1, M.NO_PREF2, M.PREFIJADO]
        self.grupo_estados.idClicked.connect(lambda i: setattr(self.rejilla, "estado_pincel", self._estados[i]))
        sel.addStretch()
        bl = QToolButton(); bl.setIcon(icono("limpiar", 22)); bl.setAutoRaise(True); bl.setToolTip(TX("vaciar_plantillas_proximamente"))
        bl.setEnabled(False); sel.addWidget(bl)
        lay.addLayout(sel)
        # rejilla
        self.rejilla = RejillaPlantilla(); self.rejilla.cambiada.connect(self.cambiada)
        sc = QScrollArea(); sc.setWidget(self.rejilla); sc.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        sc.setFrameShape(QFrame.NoFrame); sc.setWidgetResizable(False); self.scroll = sc
        lay.addWidget(sc, 1)
        self.nota = QLabel(TX("posiciones_prohibidas_preferentes_marcan_cada"))
        self.nota.setWordWrap(True); self.nota.setAlignment(Qt.AlignCenter); self.nota.setFrameShape(QFrame.StyledPanel)
        self.nota.setStyleSheet("background:white; padding:4px;")
        lay.addWidget(self.nota)
        self._plantilla = None; self._heredada = {}

    def set_proyecto(self, proyecto):
        self.proyecto = proyecto
        for b in self.grupo_marcos.buttons():
            self.grupo_marcos.removeButton(b); b.deleteLater()
        self._ids = list(proyecto.marcos) if proyecto else []
        for n, mid in enumerate(self._ids):
            b = QToolButton(); b.setText(proyecto.marcos[mid].nombre); b.setCheckable(True)
            self.grupo_marcos.addButton(b, n); self.lay_marcos.addWidget(b)
        self.lay_marcos.addStretch()
        self.mostrar(None, "", None)

    def set_estados(self, estados=None):
        """Restringe el selector a los estados válidos de la lista (None = todos)."""
        estados = estados or self._estados
        for n, est in enumerate(self._estados):
            b = self.grupo_estados.button(n); b.setVisible(est in estados)
        if self.rejilla.estado_pincel not in estados:
            n = self._estados.index(M.PROHIBIDO if M.PROHIBIDO in estados else estados[0])
            self.grupo_estados.button(n).setChecked(True); self.rejilla.estado_pincel = self._estados[n]

    def mostrar(self, plantilla, nombre, marco_id, heredada=None, editable=True):
        self._plantilla, self._heredada = plantilla, heredada or {}
        self.nombre.setText(nombre)
        if self.proyecto and self._ids:
            mid = marco_id if marco_id in self._ids else self._ids[0]
            idx = self._ids.index(mid); self.grupo_marcos.button(idx).setChecked(True)
            self._cambiar_marco(idx)
        else:
            self.rejilla.set_datos(None, None)
        self.rejilla.editable = editable and plantilla is not None

    def _cambiar_marco(self, idx):
        if self.proyecto:
            self.rejilla.set_datos(self.proyecto.marcos[self._ids[idx]], self._plantilla, self._heredada)
