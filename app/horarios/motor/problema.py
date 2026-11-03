"""Traducción de un Proyecto a un problema de horario en datos puros (dict/list), serializable a JSON.

Supuestos documentados (ui_spec.md, Anexo F):
- Las sesiones de un bloque de simultáneas se colocan juntas: forman una «unidad».
- listaDeAulas: todas las aulas indicadas quedan ocupadas por la sesión.
  listaDeAlternativas: la sesión necesita UNA aula de la unión de los conjuntos/aulas indicados.
- Distribución fija «21» -> piezas de 2 y 1 periodos, en días distintos.
  Distribución variable «9*» -> en cada día un bloque continuo de 1..numMaximoDeSesiones periodos, suma = total.
- Las piezas de varios periodos ocupan tramos lectivos consecutivos del mismo día sin recreo entre medias.
"""
from __future__ import annotations
from collections import defaultdict
import math
from .. import modelo as M

PROHIBIDO = M.PROHIBIDO
NOPREF = {M.NO_PREF1: 1, M.NO_PREF2: 2}
PREFIJADO = M.PREFIJADO

PESOS_DEF = {"huecosEnGrupos": 5, "huecosEnProfesores": 2, "enGrupos": 4, "enProfesores": 3,
             "enMateriasYTareas": 1, "enSesionesLectivas": 2, "enDiasConsecutivos": 1, "enHorasExtremas": 2,
             "guardiasEnExtremos": 1}


def _min(h):
    h = (h or "0:0")[:5]
    a, b = h.split(":")
    return int(a) * 60 + int(b)


def _txt(e, ruta, defecto=""):
    if e is None:
        return defecto
    x = e.find(ruta)
    return (x.text or "").strip() if x is not None and x.text else defecto


def _nombres_integrantes(x):
    out = []
    ints = x.find("integrantes") if x is not None else None
    for i in (ints.findall("integrante") if ints is not None else []):
        n = i.find("nombre")
        out.append((((n.text if n is not None else i.text) or "").strip(), i))
    return out


def conjuntos_con_sin_declarar(p: M.Proyecto) -> dict:
    """Conjuntos de aulas. Supuesto: el atributo sinDeclarar="N" de un conjunto indica N aulas más del conjunto
    que no están declaradas en la lista de aulas; se representan como aulas virtuales «[conjunto sin declarar i]»."""
    out = {}
    ca = p.doc.raiz.find("conjuntoDeAulas") if p.doc is not None else None
    for c in (list(ca) if ca is not None else []):
        n = c.get("nombre", c.tag)
        l = [(a.text or "").strip() for a in c.findall("aula") if (a.text or "").strip()]
        try:
            extra = int(c.get("sinDeclarar", "0") or 0)
        except ValueError:
            extra = 0
        out[n] = l + [f"[{n} sin declarar {i + 1}]" for i in range(extra)]
    return out


import copy
from .. import semanas as SEM


