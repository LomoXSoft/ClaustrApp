"""Genera un .lphr de ejemplo: generar_lphr.py archivo.xghc segundos destino.lphr"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from horarios import xghc, resultado, comprobador
from horarios.motor import problema, cpsat
f, seg, dest = sys.argv[1], float(sys.argv[2]), sys.argv[3]
p = xghc.cargar(f); r = cpsat.resolver(problema.construir(p), seg)
doc = resultado.crear(r, f); resultado.guardar(doc, dest)
print(dest, r["estadisticas"].get("peso"), r["estadisticas"].get("no_colocadas"), comprobador.comprobar(p, doc).resumen())
