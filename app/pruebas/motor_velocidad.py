"""Velocidad del motor en casos grandes (4 hilos, semilla fija) y comportamiento de las fases.
- SINTETICO_grande y SINTETICO_enorme: primer resultado completo en pocos segundos y resultado final válido.
- Parar durante la fase 1 devuelve un resultado (o ninguno) sin colgarse.
- Con «desechar guardias» se salta el escalón «todo duro» y sigue siendo válido.
- Eventos de la fase 1 con peso None; evento «peso_provisional» con el peso real (modelo completo) del resultado sin optimizar, que la ventana muestra.
"""
import sys, os, time, threading, copy
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import _rutas as _R
from horarios.textos import TX
from horarios import xghc, comprobador
from horarios.motor import problema, cpsat
fallos = 0
def check(c, m):
    global fallos
    print(("OK   " if c else "FALLO") + " " + m, flush=True); fallos += (not c)
R = _R.R
LIM = {"SINTETICO_grande": 8.0, "SINTETICO_enorme": 12.0}
for base, lim in LIM.items():
    p = xghc.cargar(f"{R}/{base}.xghc"); pb = problema.construir(p); ev = []
    r = cpsat.resolver(pb, segundos=20, hilos=4, semilla=1, informar=ev.append)
    sol = [e for e in ev if e["evento"] == "solucion"]
    t1 = next((e["t"] for e in sol if e["no_colocadas"] == 0), None)
    inf = comprobador.comprobar(p, r); est = r["estadisticas"]
    check(t1 is not None and t1 <= lim, f"{base}: primer resultado completo a los {t1 and round(t1, 2)} s (límite {lim})")
    check(inf.valido and est["no_colocadas"] == 0 and not est.get("sin_optimizar"), f"{base}: final válido, peso {est['peso']}")
    check(any(e["peso"] is None and e.get("fase") == 1 for e in sol) and any(e.get("fase") == 2 for e in sol),
          f"{base}: eventos de fase 1 (sin peso) y de fase 2")
    prov = [e for e in ev if e["evento"] == "peso_provisional"]
    t2 = next((e["t"] for e in sol if e.get("fase") == 2), 1e9)
    check(prov and isinstance(prov[0]["peso"], int) and prov[0]["tiempo"] <= t2,
          f"{base}: peso real del resultado sin optimizar ({prov and prov[0]['peso']}) a los {prov and prov[0]['tiempo']} s, antes de la 1ª solución de fase 2 ({round(t2, 2)} s)")
    fases = [e["texto"] for e in ev if e["evento"] == "fase"]
    check("Buscando un resultado completo" in fases and TX("optimizando") in fases, f"{base}: fases informadas")
# parar en fase 1
p = xghc.cargar(f"{R}/SINTETICO_enorme.xghc"); pb = problema.construir(p); alto = threading.Event()
threading.Timer(1.0, alto.set).start(); t0 = time.time()
r = cpsat.resolver(pb, segundos=60, hilos=4, informar=None, parar=alto)
check(time.time() - t0 < 10 and r["estadisticas"].get("parado"), f"parar en fase 1: devuelve en {time.time() - t0:.1f} s")
# desechar guardias
pb2 = copy.deepcopy(problema.construir(xghc.cargar(f"{R}/SINTETICO_grande.xghc"))); pb2["desechar_guardias"] = True
r = cpsat.resolver(pb2, segundos=12, hilos=4, semilla=1)
inf = comprobador.comprobar(xghc.cargar(f"{R}/SINTETICO_grande.xghc"), r)
check(inf.valido and r["estadisticas"].get("no_colocadas") == 0,
      f"desechar guardias: resultado completo y válido ({r['estadisticas'].get('estado')}, {inf.resumen()}, nc={r['estadisticas'].get('no_colocadas')})")
# ventana del motor: evento de fase 1 sin peso
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication(sys.argv)
from horarios.ventana_motor import VentanaMotor
try:
    w = VentanaMotor(xghc.cargar(f"{R}/prueba1.xghc" if _R.hay(f"{R}/prueba1.xghc") else f"{R}/SINTETICO_grande.xghc"), segundos=5, hilos=4, autoarranque=False, autoguardar=False)
    w.t_mejor = "12:00:00"
    w._mostrar_solucion({"evento": "solucion", "n": 3, "completos": 1, "no_colocadas": 0, "peso": None, "cota": None, "fase": 1})
    check(w.ed["peso"].text() == "—" and "sin optimizar" in w.ed_estado.text(), "ventana: fase 1 muestra «—» y «sin optimizar todavía»")
    w._mostrar_solucion({"evento": "solucion", "n": 4, "completos": 2, "no_colocadas": 0, "peso": 321, "cota": None, "fase": 2})
    check(w.ed["peso"].text() == "321" and "peso 321" in w.ed_estado.text(), "ventana: fase 2 muestra el mejor peso")
    class _M:                      # motor simulado: solo entrega eventos
        pausado = False; resultado = None
        def __init__(self, evs): self.evs = evs
        def eventos(self): e, self.evs = self.evs, []; return e
        def vivo(self): return True
    w.ultimo = {"evento": "solucion", "n": 3, "completos": 1, "no_colocadas": 0, "peso": None, "cota": None, "fase": 1}
    w.motor = _M([{"evento": "peso_provisional", "peso": 2958, "no_colocadas_peso": 0, "tiempo": 2.8}])
    w._sondear(); w.motor = None
    check(w.ed["peso"].text() == "2958" and "peso 2958 (sin optimizar" in w.ed_estado.text(),
          f"ventana: peso provisional del resultado sin optimizar («{w.ed_estado.text()}»)")
except Exception as ex:  # noqa: BLE001
    check(False, f"ventana: {ex!r}")
print("FALLOS:", fallos); os._exit(1 if fallos else 0)
