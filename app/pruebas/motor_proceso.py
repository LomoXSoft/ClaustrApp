"""Prueba del motor en proceso aparte: eventos, pausa (el tiempo en pausa no cuenta), parar, .lphr y comprobador."""
import sys, os, time, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import _rutas as _R
from horarios import xghc, comprobador, resultado
from horarios.motor import problema
from horarios.motor.proceso import MotorEnProceso

if __name__ == "__main__":
    f = os.path.join(_R.R, "prueba2.xghc"); _R.exigir(f)
    p = xghc.cargar(f); pb = problema.construir(p)
    m = MotorEnProceso(pb, segundos=8, hilos=4); t0 = time.time(); m.iniciar()
    evs = []; pausado_ok = False
    while m.vivo() or not m.resultado:
        evs += m.eventos()
        if not pausado_ok and any(e["evento"] == "solucion" for e in evs):
            m.pausar(); n0 = len(evs + m.eventos()); time.sleep(3); n1 = len(m.eventos())
            m.reanudar(); pausado_ok = True
            print("pausa 3 s: eventos durante la pausa =", n1)
        if m.resultado:
            break
        time.sleep(0.1)
    evs += m.eventos()
    pared = time.time() - t0
    r = m.resultado; e = r["estadisticas"]
    print(f"fin: pared={pared:.1f}s activo={e['tiempo']}s (pausa excluida) peso={e['peso']} nc={e['no_colocadas']} eventos={len(evs)}")
    assert pared >= e["tiempo"] + 2.5, "el tiempo de pausa no debería contar"
    doc = resultado.crear(r, f, {"nombre": "cpsat", "segundos": 8})
    ruta = os.path.join(tempfile.mkdtemp(), "r.lphr"); resultado.guardar(doc, ruta)
    d2 = resultado.cargar(ruta)
    assert resultado.corresponde(d2, f) and len(d2["sesiones"]) == len(r["sesiones"])
    inf = comprobador.comprobar(p, d2)
    print(".lphr ida y vuelta OK; comprobador sobre el .lphr:", inf.resumen())
    try:
        resultado.exportar(d2, ruta[:-5] + ".xrho"); raise SystemExit("xrho no debería exportar")
    except NotImplementedError:
        print(".xrho: NotImplementedError (correcto)")
    # parar
    m = MotorEnProceso(pb, segundos=120, hilos=4); m.iniciar(); t0 = time.time()
    while not any(e["evento"] == "solucion" for e in m.eventos()):
        time.sleep(0.1)
    m.parar()
    while not m.resultado:
        m.eventos(); time.sleep(0.1)
    print(f"parar: detenido a los {time.time()-t0:.1f}s, parado={m.resultado['estadisticas'].get('parado')}, "
          f"piezas={len(m.resultado['sesiones'])}")
    assert time.time() - t0 < 20
    # comprobador detecta errores (resultado manipulado)
    mal = dict(d2); mal["sesiones"] = [dict(x) for x in d2["sesiones"]]
    a, b = mal["sesiones"][0], mal["sesiones"][1]
    b.update(marco=a["marco"], dia=a["dia"], tramos=a["tramos"])
    mal["guardias"] = d2["guardias"][1:]
    inf = comprobador.comprobar(p, mal)
    print("comprobador con resultado manipulado:", inf.resumen()["por_categoria"])
    assert not inf.valido
    print("OK")
