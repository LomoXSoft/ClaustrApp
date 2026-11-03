"""Resuelve los ejemplos y valida con el comprobador independiente. Uso: motor_ejemplos.py [segundos] [archivos...]"""
import sys, time, json, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import _rutas as _R
from horarios import xghc, comprobador
from horarios.motor import problema, cpsat
seg = float(sys.argv[1]) if len(sys.argv) > 1 else 30
archivos = sys.argv[2:] or _R.disponibles(os.path.join(_R.R, "prueba1.xghc"), os.path.join(_R.R, "prueba2.xghc"))
fallos = 0
for f in archivos:
    p = xghc.cargar(f)
    r = cpsat.resolver(problema.construir(p), segundos=seg)
    inf = comprobador.comprobar(p, r)
    e = r["estadisticas"]
    print(f"{os.path.basename(f)}: estado={e.get('estado')} tiempo={e.get('tiempo')}s peso={e.get('peso')} "
          f"no_colocadas={e.get('no_colocadas')} guardias_nc={e.get('guardias_no_colocadas')} "
          f"completos={e.get('completos')} cota={e.get('cota')} -> comprobador {inf.resumen()}")
    for c, t in inf.errores[:15]:
        print("   ERROR", c, "-", t)
    fallos += not inf.valido
sys.exit(1 if fallos else 0)