def construir(p: M.Proyecto) -> dict:
    raiz = p.doc.raiz
    # ------------------------------------------------ marcos, tramos y átomos de tiempo
    slots = []          # {id, marco, dia, indice, ini, fin, tipo}
    sid = {}
    for m in p.marcos.values():
        for t in sorted(m.tramos, key=lambda t: (t.dia, t.indice)):
            k = (m.id, t.dia, t.indice)
            sid[k] = len(slots)
            slots.append({"id": len(slots), "marco": m.id, "dia": t.dia, "indice": t.indice,
                          "ini": _min(t.entrada), "fin": _min(t.salida), "tipo": t.tipo})
    # átomos: intervalos elementales de cada día definidos por todos los límites de todos los marcos
    atomos, slot_atomos = [], {}
    for d in sorted({s["dia"] for s in slots}):
        lim = sorted({x for s in slots if s["dia"] == d for x in (s["ini"], s["fin"])})
        base = len(atomos)
        for a, b in zip(lim, lim[1:]):
            atomos.append({"dia": d, "ini": a, "fin": b})
        for s in slots:
            if s["dia"] == d:
                slot_atomos[s["id"]] = [base + i for i, (a, b) in enumerate(zip(lim, lim[1:]))
                                        if a >= s["ini"] and b <= s["fin"]]
    # filas (secuencias de tramos lectivos consecutivos) por marco y día
    lectivos = {}
    for m in p.marcos.values():
        for d in m.dias:
            ts = sorted((t for t in m.tramos if t.dia == d), key=lambda t: t.indice)
            lectivos[(m.id, d)] = [sid[(m.id, d, t.indice)] if t.tipo == "lectivo" else None for t in ts]
    # tramos lectivos separados por el mediodía (para no contar como huecos de profesor los periodos entre la
    # mañana y la tarde, salvo que esté marcada la opción general «contarHuecosMediodia»)
    contar_mediodia = _txt(raiz, "otros/opciones/opcionesGenerales/contarHuecosMediodia") == "true"
    tramos_prof = {}
    for m in p.marcos.values():
        for d in m.dias:
            ts = sorted((t for t in m.tramos if t.dia == d), key=lambda t: t.indice)
            partes, actual = [], []
            for t in ts:
                if t.tipo == "mediodia" and not contar_mediodia:
                    partes.append(actual); actual = []
                elif t.tipo == "lectivo":
                    actual.append(sid[(m.id, d, t.indice)])
            partes.append(actual)
            tramos_prof[(m.id, d)] = [x for x in partes if x]
    recreos = {}
    for m in p.marcos.values():
        for d in m.dias:
            recreos[(m.id, d)] = [sid[(m.id, d, t.indice)] for t in sorted(m.tramos, key=lambda t: t.indice)
                                  if t.dia == d and t.tipo != "lectivo"]

    def bloques(marco, d, L):
        """Posibles inicios de una pieza de L periodos: listas de slots consecutivos lectivos."""
        fila = lectivos.get((marco, d), [])
        out = []
        for i in range(len(fila) - L + 1):
            seg = fila[i:i + L]
            if all(x is not None for x in seg):
                out.append(seg)
        return out

    # ------------------------------------------------ plantillas por entidad
    def pl_de(e):
        return {sid[k]: v for k, v in (e.plantilla or {}).items() if k in sid and v}

    prof = {e.nombre: pl_de(e) for e in p.profesores}
    grup = {e.nombre: pl_de(e) for e in p.grupos}
    mate = {e.nombre: pl_de(e) for e in p.materias}
    aula_pl = {e.nombre: pl_de(e) for e in p.aulas}
    tarea_pl = {e.nombre: pl_de(e) for e in p.tareas}
    conj = conjuntos_con_sin_declarar(p)
    aulas = [e.nombre for e in p.aulas] + sorted({a for l in conj.values() for a in l if a.startswith("[")})

    # ------------------------------------------------ unidades (sesión o bloque de simultáneas)
    por_bloque = {}
    for s in p.sesiones:
        por_bloque.setdefault(s.bloque if s.bloque is not None else f"s{s.id}", []).append(s)
    unidades = []
    espejos = []
    dia_slot = {v: k[1] for k, v in sid.items()}
    for clave, miembros in por_bloque.items():
        s0 = miembros[0]
        x0 = s0.xml
        ds = x0.find("distribucionSemanal")
        var = ds.find("distribucionVariable") if ds is not None else None
        fija = ds.find("distribucionFija") if ds is not None else None
        u = {"id": len(unidades), "sesiones": [s.id for s in miembros], "marco": s0.marco,
             "profesores": sorted({s.profesor for s in miembros if s.profesor}),
             "grupos": sorted({g for s in miembros for g in [s.grupo] + s.otros_grupos if g}),
             "aulas_fijas": sorted({a for s in miembros for a in s.aulas if a}),
             "alternativas": [], "etiqueta": " / ".join(f"{s.materia} {s.grupo}" for s in miembros)}
        for s in miembros:
            if s.alternativas and any(s.alternativas) and not s.aulas:
                cand = set()
                for c in s.alternativas:
                    cand |= set(conj.get(c, [c] if c in aulas else []))
                if cand:
                    u["alternativas"].append(sorted(cand))
        # «Se ofrece siempre un aula alternativa de tipo general»: si la sesión tiene aula
        # fija y no tiene alternativas, puede usar un aula del conjunto general con penalización enAulaNoPreferente.
        general = next((l for n, l in conj.items() if n.lower() == "general"), [])
        u["alt_general"] = sorted(set(general) - set(u["aulas_fijas"])) if u["aulas_fijas"] and not u["alternativas"] else []
        if var is not None:
            total = float(_txt(var, "numSesiones", "0") or 0)
            u["variable"] = {"total": int(round(total)), "max": int(_txt(var, "numMaximoDeSesiones", "3") or 3),
                             "penalizar_sueltas": _txt(var, "penalizarSesionesSueltas") == "penalizado"}
            u["piezas"] = []
        else:
            u["piezas"] = [int(float((n.text or "0").strip())) for n in fija.findall("numSesiones")] if fija is not None else []
            u["piezas"] = [x for x in u["piezas"] if x > 0]
        op = x0.find("opciones")
        u["pena_primera"] = _txt(op, "penaSesionesAPrimera") == "true"
        u["pena_ultima"] = _txt(op, "penaSesionesAUltima") == "true"
        u["dias_seguidos"] = _txt(op, "permitirImpartanEnDiasSeguidos", "preferiblemente")
        u["sin_cambio_aula"] = _txt(op, "sinCambioAula", "false") == "true"
        u["lunes_viernes"] = _txt(op, "considerarLunesViernesSeguidos") == "true"
        # plantilla combinada: prohibidos (duros), no preferentes con su peso, prefijados
        prohib, nopref, prefij = set(), {}, set()
        origen = defaultdict(set)     # tramo prohibido -> {(tipo, nombre)} (rechazos por plantilla)

        def mezclar(pl, criterio, tipo="", nombre=""):
            for k, v in pl.items():
                if v == PROHIBIDO:
                    prohib.add(k); origen[k].add((tipo, nombre))
                elif v in NOPREF:
                    nopref.setdefault(criterio, {})
                    nopref[criterio][k] = max(nopref[criterio].get(k, 0), NOPREF[v])
                elif v == PREFIJADO and criterio == "enSesionesLectivas":
                    prefij.add(k)
        mezclar({sid[k]: v for k, v in (s0.plantilla or {}).items() if k in sid and v}, "enSesionesLectivas", "sesion", s0.id)
        for s in miembros:
            mezclar(prof.get(s.profesor, {}), "enProfesores", "profesor", s.profesor)
            for g in [s.grupo] + s.otros_grupos:
                mezclar(grup.get(g, {}), "enGrupos", "grupo", g)
            mezclar(mate.get(s.materia, {}), "enMateriasYTareas", "materia", s.materia)
            mezclar(tarea_pl.get(s.tarea, {}), "enMateriasYTareas", "tarea", s.tarea)
            for a in s.aulas:
                for k, v in aula_pl.get(a, {}).items():
                    if v == PROHIBIDO:
                        prohib.add(k); origen[k].add(("aula", a))
        u["prohibidos"] = sorted(prohib)
        u["origen_prohibidos"] = {str(k): sorted(v) for k, v in origen.items()}
        u["nopref"] = {c: {str(k): v for k, v in d.items()} for c, d in nopref.items()}
        u["prefijados"] = sorted(prefij)
        # varias semanas: una unidad por semana asignada, limitada a los días de esa semana (ver semanas.py)
        pers = SEM.periodos(raiz, p.marcos[s0.marco].dias if s0.marco in p.marcos else [])
        if len(pers) > 1:
            refs, modo = SEM.de_sesion(x0, [n for n, _ in pers])
            grupo_esp = len(espejos)
            espejos.append({"modo": modo, "unidades": []})
            for w, (nom, dias_w) in enumerate(pers):
                if nom not in refs:
                    continue
                uw = copy.deepcopy(u); uw["id"] = len(unidades)
                dset = set(dias_w)    # plantillas por día absoluto: cada semana solo ve los prefijados de sus días
                uw["prefijados"] = [x for x in u["prefijados"] if dia_slot.get(x) in dset]
                uw["semana"] = w; uw["dias_semana"] = dias_w; uw["base_semana"] = dias_w[0] if dias_w else 0
                uw["espejo"] = grupo_esp; uw["etiqueta"] = f"{u['etiqueta']} [{nom}]"
                espejos[-1]["unidades"].append(uw["id"])
                unidades.append(uw)
        else:
            u["id"] = len(unidades)
            unidades.append(u)
    uid_de_sesion = defaultdict(list)
    for u in unidades:
        for sid_ in u["sesiones"]:
            uid_de_sesion[sid_].append(u)
    distintos = set()
    for s in p.sesiones:
        for o in s.en_distinto_dia:
            for ua in uid_de_sesion.get(s.id, []):
                for ub in uid_de_sesion.get(o, []):
                    a, b = ua["id"], ub["id"]
                    if a != b and ua.get("semana", 0) == ub.get("semana", 0):
                        distintos.add((min(a, b), max(a, b), s.en_dias_seguidos))
    def propia(x, marco):
        """(prohibidos, prefijados) de la <plantilla> propia de x, como ids de átomo."""
        pro, pre = set(), set()
        pl = x.find("plantilla") if x is not None else None
        for tr in (pl.findall("tramo") if pl is not None else []):
            k = (tr.get("marco", marco), int(tr.get("dia", 0)), int(tr.get("indice", 0)))
            v = (tr.text or "").strip()
            if k in sid:
                (pro if v == PROHIBIDO else pre if v == PREFIJADO else set()).add(sid[k])
        return pro, pre

    def proh_tarea(nombre):
        return {k for k, v in tarea_pl.get(nombre, {}).items() if v == PROHIBIDO}

    # ------------------------------------------------ guardias
    guardias = []
    gx = raiz.find("guardias")
    for g in (gx.findall("guardia") if gx is not None else []):
        marco = g.get("subMarco", next(iter(p.marcos), "A"))
        recreo = _txt(g, "enRecreos") == "true"
        cant = int(_txt(g, "profesoresACadaHora/cantidad", "1") or 1)
        pl = {}
        for tr in (g.find("plantilla").findall("tramo") if g.find("plantilla") is not None else []):
            k = (tr.get("marco", marco), int(tr.get("dia", 0)), int(tr.get("indice", 0)))
            if k in sid:
                pl[sid[k]] = (tr.text or "").strip()
        detalle = {}
        pac = g.find("profesoresACadaHora")
        for tr in (pac.findall("tramo") if pac is not None else []):
            k = (tr.get("marco", marco), int(tr.get("dia", 0)), int(tr.get("indice", 0)))
            if k in sid:
                try:
                    detalle[sid[k]] = int((tr.text or "0").strip())
                except ValueError:
                    pass
        puestos = [s["id"] for s in slots if s["marco"] == marco and ((s["tipo"] != "lectivo") == recreo)
                   and pl.get(s["id"]) != PROHIBIDO and (not recreo or s["tipo"] == "recreo")]
        ints = []
        for nombre, ix in _nombres_integrantes(g):
            try:
                n = int(_txt(ix, "numeroDeGuardias", "1") or 1)
            except ValueError:
                n = 1
            plx, prefx = propia(ix, marco)
            proh = plx | {k for k, v in prof.get(nombre, {}).items() if v == PROHIBIDO} | proh_tarea(_txt(g, "tipoDeTarea"))
            ints.append({"profesor": nombre, "n": n, "prohibidos": sorted(proh), "prefijados": sorted(prefx - proh)})
        guardias.append({"nombre": _txt(g, "nombre"), "marco": marco, "recreo": recreo, "cantidad": cant,
                         "detalle": {str(k): v for k, v in detalle.items()}, "puestos": puestos, "integrantes": ints})
    # ------------------------------------------------ reuniones
    reuniones = []
    rx = raiz.find("reuniones")
    for r in (rx.findall("reunion") if rx is not None else []):
        marco = r.get("subMarco", next(iter(p.marcos), "A"))
        ints = [n for n, _ in _nombres_integrantes(r) if n]
        proh = set()
        for tr in (r.find("plantilla").findall("tramo") if r.find("plantilla") is not None else []):
            k = (tr.get("marco", marco), int(tr.get("dia", 0)), int(tr.get("indice", 0)))
            if k in sid and (tr.text or "").strip() == PROHIBIDO:
                proh.add(sid[k])
        for n in ints:
            proh |= {k for k, v in prof.get(n, {}).items() if v == PROHIBIDO}
        proh |= proh_tarea(_txt(r, "tipoDeTarea"))
        reuniones.append({"prefijados": sorted(propia(r, marco)[1] - proh), "nombre": _txt(r, "nombre"), "marco": marco,
                          "n": int(_txt(r, "numeroDeReuniones", "1") or 1),
                          "duracion": 2 if _txt(r, "dobleDuracion") == "true" else 1,
                          "integrantes": ints, "prohibidos": sorted(proh)})
    # ------------------------------------------------ complementarias
    complementarias = []
    cx = raiz.find("complementarias")
    for c in (cx.findall("complementaria") if cx is not None else []):
        marco = c.get("subMarco", next(iter(p.marcos), "A"))
        pr = _txt(c, "profesor")
        pro_c, pre_c = propia(c, marco)
        proh = {k for k, v in prof.get(pr, {}).items() if v == PROHIBIDO} | pro_c | proh_tarea(_txt(c, "tarea"))
        complementarias.append({"prefijados": sorted(pre_c - proh), "id": _txt(c, "identificador"), "tarea": _txt(c, "tarea"), "profesor": pr,
                                "marco": marco, "n": int(_txt(c, "intervalosSemanales", "0") or 0),
                                "max_dia": int(_txt(c, "maxIntervalosDiarios", "1") or 1),
                                "continuos": _txt(c, "noConsecutivos") != "true", "prohibidos": sorted(proh)})
    # ------------------------------------------------ pesos (Criterios de optimización 0-10)
    pesos = dict(PESOS_DEF)
    cr = raiz.find("criterios")
    if cr is not None:
        for e in cr.iter():
            if len(e) == 0 and e.text and e.text.strip().lstrip("-").isdigit():
                pesos[e.tag] = int(e.text.strip())
    # marco de referencia de cada profesor (para huecos): el de la mayoría de sus sesiones
    marco_prof = {}
    for e in p.profesores:
        cuenta = {}
        for s in p.sesiones:
            if s.profesor == e.nombre:
                cuenta[s.marco] = cuenta.get(s.marco, 0) + s.duracion
        marco_prof[e.nombre] = max(cuenta, key=cuenta.get) if cuenta else next(iter(p.marcos), "A")
    eliminar_huecos_grupo = {e.nombre: _txt(e.datos.get("_xml"), "eliminarHuecos", "true") == "true" for e in p.grupos}
    desechar = _txt(raiz, "otros/opciones/opcionesGenerales/desecharGuardias") == "true"
    from . import restricciones as RS
    restr_prof, restr_grupo = RS.leer(p)
    jornada = {}
    for m in p.marcos.values():
        for d in m.dias:
            ts = sorted((t for t in m.tramos if t.dia == d), key=lambda t: t.indice)
            partes, actual = [], []
            for t in ts:
                if t.tipo == "mediodia":
                    partes.append(actual); actual = []
                elif t.tipo == "lectivo":
                    actual.append(sid[(m.id, d, t.indice)])
            partes.append(actual)
            jornada[f"{m.id}|{d}"] = [x for x in partes if x]
    # grupos alejados (Opciones generales > Alejados, ref. 938): doble desplazamiento del profesorado
    ga = raiz.find("otros/gruposAlejados")
    ed = ga.find("opciones/evitarDobleDesp") if ga is not None else None
    modo_al = 0 if ed is None or (ed.text or "").strip() != "true" else \
        (2 if ed.get("prohibir") == "true" or ed.get("tipo") == "prohibir" else 1)
    alejados = {"grupos": sorted({(g.text or "").strip() for g in ga.findall("listaDeGrupos/grupo")} - {""})
                if ga is not None else [], "modo": modo_al}
    return {
        "alejados": alejados,
        "slots": slots, "atomos": atomos, "slot_atomos": {str(k): v for k, v in slot_atomos.items()},
        "filas": {f"{m}|{d}": v for (m, d), v in lectivos.items()},
        "recreos": {f"{m}|{d}": v for (m, d), v in recreos.items()},
        "bloques": {f"{m}|{d}|{L}": bloques(m, d, L) for (m, d) in lectivos for L in range(1, 10)},
        "unidades": unidades, "espejos": espejos, "distintos": sorted(distintos), "guardias": guardias, "reuniones": reuniones,
        "complementarias": complementarias, "pesos": pesos, "aulas": aulas, "conjuntos": conj,
        "marco_prof": marco_prof, "marco_grupo": {e.nombre: e.marco for e in p.grupos},
        "eliminar_huecos_grupo": eliminar_huecos_grupo, "desechar_guardias": desechar,
        "contar_huecos_mediodia": contar_mediodia,
        "filas_prof": {f"{m}|{d}": v for (m, d), v in tramos_prof.items()},
        "dias": {m.id: m.dias for m in p.marcos.values()},
        "origen": p.ruta,
        "restr_prof": restr_prof, "restr_grupo": restr_grupo, "jornada": jornada,
    }
