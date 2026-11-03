"""Pantalla de carga (imagen y textos según la marca)."""
import os, sys
from PySide6.QtCore import Qt, QTimer, QRect
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont, QIcon
from PySide6.QtWidgets import QApplication, QSplashScreen

from . import __version__, APP_NAME, VENDOR
from .textos import MARCA
HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recursos")


class LaraSplash(QSplashScreen):
    """Splash con versión (de __version__) y mensaje de estado actualizable."""

    def __init__(self, status="Cargando..."):
        pm = QPixmap(os.path.join(HERE, MARCA["splash"]))  # fondo sin versión ni estado
        self._status = status
        super().__init__(pm, Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self.setWindowIcon(QIcon(os.path.join(HERE, "icon.png")))

    def set_status(self, text):
        self._status = text
        self.repaint()
        QApplication.processEvents()

    def drawContents(self, p: QPainter):
        w, h = self.width(), self.height()
        band = int(h * 0.735)
        # tapa la versión del fondo y la redibuja desde __version__
        p.fillRect(QRect(4, band + 4, w // 2, int(h * 0.15)), QColor(201, 205, 224))
        f = QFont("DejaVu Sans"); f.setBold(True); f.setPixelSize(40)
        p.setFont(f); p.setPen(QColor(58, 61, 76))
        p.drawText(QRect(24, band + 8, w // 2, 56), Qt.AlignLeft | Qt.AlignVCenter, __version__)
        f2 = QFont("DejaVu Sans"); f2.setPixelSize(12)
        p.setFont(f2); p.setPen(QColor(95, 99, 118))
        p.drawText(QRect(26, h - 32, w // 2, 20), Qt.AlignLeft | Qt.AlignVCenter, self._status)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME); app.setOrganizationName(VENDOR)
    app.setApplicationVersion(__version__)
    s = LaraSplash(); s.show(); app.processEvents()
    pasos = ["Cargando...", "Cargando listas de datos...", "Cargando motor de horarios...", "Listo"]
    out = os.environ.get("SPLASH_CAPTURA")  # ruta para captura de prueba
    def paso(i=0):
        s.set_status(pasos[i])
        if out and i == 1:
            s.grab().save(out)
        if i + 1 < len(pasos):
            QTimer.singleShot(700, lambda: paso(i + 1))
        else:
            QTimer.singleShot(500, app.quit)
    paso()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
