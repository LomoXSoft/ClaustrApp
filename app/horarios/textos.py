"""Paquetes de textos y marca: un solo código para dos presentaciones.

* Paquete PRIVADO (uso en el centro): recursos/dialogos.json, recursos/menus_editor.json y
  recursos/mensajes_privados.json, más recursos/marca.json. No se publican.
* Paquete PÚBLICO (copia para GitHub): recursos/textos_propios.json (secciones «dialogos»,
  «menus_editor» y «mensajes», con las mismas claves y textos redactados de nuevo) y
  recursos/marca_publica.json.

Se usa el privado si recursos/dialogos.json existe; si no, el público. La variable de entorno
TEXTOS_PUBLICOS=1 fuerza el público aunque exista el privado (para probarlo sin cambiar de carpeta).
La marca se elige igual (marca.json si existe y no se fuerza el público).
"""
from __future__ import annotations
import json
import os

DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recursos")
FORZAR_PUBLICO = os.environ.get("TEXTOS_PUBLICOS", "") == "1"

PRIVADOS = {"dialogos": "dialogos.json", "menus_editor": "menus_editor.json", "mensajes": "mensajes_privados.json"}
PUBLICO = "textos_propios.json"


def _leer(nombre):
    with open(os.path.join(DIR, nombre), encoding="utf-8") as f:
        return json.load(f)


def hay_privado() -> bool:
    return not FORZAR_PUBLICO and os.path.exists(os.path.join(DIR, PRIVADOS["dialogos"]))


MODO = "privado" if hay_privado() else "publico"


def cargar_paquete(modo: str = MODO) -> dict:
    """Devuelve {"dialogos":…, "menus_editor":…, "mensajes":…} del paquete pedido."""
    if modo == "privado":
        return {k: _leer(v) for k, v in PRIVADOS.items()}
    return _leer(PUBLICO)


_P = cargar_paquete()
DIALOGOS = _P["dialogos"]
MENUS_EDITOR = _P["menus_editor"]
MENSAJES = _P["mensajes"]


def TX(clave: str, **valores) -> str:
    """Texto de mensaje por clave; con valores, se rellenan los {campos}."""
    s = MENSAJES[clave]
    return s.format(**valores) if valores else s


def cargar_marca() -> dict:
    priv = os.path.join(DIR, "marca.json")
    return _leer("marca.json" if (not FORZAR_PUBLICO and os.path.exists(priv)) else "marca_publica.json")


MARCA = cargar_marca()


def formatos_antiguos() -> list:
    """Identificadores de formato .lphr de versiones anteriores (de la marca activa y, si existe, de la privada)."""
    ids = list(MARCA.get("formatos_antiguos", []))
    if os.path.exists(os.path.join(DIR, "marca.json")):
        ids += _leer("marca.json").get("formatos_antiguos", [])
    return ids
