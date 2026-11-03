"""A3: semanas de sesión en <distribucionPeriodica> (GHCFile.xsd), ida y vuelta, y lectura del formato provisional."""
import sys, os, tempfile, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import _rutas as _R
from horarios import xghc, semanas as SEM, edicion as ED
from lxml import etree
fallos = 0
def check(c, m):
    global fallos; print(("OK   " if c else "FALLO") + " " + m); fallos += (not c)
T = tempfile.mkdtemp()
p = xghc.cargar(os.path.join(_R.R, "SINTETICO_grande.xghc")); raiz = p.doc.raiz; arbol = ED.Arbol(raiz)
SEM.fijar_num_semanas(p, 3, ED); noms = ["s1", "s2", "s3"]
ses = p.sesiones
var = next((s for s in ses if s.xml.find("distribucionSemanal/distribucionVariable") is not None), None)
SEM.fijar_sesion(ses[0].xml, ["s1", "s3"], "obligatorio", ED, arbol, noms)
SEM.fijar_sesion(ses[1].xml, ["s2"], "ignorar", ED, arbol, noms)
if var is not None:
    SEM.fijar_sesion(var.xml, ["s1", "s2"], "prohibido", ED, arbol, noms)
esperado = {s.id: SEM.de_sesion(s.xml, noms) for s in ses}
mem_antes = xghc.serializar(p)
check(raiz.find(".//distribucionPeriodica") is None and ses[0].xml.find("enPeriodos") is not None, "tras serializar el árbol vuelve a la forma interna")
X = os.path.join(T, "SINT_sem.xghc"); xml = xghc.guardar(p, X)
d = etree.fromstring(xml)
s0 = d.xpath(f"//sesion[distribucionPeriodica]")
check(len(s0) == len(ses) and not d.xpath("//sesion/enPeriodos") and not d.xpath("//sesion/distribucionSemanal"),
      f"fichero: {len(s0)} sesiones con distribucionPeriodica, sin enPeriodos ni distribucionSemanal directos")
r0 = d.xpath("//sesion[distribucionPeriodica/distribucionPeriodicaFija/enPeriodos[refPeriodo='s3']][mismaPosicionDistintosPeriodos='obligatorio']")
check(len(r0) >= 1, "fija: distribucionSemanal + enPeriodos dentro de distribucionPeriodicaFija; misma posición como hermano")
if var is not None:
    check(bool(d.xpath("//distribucionPeriodicaVariable/distribucionTotal/distribucionVariable")), "variable: distribucionTotal")
# validación con el XSD del fragmento de sesión: orden y contenido
xsd = _R.XSD
try:
    sch = etree.XMLSchema(etree.parse(xsd)); ok = sch.validate(d)
    errs = [e.message for e in sch.error_log if "distribucionPeriodica" in e.message or "enPeriodos" in e.message]
    check(not errs, f"XSD: sin errores en distribucionPeriodica/enPeriodos ({'válido' if ok else 'otros avisos ajenos'})")
except etree.XMLSchemaParseError as e:
    print("AVISO XSD no cargable:", e)
p2 = xghc.cargar(X)
check({s.id: SEM.de_sesion(s.xml, noms) for s in p2.sesiones} == esperado, "ida y vuelta: mismas semanas y modos")
check(xghc.serializar(p2) == xml, "segunda escritura idéntica (estable)")
# formato provisional anterior: enPeriodos directo
prov = re.sub(rb"<distribucionPeriodica><distribucionPeriodicaFija>(.*?)</distribucionPeriodicaFija></distribucionPeriodica>", rb"\1", mem_antes, flags=re.S)
prov = mem_antes if prov == mem_antes else prov
Xp = os.path.join(T, "SINT_prov.xghc")
open(Xp + ".xml", "wb").write(mem_antes)
p3 = xghc.construir(xghc.Documento(mem_antes))
# construir un XML provisional explícito: forma interna sin convertir
import copy
pr = xghc.cargar(X); r = pr.doc.raiz
volver = lambda: None
xml_prov = etree.tostring(etree.fromstring(xghc.serializar(pr)))
xp = etree.fromstring(xml_prov)
for sx in xp.xpath("//sesion[distribucionPeriodica]"):
    dp = sx.find("distribucionPeriodica"); inner = dp[0]; i = sx.index(dp); sx.remove(dp)
    for j, c in enumerate(list(inner)):
        if c.tag == "distribucionTotal": c.tag = "distribucionSemanal"
        if c.tag == "enPeriodos" and len(c) == 3: continue
        sx.insert(i + j, c)
p4 = xghc.construir(xghc.Documento(etree.tostring(xp, xml_declaration=True, encoding="ISO-8859-1")))
check({s.id: SEM.de_sesion(s.xml, noms) for s in p4.sesiones} == esperado, "lee el formato provisional (enPeriodos directo)")
check(b"distribucionPeriodica" in xghc.serializar(p4), "y lo escribe en el formato del XSD")
print(f"\n{fallos} fallos")
