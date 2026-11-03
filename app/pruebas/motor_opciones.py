"""Opciones del planificador de referencia conectadas al motor: días seguidos (prohibido / obligatoriamente), sinCambioAula,
desecharGuardias y contarHuecosMediodia. Trabaja en memoria sobre copias cargadas; no escribe archivos."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import _rutas as _R
from horarios import xghc, edicion as ED
from horarios.motor import problema, cpsat
fallos = 0
def check(c, m):
    global fallos
    print(("OK   " if c else "FALLO") + " " + m); fallos += (not c)

F = os.path.join(_R.R, "prueba1.xghc"); _R.exigir(F)

def con(fn):
    p = xghc.cargar(F); a = ED.Arbol(p.doc.raiz); fn(a); return xghc.construir(p.doc, F)

def todas(valor, tag="permitirImpartanEnDiasSeguidos"):
    def fn(a):
        for s in a.raiz.find("sesionesLectivas").findall("sesion"):
            ED.escribir(a, s, "opciones/" + tag, valor)
    return fn

def dias_por_unidad(pb, r):
    orden = {m: {d: i for i, d in enumerate(ds)} for m, ds in pb["dias"].items()}
    out = {}
    for pz in r["sesiones"]:
        out.setdefault(pz["unidad"], []).append(orden[pz["marco"]][pz["dia"]])
    return {u: sorted(v) for u, v in out.items()}

for modo in ("prohibido", "obligatoriamente"):
    pb = problema.construir(con(todas(modo)))
    r = cpsat.resolver(pb, segundos=15)
    du = dias_por_unidad(pb, r); multi = {u: d for u, d in du.items() if len(d) >= 2}
    if modo == "prohibido":
        U = {u["id"]: u for u in pb["unidades"]}
        malos = [u for u, d in multi.items() if any(b - a == 1 for a, b in zip(d, d[1:]))
                 or (U[u]["lunes_viernes"] and 0 in d and len(pb["dias"][U[u]["marco"]]) - 1 in d)]
    else:
        U = {u["id"]: u for u in pb["unidades"]}
        def vecino(x, y, u):
            n = len(pb["dias"][U[u]["marco"]])
            return abs(x - y) == 1 or (U[u]["lunes_viernes"] and n >= 5 and {x, y} == {0, n - 1})
        malos = [u for u, d in multi.items() if any(not any(vecino(x, y, u) for y in d if y != x) for x in d)]
    check(not malos and multi, f"días seguidos «{modo}»: {len(multi)} unidades con varias piezas, incumplen {len(malos)}"
                                f" (no colocadas {r['estadisticas'].get('no_colocadas')})")

pb = problema.construir(con(todas("true", "sinCambioAula")))
check(all(u["sin_cambio_aula"] for u in pb["unidades"]), "sinCambioAula llega a las unidades")
r = cpsat.resolver(pb, segundos=10)
por_u = {}
for pz in r["sesiones"]:
    check(not pz["aula_no_preferente"], "") if pz["aula_no_preferente"] else None
    if pz["aulas"]:
        por_u.setdefault(pz["unidad"], set()).add(tuple(pz["aulas"]))
check(all(len(v) == 1 for v in por_u.values()), f"sinCambioAula: misma aula en todas las piezas ({len(por_u)} unidades con aula)")

pb0 = problema.construir(con(lambda a: None))
pb1 = problema.construir(con(lambda a: ED.escribir(a, a.raiz, "otros/opciones/opcionesGenerales/desecharGuardias", "true")))
check(not pb0["desechar_guardias"] and pb1["desechar_guardias"], "desecharGuardias se lee de opcionesGenerales")
m1 = cpsat.Modelo(pb1).construir() if hasattr(cpsat, "Modelo") else None
if m1 is not None:
    pg = [w for w, _e, u, _k in m1.no_col if isinstance(u, tuple) and u[0] == "guardia"]
    check(pg and all(w == cpsat.PESO_GUARDIA_DESECHABLE for w in pg), f"guardias desechables con peso {cpsat.PESO_GUARDIA_DESECHABLE}")

def mediodia(a):
    ED.escribir(a, a.raiz, "otros/opciones/opcionesGenerales/contarHuecosMediodia", "true")
q = problema.construir(con(mediodia)); check(q["contar_huecos_mediodia"], "contarHuecosMediodia se lee de opcionesGenerales")
check(all(len(v) <= 1 for v in q["filas_prof"].values()), "con contarHuecosMediodia: una sola fila por día")
EJ = os.path.join(_R.X, "ejemploFormacionProConMediodia.xghc")
if os.path.exists(EJ):
    p = xghc.cargar(EJ); a = ED.Arbol(p.doc.raiz)
    check(problema.construir(p)["contar_huecos_mediodia"], "ejemplo con mediodía: contarHuecosMediodia=true (una fila)")
    ED.borrar(a, a.raiz, "otros/opciones/opcionesGenerales/contarHuecosMediodia")
    q = problema.construir(xghc.construir(p.doc, EJ))
    check(not q["contar_huecos_mediodia"] and any(len(v) == 2 for v in q["filas_prof"].values()),
          "ejemplo con mediodía: sin la opción, los huecos de profesor se cuentan por separado mañana/tarde")
print("FALLOS:", fallos); sys.exit(1 if fallos else 0)
