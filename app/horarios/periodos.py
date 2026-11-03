"""Edición de los periodos (tramos) de los marcos: «Revise y marque las horas que quiere cargar» (ref. 425),
«Modifica periodo» (426), «Copiar las horas marcadas» (521) y «Un horario distinto para cada día» (448).

Una fila = un tramo: {marco, dia, entrada, salida, tipo ('lectivo'|'recreo'|…), clave, activo}. Al aplicar, cada
(marco, día) se reordena por hora de entrada y se renumera el índice; las filas inactivas se eliminan.
"""
from __future__ import annotations
import copy

DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
DIAS_C = ["L", "M", "X", "J", "V", "S", "D"]


def _min(h):
    try:
        a, b = h.split(":")[:2]; return int(a) * 60 + int(b)
    except (ValueError, AttributeError):
        return 0


def filas(p):
    out = []
    for m in p.marcos.values():
        for t in sorted(m.tramos, key=lambda t: (t.dia, _min(t.entrada), t.indice)):
            out.append({"marco": m.id, "dia": t.dia, "entrada": t.entrada, "salida": t.salida, "tipo": t.tipo,
                        "clave": t.clave, "activo": True, "orig": (m.id, t.dia, t.indice)})
    return out


def validar(fs):
    """Lista de avisos: solapes dentro del mismo marco y día, salida <= entrada, periodos lectivos de <= 30 min."""
    av = []
    por = {}
    for f in fs:
        if not f["activo"]:
            continue
        if _min(f["salida"]) <= _min(f["entrada"]):
            av.append(f"{f['marco']} {DIAS[f['dia'] % 7]} {f['entrada']}: la salida no es posterior a la entrada")
        por.setdefault((f["marco"], f["dia"]), []).append(f)
    for (mc, d), l in por.items():
        l.sort(key=lambda f: _min(f["entrada"]))
        for a, b in zip(l, l[1:]):
            if _min(b["entrada"]) < _min(a["salida"]):
                av.append(f"{mc} {DIAS[d % 7]}: {a['entrada']}-{a['salida']} se solapa con {b['entrada']}-{b['salida']}")
    return av


def cortos(fs):
    return [f for f in fs if f["activo"] and f["tipo"] == "lectivo" and _min(f["salida"]) - _min(f["entrada"]) <= 30]


def distinto_cada_dia(p, marco=None):
    """True si algún marco tiene días con distinta estructura de tramos (horas/tipo)."""
    for m in p.marcos.values():
        if marco and m.id != marco:
            continue
        firmas = {tuple(sorted((t.entrada, t.salida, t.tipo) for t in m.tramos if t.dia == d)) for d in m.dias}
        if len(firmas) > 1:
            return True
    return False


def copiar(fs, origen, marco_dest, dias_dest):
    """Copia las filas `origen` al marco/días destino (sustituye las de esos días). Devuelve las filas nuevas."""
    dias_o = {f["dia"] for f in origen}
    out = [f for f in fs if not (f["marco"] == marco_dest and f["dia"] in dias_dest)]
    for d in dias_dest:
        for f in origen:
            if len(dias_o) > 1 and f["dia"] != min(dias_o):
                continue
            g = dict(f); g["marco"] = marco_dest; g["dia"] = d; g.pop("orig", None); out.append(g)
    out.sort(key=lambda f: (f["marco"], f["dia"], _min(f["entrada"])))
    return out


def aplicar(p, fs, ED, arbol):
    """Reescribe los <tramo> de cada <marcoHorario> según las filas activas. Devuelve True si hubo cambios."""
    raiz = p.doc.raiz
    md = raiz.find("marcosDeHorario")
    if md is None:
        md = ED.insertar_hijo(arbol, raiz, ED.nuevo("marcosDeHorario"))
    actuales = {mx.get("id", "A"): mx for mx in md.findall("marcoHorario")}
    antes = filas(p)
    norm = lambda l: sorted((f["marco"], f["dia"], f["entrada"], f["salida"], f["tipo"], f["clave"]) for f in l if f["activo"])
    if norm(antes) == norm(fs):
        return False
    mapa = {}
    for mid in sorted({f["marco"] for f in fs if f["activo"]} | set(actuales)):
        mx = actuales.get(mid)
        if mx is None:
            mx = ED.insertar_hijo(arbol, md, ED.nuevo("marcoHorario", attrib={"id": mid, "nombre": f"Marco {mid}", "claveX": mid}))
            arbol.padre[mx] = md
        modelo = mx.find("tramo")
        for t in list(mx.findall("tramo")):
            ED.quitar_hijo(arbol, mx, t)
        mias = sorted((f for f in fs if f["activo"] and f["marco"] == mid), key=lambda f: (f["dia"], _min(f["entrada"])))
        idx = {}
        for f in mias:
            i = idx.get(f["dia"], 0); idx[f["dia"]] = i + 1
            o = f.get("orig")
            if o and o[0] == mid and o[1] == f["dia"]:
                mapa[o] = i
            hijos = [ED.nuevo("submarco", mid), ED.nuevo("dia", str(f["dia"])), ED.nuevo("indice", str(i)),
                     ED.nuevo("horaEntrada", f["entrada"][:5] + ":00"), ED.nuevo("horaSalida", f["salida"][:5] + ":00"),
                     ED.nuevo("Tipo", f["tipo"])]
            if f.get("clave"):
                hijos.append(ED.nuevo("clavX", f["clave"]))
            ED.insertar_hijo(arbol, mx, ED.nuevo("tramo", hijos=hijos), pos=len(mx))
    remapear(raiz, mapa, {k for k in (f.get("orig") for f in antes) if k}, ED, arbol)
    return True


def remapear(raiz, mapa, viejos, ED, arbol):
    """Plantillas, prefijados (chinchetas) y no lectivas se guardan como <tramo marco= dia= indice=> fuera de
    marcosDeHorario: se trasladan al índice nuevo del mismo periodo y se quitan los de periodos eliminados.
    Sin atributo marco se usa el único marco (o «A»). Devuelve (movidos, quitados)."""
    marcos = sorted({k[0] for k in viejos}) or ["A"]
    defecto = marcos[0] if len(marcos) == 1 else "A"
    md = raiz.find("marcosDeHorario")
    excl = set(md.iter()) if md is not None else set()
    mov = quit = 0
    for padre in list(raiz.iter()):
        if padre in excl:
            continue
        for tr in list(padre):
            if tr.tag != "tramo" or tr.get("dia") is None or tr.get("indice") is None:
                continue
            try:
                k = (tr.get("marco", defecto), int(tr.get("dia")), int(tr.get("indice")))
            except ValueError:
                continue
            if k not in viejos:
                continue
            if k in mapa:
                if mapa[k] != k[2]:
                    tr.set("indice", str(mapa[k])); mov += 1
            else:
                ED.quitar_hijo(arbol, padre, tr); quit += 1
    return mov, quit
