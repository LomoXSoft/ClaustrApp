"""Escribe en un .cmd las variables de marca y versión para construir_windows.bat.

Uso: python info_marca.py SALIDA.cmd
Se escribe en la página de códigos OEM de la consola para que cmd lea bien las tildes.
"""
import ctypes
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "app"))

from horarios import __version__  # noqa: E402
from horarios.textos import MARCA  # noqa: E402

try:
    cp = "cp%d" % ctypes.windll.kernel32.GetOEMCP()
except Exception:  # fuera de Windows
    cp = "utf-8"

valores = {
    "NOMBRE": MARCA["nombre_archivo"],
    "VERSION": __version__,
    "APPID": MARCA.get("appid_inno", ""),
    "TITULO": MARCA["nombre"],
}
with open(sys.argv[1], "w", encoding=cp, errors="replace", newline="\r\n") as f:
    for k, v in valores.items():
        f.write('set "%s=%s"\n' % (k, v))
