"""Prueba de ida y vuelta: abrir -> guardar -> reabrir -> comparar XML semánticamente."""
import sys, os, difflib, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import _rutas as _R
import xml.etree.ElementTree as ET
from horarios import xghc, edicion as ED

EJ = _R.disponibles(os.path.join(_R.R, "prueba1.xghc"), os.path.join(_R.R, "prueba2.xghc"), os.path.join(_R.X, "ejemploDosMarcosHorarios.xghc"), os.path.join(_R.X, "ejemploFormacionProConMediodia.xghc"), next((r for r in (os.path.join(_R.R, "SINT_instituto.xghc"), os.path.join(_R.RAIZ, "dist", "ejemplos", "SINT_instituto.xghc")) if os.path.exists(r)), os.path.join(_R.R, "SINT_instituto.xghc")), os.path.join(_R.R, "SINTETICO_grande.xghc"))


def canon(e, ruta=""):
    """Lista de líneas canónicas (ruta, atributos, texto) para un diff semántico."""
    r = f"{ruta}/{e.tag}" + (f"[@id={e.get('id')}]" if e.get("id") else "")
    out = [f"{r} {sorted(e.attrib.items())} {(e.text or '').strip()!r}"]
    for c in e:
        out += canon(c, r)
    return out


def diff(a, b):
    return [l for l in difflib.unified_diff(canon(a), canon(b), lineterm="", n=0) if l[:1] in "+-" and l[:3] not in ("+++", "---")]


fallos = 0
tmp = tempfile.mkdtemp()
for f in EJ:
    nombre = os.path.basename(f)
    orig_bytes = open(f, "rb").read()
    p = xghc.cargar(f)
    # 1) sin cambios
    out = os.path.join(tmp, nombre.replace(".xghc", "_lph.xghc"))
    xghc.guardar(p, out)
    ident = open(out, "rb").read() == orig_bytes
    c2 = xghc.leer_contenedor(out)
    print(f"{nombre}: sin cambios -> archivo idéntico byte a byte: {ident}; "
          f"prefijo/cola iguales: {c2.prefijo == p.contenedor.prefijo and c2.cola == p.contenedor.cola}")
    fallos += not ident
    # 2) con ediciones
    raiz0 = ET.fromstring(p.contenedor.xml)
    ar = ED.Arbol(p.doc.raiz)
    s0 = p.doc.raiz.find("sesionesLectivas")[0]
    prof = p.doc.raiz.find("profesores")[0]
    viejo = ED.leer(prof, "nombre")
    ED.set_campo_sesion(ar, s0, "tmp", "21")
    ED.renombrar(ar, "profesores", prof, "PROF_PRUEBA")
    ED.escribir(ar, prof, "opciones/maximasHorasSeguidas", "4")
    nueva = ED.insertar_sesion(ar, s0, "M_PRUEBA", ED.leer(s0, "grupo"), "PROF_PRUEBA")
    ED.volcar_plantilla(ar, nueva, {("A", 0, 0): "prohibido"})
    xghc.guardar(p, out)
    p2 = xghc.cargar(out)
    d = diff(raiz0, ET.fromstring(p2.contenedor.xml))
    refs = sum(1 for x in raiz0.iter() if len(x) == 0 and (x.text or "").strip() == viejo)
    esperado_otros = [l for l in d if "PROF_PRUEBA" not in l and "M_PRUEBA" not in l
                      and "distribucion" not in l and "duracionSemanal" not in l
                      and "maximasHorasSeguidas" not in l and repr(viejo) not in l and f"id={nueva.get('id')}" not in l]
    print(f"  editado: {len(d)} líneas de diff semántico; referencias renombradas al profesor: {refs}; "
          f"cambios inesperados: {len(esperado_otros)}; sesiones {len(p.sesiones)}->{len(p2.sesiones)}")
    for l in esperado_otros[:10]:
        print("   !", l[:60])
    fallos += bool(esperado_otros)
    # 3) guardar de nuevo lo releído: estable
    out2 = out + "2"
    xghc.guardar(p2, out2)
    est = open(out2, "rb").read() == open(out, "rb").read()
    print(f"  reguardado del editado idéntico: {est}")
    fallos += not est
print("RESULTADO:", "OK" if not fallos else f"{fallos} fallos")
sys.exit(1 if fallos else 0)
