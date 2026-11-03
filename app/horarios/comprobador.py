"""Comprobador independiente de un resultado de horario.

No usa el motor (horarios.motor) ni su traducción del problema: trabaja directamente sobre el Proyecto
leído del .xghc (marcos con horas reales, sesiones, plantillas, XML de guardias/reuniones/complementarias)
y sobre el resultado (formato .lphr / salida del motor: piezas con marco, día, tramos y aulas).

Comprueba (cada incumplimiento es un «error»; lo que no invalida el horario es un «aviso»):
  1. Cada pieza está en tramos lectivos consecutivos (sin recreo entre medias) de un marco existente.
  2. Sin solapes reales (por minutos, válido entre marcos) de profesor, grupo y aula, contando
     también guardias, reuniones y complementarias para los profesores.
  3. Distribución (Tmp): fija -> piezas con esas duraciones en días distintos; variable -> suma total,
     un bloque por día de como mucho numMaximoDeSesiones. Lo que el resultado declara no colocado se descuenta.
  4. Simultáneas: todas las sesiones de un bloque a la misma hora.
  5. Días distintos (enDistintoDia).
  6. Tramos prohibidos de sesión/bloque, profesor, grupo, materia, tarea y aula; prefijados cubiertos.
  7. Aulas: las fijas presentes (o una del conjunto general marcada como no preferente); alternativas dentro
     de sus conjuntos.
  8. Guardias: cada integrante tiene numeroDeGuardias (salvo las declaradas no colocadas), en tramos del tipo
     correcto (lectivo / recreo) no prohibidos, y en cada tramo como mucho los profesores indicados.
  9. Reuniones: numeroDeReuniones en días distintos con su duración. 10. Complementarias: total y máximo diario.
"""
from __future__ import annotations
from .textos import TX
from collections import defaultdict
from .modelo import Proyecto, PROHIBIDO, PREFIJADO


def _min(h):
    h = (h or "0:00")[:5]
    a, _, b = h.partition(":")
    return int(a or 0) * 60 + int(b or 0)


def _t(e, ruta, defecto=""):
    if e is None:
        return defecto
    x = e.find(ruta)
    return (x.text or "").strip() if x is not None and x.text else defecto


def _integrantes(x):
    out = []
    ints = x.find("integrantes") if x is not None else None
    for i in (ints.findall("integrante") if ints is not None else []):
        n = i.find("nombre")
        out.append((((n.text if n is not None else i.text) or "").strip(), i))
    return out


def _pref(e, marco):
    out = set()
    pl = e.find("plantilla") if e is not None else None
    for tr in (pl.findall("tramo") if pl is not None else []):
        if (tr.text or "").strip() == PREFIJADO:
            out.add((tr.get("marco", marco), int(tr.get("dia", 0)), int(tr.get("indice", 0))))
    return out


def _proh(e, marco):
    out = set()
    pl = e.find("plantilla") if e is not None else None
    for tr in (pl.findall("tramo") if pl is not None else []):
        if (tr.text or "").strip() == PROHIBIDO:
            out.add((tr.get("marco", marco), int(tr.get("dia", 0)), int(tr.get("indice", 0))))
    return out


class Informe:
    def __init__(self):
        self.errores, self.avisos, self.cuentas = [], [], defaultdict(int)

    def error(self, cat, txt):
        self.errores.append((cat, txt)); self.cuentas[cat] += 1

    def aviso(self, cat, txt):
        self.avisos.append((cat, txt))

    @property
    def valido(self):
        return not self.errores

    def resumen(self):
        return {"valido": self.valido, "errores": len(self.errores), "avisos": len(self.avisos),
                "por_categoria": dict(self.cuentas)}


