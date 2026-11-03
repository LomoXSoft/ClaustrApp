"""Construye páginas Qt a partir de la descripción de diálogos (posiciones en unidades de diálogo).

La descripción (sección «dialogos» del paquete de textos, ver textos.py) recoge, para cada diálogo, el título y la lista
de controles (clase, id, x, y, ancho, alto, texto). Aquí se convierten a widgets Qt con
las mismas posiciones y los textos del paquete activo. Los iconos se dibujan aquí (no se usan gráficos de terceros).
"""
from __future__ import annotations
import json
import os
import sys
from PySide6.QtCore import Qt, QRect, QRectF, QPointF, QSize
from PySide6.QtGui import QPainter, QColor, QPen, QPixmap, QFont, QPolygonF, QBrush
from PySide6.QtWidgets import (QWidget, QLabel, QLineEdit, QComboBox, QCheckBox, QRadioButton, QPushButton,
                               QGroupBox, QListWidget, QTreeWidget, QSpinBox, QButtonGroup, QAbstractItemView,
                               QPlainTextEdit, QToolButton)

_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recursos")   # también en el ejecutable (horarios/recursos)
from .textos import DIALOGOS   # paquete de textos privado o público (ver textos.py)

FX, FY = 1.5, 1.625      # píxeles por unidad de diálogo (fuente de diálogo de 8 puntos, 96 ppp)
SIN_ID = 4294967295
NO_PERSISTIDO = "Este campo aún no se guarda en el archivo"


def fuente_dialogo():
    f = QFont("MS Shell Dlg 2" if sys.platform == "win32" else "DejaVu Sans")
    if sys.platform == "win32":
        f.setPointSize(8)
    else:
        f.setPixelSize(11)
    return f


def ajustar(w, minimo=8):
    """Encoge la letra de un botón/casilla/etiqueta hasta que su texto quepa en su rectángulo."""
    from PySide6.QtGui import QFontMetrics
    t = w.text() if hasattr(w, "text") else ""
    if not t or (isinstance(w, QLabel) and w.pixmap() is not None and not w.pixmap().isNull()):
        return
    f = QFont(w.font()); size = f.pixelSize() if f.pixelSize() > 0 else round(f.pointSizeF() * 96 / 72)
    margen = 10 if isinstance(w, QPushButton) else (20 if isinstance(w, (QCheckBox, QRadioButton)) else 0)
    multilinea = (isinstance(w, QLabel) and w.wordWrap()) or ((isinstance(w, (QCheckBox, QRadioButton)) and "\n" in t))

    def cabe(sz):
        f.setPixelSize(sz); fm = QFontMetrics(f)
        if isinstance(w, QLabel) and w.wordWrap():
            r = fm.boundingRect(0, 0, max(1, w.width()), 10000, Qt.TextWordWrap, t)
            return r.height() <= w.height() + 2
        lineas = t.split("\n")
        return (max(fm.horizontalAdvance(x) for x in lineas) <= w.width() - margen and
                (not multilinea or fm.lineSpacing() * len(lineas) <= w.height() + 4))
    if isinstance(w, (QCheckBox, QRadioButton)) and "\n" not in t and not cabe(size):
        # casillas altas (2-3 líneas en el recurso): partir en líneas antes de encoger la letra
        for sz in range(size, 8, -1):
            f.setPixelSize(sz); fm = QFontMetrics(f); ancho = w.width() - margen; lineas = [""]
            for pal in t.split(" "):
                prueba = (lineas[-1] + " " + pal).strip()
                if fm.horizontalAdvance(prueba) <= ancho or not lineas[-1]:
                    lineas[-1] = prueba
                else:
                    lineas.append(pal)
            if len(lineas) > 1 and fm.lineSpacing() * len(lineas) <= w.height() + 4 and \
                    max(fm.horizontalAdvance(x) for x in lineas) <= ancho:
                t = "\n".join(lineas); w.setText(t); multilinea = True
                if sz != size:
                    w.setFont(QFont(f))
                return
        f.setPixelSize(size)
    sz = size
    while sz > 9 and not cabe(sz):
        sz -= 1
    if not cabe(sz) and isinstance(w, QPushButton) and " " in t and "\n" not in t:
        # partir en dos líneas por el espacio más centrado
        pal = t.split(" "); mejor = min(range(1, len(pal)), key=lambda k: abs(len(" ".join(pal[:k])) - len(t) / 2))
        t = " ".join(pal[:mejor]) + "\n" + " ".join(pal[mejor:]); multilinea = True; w.setText(t); sz = size
        while sz > 9 and not cabe(sz):
            sz -= 1
    while sz > minimo and not cabe(sz):
        sz -= 1
    if sz != size:
        f.setPixelSize(sz); w.setFont(f)
    if not cabe(sz) and isinstance(w, (QPushButton, QCheckBox, QRadioButton)):
        w.setToolTip(t.replace("\n", " "))


