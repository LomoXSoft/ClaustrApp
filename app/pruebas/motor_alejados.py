"""Grupos alejados: doble desplazamiento prohibido / procurar evitar (motor y comprobador) sobre copia SINT reducida."""
import sys, os, tempfile, hashlib, multiprocessing
import xml.etree.ElementTree as ET
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import _rutas as _R
if __name__ == "__main__":
    multiprocessing.freeze_support()
    from horarios import xghc, comprobador
    from horarios.motor import problema, cpsat
    fallos = 0
    def check(c, m):
        global fallos
        print(("OK   " if c else "FALLO") + " " + m, flush=True); fallos += (not c)
    SRC = os.path.join(_R.R, "SINTETICO_grande.xghc"); h0 = hashlib.md5(open(SRC, "rb").read()).hexdigest()
    tmp = tempfile.mkdtemp(prefix="lp_alej_")
    p = xghc.cargar(SRC); raiz = p.doc.raiz
    gr = [g.findtext("nombre") for g in raiz.findall("grupos/grupo")[:10]]
    sl = raiz.find("sesionesLectivas")
    for x in list(sl):
        if (x.findtext("grupo") or "") not in gr:
            sl.remove(x)
    for tag in ("guardias", "reuniones", "complementarias"):
        e = raiz.find(tag)
        if e is not None:
            for c in list(e):
                e.remove(c)
    otros = raiz.find("otros")
    ga = ET.SubElement(otros, "gruposAlejados"); op = ET.SubElement(ga, "opciones")
    ed = ET.SubElement(op, "evitarDobleDesp"); ed.text = "true"; ed.set("prohibir", "true")
    lg = ET.SubElement(ga, "listaDeGrupos")
    for g in gr[:3]:
        ET.SubElement(lg, "grupo").text = g
    X = os.path.join(tmp, "SINT_alejados.xghc"); xghc.guardar(p, X); p = xghc.cargar(X)
    pb = problema.construir(p)
    check(pb["alejados"] == {"grupos": sorted(gr[:3]), "modo": 2}, "lectura de grupos alejados y modo prohibir")
    r = cpsat.resolver(pb, segundos=40, hilos=8)
    print("estado", r["estado"], "no colocadas", len(r["no_colocadas"]), flush=True)
    inf = comprobador.comprobar(p, r)
    check(inf.valido and not any(c == "Doble desplazamiento" for c, _ in inf.avisos), "sin dobles desplazamientos " + str(inf.errores[:3]))
    # el comprobador detecta un patrón lejos-cerca-lejos fabricado
    mixtos = [s.profesor for s in p.sesiones if s.grupo in gr[:3] and s.profesor and
              any(o.profesor == s.profesor and o.grupo not in gr[:3] for o in p.sesiones)]
    check(bool(mixtos), "hay profesores con grupos alejados y cercanos")
    pr = mixtos[0] if mixtos else None
    lej = next(s for s in p.sesiones if s.profesor == pr and s.grupo in gr[:3])
    cer = next((s for s in p.sesiones if s.profesor == pr and s.grupo not in gr[:3]), None)
    if cer:
        mc = lej.marco; d = p.marcos[mc].dias[0]
        r2 = {"sesiones": [{"sesiones": [lej.id], "marco": mc, "dia": d, "tramos": [0], "aulas": []},
                           {"sesiones": [cer.id], "marco": mc, "dia": d, "tramos": [1], "aulas": []},
                           {"sesiones": [lej.id], "marco": mc, "dia": d, "tramos": [2], "aulas": []}]}
        check(any(c == "Doble desplazamiento" for c, _ in comprobador.comprobar(p, r2).errores), "comprobador detecta doble desplazamiento")
    check(hashlib.md5(open(SRC, "rb").read()).hexdigest() == h0, "original intacto")
    print(f"\n{fallos} fallos")
