"""Archivo > Nuevo: proyecto vacío a partir de la plantilla recursos/nuevo.xghc.xml (sin datos de centro)."""
import os
from . import xghc

PLANTILLA = os.path.join(os.path.dirname(__file__), "recursos", "nuevo.xghc.xml")


def crear(perfil="avanzado"):  # el perfil lo aplica después el asistente (450)
    with open(PLANTILLA, "rb") as f:
        xml = f.read()
    p = xghc.construir(xghc.Documento(xml), "")
    p.contenedor = xghc.Contenedor(None, b"", xml, b"")   # se guarda como XML plano
    p.ruta_original = None; p.ruta_guardado = None; p.modificado = False
    return p