def px(x, y, w, h):
    return QRect(round(x * FX), round(y * FY), round(w * FX), round(h * FY))


# ---------------------------------------------------------------- iconos propios
def icono(n: int, tam=18) -> QPixmap:
    pm = QPixmap(tam, tam); pm.fill(Qt.transparent)
    p = QPainter(pm); p.setRenderHint(QPainter.Antialiasing)
    r = QRectF(1.5, 1.5, tam - 3, tam - 3)
    if n == 244:      # cara sonriente: condición ponderable / preferencia
        p.setPen(QPen(QColor("#2d7d2d"), 1.2)); p.setBrush(QColor("#b6f0a8")); p.drawEllipse(r)
        p.setBrush(QColor("#1d4d1d")); p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(tam * .36, tam * .40), tam * .06, tam * .07)
        p.drawEllipse(QPointF(tam * .64, tam * .40), tam * .06, tam * .07)
        p.setPen(QPen(QColor("#1d4d1d"), 1.3)); p.setBrush(Qt.NoBrush)
        p.drawArc(QRectF(tam * .28, tam * .38, tam * .44, tam * .34), 200 * 16, 140 * 16)
    elif n == 374:    # chincheta: condición estricta
        p.setPen(QPen(QColor("#333"), 1.4)); p.drawLine(QPointF(tam * .30, tam * .85), QPointF(tam * .52, tam * .55))
        p.setPen(QPen(QColor("#7a1010"), 1)); p.setBrush(QColor("#d23a3a"))
        p.drawPolygon(QPolygonF([QPointF(tam * .45, tam * .45), QPointF(tam * .62, tam * .15), QPointF(tam * .88, tam * .40),
                                 QPointF(tam * .60, tam * .58)]))
        p.drawEllipse(QPointF(tam * .70, tam * .30), tam * .14, tam * .14)
    elif n == 400:    # punto
        p.setPen(Qt.NoPen); p.setBrush(QColor("#1a8a1a")); p.drawEllipse(r)
    elif n == 934:    # más
        p.setPen(Qt.NoPen); p.setBrush(QColor("#1a8a1a"))
        p.drawRect(QRectF(tam * .38, tam * .1, tam * .24, tam * .8)); p.drawRect(QRectF(tam * .1, tam * .38, tam * .8, tam * .24))
    elif n in (194, 195, 196, 220):   # ilustraciones de cabecera: rejilla simple
        p.setPen(QPen(QColor("#2a6f8f"), 1)); p.setBrush(QColor("#eaf6fb")); p.drawRect(r)
        for i in range(1, 4):
            p.drawLine(QPointF(r.left(), r.top() + i * r.height() / 4), QPointF(r.right(), r.top() + i * r.height() / 4))
        p.setBrush(QColor("#c9a227")); p.drawRect(QRectF(r.left() + 2, r.top() + r.height() / 4 + 1, r.width() - 4, r.height() / 4 - 2))
    else:             # icono genérico de ficha
        p.setPen(QPen(QColor("#4a6fa5"), 1)); p.setBrush(QColor("#dfe8f5")); p.drawRoundedRect(r, 3, 3)
        p.setPen(QPen(QColor("#4a6fa5"), 1.2))
        for i in range(3):
            y = r.top() + r.height() * (0.3 + 0.2 * i); p.drawLine(QPointF(r.left() + 4, y), QPointF(r.right() - 4, y))
    p.end()
    return pm


