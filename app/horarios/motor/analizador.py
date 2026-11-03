"""Analizador de conflictos («Busca conjuntos mínimos de sesiones que no encajan», Depurador, botón id=3).
Modelo de factibilidad con un literal de suposición por unidad («la unidad se coloca entera»); si es infactible,
CP-SAT devuelve un núcleo (SufficientAssumptionsForInfeasibility) que se reduce por eliminación hasta un conjunto
mínimo (irreducible): quitando cualquiera de sus sesiones el resto sí encaja."""
from __future__ import annotations
import time
from ortools.sat.python import cp_model
from .cpsat import Modelo


def _modelo(pb, ids=None):
    mod = Modelo(pb, ligero=True).construir(); m = mod.m
    lits = {}
    for _w, falta, u, _k in mod.no_col:
        if isinstance(u, dict) and (ids is None or u["id"] in ids):
            if u["id"] not in lits:
                lits[u["id"]] = m.NewBoolVar(f"a{u['id']}")
            b = lits[u["id"]]
            m.Add(falta == 0).OnlyEnforceIf(b)
    return mod, lits


def _resolver(pb, ids, segundos, hilos, duro=False):
    mod, lits = _modelo(pb, ids)
    m = mod.m; m.ClearAssumptions()
    if duro:       # comprobación rápida de factibilidad (como la fase 1 del motor): suposiciones como restricciones
        for b in lits.values():
            m.Add(b == 1)
    else:
        m.AddAssumptions(list(lits.values()))
    s = cp_model.CpSolver(); s.parameters.max_time_in_seconds = segundos; s.parameters.num_workers = max(1, hilos)
    s.parameters.linearization_level = 0
    st = s.Solve(m)
    if st == cp_model.INFEASIBLE:
        inv = {v.Index(): k for k, v in lits.items()}
        return "infactible", [inv[i] for i in s.SufficientAssumptionsForInfeasibility() if i in inv]
    return ("factible" if st in (cp_model.OPTIMAL, cp_model.FEASIBLE) else "desconocido"), []


def analizar(pb: dict, segundos: float = 60.0, hilos: int = 4, parar=None, informar=None) -> dict:
    """{'estado': factible|infactible|desconocido, 'conjunto': [ids de unidad], 'minimo': bool, 'tiempo': s}."""
    t0 = time.time(); dur = lambda: time.time() - t0
    estado, _n = _resolver(pb, None, max(5.0, segundos / 3), hilos, duro=True)
    if estado == "factible":
        return {"estado": estado, "conjunto": [], "minimo": False, "tiempo": round(dur(), 1)}
    estado, nucleo = _resolver(pb, None, max(5.0, segundos / 3), hilos)
    if estado != "infactible":
        return {"estado": estado, "conjunto": [], "minimo": False, "tiempo": round(dur(), 1)}
    actual = sorted(nucleo); minimo = True; i = 0
    while i < len(actual):
        if dur() > segundos or (parar and parar.is_set()):
            minimo = False; break
        prueba = actual[:i] + actual[i + 1:]
        est, _nuc = _resolver(pb, set(prueba), min(10.0, max(1.0, segundos - dur())), hilos, duro=True)
        if est == "infactible":
            actual = prueba   # sigue siendo imposible sin la sesión i
        elif est == "factible":
            i += 1                                              # la sesión i es necesaria
        else:
            minimo = False; i += 1
        if informar:
            informar(len(actual), i)
    return {"estado": "infactible", "conjunto": actual, "minimo": minimo, "tiempo": round(dur(), 1)}


def describir(pb: dict, conjunto) -> list[str]:
    unid = {u["id"]: u for u in pb["unidades"]}
    return [f"{unid[i]['etiqueta']} — profesorado: {', '.join(unid[i]['profesores']) or '-'}" for i in conjunto if i in unid]
