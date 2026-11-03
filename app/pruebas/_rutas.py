"""Rutas de datos de las pruebas, sin rutas absolutas en el código.

* R: carpeta de archivos de prueba. Por orden: variable HORARIOS_DATOS, la carpeta de trabajo privada
  (../../pruebas respecto a app/, si existe) o app/pruebas/datos (copia pública: solo datos SINT-*).
* exigir(...): si falta algún archivo (p. ej. datos reales que no se publican), la prueba termina como
  OMITIDA con salida 0.
"""
import os
import sys

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAIZ = os.path.dirname(APP)
DATOS = os.path.join(APP, "pruebas", "datos")
_priv = os.path.join(RAIZ, "pruebas")
R = os.environ.get("HORARIOS_DATOS") or (_priv if os.path.isdir(_priv) else DATOS)
CAP = os.path.join(APP, "capturas")
CAPG = os.path.join(RAIZ, "capturas") if os.path.isdir(os.path.join(RAIZ, "capturas")) else CAP
X = os.path.join(RAIZ, "x")                                   # ejemplos externos (no se publican)
MUESTRAS = os.path.join(RAIZ, "delphos_muestras")             # muestras anonimizadas (no se publican)
_xsd = [os.path.join(RAIZ, "xmlghc", "repo", "GHCFile.xsd"), os.path.join(DATOS, "GHCFile.xsd")]
XSD = next((x for x in _xsd if os.path.exists(x)), _xsd[-1])
os.makedirs(CAP, exist_ok=True)


def hay(*rutas):
    return all(os.path.exists(r) for r in rutas)


def exigir(*rutas):
    falta = [os.path.basename(r) for r in rutas if not os.path.exists(r)]
    if falta:
        print(f"OMITIDA: faltan datos no publicados ({', '.join(falta)})")
        print("RESULTADO: OMITIDA")
        sys.exit(0)


def disponibles(*rutas):
    """Las rutas que existen; avisa de las omitidas. Si no queda ninguna, la prueba termina como OMITIDA."""
    hay_ = [r for r in rutas if os.path.exists(r)]
    for r in rutas:
        if r not in hay_:
            print(f"OMITIDO {os.path.basename(r)}: datos no publicados")
    if not hay_:
        exigir(*rutas)
    return hay_