def _comprobar_semanas(inf, s, pers, pzs, nc, xml_semanas=None):
    """Varias semanas: la distribución semanal se repite en cada semana asignada y en ninguna otra; posición
    entre semanas según mismaPosicionDistintosPeriodos (obligatorio / prohibido son condiciones estrictas)."""
    from . import semanas as SEM
    refs, modo = SEM.de_sesion(xml_semanas if xml_semanas is not None else s.xml, [n for n, _ in pers])
    ds = s.xml.find("distribucionSemanal") if s.xml is not None else None
    fija = ds.find("distribucionFija") if ds is not None else None
    var = ds.find("distribucionVariable") if ds is not None else None
    partes = sorted(x for x in (int(float((n.text or "0").strip() or 0)) for n in fija.findall("numSesiones")) if x > 0) \
        if fija is not None else []
    total = int(round(float(_t(var, "numSesiones", "0") or 0))) if var is not None else sum(partes)
    firmas, faltan = {}, 0
    for nom, dias in pers:
        en = [x for x in pzs if x[0] in dias]
        if nom not in refs:
            if en:
                inf.error("Asignación semanal incumplida", f"sesión {s.id}: piezas en la semana {nom}, no asignada")
            continue
        got = sorted(len(x[1]) for x in en)
        if fija is not None:
            rest = list(partes)
            for L in got:
                if L in rest:
                    rest.remove(L)
                else:
                    inf.error("Tmp incumplido", f"sesión {s.id} ({nom}): piezas {got} frente a {partes}"); break
            faltan += sum(rest)
        else:
            faltan += total - sum(got)
        if len({x[0] for x in en}) != len(en):
            inf.error("Tmp incumplido", f"sesión {s.id} ({nom}): dos piezas el mismo día")
        firmas[nom] = sorted((x[0] - dias[0], x[1]) for x in en)
    if faltan != nc:
        inf.error("Tmp incumplido", f"sesión {s.id}: faltan {faltan} periodos y se declaran {nc} sin colocar")
    vals = list(firmas.values())
    if modo == "obligatorio" and len({tuple(v) for v in vals}) > 1:
        inf.error("Misma posición entre semanas incumplida", f"sesión {s.id}")
    if modo == "prohibido":
        for i, a in enumerate(vals):
            for b in vals[i + 1:]:
                if set(a) & set(b):
                    inf.error("Distinta posición entre semanas incumplida", f"sesión {s.id}")
    asign = {d for nom, dias in pers if nom in refs for d in dias}
    for k2, v in s.plantilla.items():
        if v == PREFIJADO and k2[1] in asign and not any(x[0] == k2[1] and k2[2] in x[1] for x in pzs):
            inf.error("Prefijado no respetado", f"sesión {s.id}")


