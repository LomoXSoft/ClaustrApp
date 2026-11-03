"""«Calcular un horario parcial» (planificador de referencia, diálogo 690; icono embudo): el motor busca un horario solamente para los
elementos señalados (grupos de alumnos, reuniones y, opcionalmente, guardias y actividades complementarias).
Se filtra el problema, no el archivo; los ids de unidad se conservan."""
from __future__ import annotations
from ..textos import TX
import copy


def filtrar(pb: dict, grupos, reuniones=(), guardias=False, complementarias=False) -> dict:
    g = set(grupos); r = set(reuniones); q = copy.deepcopy(pb)
    q["unidades"] = [u for u in q["unidades"] if set(u["grupos"]) & g]
    ids = {u["id"] for u in q["unidades"]}
    q["distintos"] = [x for x in q["distintos"] if x[0] in ids and x[1] in ids]
    q["reuniones"] = [x for x in q["reuniones"] if x["nombre"] in r]
    if not guardias:
        q["guardias"] = []
    if not complementarias:
        q["complementarias"] = []
    q["parcial"] = {"grupos": sorted(g), "reuniones": sorted(r), "guardias": bool(guardias),
                    "complementarias": bool(complementarias)}
    return q


def anotacion(pb_completo: dict, q: dict) -> list[str]:
    """Líneas de «Anotación» (propias)."""
    p = q.get("parcial") or {}
    out = [TX("cuidado_resultado_parcial")]
    grupos = sorted({x for u in pb_completo["unidades"] for x in u["grupos"]})
    out += [f"{x} - Se ha omitido el horario del grupo." for x in grupos if x not in set(p.get("grupos", []))]
    out += [f"Se ha omitido la reunión: {x['nombre']}" for x in pb_completo["reuniones"] if x["nombre"] not in set(p.get("reuniones", []))]
    if not p.get("guardias"):
        out += [f"Se ha omitido el servicio de guardias: {x['nombre']}" for x in pb_completo["guardias"]]
    if not p.get("complementarias") and pb_completo["complementarias"]:
        out.append(TX("no_han_tenido_cuenta_actividades"))
    return out
