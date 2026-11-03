"""Varias semanas y «Asignación semanal»: modelo (periodos, enPeriodos), motor y comprobador sobre una copia SINT."""
import sys, os, tempfile, hashlib, multiprocessing, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import _rutas as _R
if __name__ == "__main__":
    multiprocessing.freeze_support()
    from horarios import xghc, comprobador, semanas as SEM, edicion as ED
    from horarios.motor import problema, cpsat
    fallos = 0
    def check(c, m):
        global fallos
        print(("OK   " if c else "FALLO") + " " + m, flush=True); fallos += (not c)
    SRC = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] else os.path.join(_R.R, "SINTETICO_grande.xghc")
    NG = int(sys.argv[3]) if len(sys.argv) > 3 else 6      # nº de grupos SINT que se conservan (0 = todos)
    SEG = float(sys.argv[2]) if len(sys.argv) > 2 else 60
    h0 = hashlib.md5(open(SRC, "rb").read()).hexdigest()
    tmp = tempfile.mkdtemp(prefix="lp_sem_")
    p = xghc.cargar(SRC); raiz = p.doc.raiz
    if NG:     # caso reducido: solo las sesiones de los NG primeros grupos, sin guardias/reuniones/complementarias
        keep = {g.findtext("nombre") for g in raiz.findall("grupos/grupo")[:NG]}
        sl = raiz.find("sesionesLectivas")
        for x in list(sl):
            if (x.findtext("grupo") or "") not in keep:
                sl.remove(x)
        for tag in ("guardias", "reuniones", "complementarias"):
            e = raiz.find(tag)
            if e is not None:
                for c in list(e):
                    e.remove(c)
        Y = os.path.join(tmp, "SINT_reducido.xghc"); xghc.guardar(p, Y); p = xghc.cargar(Y); raiz = p.doc.raiz
    m0 = next(iter(p.marcos.values())); n1 = len(m0.tramos); d1 = len(m0.dias)
    SEM.fijar_num_semanas(p, 3, ED)
    check(SEM.num_semanas(raiz) == 3 and len(p.marcos[m0.id].tramos) == 3 * n1, "3 semanas: tramos replicados")
    pers = SEM.periodos(raiz, p.marcos[m0.id].dias)
    check([n for n, _ in pers] == ["s1", "s2", "s3"] and all(len(d) == d1 for _, d in pers), "periodos s1..s3 con sus días")
    arbol = ED.Arbol(raiz); noms = [n for n, _ in pers]
    ses = [s for s in p.sesiones if s.marco == m0.id]
    casos = {"obl": ses[0:6], "s3": ses[6:12], "proh": ses[12:18], "pref": ses[18:24]}
    for s in casos["obl"]:
        SEM.fijar_sesion(s.xml, ["s1", "s2"], "obligatorio", ED, arbol, noms)
    for s in casos["s3"]:
        SEM.fijar_sesion(s.xml, ["s3"], "ignorar", ED, arbol, noms)
    for s in casos["proh"]:
        SEM.fijar_sesion(s.xml, noms, "prohibido", ED, arbol, noms)
    for s in casos["pref"]:
        SEM.fijar_sesion(s.xml, noms, "preferente", ED, arbol, noms)
    X = os.path.join(tmp, "SINT_semanas.xghc"); xghc.guardar(p, X)
    p = xghc.cargar(X)
    s0 = next(s for s in p.sesiones if s.id == casos["obl"][0].id)
    check(SEM.de_sesion(s0.xml, noms) == (["s1", "s2"], "obligatorio"), "ida y vuelta de enPeriodos / mismaPosicion")
    check(SEM.texto_en_semanas(s0.xml, noms) == "s1 s2 -", "columna «En semanas»")
    pb = problema.construir(p)
    check(len(pb["espejos"]) > 0 and any(len(e["unidades"]) == 2 for e in pb["espejos"]), "motor: unidades por semana")
    t0 = time.time(); r = cpsat.resolver(pb, segundos=SEG, hilos=8)
    print(f"estado {r['estado']} en {time.time() - t0:.1f}s; no colocadas {len(r['no_colocadas'])}", flush=True)
    inf = comprobador.comprobar(p, r)
    check(inf.valido, "comprobador sin errores " + str(inf.errores[:4]))
    by = {}
    for pz in r["sesiones"]:
        for sid in pz["sesiones"]:
            by.setdefault(sid, []).append(pz)
    def sem(d):
        return next(i for i, (_, ds) in enumerate(pers) if d in ds)
    ok = all(all(sem(z["dia"]) == 2 for z in by.get(s.id, [])) for s in casos["s3"])
    check(ok, "sesiones solo en s3")
    ok = True
    for s in casos["obl"]:
        f = [sorted((z["dia"] - pers[w][1][0], tuple(z["tramos"])) for z in by.get(s.id, []) if sem(z["dia"]) == w) for w in (0, 1)]
        ok &= f[0] == f[1] and not any(sem(z["dia"]) == 2 for z in by.get(s.id, []))
    check(ok, "misma posición obligatoria en s1 y s2")
    # el comprobador detecta incumplimientos
    if casos["obl"] and by.get(casos["obl"][0].id):
        r2 = dict(r); r2["sesiones"] = [dict(z) for z in r["sesiones"]]
        z = next(z for z in r2["sesiones"] if casos["s3"][0].id in z["sesiones"]) if by.get(casos["s3"][0].id) else None
        if z:
            z["dia"] = pers[0][1][0] + (z["dia"] - pers[2][1][0])
            check(any("Asignación semanal" in e[0] for e in comprobador.comprobar(p, r2).errores) or not comprobador.comprobar(p, r2).valido,
                  "comprobador detecta pieza en semana no asignada")
    check(hashlib.md5(open(SRC, "rb").read()).hexdigest() == h0, "original intacto")
    print(f"\n{fallos} fallos")
