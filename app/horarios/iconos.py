"""Iconos propios dibujados con QPainter (no se usa ningún gráfico ajeno)."""
from __future__ import annotations
from functools import lru_cache
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QPen, QBrush, QPolygonF, QFont
from . import modelo as M

VERDE, AZUL, ROJO, AMARILLO, NARANJA = "#2fa84f", "#2f7fd8", "#d83030", "#f2cf2a", "#f08a24"
OSCURO = "#3a3d4c"


def _pm(s=32):
    pm = QPixmap(s, s); pm.fill(Qt.transparent)
    p = QPainter(pm); p.setRenderHint(QPainter.Antialiasing)
    return pm, p


def _pen(c=OSCURO, w=1.6):
    pen = QPen(QColor(c)); pen.setWidthF(w); pen.setCapStyle(Qt.RoundCap); pen.setJoinStyle(Qt.RoundJoin)
    return pen


def _cara(p, r, color, triste=True):
    p.setPen(_pen(OSCURO, 1.3)); p.setBrush(QColor(color)); p.drawEllipse(r)
    cx, cy, w = r.center().x(), r.center().y(), r.width()
    p.setBrush(QColor(OSCURO)); p.setPen(Qt.NoPen)
    for dx in (-0.18, 0.18):
        p.drawEllipse(QPointF(cx + dx * w, cy - 0.1 * w), 0.06 * w, 0.06 * w)
    p.setPen(_pen(OSCURO, 1.3)); p.setBrush(Qt.NoBrush)
    m = QRectF(cx - 0.22 * w, cy + (0.12 if triste else -0.05) * w, 0.44 * w, 0.3 * w)
    p.drawArc(m, 0 if triste else 180 * 16, 180 * 16)


def pintar_estado(p: QPainter, r: QRectF, estado: str):
    """Dibuja el símbolo de un estado de plantilla en el rectángulo r."""
    r = r.adjusted(r.width() * 0.12, r.height() * 0.12, -r.width() * 0.12, -r.height() * 0.12)
    p.save(); p.setRenderHint(QPainter.Antialiasing)
    if estado == M.PREFERENTE:
        p.setPen(_pen(OSCURO, 1.2)); p.setBrush(QColor(VERDE)); p.drawEllipse(r)
        p.setPen(_pen("white", max(1.5, r.width() * 0.12)))
        w, x, y = r.width(), r.x(), r.y()
        p.drawPolyline(QPolygonF([QPointF(x + .25 * w, y + .52 * w), QPointF(x + .43 * w, y + .7 * w), QPointF(x + .76 * w, y + .32 * w)]))
    elif estado == M.INDIFERENTE:
        p.setPen(_pen("#5a8ac0", 1.0)); p.setBrush(QColor("#cfe6fa"))
        k = r.width() * 0.12; p.drawEllipse(r.adjusted(k, k, -k, -k))
    elif estado == M.PROHIBIDO:
        p.setPen(_pen(OSCURO, 1.2)); p.setBrush(QColor(ROJO)); p.drawEllipse(r)
        p.setPen(_pen("white", max(1.5, r.width() * 0.13)))
        k = r.width() * 0.3
        p.drawLine(r.center() + QPointF(-k, -k), r.center() + QPointF(k, k))
        p.drawLine(r.center() + QPointF(-k, k), r.center() + QPointF(k, -k))
    elif estado == M.NO_PREF1:
        _cara(p, r, AMARILLO)
    elif estado == M.NO_PREF2:
        _cara(p, r, NARANJA)
    elif estado == M.PREFIJADO:
        w, x, y = r.width(), r.x(), r.y()
        p.setPen(_pen(OSCURO, 1.4)); p.drawLine(QPointF(x + .5 * w, y + .55 * w), QPointF(x + .5 * w, y + w))
        p.setBrush(QColor(ROJO)); p.setPen(_pen(OSCURO, 1.1))
        p.drawEllipse(QRectF(x + .22 * w, y, .56 * w, .56 * w))
        p.setBrush(QColor("white")); p.setPen(Qt.NoPen); p.drawEllipse(QRectF(x + .34 * w, y + .1 * w, .14 * w, .14 * w))
    else:  # valor desconocido: interrogación
        p.setPen(_pen(OSCURO)); p.setBrush(QColor("#dddddd")); p.drawEllipse(r)
        p.drawText(r, Qt.AlignCenter, "?")
    p.restore()


