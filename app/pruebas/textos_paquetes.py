"""Paquetes de textos: el público (textos_propios.json) cubre todas las claves.

* Si existe el paquete privado: misma estructura (claves, longitudes de listas, ids y geometría), ningún
  texto vacío donde el privado tiene texto y los mismos {campos} de formato.
* Siempre: toda clave TX("…") usada en el código existe en el paquete público y no está vacía.
"""
import os, re, string, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from horarios import textos

fallos = []


def campos(s):
    try:
        return sorted(f for _, f, _, _ in string.Formatter().parse(s) if f)
    except ValueError:
        return None


def comparar(a, b, ruta):
    if type(a) is not type(b) and not (isinstance(a, (int, float)) and isinstance(b, (int, float))):
        fallos.append(f"{ruta}: tipo {type(a).__name__} frente a {type(b).__name__}"); return
    if isinstance(a, dict):
        for k in a:
            if k not in b:
                fallos.append(f"{ruta}/{k}: falta en el público")
            else:
                comparar(a[k], b[k], f"{ruta}/{k}")
    elif isinstance(a, list):
        if len(a) != len(b):
            fallos.append(f"{ruta}: {len(a)} elementos frente a {len(b)}"); return
        for i, (x, y) in enumerate(zip(a, b)):
            comparar(x, y, f"{ruta}[{i}]")
    elif isinstance(a, str):
        if a.strip() and not b.strip():
            fallos.append(f"{ruta}: texto vacío en el público")
        if ruta.startswith("mensajes") and campos(a) != campos(b):
            fallos.append(f"{ruta}: campos {campos(a)} frente a {campos(b)}")
    elif a != b:
        fallos.append(f"{ruta}: valor {a!r} frente a {b!r}")


pub = textos.cargar_paquete("publico")
if os.path.exists(os.path.join(textos.DIR, textos.PRIVADOS["dialogos"])):
    priv = textos.cargar_paquete("privado")
    for sec in ("dialogos", "menus_editor", "mensajes"):
        comparar(priv[sec], pub[sec], sec)
    print(f"comparado con el paquete privado: {sum(len(priv[s]) for s in priv)} entradas")
else:
    print("sin paquete privado (copia pública): solo se comprueba el público")

raiz = os.path.join(os.path.dirname(textos.DIR))
usadas = set()
for base in (raiz, os.path.join(os.path.dirname(raiz), "pruebas")):
    for d, _, fs in os.walk(base):
        for f in fs:
            if f.endswith(".py"):
                usadas |= set(re.findall(r'TX\("([A-Za-z0-9_]+)"\s*[,)]', open(os.path.join(d, f), encoding="utf-8").read()))
for k in sorted(usadas):
    if not str(pub["mensajes"].get(k, "")).strip():
        fallos.append(f"TX(\"{k}\") sin texto en el público")
print(f"claves TX usadas en el código: {len(usadas)}")
for f in fallos[:40]:
    print("FALLO", f)
print(f"RESULTADO: {len(fallos)} fallos")
sys.exit(1 if fallos else 0)
