"""Formato de resultado propio del programa: .lphr (JSON UTF-8). Documentado en ui_spec.md, Anexo F.

    {
      "formato": "horario-lphr", "version": 1,
      "generado": "2026-11-01T13:50:00+01:00", "aplicacion": "<nombre de la marca> 0.0.2",
      "configuracion": {"archivo": "nombre.xghc", "sha256": "<del XML de configuración>"},
      "motor": {"nombre": "cpsat", "segundos": 60, "semilla": 0},
      "estadisticas": {...},                                  # tiempo, estado, peso, no_colocadas, resumen...
      "sesiones": [{"sesiones": ["12","14"], "marco": "A", "dia": 0, "tramos": [3,4], "aulas": ["A-1"],
                    "aula_no_preferente": false, "pieza": 0, "unidad": 7}],
      "guardias": [{"servicio", "profesor", "marco", "dia", "tramo"}],
      "reuniones": [{"reunion", "marco", "dia", "tramos"}],
      "complementarias": [{"id", "tarea", "profesor", "marco", "dia", "tramo"}],
      "no_colocadas": [{"tipo": "sesion"|"guardia"|"reunion"|"complementaria", ...}]
    }

Días e índices de tramo son los de <marcosDeHorario> del .xghc (dia 0 = primer día). El archivo no contiene
datos personales aparte de los nombres ya presentes en la configuración.

Exportadores: registro extensible. El formato .xrho (resultado de GHC) NO se conoce: su exportador es un
marcador que lanza NotImplementedError hasta que se documente con archivos reales.
"""
from __future__ import annotations
import datetime, hashlib, json, os
from .textos import TX
from .motor import categorias as CAT
from . import __version__, APP_NAME
from .textos import MARCA, formatos_antiguos

FILTRO_LPHR = f"Resultado de {APP_NAME} (*.lphr)"

FORMATO = "horario-lphr"
FORMATOS_LEIDOS = {FORMATO, *formatos_antiguos()}   # identificadores de versiones anteriores
VERSION = 1
EXTENSION = ".lphr"
CAMPOS_PIEZA = ("unidad", "sesiones", "marco", "dia", "tramos", "aulas", "aula_no_preferente", "pieza", "avisos")


def huella(ruta_xghc: str) -> str:
    from . import xghc
    try:
        return hashlib.sha256(xghc.leer_contenedor(ruta_xghc).xml).hexdigest()
    except Exception:
        return ""


def crear(resultado: dict, ruta_xghc: str = "", motor: dict | None = None) -> dict:
    return {
        "formato": FORMATO, "version": VERSION,
        "generado": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "aplicacion": f"{APP_NAME} {__version__}",
        "configuracion": {"archivo": os.path.basename(ruta_xghc), "sha256": huella(ruta_xghc) if ruta_xghc else ""},
        "motor": motor or {"nombre": "cpsat"},
        "estadisticas": resultado.get("estadisticas", {}),
        "sesiones": [{k: pz[k] for k in CAMPOS_PIEZA if k in pz} for pz in resultado.get("sesiones", [])],
        "guardias": resultado.get("guardias", []), "reuniones": resultado.get("reuniones", []),
        "complementarias": resultado.get("complementarias", []), "no_colocadas": resultado.get("no_colocadas", []),
    }


def guardar(doc: dict, ruta: str) -> None:
    if not ruta.lower().endswith(EXTENSION):
        ruta += EXTENSION
    tmp = ruta + ".tmp~"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    os.replace(tmp, ruta)


def cargar(ruta: str) -> dict:
    with open(ruta, encoding="utf-8") as f:
        doc = json.load(f)
    if doc.get("formato") not in FORMATOS_LEIDOS:
        raise ValueError(f"No es un resultado de {APP_NAME} (.lphr)")
    if int(doc.get("version", 0)) > VERSION:
        raise ValueError(f"Versión de resultado {doc['version']} no soportada")
    for k in ("sesiones", "guardias", "reuniones", "complementarias", "no_colocadas"):
        doc.setdefault(k, [])
    return doc


def corresponde(doc: dict, ruta_xghc: str) -> bool:
    """¿El resultado se generó con esta misma configuración?"""
    h = doc.get("configuracion", {}).get("sha256")
    return bool(h) and h == huella(ruta_xghc)


# ---------------------------------------------------------------- exportadores
EXPORTADORES = {}


def exportador(ext, descripcion):
    def reg(f):
        EXPORTADORES[ext] = (descripcion, f); return f
    return reg


@exportador(".lphr", FILTRO_LPHR)
def _exp_lphr(doc, ruta, proyecto=None):
    guardar(doc, ruta)


@exportador(".xrho", "Resultado de GHC (*.xrho) — no disponible")
def _exp_xrho(doc, ruta, proyecto=None):
    raise NotImplementedError("El formato .xrho no está documentado; se implementará al disponer de archivos reales.")


def exportar(doc, ruta, proyecto=None):
    ext = os.path.splitext(ruta)[1].lower()
    if ext not in EXPORTADORES:
        raise ValueError(f"Formato de exportación desconocido: {ext}")
    return EXPORTADORES[ext][1](doc, ruta, proyecto)


def resumen_texto(doc: dict) -> str:
    e = doc.get("estadisticas", {})
    lin = [f"Configuración: {doc.get('configuracion', {}).get('archivo', '')}",
           f"Generado: {doc.get('generado', '')}",
           TX("resumen_estado_tiempo", estado=e.get('estado', ''), tiempo=e.get('tiempo', '')),
           TX("resumen_peso_no_colocadas", peso=e.get('peso', ''), n=e.get('no_colocadas', '')) +
           f"   Guardias no colocadas: {e.get('guardias_no_colocadas', 0)}",
           f"Resultados completos encontrados: {e.get('completos', '')} de {e.get('resultados', '')}",
           f"Piezas colocadas: {len(doc.get('sesiones', []))}   Guardias: {len(doc.get('guardias', []))}"
           f"   Reuniones: {len(doc.get('reuniones', []))}   Complementarias: {len(doc.get('complementarias', []))}", ""]
    for k, v in sorted(CAT.normalizar(e.get("resumen", {})).items()):
        lin.append(f"  {CAT.nombre(k)}: {v}")
    return "\n".join(lin)
