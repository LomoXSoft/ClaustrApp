"""A2: plantillas con varias semanas. Al pasar a 3 semanas la plantilla de la semana 1 se copia en s2 y s3; una
marca propia de s2 se conserva al pasar a 2 semanas; el motor respeta un prefijado de la semana 3."""
import sys, os, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import _rutas as _R
from horarios import xghc, semanas as SEM, edicion as ED
fallos = 0
def check(c, m):
    global fallos; print(("OK   " if c else "FALLO") + " " + m); fallos += (not c)
T = tempfile.mkdtemp()
p = xghc.cargar(os.path.join(_R.R, "SINTETICO_grande.xghc")); raiz = p.doc.raiz
pr = raiz.find("profesores")[0]; arbol = ED.Arbol(raiz)
m = next(iter(p.marcos.values()))
ED.volcar_plantilla(arbol, pr, {(m.id, 0, 0): "prohibido", (m.id, 4, 5): "noPreferente"}, m.id)
marcas = lambda e: sorted((int(t.get("dia")), int(t.get("indice")), (t.text or "").strip()) for t in e.iter("tramo") if t.get("dia"))
m1 = marcas(pr)
SEM.fijar_num_semanas(p, 3, ED)
m3 = marcas(pr)
check(len(m3) == 3 * len(m1) and (5, 0, "prohibido") in m3 and (14, 5, "noPreferente") in m3, f"plantilla copiada a las 3 semanas ({len(m1)} -> {len(m3)})")
# marca propia de s2 y paso a 2 semanas
pl = pr.find("plantilla"); x = next(t for t in pl if t.get("dia") == "5" and t.get("indice") == "0"); x.text = "preferente"
SEM.fijar_num_semanas(p, 2, ED)
m2 = marcas(pr)
check((5, 0, "preferente") in m2 and not any(d >= 10 for d, _, _ in m2), "s2 conserva su marca; s3 se borra al quitarla")
X = os.path.join(T, "SINT_plsem.xghc"); xghc.guardar(p, X); p = xghc.cargar(X)
check(marcas(p.doc.raiz.find("profesores")[0]) == m2, "ida y vuelta de la plantilla por semana")
# motor: prefijado de una sesión solo en la semana 2
from horarios.motor import problema
s = p.sesiones[1]
ED.volcar_plantilla(ED.Arbol(p.doc.raiz), s.xml, {(s.marco, 7, 1): "prefijado"}, s.marco)
SEM._recargar_plantillas(p)
pb = problema.construir(p)
us = [u for u in pb["unidades"] if s.id in u["sesiones"]]
check(any(u.get("semana") == 1 and u["prefijados"] for u in us) and not any(u.get("semana") == 0 and u["prefijados"] for u in us),
      "el motor recibe el prefijado solo en la unidad de la semana 2")
print(f"\n{fallos} fallos")
