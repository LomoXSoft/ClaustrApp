"""B1: importador Delphos (principal + KRONOWIN opcional) sin GUI. Las muestras *_anon solo se usan aquí, para
contar; no se imprime ni se guarda su contenido."""
import os, sys, glob, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import _rutas as _R
from lxml import etree
from horarios import xghc, delphos as DL, edicion as ED

F = 0
def check(c, m):
    global F
    print(("OK   " if c else "FALLO"), m); F += (not c)

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "datos")
BASE = os.path.join(_R.R, "SINTETICO_grande.xghc")
XSD = etree.XMLSchema(etree.parse(_R.XSD))

def importar(pen, kro, modo="nuevo", base=BASE):
    p = xghc.cargar(base); r = p.doc.raiz; a = ED.Arbol(r); inc = DL.Incidencias()
    P = DL.leer(pen, inc) if pen else None
    K = DL.leer(kro, inc) if kro else None
    if P is None:
        P, K = K, None
    antes = p.doc.serializar()
    DL.importar(r, P, ED, a, modo, kro=K, inc=inc)
    return p, inc, antes

def _norm():
    import re
    return {re.sub(r"'[^']*'", "'…'", e.message) + " @" + re.sub(r"\[\d+\]", "", e.path) for e in XSD.error_log}

XSD.validate(etree.fromstring(xghc.cargar(BASE).doc.serializar())); _BASE = _norm()   # el SINT de partida ya trae avisos

def errores_xsd(xml):
    """Errores del XSD nuevos respecto al proyecto de partida."""
    XSD.validate(etree.fromstring(xml))
    return sorted(_norm() - _BASE)

# 1. sintético principal + KRONOWIN
p, inc, antes = importar(os.path.join(D, "delphos_sintetico.xml"), os.path.join(D, "delphos_sintetico_kronowin.xml"))
c = inc.cuentas
check(c.get("grupos") == 4 and c.get("profesores") == 8 and c.get("aulas") == 5 and c.get("tareas") == 5, f"cuentas {dict(c)}")
check(c.get("cursos") == 3 and c.get("cursos de la oferta sin grupos (no importados)") == 1, "cursos sin grupos fuera")
check(any("recreo" in t for _, _, t in inc.lineas), "recreo propuesto e informado")
check(any("N_HORAS vacío" in t for _, _, t in inc.lineas), "N_HORAS vacío informado")
xml = p.doc.serializar()
T = tempfile.mkdtemp(); X = os.path.join(T, "SINT_delphos.xghc")
open(X, "wb").write(xml)
p2 = xghc.cargar(X)
m = list(p2.marcos.values())[0]
ini = [t.entrada for t in m.tramos if t.dia == 0]
check(ini == sorted(ini) and len(ini) == 6, f"intervalos ordenados: {ini}")
check([t.tipo for t in m.tramos if t.dia == 0].count("recreo") == 1, "un recreo por día")
check(all(t.clave for t in m.tramos), "todos los periodos con clavX")
check(len(p2.sesiones) == c.get("sesiones propuestas (sin profesor)") == 19, f"sesiones propuestas: {len(p2.sesiones)}")
check(all(s.tmp and len(s.tmp) <= 5 for s in p2.sesiones), "sesiones de N_HORAS/60 periodos sueltos")
r2 = p2.doc.raiz
check(all(e.findtext("claveDeExportacion") for e in r2.find("profesores")), "profesores con clave externa")
check(all(e.findtext("tomaDePosesion") for e in r2.find("profesores")), "profesores con toma de posesión")
check(r2.findtext("otros/origenDatos") == DL.ORIGEN and r2.findtext("otros/claveXDias/lunes"), "origenDatos y claveXDias")
check(r2.find("cursos/curso/materiasDelCurso/materia") is not None, "materias del curso")
check(r2.findtext("tareas/lectivaPorDefecto") in {(t.findtext("nombre") or "") for t in r2.find("tareas").findall("tarea")},
      "se conserva la tarea lectiva por defecto")
errs = errores_xsd(xml)
check(not errs, f"XSD válido ({len(errs)} errores){': ' + errs[0] if errs else ''}")
check(xghc.serializar(p2) == xml, "ida y vuelta estable")

# 2. deshacer: el XML anterior se restaura (la GUI apila doc.serializar())
p3 = xghc.cargar(BASE)
check(p3.doc.serializar() == antes, "estado anterior intacto para deshacer")

# 3. actualizar: idempotente (no duplica) y conserva nombres cambiados por la usuaria
for e in r2.find("grupos"):
    if e.findtext("claveDeExportacion"):
        a2 = ED.Arbol(r2); v = e.findtext("nombre")
        ED.escribir(a2, e, "nombre", "SINT-renombrado"); ED.renombrar_referencias(a2, "grupos", v, "SINT-renombrado"); break
open(X, "wb").write(p2.doc.serializar())
p4, inc4, _ = importar(os.path.join(D, "delphos_sintetico.xml"), os.path.join(D, "delphos_sintetico_kronowin.xml"),
                       "actualizar", X)
r4 = p4.doc.raiz
check(len(r4.find("grupos").findall("grupo")) == 4 and len(r4.find("profesores").findall("profesor")) == 8, "sin duplicados")
check(any((g.findtext("nombre") or "") == "SINT-renombrado" for g in r4.find("grupos")), "nombre de la usuaria conservado")
check(inc4.cuentas.get("sesiones ya existentes (no se duplican)") == 19, "sesiones no duplicadas")

# 4. modo claves: no toca el XML
p5, inc5, antes5 = importar(os.path.join(D, "delphos_sintetico.xml"), None, "claves")
check(p5.doc.serializar() == antes5 and len(inc5.claves["profesores"]) == 8, "modo claves: catálogo sin modificar")

# 5. solo KRONOWIN
p6, inc6, _ = importar(None, os.path.join(D, "delphos_sintetico_kronowin.xml"))
check(inc6.cuentas.get("grupos") == 4 and inc6.cuentas.get("sesiones propuestas (sin profesor)", 0) > 0, "solo KRONOWIN")

# 6. errores tolerados
bad = os.path.join(T, "malo.xml")
open(bad, "w").write('<SERVICIO><SALIDAS><ERROR><CN_ERROR>3</CN_ERROR><TE_ERROR>SINT error</TE_ERROR></ERROR></SALIDAS></SERVICIO>')
try:
    DL.leer(bad, DL.Incidencias()); check(False, "CN_ERROR detectado")
except DL.ErrorDelphos:
    check(True, "CN_ERROR detectado")

# 7. muestras anonimizadas (confidenciales): solo recuentos
M = sorted(glob.glob(os.path.join(_R.MUESTRAS, "*_anon.xml")))
pen = [f for f in M if "kronowin" not in f]; kro = [f for f in M if "kronowin" in f]
if pen:
    p7, inc7, _ = importar(pen[0], kro[0] if kro else None)
    x7 = p7.doc.serializar()
    c7 = inc7.cuentas
    check(c7.get("grupos", 0) > 0 and c7.get("profesores", 0) > 0 and c7.get("intervalos", 0) > 0,
          f"muestra anon: {len(c7)} tipos de recuento, {len(inc7.errores)} errores")
    e7 = errores_xsd(x7); check(not e7, f"muestra anon: XSD válido {e7[:3]}")
    open(X, "wb").write(x7)
    check(len(xghc.cargar(X).sesiones) == c7.get("sesiones propuestas (sin profesor)", 0), "muestra anon: recarga")
    os.remove(X)
else:
    print("AVISO sin muestras anonimizadas")
print("FALLOS:", F)