class BotonIcono(QToolButton):
    """Botón pequeño que alterna estricto (chincheta) / preferente (cara)."""

    def __init__(self, parent=None):
        super().__init__(parent); self.estricto = False; self.setAutoRaise(True); self._pintar()

    def set_estricto(self, v):
        self.estricto = bool(v); self._pintar()

    def _pintar(self):
        self.setIcon(icono(374 if self.estricto else 244, 14)); self.setIconSize(QSize(14, 14))


# ---------------------------------------------------------------- página
class PaginaRC(QWidget):
    """Página construida a partir de un diálogo de la descripción."""

    OCULTAR = {1376, 1377, 1395}   # rótulos de estado/edición del original sin contenido útil

    def __init__(self, rid: str, parent=None, sin_botones=False):
        super().__init__(parent)
        self.rid = rid
        d = DIALOGOS[rid]
        self.titulo = d["titulo"].strip()
        self.setFont(fuente_dialogo())
        self.setFixedSize(round(d["w"] * FX), round(d["h"] * FY))
        self.c: dict[int, QWidget] = {}
        self.etiquetas: list[QLabel] = []
        ctr = d["controles"]
        updowns = [c for c in ctr if c[0] == "msctls_updown32"]
        grupos_radio: list[QButtonGroup] = []
        ultimo_grupo = None
        # cajas de grupo primero (quedan detrás)
        for cls, cid, x, y, w, h, t in ctr:
            if cls == "GROUPBOX":
                g = QGroupBox(t.replace("&&", "&"), self); g.setGeometry(px(x, y, w, h)); g.lower()
                g.setStyleSheet("QGroupBox{border:1px solid #c8c8c8; margin-top:6px;}"
                                "QGroupBox::title{subcontrol-origin:margin; left:6px; padding:0 2px;}")
                if cid != SIN_ID:
                    self.c[cid] = g
        for cls, cid, x, y, w, h, t in ctr:
            if cid in self.OCULTAR or cls in ("GROUPBOX", "msctls_updown32"):
                continue
            if sin_botones and cls == "BUTTON" and cid in (1, 2, 57670, 1053, 1054):
                continue
            r = px(x, y, w, h)
            t = (t or "").replace("&&", "\x00").replace("&", "").replace("\x00", "&").replace("\\n", "\n")
            wdg = None
            if cls == "STATIC":
                if t.startswith("#"):
                    n = int(t[1:]); lbl = QLabel(self); lbl.setPixmap(icono(n, min(r.width(), r.height(), 22)))
                    lbl.setGeometry(r); lbl.setAlignment(Qt.AlignCenter); wdg = lbl
                else:
                    lbl = QLabel(t, self); lbl.setGeometry(r); lbl.setWordWrap(r.height() > 18 or "\n" in t)
                    lbl.setAlignment(Qt.AlignLeft | Qt.AlignTop); wdg = lbl; self.etiquetas.append(lbl)
            elif cls == "EDIT":
                ud = next((u for u in updowns if abs(u[3] - y) < 8 and -6 < u[2] - (x + w) < 6 or
                           abs(u[3] - y) < 8 and x < u[2] < x + w), None)
                if ud is not None:
                    sp = QSpinBox(self); sp.setRange(0, 999)
                    sp.setGeometry(px(x, y, max(w, ud[2] + ud[4] - x), h)); wdg = sp
                elif h > 22:
                    e = QPlainTextEdit(self); e.setGeometry(r); wdg = e
                else:
                    e = QLineEdit(self); e.setGeometry(r); wdg = e
            elif cls == "COMBOBOX":
                cb = QComboBox(self); cb.setGeometry(QRect(r.x(), r.y(), r.width(), max(20, round(13 * FY))))
                cb.setMaxVisibleItems(15); wdg = cb
            elif cls == "CHECKBOX":
                cb = QCheckBox(t, self); wdg = cb; cb.setGeometry(r)
                if "\n" not in t and cb.sizeHint().width() > r.width() and r.height() < 20:
                    cb.resize(cb.sizeHint().width(), r.height())
                if r.height() >= 20:
                    cb.setText(""); cb.resize(18, r.height())
                    l = QLabel(t, self); l.setWordWrap(True); l.setGeometry(r.adjusted(18, 0, 0, 0)); l.setBuddy(cb)
                    l.mousePressEvent = lambda ev, b=cb: b.toggle(); self.etiquetas.append(l)
            elif cls == "RADIO":
                rb = QRadioButton(t.strip() if t != "QQQQQQQ" else "", self); wdg = rb; rb.setGeometry(r)
                if rb.sizeHint().width() > r.width() and r.height() < 20:
                    rb.resize(rb.sizeHint().width(), r.height())
                if r.height() >= 20:
                    rb.setText(""); rb.resize(18, r.height())
                    l = QLabel(t, self); l.setWordWrap(True); l.setGeometry(r.adjusted(18, 0, 0, 0))
                    l.mousePressEvent = lambda ev, b=rb: b.setChecked(True); self.etiquetas.append(l)
                rb.setAutoExclusive(False)
            elif cls in ("BUTTON", "DEFBUTTON"):
                if not t or t == "Button1":
                    b = BotonIcono(self) if not t and r.width() <= 22 and r.height() <= 18 else QToolButton(self)
                    if t == "Button1":
                        b.setText("…")
                    b.setGeometry(r); wdg = b
                else:
                    b = QPushButton(t, self); b.setGeometry(r); b.setDefault(cls == "DEFBUTTON"); wdg = b
            elif cls == "SysListView32":
                tv = QTreeWidget(self); tv.setRootIsDecorated(False); tv.setGeometry(r)
                tv.setAlternatingRowColors(False); tv.setSelectionMode(QAbstractItemView.ExtendedSelection)
                tv.setUniformRowHeights(True); wdg = tv
            elif cls == "LISTBOX":
                lw = QListWidget(self); lw.setGeometry(r); wdg = lw
            if wdg is not None and cid != SIN_ID:
                self.c[cid] = wdg
            if wdg is not None:
                wdg.setObjectName(f"c{cid}" if cid != SIN_ID else "")
        self._agrupar_radios(ctr)
        self.ajustar_textos()

    def ajustar_textos(self):
        """Reduce la letra de los controles cuyo texto no cabe (las fuentes de Linux son más anchas)."""
        for w in self.findChildren(QWidget):
            if isinstance(w, (QPushButton, QCheckBox, QRadioButton, QLabel)):
                ajustar(w)

    def _agrupar_radios(self, ctr):
        """Agrupa radios que comparten caja de grupo (o, sin caja, columna/zona) como exclusivos."""
        cajas = [(c[2], c[3], c[2] + c[4], c[3] + c[5]) for c in ctr if c[0] == "GROUPBOX"]
        grupos = {}
        for cls, cid, x, y, w, h, t in ctr:
            if cls != "RADIO" or cid not in self.c:
                continue
            dentro = [b for b in cajas if b[0] <= x <= b[2] and b[1] <= y <= b[3]]
            clave = min(dentro, key=lambda b: (b[2] - b[0]) * (b[3] - b[1])) if dentro else None
            grupos.setdefault(clave, []).append(self.c[cid])
        self.grupos_radio = []
        for lista in grupos.values():
            g = QButtonGroup(self); g.setExclusive(True)
            for rb in lista:
                g.addButton(rb)
            self.grupos_radio.append(g)

    def regrupar(self, *conjuntos):
        """Redefine grupos exclusivos explícitamente: regrupar([1043, 1044], [1205, 1214])."""
        for ids in conjuntos:
            for g in self.grupos_radio:
                for i in ids:
                    if self.c[i] in g.buttons():
                        g.removeButton(self.c[i])
            g = QButtonGroup(self); g.setExclusive(True)
            for i in ids:
                g.addButton(self.c[i])
            self.grupos_radio.append(g)