def comprobar(p: Proyecto, r: dict) -> Informe:
    inf = Informe()
    PARC = r.get("parcial")      # horario parcial (diálogo 690): se omiten los elementos no incluidos
    def fuera(s):
        return bool(PARC) and not ({s.grupo, *s.otros_grupos} & set(PARC.get("grupos", [])))
    tramos = {(m.id, t.dia, t.indice): t for m in p.marcos.values() for t in m.tramos}

    def intervalo(marco, dia, indice):
        t = tramos[(marco, dia, indice)]
        return (dia, _min(t.entrada), _min(t.salida))

    ses = {s.id: s for s in p.sesiones}
    raiz = p.doc.raiz
    ocup = defaultdict(list)    # (tipo, nombre) -> [(dia, ini, fin, descripción)]

    def ocupar(tipo, nombre, marco, dia, idxs, desc):
        for i in idxs:
            d, a, b = intervalo(marco, dia, i)
            ocup[(tipo, nombre)].append((d, a, b, desc))

    # ------------------------------------------------ declarado no colocado
    nc_ses = defaultdict(int)
    nc_guard = defaultdict(int)
    nc_reun = defaultdict(int)
    nc_comp = defaultdict(int)
    for n in r.get("no_colocadas", []):
        if n.get("tipo") == "sesion":
            for sid in n["sesiones"]:
                nc_ses[sid] += int(n.get("periodos", 0))
        elif n.get("tipo") == "guardia":
            nc_guard[(n["nombre"], n.get("profesor", ""))] += int(n.get("cantidad", 0))
        elif n.get("tipo") == "reunion":
            nc_reun[n["nombre"]] += int(n.get("cantidad", 0))
        elif n.get("tipo") == "complementaria":
            nc_comp[n.get("id") or (n["nombre"], n.get("profesor", ""))] += int(n.get("cantidad", 0))

    # ------------------------------------------------ plantillas de prohibidos
    def pl_proh(lista):
        return {e.nombre: {k for k, v in e.plantilla.items() if v == PROHIBIDO} for e in lista}
    pr_prof, pr_grup, pr_mat, pr_aula, pr_tar = (pl_proh(p.profesores), pl_proh(p.grupos), pl_proh(p.materias),
                                                 pl_proh(p.aulas), pl_proh(p.tareas))
    # conjuntos (sinDeclarar="N" = N aulas del conjunto no declaradas; mismas reglas que la documentación)
    conjuntos = {}
    ca = raiz.find("conjuntoDeAulas")
    for c in (list(ca) if ca is not None else []):
        n = c.get("nombre", c.tag)
        conjuntos[n] = [(a.text or "").strip() for a in c.findall("aula")] + \
            [f"[{n} sin declarar {i + 1}]" for i in range(int(c.get("sinDeclarar", "0") or 0))]
    general = set(next((l for n, l in conjuntos.items() if n.lower() == "general"), []))

    # ------------------------------------------------ sesiones lectivas
    piezas_de = defaultdict(list)   # sesión -> [(dia, (idx...), marco)]
    for k, pz in enumerate(r.get("sesiones", [])):
        marco, dia, idxs = pz["marco"], pz["dia"], list(pz["tramos"])
        desc = f"pieza {k} (sesiones {','.join(pz['sesiones'])})"
        # 1. tramos válidos y consecutivos
        if marco not in p.marcos or any((marco, dia, i) not in tramos for i in idxs):
            inf.error("Tramo inexistente", desc); continue
        if any(tramos[(marco, dia, i)].tipo != "lectivo" for i in idxs):
            inf.error("Sesión fuera de tramo lectivo", desc)
        if idxs != list(range(idxs[0], idxs[0] + len(idxs))):
            inf.error("Pieza no consecutiva", desc)
        for sid in pz["sesiones"]:
            s = ses.get(sid)
            if s is None:
                inf.error("Sesión desconocida", desc); continue
            if s.marco != marco:
                inf.error("Sesión fuera de su marco", desc)
            piezas_de[sid].append((dia, tuple(idxs), marco))
            for g in [s.grupo] + s.otros_grupos:
                if g:
                    # las sesiones de un mismo bloque de simultáneas pueden compartir grupo (desdobles/optativas)
                    ocupar("grupo", g, marco, dia, idxs, f"bloque {s.bloque}" if s.bloque is not None else f"sesión {sid}")
            if s.profesor:
                ocupar("profesor", s.profesor, marco, dia, idxs, f"sesión {sid}")
            # 6. prohibidos
            claves = {(marco, dia, i) for i in idxs}
            fuentes = [("sesión", {k2 for k2, v in s.plantilla.items() if v == PROHIBIDO}),
                       ("profesor", pr_prof.get(s.profesor, set())),
                       ("materia", pr_mat.get(s.materia, set())), ("tarea", pr_tar.get(s.tarea, set()))]
            fuentes += [("grupo", pr_grup.get(g, set())) for g in [s.grupo] + s.otros_grupos]
            if not pz.get("aula_no_preferente"):
                fuentes += [("aula", pr_aula.get(a, set())) for a in s.aulas]
            for nombre, pr in fuentes:
                if claves & pr:
                    inf.error("Tramo prohibido", f"sesión {sid} en tramo prohibido por {nombre}")
            # 7. aulas
            if s.aulas:
                faltan = [a for a in s.aulas if a not in pz["aulas"]]
                if faltan and not (pz.get("aula_no_preferente") and set(pz["aulas"]) & general):
                    inf.error("Aula fija ausente", f"sesión {sid}")
                elif faltan:
                    inf.aviso("Aula no preferente", f"sesión {sid} en {','.join(pz['aulas'])}")
            elif s.alternativas and any(s.alternativas):
                cand = set()
                for c in s.alternativas:
                    cand |= set(conjuntos.get(c, [c]))
                if not set(pz["aulas"]) & cand:
                    inf.error("Aula fuera de su conjunto", f"sesión {sid}")
        for a in set(pz["aulas"]):
            ocupar("aula", a, marco, dia, idxs, desc)

    from . import semanas as SEM
    lider = {}          # bloque de simultáneas -> primera sesión: su asignación semanal vale para todo el bloque
    for s in p.sesiones:
        if s.bloque is not None:
            lider.setdefault(s.bloque, s)
    for s in p.sesiones:
        if fuera(s):
            continue
        pers = SEM.periodos(raiz, p.marcos[s.marco].dias if s.marco in p.marcos else [])
        if len(pers) > 1:
            _comprobar_semanas(inf, s, pers, piezas_de.get(s.id, []), nc_ses.get(s.id, 0),
                               lider.get(s.bloque, s).xml if s.bloque is not None else None)
            continue
        pzs = piezas_de.get(s.id, [])
        ds = s.xml.find("distribucionSemanal") if s.xml is not None else None
        var = ds.find("distribucionVariable") if ds is not None else None
        fija = ds.find("distribucionFija") if ds is not None else None
        colocados = sum(len(x[1]) for x in pzs)
        dias = [x[0] for x in pzs]
        if var is not None:
            total = int(round(float(_t(var, "numSesiones", "0") or 0)))
            mx = int(_t(var, "numMaximoDeSesiones", "3") or 3)
            if colocados + nc_ses.get(s.id, 0) != total:
                inf.error("Tmp incumplido", f"sesión {s.id}: {colocados}+{nc_ses.get(s.id, 0)} de {total} periodos")
            if len(set(dias)) != len(dias):
                inf.error("Tmp incumplido", f"sesión {s.id}: dos bloques el mismo día")
            if any(len(x[1]) > mx for x in pzs):
                inf.error("Tmp incumplido", f"sesión {s.id}: bloque mayor que {mx}")
        elif fija is not None:
            partes = sorted(int(float((n.text or "0").strip() or 0)) for n in fija.findall("numSesiones"))
            partes = [x for x in partes if x > 0]
            got = sorted(len(x[1]) for x in pzs)
            restante = list(partes)
            ok = True
            for L in got:
                if L in restante:
                    restante.remove(L)
                else:
                    ok = False
            if not ok or sum(restante) != nc_ses.get(s.id, 0):
                inf.error("Tmp incumplido", f"sesión {s.id}: piezas {got} frente a {partes}")
            ndias = len(p.marcos[s.marco].dias) if s.marco in p.marcos else 5
            if len(partes) <= ndias and len(set(dias)) != len(dias):
                inf.error("Tmp incumplido", f"sesión {s.id}: dos piezas el mismo día")
        # prefijados
        for k2, v in s.plantilla.items():
            if v == PREFIJADO and not any(x[0] == k2[1] and k2[2] in x[1] for x in pzs):
                inf.error("Prefijado no respetado", f"sesión {s.id}")
    # 4. simultáneas
    bloques = defaultdict(list)
    for s in p.sesiones:
        if s.bloque is not None:
            bloques[s.bloque].append(s.id)
    for b, ids in bloques.items():
        firmas = {sid: sorted(piezas_de.get(sid, [])) for sid in ids}
        if len({tuple(v) for v in firmas.values()}) > 1:
            inf.error("Simultáneas no simultáneas", f"bloque {b}")
    # 5. días distintos
    for s in p.sesiones:
        for o in s.en_distinto_dia:
            if o in ses and ses[o].bloque is not None and ses[o].bloque == s.bloque:
                continue
            d1 = {x[0] for x in piezas_de.get(s.id, [])}
            d2 = {x[0] for x in piezas_de.get(o, [])}
            if d1 & d2:
                inf.error(TX("no_cumple_dias_diferentes"), f"sesiones {s.id} y {o}")

    # 5b. grupos alejados: doble desplazamiento del profesorado en el mismo día
    ga = raiz.find("otros/gruposAlejados")
    ed = ga.find("opciones/evitarDobleDesp") if ga is not None else None
    if ed is not None and (ed.text or "").strip() == "true":
        estricto = ed.get("prohibir") == "true" or ed.get("tipo") == "prohibir"
        lejos = {(g.text or "").strip() for g in ga.findall("listaDeGrupos/grupo")}
        dia_prof = defaultdict(dict)       # (prof, marco, dia) -> {indice: lejos?}
        for pz in r.get("sesiones", []):
            for sid in pz["sesiones"]:
                s = ses.get(sid)
                if s is None or not s.profesor:
                    continue
                lej = bool(lejos & set([s.grupo] + s.otros_grupos))
                for i in pz["tramos"]:
                    dia_prof[(s.profesor, pz["marco"], pz["dia"])][i] = lej
        for (pr, mc, d), occ in sorted(dia_prof.items()):
            seq = [occ[i] for i in sorted(occ)]
            cambios = sum(1 for a, b in zip(seq, seq[1:]) if a != b)
            if True in seq and cambios >= 2:
                (inf.error if estricto else inf.aviso)("Doble desplazamiento", f"profesor {pr}, día {d}")

    # ------------------------------------------------ guardias
    gx = raiz.find("guardias")
    asignadas = defaultdict(list)
    for g in r.get("guardias", []):
        asignadas[g["servicio"]].append(g)
    for gxml in (gx.findall("guardia") if gx is not None else []):
        if PARC and not PARC.get("guardias"):
            continue
        nombre = _t(gxml, "nombre"); marco = gxml.get("subMarco", next(iter(p.marcos), "A"))
        recreo = _t(gxml, "enRecreos") == "true"
        cant = int(_t(gxml, "profesoresACadaHora/cantidad", "1") or 1)
        detalle = {}
        pac = gxml.find("profesoresACadaHora")
        for tr in (pac.findall("tramo") if pac is not None else []):
            try:
                detalle[(tr.get("marco", marco), int(tr.get("dia", 0)), int(tr.get("indice", 0)))] = int((tr.text or "0").strip())
            except ValueError:
                pass
        proh_serv = _proh(gxml, marco)
        lista = asignadas.get(nombre, [])
        por_tramo = defaultdict(int); por_prof = defaultdict(int)
        ints = {n: ix for n, ix in _integrantes(gxml)}
        for g in lista:
            k = (g["marco"], g["dia"], g["tramo"])
            if k not in tramos:
                inf.error("Guardia en tramo inexistente", nombre); continue
            tipo = tramos[k].tipo
            if recreo and tipo != "recreo" or not recreo and tipo != "lectivo":
                inf.error("Guardia en tramo de tipo incorrecto", f"{nombre} {k}")
            if k in proh_serv:
                inf.error("Tramo prohibido", f"guardia {nombre} en tramo prohibido del servicio")
            if g["profesor"] not in ints:
                inf.error("Guardia de profesor no integrante", nombre)
            elif k in _proh(ints[g["profesor"]], marco) or k in pr_prof.get(g["profesor"], set()):
                inf.error("Tramo prohibido", f"guardia {nombre} en tramo prohibido del profesor")
            if k in pr_tar.get(_t(gxml, "tipoDeTarea"), set()):
                inf.error("Tramo prohibido", f"guardia {nombre} en tramo prohibido de su tipo de tarea")
            por_tramo[k] += 1; por_prof[g["profesor"]] += 1
            ocupar("profesor", g["profesor"], g["marco"], g["dia"], [g["tramo"]], f"guardia {nombre}")
        for k, c in por_tramo.items():
            if c > detalle.get(k, cant):
                inf.error("Guardias: exceso de profesores", f"{nombre} {k}: {c} > {detalle.get(k, cant)}")
        for prof, ix in ints.items():
            hechas = {(g["marco"], g["dia"], g["tramo"]) for g in lista if g["profesor"] == prof}
            for k in _pref(ix, marco) - _proh(ix, marco):
                if k in tramos and k not in hechas and not nc_guard.get((nombre, prof)):
                    inf.error("Prefijado incumplido", f"guardia {nombre} {k}")
            n = int(_t(ix, "numeroDeGuardias", "1") or 1)
            if por_prof.get(prof, 0) + nc_guard.get((nombre, prof), 0) != n:
                inf.error("Guardias no cubiertas", f"{nombre}: {por_prof.get(prof, 0)} de {n}")
            elif nc_guard.get((nombre, prof)):
                inf.aviso("Guardias no colocadas (declaradas)", nombre)
    # ------------------------------------------------ reuniones
    rx = raiz.find("reuniones")
    por_reunion = defaultdict(list)
    for x in r.get("reuniones", []):
        por_reunion[x["reunion"]].append(x)
    for rxml in (rx.findall("reunion") if rx is not None else []):
        nombre = _t(rxml, "nombre"); marco = rxml.get("subMarco", next(iter(p.marcos), "A"))
        if PARC and nombre not in PARC.get("reuniones", []):
            continue
        n = int(_t(rxml, "numeroDeReuniones", "1") or 1)
        dur = 2 if _t(rxml, "dobleDuracion") == "true" else 1
        lista = por_reunion.get(nombre, [])
        if len(lista) + nc_reun.get(nombre, 0) != n:
            inf.error("Reuniones no colocadas", f"{nombre}: {len(lista)} de {n}")
        if len({x["dia"] for x in lista}) != len(lista):
            inf.error("Reuniones el mismo día", nombre)
        pr = _proh(rxml, marco) | pr_tar.get(_t(rxml, "tipoDeTarea"), set())
        cubiertos = {(x["marco"], x["dia"], i) for x in lista for i in x["tramos"]}
        for k in _pref(rxml, marco) - pr:
            if k in tramos and k not in cubiertos and not nc_reun.get(nombre):
                inf.error("Prefijado incumplido", f"reunión {nombre} {k}")
        for x in lista:
            idxs = list(x["tramos"])
            if len(idxs) != dur or any((x["marco"], x["dia"], i) not in tramos or tramos[(x["marco"], x["dia"], i)].tipo != "lectivo" for i in idxs):
                inf.error("Reunión mal situada", nombre); continue
            if {(x["marco"], x["dia"], i) for i in idxs} & pr:
                inf.error("Tramo prohibido", f"reunión {nombre}")
            for prof, _ in _integrantes(rxml):
                if prof:
                    ocupar("profesor", prof, x["marco"], x["dia"], idxs, f"reunión {nombre}")
                    if {(x["marco"], x["dia"], i) for i in idxs} & pr_prof.get(prof, set()):
                        inf.error("Tramo prohibido", f"reunión {nombre}: tramo prohibido de un integrante")
    # ------------------------------------------------ complementarias
    cx = raiz.find("complementarias")
    por_comp = defaultdict(list)
    for x in r.get("complementarias", []):
        por_comp[x.get("id") or (x["tarea"], x["profesor"])].append(x)
    for cxml in (cx.findall("complementaria") if cx is not None else []):
        if PARC and not PARC.get("complementarias"):
            continue
        tarea, prof = _t(cxml, "tarea"), _t(cxml, "profesor")
        n = int(_t(cxml, "intervalosSemanales", "0") or 0)
        mx = int(_t(cxml, "maxIntervalosDiarios", "1") or 1)
        clave = _t(cxml, "identificador") or (tarea, prof)    # identificador único de la actividad
        lista = por_comp.pop(clave, [])
        if any(x["profesor"] != prof or x["tarea"] != tarea for x in lista):
            inf.error(TX("complementaria_otro_profesor_u_otra"), tarea)
        if len(lista) + nc_comp.get(clave, 0) != n:
            inf.error(TX("complementarias_sin_colocar"), f"{tarea}: {len(lista)} de {n}")
        pd = defaultdict(list)
        marco_c = cxml.get("subMarco", next(iter(p.marcos), "A"))
        pr_c = _proh(cxml, marco_c) | pr_tar.get(tarea, set()) | pr_prof.get(prof, set())
        hechas = set()
        for x in lista:
            k = (x["marco"], x["dia"], x["tramo"]); hechas.add(k)
            if k not in tramos or tramos[k].tipo != "lectivo":
                inf.error(TX("complementaria_mal_sitio"), tarea); continue
            if k in pr_c:
                inf.error("Tramo prohibido", f"complementaria {tarea}")
            pd[x["dia"]].append(x["tramo"])
            ocupar("profesor", prof, x["marco"], x["dia"], [x["tramo"]], f"complementaria {tarea}")
        if any(len(v) > mx for v in pd.values()):
            inf.error(TX("complementarias_tope_diario"), tarea)
        if _t(cxml, "noConsecutivos") != "true":       # deben ser contiguas dentro del día
            for d, idxs in pd.items():
                lect = sorted(t.indice for t in p.marcos[marco_c].tramos if t.dia == d and t.tipo == "lectivo") \
                    if marco_c in p.marcos else []
                pos = sorted(lect.index(i) for i in idxs if i in lect)
                if pos and pos[-1] - pos[0] + 1 != len(pos):
                    inf.error(TX("complementarias_no_seguidas"), tarea)
        for k in _pref(cxml, marco_c) - pr_c:
            if k in tramos and k not in hechas and not nc_comp.get(clave):
                inf.error("Prefijado incumplido", f"complementaria {tarea} {k}")
    # ------------------------------------------------ 2. solapes reales
    for (tipo, nombre), lista in ocup.items():
        lista.sort()
        for i in range(1, len(lista)):
            a, b = lista[i - 1], lista[i]
            # comparar con todos los anteriores aún abiertos
            j = i - 1
            while j >= 0 and lista[j][0] == b[0]:
                if lista[j][2] > b[1] and lista[j][3] != b[3]:
                    inf.error(f"Solape de {tipo}", f"{lista[j][3]} / {b[3]}")
                j -= 1
    # ------------------------------------------------ restricciones de profesores y grupos (motor/restricciones.py)
    try:
        from .motor import problema as _PB, restricciones as _RS
        pbx = _PB.construir(p)
        for estricto, cat, txt in _RS.evaluar(pbx, r):
            (inf.error if estricto else inf.aviso)(cat, txt)
    except Exception as ex:  # noqa: BLE001
        inf.aviso("Restricciones", f"No se pudieron comprobar: {ex}")
    return inf


def comprobar_archivo(ruta_xghc: str, resultado: dict) -> Informe:
    from . import xghc
    return comprobar(xghc.cargar(ruta_xghc), resultado)
