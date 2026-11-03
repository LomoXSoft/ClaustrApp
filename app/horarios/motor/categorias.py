"""Categorías de penalización del motor.

El motor y los .lphr usan códigos internos neutros (p. ej. «huecos_alumnos»); el texto visible se
obtiene al mostrar con nombre(). Los .lphr antiguos guardaban el texto visible: normalizar() los
convierte a códigos.
"""
from __future__ import annotations
from ..textos import TX, cargar_paquete

CODIGOS = ['cambios_aula', 'carga_desigual', 'desplazamientos', 'guardias_extremas', 'horas_seguidas', 'medias_jornadas', 'ocupaciones_no_pref', 'permanencia_dia', 'permanencia_semana', 'ultima_primera', 'semanas_distinta', 'dias_consecutivos', 'dias_no_seguidos', 'horas_extremas', 'semanas_misma', 'sueltas_variable', 'huecos_profes', 'huecos_alumnos', 'maximo_diario', 'minimo_diario', 'aula_no_preferente']


def nombre(codigo: str) -> str:
    """Texto visible de una categoría (o el propio valor si no es un código conocido)."""
    return TX("cat_" + codigo) if codigo in CODIGOS else codigo


def _textos_antiguos() -> dict:
    d = {}
    for modo in ("privado", "publico"):
        try:
            men = cargar_paquete(modo)["mensajes"]
        except OSError:
            continue
        for c in CODIGOS:
            if "cat_" + c in men:
                d[men["cat_" + c]] = c
    return d


def normalizar(resumen: dict) -> dict:
    """Convierte las claves de un resumen (códigos o textos antiguos) a códigos."""
    antiguos = None; out = {}
    for k, v in (resumen or {}).items():
        if k not in CODIGOS:
            antiguos = antiguos if antiguos is not None else _textos_antiguos()
            k = antiguos.get(k, k)
        out[k] = out.get(k, 0) + v
    return out
