"""Arranque: python -m horarios [archivo.xghc | resultado.lphr]"""
import sys
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from . import __version__, APP_NAME, VENDOR
from .splash import LaraSplash


def main():
    if "--autoprueba" in sys.argv:
        import os
        if not sys.platform.startswith("win"):   # en Windows se usa la plataforma nativa (fuentes del sistema)
            os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        a = sys.argv[sys.argv.index("--autoprueba") + 1:]
        from .autoprueba import ejecutar
        return ejecutar(a[0], a[1], int(a[2]) if len(a) > 2 else 60)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME); app.setOrganizationName(VENDOR); app.setApplicationVersion(__version__)
    app.setStyle("Fusion")
    s = LaraSplash(); s.show(); app.processEvents()
    s.set_status("Cargando módulos...")
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if args and args[0].lower().endswith(".lphr"):
        s.set_status("Abriendo el editor...")
        from .editor import VentanaEditor
        w = VentanaEditor(args[0])
        QTimer.singleShot(600, lambda: (w.show(), s.finish(w)))
        return app.exec()
    from .ventana import Planificador
    from .sencilla import selector
    forzar = "sencilla" if "--sencilla" in sys.argv else "clasica" if "--clasica" in sys.argv else None
    w = Planificador()
    if args:
        s.set_status("Abriendo " + args[0] + "...")
        w.abrir(args[0])
    s.hide()
    if selector.preguntar(None, forzar) == "sencilla":
        from .sencilla.ventana import VentanaSencilla
        vs = w.sencilla = VentanaSencilla(nucleo=w)
        if args and w.proyecto is not None:
            vs.mostrar_desde_nucleo(); vs.hide()
        w = vs
    s.show()
    s.set_status("Listo")
    QTimer.singleShot(900, lambda: (w.show(), s.finish(w)))
    return app.exec()


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()   # el motor se ejecuta en un proceso aparte (spawn); necesario con PyInstaller
    sys.exit(main())
