"""Mensajes del motor y análisis de rechazos.

- mensajes_resultado(pb, doc, n): avisos «(Rn) …» del resultado número n.
- rechazos(pb): rechazos por plantilla (posiciones prohibidas) agrupados por alumnos/profesores y por sesión.
- rechazos_intento(pb, doc): para cada sesión no colocada, por qué se rechaza cada tramo lectivo de su marco.
Son análisis propios (el motor CP-SAT no registra intentos individuales).
"""
from __future__ import annotations
from ..textos import TX
from collections import defaultdict

DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
MAX_MENSAJES = 300


def _lectivos(pb):
    por_marco = defaultdict(list)
    for s in pb["slots"]:
        if s["tipo"] == "lectivo":
            por_marco[s["marco"]].append(s)
    return por_marco


def _hora(pb, sid):
    s = pb["slots"][sid]
    return DIAS[s["dia"]] if s["dia"] < len(DIAS) else f"día {s['dia'] + 1}", s["indice"] + 1


def _slots_pieza(pb, pz):
    if pz.get("slots"):
        return pz["slots"]
    idx = pb.setdefault("_idx_slots", {(x["marco"], x["dia"], x["indice"]): x["id"] for x in pb["slots"]})
    return [idx[k] for k in ((pz["marco"], pz["dia"], t) for t in pz.get("tramos", [])) if k in idx]


def mensajes_resultado(pb: dict, doc: dict, n: int) -> list[str]:
    R = f"(R{n}) "
    out = []
    nc = [x for x in doc.get("no_colocadas", []) if x.get("tipo") == "sesion"]
    if nc:
        out.append(R + "Resultados incompletos: pueden existir condiciones imposibles.")
        out.append(R + f"¡No ha podido colocar {len(nc)} sesiones!")
        out.append(R + TX("si_no_salen_horarios_completos"))
        out.append(R + TX("revisarlas_use_motor_depurar_condiciones"))
    for x in doc.get("no_colocadas", []):
        if x.get("tipo") == "guardia":
            out.append(R + f"(#7) Hay guardias del servicio {x['nombre']} que no se han podido colocar.")
    unid = {u["id"]: u for u in pb["unidades"]}
    # (#4) posiciones no preferentes ocupadas para los alumnos
    ocup_g = defaultdict(set)
    for pz in doc.get("sesiones", []):
        u = unid.get(pz["unidad"])
        if not u:
            continue
        npg = u.get("nopref", {}).get("enGrupos", {})
        for sid in _slots_pieza(pb, pz):
            for g in u["grupos"]:
                ocup_g[(g, pb["slots"][sid]["marco"])].add(sid)
            if str(sid) in npg:
                d, h = _hora(pb, sid)
                out.append(R + f"(#4) Posición no preferente ocupada para los alumnos de {', '.join(u['grupos'])}, el {d} a {h}ª hora")
    # (#2) huecos en el horario de los alumnos (tramos lectivos libres entre dos ocupados del mismo día)
    lect = _lectivos(pb)
    for (g, marco), occ in sorted(ocup_g.items()):
        por_dia = defaultdict(list)
        for s in lect.get(marco, []):
            por_dia[s["dia"]].append(s)
        for d, ss in sorted(por_dia.items()):
            ss.sort(key=lambda s: s["indice"])
            idx = [i for i, s in enumerate(ss) if s["id"] in occ]
            if len(idx) >= 2:
                for i in range(idx[0], idx[-1]):
                    if ss[i]["id"] not in occ:
                        dd, h = _hora(pb, ss[i]["id"])
                        out.append(R + f"(#2) Hueco en el horario de los alumnos de {g}, el {dd} a {h}ª hora")
    if len(out) > MAX_MENSAJES:
        out = out[:MAX_MENSAJES] + [R + f"... y {len(out) - MAX_MENSAJES} mensajes más."]
    return out


def rechazos(pb: dict):
    """-> (por_elemento, por_sesion). por_elemento: [(tipo, nombre, nº tramos rechazados)] de alumnos y profesores;
    por_sesion: [(etiqueta, sesiones, rechazados, lectivos del marco)] ordenado de más a menos rechazos."""
    lect = _lectivos(pb)
    elem = defaultdict(int); ses = []
    for u in pb["unidades"]:
        lm = {s["id"] for s in lect.get(u["marco"], [])}
        rech = [k for k in u.get("origen_prohibidos", {}) if int(k) in lm]
        for k in rech:
            for tipo, nombre in u["origen_prohibidos"][k]:
                if tipo in ("grupo", "profesor"):
                    elem[(tipo, nombre)] += 1
        if rech:
            ses.append((u["etiqueta"], u["sesiones"], len(rech), len(lm)))
    ses.sort(key=lambda x: (-x[2] / max(1, x[3]), x[0]))
    return sorted(((t, n, c) for (t, n), c in elem.items()), key=lambda x: (-x[2], x[0], x[1])), ses


def rechazos_intento(pb: dict, doc: dict) -> list[tuple[str, list[str]]]:
    """Para cada sesión no colocada del resultado, motivo por el que no cabe en cada tramo lectivo."""
    unid_ses = {tuple(u["sesiones"]): u for u in pb["unidades"]}
    unid = {u["id"]: u for u in pb["unidades"]}
    ocup = defaultdict(list)     # slot -> [(tipo, nombre)]
    for pz in doc.get("sesiones", []):
        u = unid.get(pz["unidad"])
        if u:
            for sid in _slots_pieza(pb, pz):
                ocup[sid] += [("grupo", g) for g in u["grupos"]] + [("profesor", p) for p in u["profesores"]]
    for gd in doc.get("guardias", []):
        pass   # las guardias no llevan slot en el resultado; se omiten del análisis
    lect = _lectivos(pb); out = []
    for x in doc.get("no_colocadas", []):
        if x.get("tipo") != "sesion":
            continue
        u = unid_ses.get(tuple(x["sesiones"]))
        if not u:
            continue
        mot = []
        for s in lect.get(u["marco"], []):
            d, h = _hora(pb, s["id"])
            if str(s["id"]) in u.get("origen_prohibidos", {}):
                quien = ", ".join(f"{t} {n}" for t, n in u["origen_prohibidos"][str(s["id"])])
                mot.append(f"{d} {h}ª: prohibido en la plantilla ({quien})")
                continue
            choca = [f"{t} {n}" for t, n in ocup.get(s["id"], [])
                     if (t == "grupo" and n in u["grupos"]) or (t == "profesor" and n in u["profesores"])]
            if choca:
                mot.append(f"{d} {h}ª: ocupado ({', '.join(sorted(set(choca)))})")
        out.append((f"{x.get('etiqueta', '')} [{', '.join(x['sesiones'])}]", mot))
    return out
