"""Selector de versión al arrancar («Recordar mi elección»)."""
from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox, QFrame
from .. import APP_NAME, VENDOR, AJUSTES
from .estilo import CSS

CLAVE_VERSION, CLAVE_RECORDAR = "interfaz/version", "interfaz/recordar"


def ajustes():
    return QSettings(VENDOR, AJUSTES)


def version_guardada():
    st = ajustes()
    if str(st.value(CLAVE_RECORDAR, "false")).lower() == "true":
        v = st.value(CLAVE_VERSION, "")
        if v in ("sencilla", "clasica"):
            return v
    return None


def recordar(version, si=True):
    st = ajustes(); st.setValue(CLAVE_VERSION, version); st.setValue(CLAVE_RECORDAR, "true" if si else "false")


class SelectorVersion(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sencilla"); self.setStyleSheet(CSS)
        self.setWindowTitle(f"{APP_NAME} — ¿Cómo quiere trabajar?")
        self.eleccion = None
        lay = QVBoxLayout(self); lay.setContentsMargins(28, 24, 28, 20); lay.setSpacing(14)
        t = QLabel("¿Cómo quiere trabajar?"); t.setObjectName("titulo"); lay.addWidget(t)
        fila = QHBoxLayout(); fila.setSpacing(16); lay.addLayout(fila)
        self.botones = {}
        for clave, tit, desc in (("sencilla", "Versión sencilla", "Paso a paso, con lenguaje llano.\n"
                                  "Recomendada para empezar y para el equipo directivo."),
                                 ("clasica", "Versión clásica", "Todas las listas y opciones avanzadas,\n"
                                  "como en el programa de siempre.")):
            f = QFrame(); f.setObjectName("tarjeta"); v = QVBoxLayout(f); v.setContentsMargins(18, 16, 18, 16)
            lt = QLabel(tit); lt.setStyleSheet("font-size:13pt;font-weight:600"); v.addWidget(lt)
            ld = QLabel(desc); ld.setObjectName("ayuda"); v.addWidget(ld)
            b = QPushButton(f"Usar la {tit.lower()}"); b.setObjectName("primario" if clave == "sencilla" else "")
            b.clicked.connect(lambda _=False, c=clave: self.elegir(c)); v.addWidget(b)
            self.botones[clave] = b; fila.addWidget(f)
        self.chk = QCheckBox("Recordar mi elección (se puede cambiar en Ver › Versión)"); lay.addWidget(self.chk)
        st = ajustes(); self.chk.setChecked(str(st.value(CLAVE_RECORDAR, "false")).lower() == "true")

    def elegir(self, clave):
        self.eleccion = clave
        recordar(clave, self.chk.isChecked())
        self.accept()


def preguntar(parent=None, forzar=None):
    """Devuelve 'sencilla' o 'clasica'. forzar: flag de línea de órdenes o elección recordada."""
    if forzar in ("sencilla", "clasica"):
        return forzar
    v = version_guardada()
    if v:
        return v
    d = SelectorVersion(parent)
    d.exec()
    return d.eleccion or "clasica"
