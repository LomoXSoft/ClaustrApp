"""A1: al aplicar periodos y renumerar, las plantillas/prefijados (<tramo dia indice>) siguen al mismo periodo."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import _rutas as _R
from horarios import xghc, periodos as PER, edicion as ED
fallos = 0
def check(c, m):
    global fallos; print(("OK   " if c else "FALLO") + " " + m); fallos += (not c)
p = xghc.cargar(os.path.join(_R.R, "SINTETICO_grande.xghc")); raiz = p.doc.raiz; arbol = ED.Arbol(raiz)
m = next(iter(p.marcos.values())); hora = {(m.id, t.dia, t.indice): (t.entrada, t.salida) for t in m.tramos}
def marcas():
    out = []
    for pa in raiz.iter():
        for tr in pa:
            if tr.tag == "tramo" and tr.get("dia") is not None and tr.get("indice") is not None:
                out.append((id(tr), tr.get("marco", m.id), int(tr.get("dia")), int(tr.get("indice")), (tr.text or "").strip()))
    return out
# fabricar marcas: un prefijado de sesión y una prohibición de profesor el lunes en el 3.er periodo y el martes en el 2.º
s = p.sesiones[0]
ED.volcar_plantilla(arbol, s.xml, {(m.id, 0, 2): "prefijado"}, m.id)
pr = raiz.find("profesores")[0]
ED.volcar_plantilla(arbol, pr, {(m.id, 1, 1): "prohibido", (m.id, 0, 4): "prohibido"}, m.id)
antes = [(x[1:], hora[x[1:4]]) for x in marcas() if x[1:4] in hora]
check(len(antes) >= 3, f"{len(antes)} marcas de plantilla antes")
fs = PER.filas(p)
lun = [f for f in fs if f["dia"] == 0]
fs.append({"marco": m.id, "dia": 0, "entrada": "07:30", "salida": "08:25", "tipo": "lectivo", "clave": "SINT-P0", "activo": True})
borrar = next(f for f in fs if f.get("orig") == (m.id, 0, 4))      # se elimina el 5.º periodo del lunes
fs.remove(borrar)
check(PER.aplicar(p, fs, ED, arbol), "aplicar")
import tempfile
X = os.path.join(tempfile.mkdtemp(), "SINT_remap.xghc"); xghc.guardar(p, X); p = xghc.cargar(X); raiz = p.doc.raiz
m2 = p.marcos[m.id]; hora2 = {(m.id, t.dia, t.indice): (t.entrada, t.salida) for t in m2.tramos}
check(hora2[(m.id, 0, 0)][0] == "07:30", "periodo nuevo primero el lunes (índices desplazados)")
despues = sorted((x[1:], hora2.get(x[1:4])) for x in marcas() if x[1:4] in hora2 or True)
from collections import Counter
ca = Counter((k[1], h, k[3]) for k, h in antes if k[:3] != (m.id, 0, 4))
cd = Counter((k[1], h, k[3]) for k, h in despues)
check(ca == cd, f"las {sum(ca.values())} marcas siguen en la misma hora (sin desplazarse)")
check(not any(d[0][:3] == (m.id, 0, 5) and d[1] == hora[(m.id, 0, 4)] and d[0][3] == "prohibido" for d in despues)
      and sum(1 for d in despues if d[0][3] == "prohibido" and d[0][1] == 0 and d[1] == hora[(m.id, 0, 4)]) == 0,
      "la marca del periodo borrado desaparece")
pref = p.sesiones[0].plantilla
check(any(v == "prefijado" and hora2[k] == hora[(m.id, 0, 2)] for k, v in pref.items()), "prefijado de sesión remapeado (modelo)")
print(f"\n{fallos} fallos")
