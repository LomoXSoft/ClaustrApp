"""Planificador de horarios escolares (LomoXSoft). El nombre visible sale de la marca (ver textos.py)."""
from .textos import MARCA

__version__ = "0.0.3"
APP_NAME = MARCA["nombre"]
APP_EDITOR = MARCA["nombre_editor"]
VENDOR = MARCA["autor"]
AJUSTES = MARCA["clave_ajustes"]       # nombre de la sección de QSettings (se conserva el de siempre en la marca privada)
