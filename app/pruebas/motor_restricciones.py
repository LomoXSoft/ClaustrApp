"""Restricciones de profesores y grupos: lectura, motor (estrictas), comprobador y Depurador.
Usa una copia temporal de SINTETICO_grande con opciones añadidas (solo SINT-*) y prueba2 (mañanas/tardes libres)."""
import sys, os, time, tempfile, hashlib, collections, multiprocessing
import xml.etree.ElementTree as ET
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import _rutas as _R
if __name__ == "__main__":
    multiprocessing.freeze_support()
    from horarios import xghc, comprobador
    from horarios.textos import TX
    from horarios.motor import problema, cpsat, restricciones as RS, flexibilizar as F
    fallos = 0
    def check(c, m):
        global fallos
        print(("OK   " if c else "FALLO") + " " + m, flush=True); fallos += (not c)
    SRC = os.path.join(_R.R, "SINTETICO_grande.xghc"); h0 = hashlib.md5(open(SRC, "rb").read()).hexdigest()
    tmp = tempfile.mkdtemp(prefix="lp_res_")
    # 1. lectura en los archivos de prueba
    if _R.hay(os.path.join(_R.R, "prueba1.xghc")):
        pb1 = problema.construir(xghc.cargar(os.path.join(_R.R, "prueba1.xghc")))
        a = next((c for c in pb1["restr_prof"].values() if c.get("seguidas", {}).get("valor") == 5), {})
        check(a.get("max_ocup", {}).get("modo") == "estricto" and a.get("seguidas", {}).get("valor") == 5
              and [c["estricto"] for c in a.get("perm_dia", [])] == [True, False], "lectura de opciones de profesor (prueba1)")
    else:
        print("OMITIDO lectura de prueba1: datos no publicados")
    # 2. copia SINT con restricciones estrictas
    p = xghc.cargar(SRC); r = p.doc.raiz
    profs = r.findall("profesores/profesor")[:12]
    def add(op, tag, txt, **at):
        e = ET.SubElement(op, tag, {k: v for k, v in at.items()}); e.text = txt; return e
    for i, e in enumerate(profs):
        op = e.find("opciones")
        if op is None:
            op = ET.SubElement(e, "opciones")
        add(op, "maximasHorasSeguidas", "3", estricto="true")
        add(op, "intervalosDePermanenciaDiarios", "6", estricto="true")
        add(op, "considerarMaximasHorasDiariasSolamenteLectivas", "estricto")
        add(op, "valorMaximasHorasCalculadoSolamenteLectivas", "unaHoraMas")
        inc = ET.SubElement(op, "incompatibilidadEntreSesiones")
        add(inc, "salirUltimaEntrarPrimera", "true", tipo="prohibición", nIntervalos="1")
    for g in r.findall("grupos/grupo")[:6]:
        add(g, "limiteOcupacionDia", "6"); add(g, "noAdmiteHuecos", "true")
    X = os.path.join(tmp, "SINT_restricciones.xghc"); xghc.guardar(p, X)
    p = xghc.cargar(X); pb = problema.construir(p)
    check(len(pb["restr_prof"]) == 12 and len(pb["restr_grupo"]) == 6, "copia SINT: 12 profesores y 6 grupos con restricciones")
    t0 = time.time(); res = cpsat.resolver(pb, segundos=25, hilos=4); t = time.time() - t0
    est = res["estadisticas"]
    duros = [v for v in RS.evaluar(pb, res) if v[0]]
    check(not res["no_colocadas"] and not duros, f"motor: completo y sin incumplir estrictas ({len(res['no_colocadas'])} no col., {duros[:3]})")
    inf = comprobador.comprobar(p, res)
    check(inf.valido, f"comprobador válido con las restricciones ({inf.resumen()})")
    # 3. el comprobador detecta incumplimientos: resultado del problema sin restricciones
    q = dict(pb); q["restr_prof"] = {}; q["restr_grupo"] = {}
    res0 = cpsat.resolver(q, segundos=8, hilos=4)
    inf0 = comprobador.comprobar(p, res0)
    cats = set(inf0.cuentas)
    check(not inf0.valido and cats & {TX("cat_horas_seguidas"), TX("cat_permanencia_dia"), "Huecos del grupo (no admite huecos)",
                                       TX("cat_maximo_diario"), TX("cat_ultima_primera"), "Ocupación máxima del grupo"},
          f"comprobador detecta incumplimientos sin restricciones ({dict(inf0.cuentas)})")
    # 4. Depurador: claves disponibles y flexibilización
    disp = F.disponibles(pb)
    claves = {"r_max", "r_seguidas", "r_perm_dia", "r_incompat", "g_limite", "g_huecos"}
    check(claves <= disp, f"Depurador: opciones disponibles {sorted(claves & disp)}")
    fq, notas = F.aplicar(pb, {k: True for k in claves})
    duros_flex = [v for v in RS.evaluar(fq, res0) if v[0]]
    check(not duros_flex and fq["restr_grupo"] == {} or all(not c for c in fq["restr_grupo"].values()),
          f"flexibilizadas: sin estrictas ({len(duros_flex)}); notas {len(notas)}")
    # 5. mañanas/tardes libres (prueba2, marco con mediodía)
    if _R.hay(os.path.join(_R.R, "prueba2.xghc")):
        pb2 = problema.construir(xghc.cargar(os.path.join(_R.R, "prueba2.xghc")))
        lib = [pr for pr, c in pb2["restr_prof"].items() if any(x["cantidad"] for x in c.get("libres", []))]
        res2 = cpsat.resolver(pb2, segundos=10, hilos=4)
        check(lib and not [v for v in RS.evaluar(pb2, res2) if v[0]], f"mañanas/tardes libres estrictas respetadas ({len(lib)} profesor/es)")
        check("r_libres" in F.disponibles(pb2), "Depurador: «Mañanas o tardes libres» disponible en prueba2")
        print(f"INFO tiempo total {t:.1f} s; estadísticas: completos={est.get('completos')} peso={est.get('peso')}")
        _pr = next(iter(pb2["restr_prof"])); _a = RS.totales(pb2)[_pr]["ocup"]; _bk = set(RS.OCUPACION_CUENTA)
        RS.OCUPACION_CUENTA.clear(); _b = RS.totales(pb2)[_pr]["ocup"]; RS.OCUPACION_CUENTA.update(_bk)
        check(_b == RS.totales(pb2)[_pr]["lect"] and _a >= _b, "regla de ocupación centralizada (RS.OCUPACION_CUENTA)")
    else:
        print("OMITIDO mañanas/tardes libres de prueba2: datos no publicados")
    check(hashlib.md5(open(SRC, "rb").read()).hexdigest() == h0, "original intacto")
    print("FALLOS:", fallos); os._exit(1 if fallos else 0)