@lru_cache(None)
def icono_estado(estado: str, s: int = 24) -> QIcon:
    pm, p = _pm(s); pintar_estado(p, QRectF(0, 0, s, s), estado); p.end(); return QIcon(pm)


def _doc(p, x, y, w, h, color="#ffffff"):
    p.setPen(_pen()); p.setBrush(QColor(color)); p.drawRoundedRect(QRectF(x, y, w, h), 2.5, 2.5)


def _persona(p, cx, cy, s, color):
    p.setPen(_pen(OSCURO, 1.2)); p.setBrush(QColor(color))
    p.drawEllipse(QPointF(cx, cy - s * .35), s * .22, s * .22)
    p.drawChord(QRectF(cx - s * .42, cy - s * .05, s * .84, s * .8), 0, 180 * 16)


def _rejilla(p, x, y, w, h, colores=()):
    _doc(p, x, y, w, h)
    p.setBrush(QColor("#7a8199")); p.drawRect(QRectF(x, y, w, h * .25))
    cw, ch = w / 3, (h * .75) / 2
    for i, c in enumerate(colores):
        if c:
            p.setBrush(QColor(c)); p.setPen(Qt.NoPen)
            p.drawRect(QRectF(x + (i % 3) * cw + 1.5, y + h * .25 + (i // 3) * ch + 1.5, cw - 3, ch - 3))


@lru_cache(None)
def icono(nombre: str, s: int = 32) -> QIcon:
    pm, p = _pm(s); k = s / 32.0; p.scale(k, k)
    f = QFont("DejaVu Sans"); f.setBold(True); f.setPixelSize(13); p.setFont(f)
    if nombre == "nuevo":
        _doc(p, 8, 4, 16, 22); p.setPen(_pen(VERDE, 2.6)); p.drawLine(22, 20, 22, 30); p.drawLine(17, 25, 27, 25)
    elif nombre == "filtro":    # embudo
        p.setPen(_pen()); p.setBrush(QColor("#5a8fd8"))
        p.drawPolygon(QPolygonF([QPointF(4, 6), QPointF(28, 6), QPointF(18, 17), QPointF(18, 27), QPointF(14, 29), QPointF(14, 17)]))
    elif nombre == "abrir":
        p.setPen(_pen()); p.setBrush(QColor("#f3c64b")); p.drawRect(4, 9, 24, 17)
        p.setBrush(QColor("#f8dc80")); p.drawPolygon(QPolygonF([QPointF(4, 26), QPointF(9, 14), QPointF(30, 14), QPointF(28, 26)]))
    elif nombre == "guardar":
        p.setPen(_pen()); p.setBrush(QColor("#4a6fb5")); p.drawRoundedRect(5, 5, 22, 22, 2, 2)
        p.setBrush(QColor("white")); p.drawRect(9, 6, 14, 8); p.setBrush(QColor("#ccd")); p.drawRect(10, 19, 12, 8)
    elif nombre in ("atras", "adelante"):
        p.setPen(_pen()); p.setBrush(QColor(VERDE)); p.drawEllipse(4, 4, 24, 24)
        p.setPen(_pen("white", 2.6)); d = -1 if nombre == "atras" else 1
        p.drawLine(16 - 6 * d, 16, 16 + 6 * d, 16); p.drawLine(16 + 6 * d, 16, 16 + 1 * d, 11); p.drawLine(16 + 6 * d, 16, 16 + 1 * d, 21)
    elif nombre == "importar":
        p.setPen(_pen()); p.setBrush(QColor("#2b9c8f")); p.drawRoundedRect(4, 10, 20, 15, 2, 2); p.drawRect(10, 7, 8, 3)
        p.setPen(_pen(VERDE, 2.6)); p.drawLine(20, 18, 30, 18); p.drawLine(30, 18, 26, 14); p.drawLine(30, 18, 26, 22)
    elif nombre == "validar":
        p.setPen(_pen(VERDE, 3.6)); p.drawPolyline(QPolygonF([QPointF(5, 17), QPointF(13, 25), QPointF(27, 7)]))
    elif nombre == "generar":
        p.setPen(_pen()); p.setBrush(QColor("#d8f2d8")); p.drawRoundedRect(3, 3, 26, 26, 3, 3)
        p.setBrush(QColor(VERDE)); p.drawPolygon(QPolygonF([QPointF(11, 8), QPointF(24, 16), QPointF(11, 24)]))
    elif nombre == "insertar":
        p.setPen(_pen(VERDE, 3.4)); p.drawLine(16, 6, 16, 24); p.drawLine(7, 15, 25, 15); p.setPen(_pen(AZUL, 2.4)); p.drawLine(5, 28, 27, 28)
    elif nombre == "leer_csv":
        p.setPen(_pen(VERDE, 2.8)); p.drawLine(11, 5, 11, 17); p.drawLine(5, 11, 17, 11); p.drawLine(22, 13, 22, 25); p.drawLine(16, 19, 28, 19)
        p.setPen(_pen(AZUL, 2.2)); p.drawLine(4, 29, 28, 29)
    elif nombre == "pegar":
        p.setPen(_pen()); p.setBrush(QColor("#c9a46a")); p.drawRoundedRect(6, 6, 18, 22, 2, 2)
        _doc(p, 13, 12, 14, 17); p.setBrush(QColor("#888")); p.drawRect(11, 3, 8, 5)
    elif nombre == "opciones":
        _rejilla(p, 4, 8, 22, 18, ("#ccc",) * 6); p.setPen(_pen(NARANJA, 3)); p.drawLine(18, 26, 29, 5)
    elif nombre == "referencia":
        f.setPixelSize(26); p.setFont(f); p.setPen(QColor("#2c8a5a")); p.drawText(QRectF(0, 0, 32, 30), Qt.AlignCenter, "a")
    elif nombre == "limpiar":
        p.setPen(_pen()); p.setBrush(QColor("#f2a0b4")); p.save(); p.translate(16, 16); p.rotate(-35)
        p.drawRoundedRect(QRectF(-12, -6, 24, 12), 3, 3); p.setBrush(QColor("#4a6fb5")); p.drawRoundedRect(QRectF(4, -6, 8, 12), 2, 2); p.restore()
    elif nombre == "filtro":
        p.setPen(_pen()); p.setBrush(QColor("#9b6bd8")); p.drawPolygon(QPolygonF([QPointF(4, 6), QPointF(28, 6), QPointF(19, 17), QPointF(19, 27), QPointF(13, 24), QPointF(13, 17)]))
    elif nombre == "quitar_filtro":
        p.setPen(_pen(ROJO, 3.4)); p.drawLine(8, 8, 24, 24); p.drawLine(8, 24, 24, 8)
    elif nombre == "ayuda":
        p.setPen(_pen()); p.setBrush(QColor(VERDE)); p.drawEllipse(4, 4, 24, 24); p.setPen(QColor("white")); f.setPixelSize(18); p.setFont(f); p.drawText(QRectF(4, 4, 24, 24), Qt.AlignCenter, "?")
    elif nombre == "imprimir":
        p.setPen(_pen()); p.setBrush(QColor("#ddd")); p.drawRoundedRect(3, 12, 26, 12, 2, 2); _doc(p, 9, 4, 14, 9); _doc(p, 9, 20, 14, 9)
    elif nombre == "editor":
        p.setPen(_pen()); p.setBrush(QColor("#d84a3a")); p.drawRoundedRect(4, 4, 24, 24, 3, 3); _doc(p, 8, 8, 16, 16)
        p.setPen(_pen("#2a8a3a", 3)); p.drawLine(11, 22, 24, 9)
    # ---- listas (barra vertical) ----
    elif nombre == "l_marco":
        _rejilla(p, 4, 5, 24, 22, ("", "", "", "", "", ""))
        p.setPen(_pen("#999", 1)); [p.drawLine(4 + 8 * i, 11, 4 + 8 * i, 27) for i in (1, 2)]; p.drawLine(4, 19, 28, 19)
    elif nombre == "l_materias":
        for i, c in enumerate(("#d84a3a", VERDE, AZUL)):
            p.setPen(_pen()); p.setBrush(QColor(c)); p.drawRoundedRect(QRectF(5 + i, 21 - 7 * i, 22, 6), 1.5, 1.5)
    elif nombre == "l_grupos":
        for cx, c in ((10, AMARILLO), (22, AZUL), (16, VERDE)):
            _persona(p, cx, 17 if cx != 16 else 20, 14, c)
    elif nombre == "l_profesores":
        _persona(p, 16, 16, 24, "#4ab0c8")
    elif nombre == "l_aulas":
        p.setPen(_pen()); p.setBrush(QColor("#2f6b4a")); p.drawRect(4, 6, 24, 16); p.setPen(_pen("#8b5a2b", 2.4)); p.drawLine(9, 22, 7, 29); p.drawLine(23, 22, 25, 29)
        p.setPen(_pen("white", 1.2)); p.drawLine(8, 11, 18, 11); p.drawLine(8, 15, 14, 15)
    elif nombre == "l_conjuntos":
        for d in (0, 6):
            p.setPen(_pen()); p.setBrush(QColor("#2f6b4a" if d else "#4c8c68")); p.drawRect(4 + d, 4 + d, 20, 14)
    elif nombre == "l_cursos":
        p.setPen(_pen()); p.setBrush(QColor("#ffffff")); p.drawPolygon(QPolygonF([QPointF(16, 6), QPointF(30, 12), QPointF(16, 18), QPointF(2, 12)]))
        p.setBrush(QColor(OSCURO)); p.drawRect(10, 15, 12, 7); p.setPen(_pen(AMARILLO, 2)); p.drawLine(28, 12, 28, 22)
    elif nombre == "l_departamentos":
        _doc(p, 5, 5, 22, 22, "#f3e2b0"); p.setPen(_pen(OSCURO, 1.2)); [p.drawLine(9, 11 + 4 * i, 23, 11 + 4 * i) for i in range(4)]
    elif nombre == "l_tareas":
        _doc(p, 6, 4, 20, 24); p.setPen(_pen(VERDE, 2.2)); [p.drawPolyline(QPolygonF([QPointF(9, 10 + 7 * i), QPointF(11, 12 + 7 * i), QPointF(15, 8 + 7 * i)])) for i in range(3)]
        p.setPen(_pen(OSCURO, 1.2)); [p.drawLine(17, 10 + 7 * i, 23, 10 + 7 * i) for i in range(3)]
    elif nombre == "l_sesiones":
        _rejilla(p, 3, 5, 26, 22, ("#d84a3a", "", VERDE, "", AMARILLO, AZUL))
    elif nombre == "l_reuniones":
        for cx, cy in ((8, 10), (24, 10), (8, 24), (24, 24)):
            _persona(p, cx, cy, 11, "#c8a0e8")
        p.setPen(_pen()); p.setBrush(QColor("#c9a46a")); p.drawEllipse(12, 13, 8, 8)
    elif nombre == "l_guardias":
        p.setPen(_pen()); p.setBrush(QColor("#f2cf2a")); p.drawPolygon(QPolygonF([QPointF(16, 3), QPointF(28, 8), QPointF(26, 20), QPointF(16, 29), QPointF(6, 20), QPointF(4, 8)]))
        p.setPen(_pen(OSCURO, 2.4)); p.drawLine(16, 9, 16, 17); p.drawPoint(16, 22)
    elif nombre == "l_complementarias":
        _doc(p, 5, 3, 18, 24, "#e8eefc"); p.setPen(_pen("#d88a24", 3)); p.drawLine(14, 28, 29, 9)
    p.end()
    return QIcon(pm)
