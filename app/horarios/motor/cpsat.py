"""Modelo CP-SAT del horario.

Duras: piezas en tramos lectivos consecutivos de su marco; sin solapes (por átomos de tiempo reales, válido entre
marcos) de profesor, grupo y aula; simultáneas (unidad común); piezas de una unidad en días distintos; días distintos
entre sesiones; prohibidas; prefijadas; disponibilidad de aulas fijas y capacidad de cada conjunto de aulas;
reuniones (integrantes a la vez), guardias (≤ profesores a cada hora), complementarias (máx. diario, continuidad).
Blandas (pesos 0-10 de Criterios): huecos de profesores y grupos, posiciones no preferentes 1/2, primeras/últimas
horas, días consecutivos, guardias en extremos. Las no colocadas se permiten con un peso muy alto (PESO_NO_COLOCADA).
"""
from __future__ import annotations
from ..textos import TX
import os
import math, time, threading
from collections import defaultdict
from ortools.sat.python import cp_model

PESO_NO_COLOCADA = 1000
PESO_GUARDIA_DESECHABLE = 20   # guardia no colocada con «Desechar las guardias que no se puedan colocar»
LIMITE_ELECCION_EXACTA = 8


class Modelo:
    def __init__(self, pb: dict, ligero=False):
        # ligero=True: modelo de FACTIBILIDAD (fase 1). Mismas restricciones duras y mismas variables de decisión
        # (en el mismo orden), pero sin la maquinaria de las penalizaciones caras (huecos, días consecutivos,
        # horas extremas). Su solución sirve de punto de partida (hint) al modelo completo de la fase 2.
        self.pb = pb; self.ligero = ligero
        self.m = cp_model.CpModel()
        self.slots = pb["slots"]
        self.sa = {int(k): v for k, v in pb["slot_atomos"].items()}
        self.ocupa = {"P": defaultdict(list), "G": defaultdict(list), "A": defaultdict(list)}  # (rec, atomo) -> vars
        self.no_lect = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        self.uso_slot = defaultdict(lambda: defaultdict(list))   # profesor/grupo -> slot -> vars (para huecos)
        self.pen = []        # (peso, expr, nombre_categoria)
        self.no_col = []     # (peso, expr, descripción)
        self.piezas = []     # (unidad, var, segmento de slots)
        self.vg, self.vr, self.vc = [], [], []
        self.stats = defaultdict(list)
        self.alt_general = {}
        self.eleccion = {}   # (id(var pieza), índice de conjunto) -> {aula: var}

    # ------------------------------------------------------------ utilidades
    def _ocupar(self, tipo, nombre, segmento, var, clase=None):
        if clase:   # no lectivas por clase (para la regla de «ocupación», RS.OCUPACION_CUENTA)
            self.no_lect[nombre][clase][self.slots[segmento[0]]["dia"]].append(len(segmento) * var)
        for s in segmento:
            for a in self.sa[s]:
                self.ocupa[tipo][(nombre, a)].append(var)
            if tipo in ("P", "G"):
                self.uso_slot[(tipo, nombre)][s].append(var)

    def _bloques(self, marco, d, L):
        return self.pb["bloques"].get(f"{marco}|{d}|{L}", [])

    # ------------------------------------------------------------ sesiones lectivas
    def unidades(self):
        m, pb = self.m, self.pb
        self.dia_uso = {}
        for u in pb["unidades"]:
            marco = u["marco"]; dias = pb["dias"].get(marco, [])
            if u.get("dias_semana") is not None:      # varias semanas: solo los días de su semana
                dias = [d for d in dias if d in u["dias_semana"]]
            proh = set(u["prohibidos"])
            nopref = {c: {int(k): v for k, v in d.items()} for c, d in u["nopref"].items()}
            if u.get("variable"):
                vv = u["variable"]; total, mx = vv["total"], min(vv["max"], 9)
                horas = []
                for d in dias:
                    vd = []
                    for L in range(1, mx + 1):
                        for seg in self._bloques(marco, d, L):
                            if proh.intersection(seg):
                                continue
                            for x in self._nueva(u, seg, nopref, None, f"u{u['id']}d{d}L{L}s{seg[0]}"):
                                vd.append(x); horas.append(L * x)
                                if L == 1 and vv["penalizar_sueltas"]:
                                    self.pen.append((1, x, "sueltas_variable"))
                    m.Add(sum(vd) <= 1)
                    self.dia_uso[(u["id"], d)] = sum(vd)
                falta = m.NewIntVar(0, total, f"falta{u['id']}")
                m.Add(sum(horas) + falta == total)
                self.no_col.append((PESO_NO_COLOCADA, falta, u, None))
            else:
                n = len(u["piezas"])
                por_dia = max(1, math.ceil(n / max(1, len(dias))))
                dv = defaultdict(list)
                # piezas de igual duración son intercambiables: una variable por posición y duración (no por pieza),
                # lo que elimina la simetría entre piezas iguales y divide el nº de variables por su multiplicidad
                cuantas = defaultdict(int)
                for L in u["piezas"]:
                    cuantas[L] += 1
                for L, c in sorted(cuantas.items(), reverse=True):
                    vs = []
                    for d in dias:
                        for seg in self._bloques(marco, d, L):
                            if proh.intersection(seg):
                                continue
                            for x in self._nueva(u, seg, nopref, ("L", L), f"u{u['id']}L{L}s{seg[0]}"):
                                vs.append(x); dv[d].append(x)
                    falta = m.NewIntVar(0, c, f"falta{u['id']}_{L}")
                    m.Add(sum(vs) + falta == c)
                    self.no_col.append((PESO_NO_COLOCADA * L, falta, u, ("L", L)))
                for d in dias:
                    m.Add(sum(dv[d]) <= por_dia)
                    self.dia_uso[(u["id"], d)] = sum(dv[d])
            # prefijadas: cada tramo prefijado debe quedar cubierto por la unidad
            for s in u["prefijados"]:
                cub = [x for (uu, x, seg, _k) in self.piezas if uu is u and s in seg]
                if cub:
                    m.Add(sum(cub) == 1)
            # primeras / últimas horas: como mucho la mitad de las piezas
            npz = len(u["piezas"]) or (u.get("variable", {}).get("total", 0) // 2)
            lim = npz // 2
            for flag, cual in (("pena_primera", 0), ("pena_ultima", -1)):
                if not u[flag] or npz < 2 or self.ligero:
                    continue
                xs = []
                for (uu, x, seg, _k) in self.piezas:
                    if uu is u:
                        s0 = self.slots[seg[cual]]
                        fila = [z for z in self.pb["filas"][f"{s0['marco']}|{s0['dia']}"] if z is not None]
                        if fila and seg[cual] == fila[cual]:
                            xs.append(x)
                if xs:
                    exc = m.NewIntVar(0, len(xs), f"ext{u['id']}{cual}")
                    m.Add(exc >= sum(xs) - lim)
                    self.pen.append((self.pb["pesos"].get("enHorasExtremas", 2), exc, "horas_extremas"))
            # días seguidos (permitirImpartanEnDiasSeguidos): indiferente | preferiblemente (no) | prohibido |
            # penalizaNoSeguidas | obligatoriamente
            modo = u["dias_seguidos"]
            if modo not in ("indiferente", "indistintamente") and (len(u["piezas"]) >= 2 or u.get("variable")):
                pares = list(zip(dias, dias[1:]))
                if u["lunes_viernes"] and len(dias) >= 5:
                    pares.append((dias[-1], dias[0]))
                usa = lambda d: self.dia_uso[(u["id"], d)]
                vecinos = {d: [b for a, b in pares if a == d] + [a for a, b in pares if b == d] for d in dias}
                w = self.pb["pesos"].get("enDiasConsecutivos", 1)
                if modo == "prohibido":
                    for a, b in pares:
                        m.Add(usa(a) + usa(b) <= 1)
                elif modo == "obligatoriamente" or (modo == "penalizaNoSeguidas" and not self.ligero):
                    for d in dias:
                        if modo == "obligatoriamente":
                            m.Add(usa(d) <= sum(usa(v) for v in vecinos[d])) if vecinos[d] else m.Add(usa(d) == 0)
                        else:
                            y = m.NewBoolVar(f"noseg{u['id']}_{d}")
                            m.Add(y >= usa(d) - sum(usa(v) for v in vecinos[d]))
                            self.pen.append((w, y, "dias_no_seguidos"))
                elif not self.ligero and modo != "penalizaNoSeguidas":
                    for a, b in pares:
                        y = m.NewBoolVar(f"cons{u['id']}_{a}{b}")
                        m.Add(y >= usa(a) + usa(b) - 1)
                        self.pen.append((w, y, "dias_consecutivos"))
        # días distintos entre sesiones
        dias_u = {u["id"]: [d for d in self.pb["dias"].get(u["marco"], []) if (u["id"], d) in self.dia_uso]
                  for u in self.pb["unidades"]}
        for a, b, seg in self.pb["distintos"]:
            comunes = [d for d in dias_u[a] if d in dias_u[b]]
            for d in comunes:
                m.Add(self.dia_uso[(a, d)] + self.dia_uso[(b, d)] <= 1)
            # enDiasSeguidos: preferentemente / obligado -> en días distintos pero contiguos
            if seg in ("preferentemente", "obligado"):
                for x, y in ((a, b), (b, a)):
                    for i, d in enumerate(comunes):
                        vec = [self.dia_uso[(y, comunes[j])] for j in (i - 1, i + 1) if 0 <= j < len(comunes)]
                        if seg == "obligado":
                            m.Add(self.dia_uso[(x, d)] <= sum(vec))
                        elif not self.ligero:
                            z = m.NewBoolVar(f"dseg{x}_{y}_{d}")
                            m.Add(z >= self.dia_uso[(x, d)] - sum(vec))
                            self.pen.append((self.pb["pesos"].get("enDiasConsecutivos", 1), z, "dias_no_seguidos"))

        self.espejos()

    def espejos(self):
        """Varias semanas («Asignación semanal», ref. 625): misma posición (Irrelevante/Preferente/Obligado) o
        distinta posición (Preferente/Obligado) de las piezas de una sesión en el horario de cada semana. La
        posición es (día dentro de la semana, primer tramo, duración)."""
        m = self.m
        por_u = defaultdict(lambda: defaultdict(list))
        for (u, x, seg, _k) in self.piezas:
            if u.get("espejo") is None:
                continue
            s0 = self.slots[seg[0]]
            por_u[u["id"]][(s0["dia"] - u["base_semana"], s0["indice"], len(seg))].append(x)
        w = self.pb["pesos"].get("mismaPosicionSemanas", 2) or 2
        for k, e in enumerate(self.pb.get("espejos", [])):
            modo, us = e["modo"], e["unidades"]
            if modo == "ignorar" or len(us) < 2:
                continue
            for a, b in zip(us, us[1:]) if modo in ("obligatorio", "preferente") else \
                    [(a, b) for i, a in enumerate(us) for b in us[i + 1:]]:
                for pos in set(por_u[a]) | set(por_u[b]):
                    xa, xb = sum(por_u[a].get(pos, [])), sum(por_u[b].get(pos, []))
                    if modo == "obligatorio":
                        m.Add(xa == xb)
                    elif modo == "prohibido":
                        m.Add(xa + xb <= 1)
                    elif not self.ligero and modo == "preferente":
                        y = m.NewBoolVar(f"esp{k}_{a}_{b}_{pos}")
                        m.Add(y >= xa - xb); m.Add(y >= xb - xa)
                        self.pen.append((w, y, "semanas_distinta"))
                    elif not self.ligero:     # procuraEvitar
                        y = m.NewBoolVar(f"esp{k}_{a}_{b}_{pos}")
                        m.Add(y >= xa + xb - 1)
                        self.pen.append((w, y, "semanas_misma"))

    def alejados(self):
        """Doble desplazamiento: en un mismo día, un profesor no va a un grupo alejado, vuelve y vuelve a ir (ni al
        revés). Patrón prohibido en tres tramos i<j<k de un día: lejos-cerca-lejos o cerca-lejos-cerca.
        modo 1 = procurar evitar (penalización), 2 = prohibir estrictamente."""
        al = self.pb.get("alejados") or {}
        lejos_g = set(al.get("grupos", [])); modo = al.get("modo", 0)
        if not lejos_g or not modo or (self.ligero and modo == 1):
            return
        m = self.m
        occ = defaultdict(lambda: defaultdict(lambda: ([], [])))    # prof -> slot -> (lejos, cerca)
        con_lejos = set()
        for (u, x, seg, _k) in self.piezas:
            lej = bool(lejos_g.intersection(u["grupos"]))
            for pr in u["profesores"]:
                if lej:
                    con_lejos.add(pr)
                for sg in seg:
                    occ[pr][sg][0 if lej else 1].append(x)
        w = self.pb["pesos"].get("dobleDesplazamiento", 3) or 3
        for pr in sorted(con_lejos):
            por_dia = defaultdict(list)
            for sg in occ[pr]:
                sl = self.slots[sg]; por_dia[(sl["marco"], sl["dia"])].append(sg)
            for (mc, d), sgs in por_dia.items():
                sgs.sort(key=lambda z: self.slots[z]["indice"])
                L = [self._occ_bool2(occ[pr][z][0]) for z in sgs]
                C = [self._occ_bool2(occ[pr][z][1]) for z in sgs]
                n = len(sgs)
                for i in range(n):
                    for j in range(i + 1, n):
                        for k in range(j + 1, n):
                            for A, B in ((L, C), (C, L)):
                                if A[i] is None or B[j] is None or A[k] is None:
                                    continue
                                if modo == 2:
                                    m.Add(A[i] + B[j] + A[k] <= 2)
                                else:
                                    y = m.NewBoolVar("")
                                    m.Add(y >= A[i] + B[j] + A[k] - 2)
                                    self.pen.append((w, y, "desplazamientos"))

    def _occ_bool2(self, vs):
        if not vs:
            return None
        if len(vs) == 1:
            return vs[0]
        b = self.m.NewBoolVar(""); self.m.AddMaxEquality(b, vs); return b

    def _nueva(self, u, seg, nopref, k, nombre):
        x = self.m.NewBoolVar(nombre)
        self._pieza(u, x, seg, nopref, k)
        out = [x]
        if u.get("alt_general") and not u.get("sin_cambio_aula"):   # sin cambio de aula: no hay aula general
            xa = self.m.NewBoolVar(nombre + "g")
            self._pieza(u, xa, seg, nopref, k, alternativa=True)
            self.pen.append((self.pb["pesos"].get("enAulaNoPreferente", 3) * len(seg), xa, "aula_no_preferente"))
            out.append(xa)
        return out

    def _pieza(self, u, x, seg, nopref, k=None, alternativa=False):
        self.piezas.append((u, x, seg, k)); self._orden[id(x)] = len(self._orden)
        self.alt_general[id(x)] = alternativa
        for pr in u["profesores"]:
            self._ocupar("P", pr, seg, x)
        for g in u["grupos"]:
            self._ocupar("G", g, seg, x)
        if not alternativa:
            for a in u["aulas_fijas"]:
                self._ocupar("A", a, seg, x)
        # elección exacta de aula para conjuntos pequeños (la pieza debe estar en la MISMA aula todo su tiempo);
        # los conjuntos grandes se controlan por capacidad (condición de Hall por átomo) y se asignan al final
        alts = [u["alt_general"]] if alternativa else u["alternativas"]
        for j, cand in enumerate(alts):
            if len(cand) <= LIMITE_ELECCION_EXACTA:
                ws = {}
                for c in cand:
                    w = self.m.NewBoolVar("")
                    ws[c] = w
                    self._ocupar("A", c, seg, w)
                self.m.Add(sum(ws.values()) == x)
                self.eleccion[(id(x), j)] = ws
        for crit, d in nopref.items():
            w = sum(d.get(s, 0) for s in seg)
            if w:
                self.pen.append((self.pb["pesos"].get(crit, 1) * w, x, "ocupaciones_no_pref"))

    # ------------------------------------------------------------ guardias, reuniones, complementarias
    def guardias(self):
        m, pb = self.m, self.pb
        w_ext = pb["pesos"].get("guardiasEnExtremos", 1)
        for gi, g in enumerate(pb["guardias"]):
            por_slot = defaultdict(list)
            for it in g["integrantes"]:
                proh = set(it["prohibidos"])
                vs = []
                for s in g["puestos"]:
                    if s in proh:
                        continue
                    x = m.NewBoolVar(f"g{gi}_{it['profesor']}_{s}")
                    vs.append(x); por_slot[s].append(x)
                    if s in it.get("prefijados", ()):
                        m.Add(x == 1)          # guardia prefijada en la plantilla del integrante
                    self._ocupar("P", it["profesor"], [s], x, "guardias")
                    self.vg.append((gi, it["profesor"], s, x))
                    if not g["recreo"]:
                        st = self.slots[s]; fila = [z for z in pb["filas"][f"{st['marco']}|{st['dia']}"] if z is not None]
                        if fila and s in (fila[0], fila[-1]):
                            self.pen.append((w_ext, x, "guardias_extremas"))
                falta = m.NewIntVar(0, it["n"], f"gf{gi}_{it['profesor']}")
                m.Add(sum(vs) + falta == it["n"])
                # desecharGuardias: las guardias que no se puedan colocar no impiden un resultado completo
                peso_g = PESO_GUARDIA_DESECHABLE if pb.get("desechar_guardias") else PESO_NO_COLOCADA // 2
                self.no_col.append((peso_g, falta, ("guardia", g["nombre"], it["profesor"]), None))
            for s, vs in por_slot.items():
                m.Add(sum(vs) <= int(g["detalle"].get(str(s), g["cantidad"])))

    def reuniones(self):
        m, pb = self.m, self.pb
        for ri, r in enumerate(pb["reuniones"]):
            proh = set(r["prohibidos"]); dias = pb["dias"].get(r["marco"], [])
            por_dia = defaultdict(list); todas = []
            for d in dias:
                for seg in self._bloques(r["marco"], d, r["duracion"]):
                    if proh.intersection(seg):
                        continue
                    x = m.NewBoolVar(f"r{ri}_{seg[0]}")
                    por_dia[d].append(x); todas.append(x); self.vr.append((ri, seg, x))
                    for p in r["integrantes"]:
                        self._ocupar("P", p, seg, x, "reuniones")
            for d in dias:
                m.Add(sum(por_dia[d]) <= 1)
            for s in r.get("prefijados", ()):    # posición prefijada: alguna reunión la cubre
                cubren = [x for (ri2, seg, x) in self.vr if ri2 == ri and s in seg]
                if cubren:
                    m.Add(sum(cubren) == 1)
            falta = m.NewIntVar(0, r["n"], f"rf{ri}")
            m.Add(sum(todas) + falta == r["n"])
            self.no_col.append((PESO_NO_COLOCADA, falta, ("reunion", r["nombre"]), None))

    def complementarias(self):
        m, pb = self.m, self.pb
        for ci, c in enumerate(pb["complementarias"]):
            if c["n"] <= 0:
                continue
            proh = set(c["prohibidos"]); todas = []
            for d in pb["dias"].get(c["marco"], []):
                fila = pb["filas"].get(f"{c['marco']}|{d}", [])
                xs = []
                for s in fila:
                    if s is None or s in proh:
                        xs.append(None); continue
                    x = m.NewBoolVar(f"c{ci}_{s}")
                    xs.append(x); todas.append(x); self.vc.append((ci, s, x))
                    if s in c.get("prefijados", ()):
                        m.Add(x == 1)
                    self._ocupar("P", c["profesor"], [s], x, "complementarias")
                vd = [x for x in xs if x is not None]
                m.Add(sum(vd) <= c["max_dia"])
                if c["continuos"]:
                    ini = []
                    for i, x in enumerate(xs):
                        if x is None:
                            continue
                        prev = xs[i - 1] if i > 0 else None
                        y = m.NewBoolVar("")
                        m.Add(y >= x - (prev if prev is not None else 0))
                        ini.append(y)
                    m.Add(sum(ini) <= 1)
            falta = m.NewIntVar(0, c["n"], f"cf{ci}")
            m.Add(sum(todas) + falta == c["n"])
            self.no_col.append((PESO_NO_COLOCADA // 2, falta, ("complementaria", c["tarea"], c["profesor"], c["id"]), None))

    # ------------------------------------------------------------ recursos y huecos
    def recursos(self):
        m, pb = self.m, self.pb
        for tipo in ("P", "G", "A"):
            for _k, vs in self.ocupa[tipo].items():
                if len(vs) > 1:
                    m.Add(sum(vs) <= 1)
        # capacidad de conjuntos de aulas por átomo: necesidades de alternativas + uso fijo de esas aulas <= nº aulas
        necesidad = defaultdict(list)
        for (u, x, seg, _k) in self.piezas:
            alts = [u["alt_general"]] if self.alt_general.get(id(x)) else u["alternativas"]
            for j, cand in enumerate(alts):
                if (id(x), j) in self.eleccion:
                    continue
                key = tuple(cand)
                for s in seg:
                    for a in self.sa[s]:
                        necesidad[(key, a)].append(x)
        # condición de Hall sobre los conjuntos que aparecen: las necesidades cuyo conjunto está contenido en K,
        # más el uso fijo de las aulas de K, no superan |K| (exacto para conjuntos anidados o disjuntos)
        claves = {k for k, _a in necesidad}
        for (key, a) in list(necesidad):
            ks = set(key)
            vs = [v for k2 in claves if set(k2) <= ks for v in necesidad.get((k2, a), [])]
            fijos = [v for aula in key for v in self.ocupa["A"].get((aula, a), [])]
            m.Add(sum({id(v): v for v in vs}.values()) + sum(fijos) <= len(key))
        self.redundantes()
        if self.ligero:
            return
        # huecos de profesores (en su marco de referencia) y grupos
        for (tipo, nombre), uso in self.uso_slot.items():
            if tipo == "P":
                marco = pb["marco_prof"].get(nombre); w = pb["pesos"].get("huecosEnProfesores", 2); cat = "huecos_profes"
            else:
                marco = pb["marco_grupo"].get(nombre); w = pb["pesos"].get("huecosEnGrupos", 5); cat = "huecos_alumnos"
                if pb["eliminar_huecos_grupo"].get(nombre, True):
                    w *= 2
            if not w:
                continue
            for d, fila in ((d, f) for d in pb["dias"].get(marco, []) for f in (
                    pb.get("filas_prof", {}).get(f"{marco}|{d}") if tipo == "P" and "filas_prof" in pb else
                    [[s for s in pb["filas"].get(f"{marco}|{d}", []) if s is not None]])):
                if len(fila) < 3:
                    continue
                occ = []
                for s in fila:
                    # cualquier actividad del recurso que se solape con el tramo s (incluye otros marcos)
                    vs = list({id(v): v for a in self.sa[s] for v in self.ocupa[tipo].get((nombre, a), [])}.values())
                    if not vs:
                        occ.append(0); continue
                    o = m.NewBoolVar(""); m.AddMaxEquality(o, vs); occ.append(o)
                if sum(1 for o in occ if not isinstance(o, int)) < 2:
                    continue
                pre, post = [0] * len(occ), [0] * len(occ)
                acc = 0
                for i in range(1, len(occ)):
                    if isinstance(acc, int) and isinstance(occ[i - 1], int):
                        acc = 0
                    else:
                        v = m.NewBoolVar(""); m.AddMaxEquality(v, [z for z in (acc, occ[i - 1]) if not isinstance(z, int)]); acc = v
                    pre[i] = acc
                acc = 0
                for i in range(len(occ) - 2, -1, -1):
                    if isinstance(acc, int) and isinstance(occ[i + 1], int):
                        acc = 0
                    else:
                        v = m.NewBoolVar(""); m.AddMaxEquality(v, [z for z in (acc, occ[i + 1]) if not isinstance(z, int)]); acc = v
                    post[i] = acc
                for i in range(1, len(occ) - 1):
                    if isinstance(pre[i], int) or isinstance(post[i], int):
                        continue
                    h = m.NewBoolVar("")
                    m.Add(h >= pre[i] + post[i] - 1 - occ[i])
                    self.pen.append((w, h, cat))

    def redundantes(self):
        """Restricciones redundantes (no cambian las soluciones, ayudan a propagar): por grupo y profesor, la carga
        colocada en cada día no supera los tramos libres de ese día en su marco."""
        pb = self.pb
        for (tipo, nombre), uso in self.uso_slot.items():
            por_dia = defaultdict(dict)
            for s, vs in uso.items():
                st = self.slots[s]; por_dia[(st["marco"], st["dia"])][s] = vs
            for (_mc, _d), tramos in por_dia.items():
                if len(tramos) < 2:
                    continue
                # cada tramo admite una actividad del recurso: suma de ocupaciones de tramos <= nº de tramos
                todos = [v for vs in tramos.values() for v in vs]
                if len(todos) > len(tramos):
                    self.m.Add(sum(todos) <= len(tramos))

    def nucleo(self):
        """Variables de decisión en orden determinista (iguales en el modelo ligero y en el completo)."""
        out = [x for (_u, x, _s, _k) in self.piezas]
        out += [w for k in sorted(self.eleccion, key=lambda k: (self._orden[k[0]], k[1])) for w in self.eleccion[k].values()]
        out += [x for *_r, x in self.vg] + [x for *_r, x in self.vr] + [x for *_r, x in self.vc]
        return out

    def sin_cambio_aula(self):
        """Opción de sesión «sinCambioAula»: todas las piezas colocadas de la unidad usan la misma aula elegida."""
        por_u = defaultdict(list)
        for (u, x, _seg, _k) in self.piezas:
            if u.get("sin_cambio_aula") and not self.alt_general.get(id(x)):
                por_u[u["id"]].append(x)
        for xs in por_u.values():
            for j in range(8):
                wss = [(x, self.eleccion.get((id(x), j))) for x in xs]
                wss = [ws for _x, ws in wss if ws]
                if len(wss) < 2:
                    continue
                # una única aula elegida para la unidad: cada pieza colocada usa esa aula
                cands = sorted({c for ws in wss for c in ws})
                z = {c: self.m.NewBoolVar("") for c in cands}
                self.m.Add(sum(z.values()) <= 1)
                for ws in wss:
                    for c, w in ws.items():
                        self.m.AddImplication(w, z[c])

    def criterios_extra(self):
        """Criterios con peso añadidos en la fase del Motor (Anexo O):
        - masClasesEnUnDiaQueEnOtro («Equilibrar la carga lectiva diaria»): por profesor, (máx - mín) de periodos
          lectivos diarios entre los días de su marco.
        - conCambiosDeAula («Sin cambios de aula»): por unidad con aula elegible y varias piezas (sin la opción
          estricta sinCambioAula), nº de aulas distintas usadas - 1."""
        if self.ligero:
            return
        pb, m = self.pb, self.m
        w = pb["pesos"].get("masClasesEnUnDiaQueEnOtro", 0)
        if w:
            carga = defaultdict(lambda: defaultdict(list))
            for (u, x, seg, _k) in self.piezas:
                st = self.slots[seg[0]]
                for pr in u["profesores"]:
                    if pb["marco_prof"].get(pr) == st["marco"]:
                        carga[pr][st["dia"]].append((len(seg), x))
            for pr, dias in carga.items():
                marco = pb["marco_prof"].get(pr)
                todos = pb["dias"].get(marco, [])
                if len(todos) < 2 or sum(len(v) for v in dias.values()) < 2:
                    continue
                cap = sum(L for v in dias.values() for L, _ in v)
                exprs = [sum(L * x for L, x in dias.get(d, [])) for d in todos]
                mx = m.NewIntVar(0, cap, ""); mn = m.NewIntVar(0, cap, "")
                m.AddMaxEquality(mx, exprs); m.AddMinEquality(mn, exprs)
                dif = m.NewIntVar(0, cap, ""); m.Add(dif == mx - mn)
                self.pen.append((w, dif, "carga_desigual"))
        w = pb["pesos"].get("conCambiosDeAula", 0)
        if w:
            por_u = defaultdict(list)
            for (u, x, _seg, _k) in self.piezas:
                if not u.get("sin_cambio_aula") and not self.alt_general.get(id(x)):
                    por_u[u["id"]].append(x)
            for xs in por_u.values():
                for j in range(8):
                    wss = [ws for ws in (self.eleccion.get((id(x), j)) for x in xs) if ws]
                    if len(wss) < 2:
                        continue
                    cands = sorted({c for ws in wss for c in ws})
                    z = {c: m.NewBoolVar("") for c in cands}
                    for ws in wss:
                        for c, v in ws.items():
                            m.AddImplication(v, z[c])
                    e = m.NewIntVar(0, len(cands), ""); m.Add(e >= sum(z.values()) - 1)
                    self.pen.append((w, e, "cambios_aula"))

    # ------------------------------------------------------------ restricciones de profesores y grupos
    def _occ_bool(self, tipo, nombre, s):
        """Bool «el recurso está ocupado durante el tramo s» (cualquier actividad que se solape en el tiempo)."""
        key = (tipo, nombre, s)
        if key in self._occ_cache:
            return self._occ_cache[key]
        a = self.slots[s]; uso = self.uso_slot.get((tipo, nombre), {})
        vs = list({id(v): v for s2, l in uso.items() for v in l
                   if self.slots[s2]["dia"] == a["dia"] and self.slots[s2]["ini"] < a["fin"] and a["ini"] < self.slots[s2]["fin"]}.values())
        if not vs:
            o = 0
        elif len(vs) == 1:
            o = vs[0]
        else:
            o = self.m.NewBoolVar(""); self.m.AddMaxEquality(o, vs)
        self._occ_cache[key] = o
        return o

    def restricciones(self):
        """Opciones de profesor (máx/mín diarios, horas seguidas, permanencias, mañanas/tardes libres, salir a última
        y entrar a primera) y de grupo (ocupación máxima diaria, tardes libres, sin huecos). Ver motor/restricciones.py."""
        from . import restricciones as RS
        m, pb = self.m, self.pb; L = self.ligero
        self._occ_cache = {}
        W = 3
        wseg = pb["pesos"].get("horasDeClaseSeguidas", 2) or 2
        wperm = pb["pesos"].get("masPermanencia", 1) or 1
        lect = defaultdict(lambda: defaultdict(list))
        for (u, x, seg, _k) in self.piezas:
            for pr in u["profesores"]:
                lect[pr][self.slots[seg[0]]["dia"]].append(len(seg) * x)
                for sg in seg:
                    lect[(pr, "slot")][sg].append(x)
        def fila_de(marco, d):
            return [z for z in pb["filas"].get(f"{marco}|{d}", []) if z is not None]
        def occ_lect(pr, s):
            a = self.slots[s]
            vs = [v for s2, l in lect[(pr, "slot")].items() for v in l
                  if self.slots[s2]["dia"] == a["dia"] and self.slots[s2]["ini"] < a["fin"] and a["ini"] < self.slots[s2]["fin"]]
            return sum(vs) if vs else 0
        for pr, cfg in pb.get("restr_prof", {}).items():
            marco = pb["marco_prof"].get(pr); dias = pb["dias"].get(marco, [])
            uso = self.uso_slot.get(("P", pr), {})
            if not uso:
                continue
            spans = []
            for d in dias:
                fila = fila_de(marco, d)
                lect_d = sum(lect[pr].get(d, [])) if lect[pr].get(d) else 0
                ocup_d = lect_d + sum(v for cl in RS.OCUPACION_CUENTA for v in self.no_lect[pr][cl].get(d, []))
                occ = [self._occ_bool("P", pr, s) for s in fila]
                vivo = [o for o in occ if not isinstance(o, int)]
                trabaja = None
                for clave in ("max_ocup", "max_lect", "min_ocup", "min_lect"):
                    c = cfg.get(clave)
                    if not c or (L and not RS.es_duro(c)):
                        continue
                    v = RS.limite(pb, pr, clave, c); e = lect_d if clave.endswith("lect") else ocup_d
                    if isinstance(e, int):
                        continue
                    cat = "maximo_diario" if clave.startswith("max") else "minimo_diario"
                    if clave.startswith("max"):
                        if RS.es_duro(c):
                            m.Add(e <= v)
                        else:
                            z = m.NewIntVar(0, 30, ""); m.Add(z >= e - v); self.pen.append((W, z, cat))
                    else:
                        if trabaja is None:
                            trabaja = m.NewBoolVar(""); m.AddMaxEquality(trabaja, vivo or [0])
                        if RS.es_duro(c):
                            m.Add(e >= v * trabaja)
                        else:
                            z = m.NewIntVar(0, 30, ""); m.Add(z >= v * trabaja - e); self.pen.append((W, z, cat))
                sg = cfg.get("seguidas")
                if sg and (sg["estricto"] or not L):
                    v = sg["valor"]; filac = pb["filas"].get(f"{marco}|{d}", [])
                    for i in range(len(filac) - v):
                        ven = filac[i:i + v + 1]
                        if None in ven:
                            continue
                        e = sum(occ_lect(pr, s) for s in ven)
                        if isinstance(e, int):
                            continue
                        if sg["estricto"]:
                            m.Add(e <= v)
                        else:
                            y = m.NewIntVar(0, v + 1, ""); m.Add(y >= e - v); self.pen.append((wseg, y, "horas_seguidas"))
                # permanencia diaria
                n = len(fila); need_span = any(c["valor"] < n for c in cfg.get("perm_dia", [])) or \
                    any(c["valor"] < sum(len(fila_de(marco, dd)) for dd in dias) for c in cfg.get("perm_sem", []))
                if need_span and len(vivo) >= 2 and not (L and not any(c["estricto"] for c in cfg.get("perm_dia", []) + cfg.get("perm_sem", []))):
                    f = m.NewIntVar(0, n - 1, ""); l = m.NewIntVar(0, n - 1, "")
                    for i, o in enumerate(occ):
                        if not isinstance(o, int):
                            m.Add(f <= i).OnlyEnforceIf(o); m.Add(l >= i).OnlyEnforceIf(o)
                    sp = m.NewIntVar(0, n, ""); m.Add(sp >= l - f + 1 - n * (1 - (trabaja if trabaja is not None else self._trabaja(vivo))))
                    spans.append(sp)
                    for c in cfg.get("perm_dia", []):
                        if c["valor"] >= n:
                            continue
                        if c["estricto"]:
                            for i in range(n):
                                for j in range(i + c["valor"], n):
                                    if not isinstance(occ[i], int) and not isinstance(occ[j], int):
                                        m.AddBoolOr([occ[i].Not(), occ[j].Not()])
                        elif not L:
                            z = m.NewIntVar(0, n, ""); m.Add(z >= sp - c["valor"]); self.pen.append((wperm, z, "permanencia_dia"))
            for c in cfg.get("perm_sem", []):
                if spans and c["valor"] < sum(len(fila_de(marco, dd)) for dd in dias):
                    if c["estricto"]:
                        m.Add(sum(spans) <= c["valor"])
                    elif not L:
                        z = m.NewIntVar(0, 300, ""); m.Add(z >= sum(spans) - c["valor"]); self.pen.append((wperm, z, "permanencia_semana"))
            # mañanas / tardes libres
            for c in cfg.get("libres", []):
                libres = []
                for d in dias:
                    partes = pb.get("jornada", {}).get(f"{marco}|{d}", [])
                    if len(partes) < 2:
                        continue
                    lib = []
                    for pt in partes[:2]:
                        os_ = [o for o in (self._occ_bool("P", pr, s) for s in pt) if not isinstance(o, int)]
                        b = m.NewBoolVar("")
                        for o in os_:
                            m.AddImplication(b, o.Not())
                        lib.append(b)
                    if c["tipo"] == "mañanas":
                        libres.append(lib[0])
                    elif c["tipo"] == "tardes":
                        libres.append(lib[1])
                    else:
                        z = m.NewBoolVar(""); m.Add(z <= lib[0] + lib[1]); libres.append(z)
                if not libres:
                    continue
                if c["cantidad"]:
                    m.Add(sum(libres) >= min(c["cantidad"], len(libres)))
                if c["preferentes"] > c["cantidad"] and not L:
                    z = m.NewIntVar(0, 5, ""); m.Add(z >= min(c["preferentes"], len(libres)) - sum(libres))
                    self.pen.append((W, z, "medias_jornadas"))
            for c in cfg.get("incompat", []):
                if L and not c["estricto"]:
                    continue
                for a, b in RS._pares_incompat(dias, c["lunes"]):
                    ult = [o for o in (self._occ_bool("P", pr, s) for s in fila_de(marco, a)[-c["n"]:]) if not isinstance(o, int)]
                    pri = [o for o in (self._occ_bool("P", pr, s) for s in fila_de(marco, b)[:c["n"]]) if not isinstance(o, int)]
                    if not ult or not pri:
                        continue
                    ya, yb = self._trabaja(ult), self._trabaja(pri)
                    if c["estricto"]:
                        m.Add(ya + yb <= 1)
                    else:
                        y = m.NewBoolVar(""); m.Add(y >= ya + yb - 1); self.pen.append((W, y, "ultima_primera"))
        for g, cfg in pb.get("restr_grupo", {}).items():
            marco = pb["marco_grupo"].get(g); dias = pb["dias"].get(marco, [])
            libres = []
            for d in dias:
                fila = fila_de(marco, d)
                occ = [self._occ_bool("G", g, s) for s in fila]
                if "limite_dia" in cfg:
                    e = sum(o for o in occ if not isinstance(o, int))
                    if not isinstance(e, int):
                        m.Add(e <= cfg["limite_dia"])
                if cfg.get("sin_huecos"):
                    for i in range(len(occ)):
                        for j in range(i + 2, len(occ)):
                            if isinstance(occ[i], int) or isinstance(occ[j], int):
                                continue
                            for k in range(i + 1, j):
                                m.Add(occ[i] + occ[j] - (occ[k] if not isinstance(occ[k], int) else 0) <= 1)
                partes = pb.get("jornada", {}).get(f"{marco}|{d}", [])
                if cfg.get("tardes_libres") and len(partes) >= 2:
                    b = m.NewBoolVar("")
                    for o in (self._occ_bool("G", g, s) for s in partes[1]):
                        if not isinstance(o, int):
                            m.AddImplication(b, o.Not())
                    libres.append(b)
            if cfg.get("tardes_libres") and libres:
                m.Add(sum(libres) >= min(cfg["tardes_libres"], len(libres)))

    def _trabaja(self, vs):
        if len(vs) == 1:
            return vs[0]
        b = self.m.NewBoolVar(""); self.m.AddMaxEquality(b, vs); return b

    def desechable(self, w, u):
        return bool(self.pb.get("desechar_guardias")) and isinstance(u, tuple) and u[:1] == ("guardia",) \
            and w == PESO_GUARDIA_DESECHABLE

    # ------------------------------------------------------------ objetivo
    def construir(self):
        self._orden = {}
        self.unidades(); self.guardias(); self.reuniones(); self.complementarias(); self.recursos(); self.sin_cambio_aula(); self.restricciones(); self.criterios_extra(); self.alejados()
        self.peso_expr = sum(w * e for w, e, _ in self.pen)
        self.nocol_expr = sum(w * e for w, e, _u, _k in self.no_col)
        return self


class _Callback(cp_model.CpSolverSolutionCallback):
    def __init__(self, mod, informar, t0, fase=2):
        super().__init__(); self.mod, self.informar, self.t0, self.fase = mod, informar, t0, fase
        self.n = 0; self.completos = 0; self.mejor = None

    def on_solution_callback(self):
        self.n += 1
        nc = sum(self.Value(e) for w, e, u, _k in self.mod.no_col if w and not self.mod.desechable(w, u))
        peso = None if self.fase == 1 else (self.Value(self.mod.peso_expr) if not isinstance(self.mod.peso_expr, int) else 0)
        if nc == 0:
            self.completos += 1
        self.mejor = (nc, peso)
        if self.informar:
            self.informar({"evento": "solucion", "t": self.reloj.leer(), "n": self.n, "completos": self.completos,
                           "no_colocadas": nc, "peso": peso, "fase": self.fase,
                           "cota": self.BestObjectiveBound() if self.fase == 2 and _con_cota() else None})


class Reloj:
    """Tiempo de proceso ACTIVO: los saltos de más de 1 s entre lecturas (proceso suspendido con «Pausa»)
    no cuentan. El límite de tiempo del motor se aplica sobre este reloj, no sobre el de pared."""
    def __init__(self):
        self.activo = 0.0; self._ult = time.monotonic(); self._lock = threading.Lock()

    def leer(self):
        with self._lock:
            ahora = time.monotonic(); dt = ahora - self._ult; self._ult = ahora
            if dt < 1.0:
                self.activo += dt
            return self.activo


MODO_FASE2 = "lns"
EVALUAR_FASE1 = os.environ.get("HORARIOS_EVAL1", "1") == "1"


def _modo():
    return os.environ.get("HORARIOS_FASE2", MODO_FASE2)


def _con_cota():
    # con «lns» ningún trabajador calcula cota inferior (sería trivial)
    return _modo() != "lns"


def _parametros(sol, hilos, semilla, fase):
    p = sol.parameters
    p.num_workers = max(1, int(hilos)); p.random_seed = int(semilla)
    p.max_time_in_seconds = 1e6        # el límite real lo aplica el vigilante con el reloj activo
    if fase == 1:
        # factibilidad: el objetivo (no colocadas) llega a su cota 0 en cuanto hay un resultado completo
        p.linearization_level = 0
    else:
        # optimización: búsqueda local en vecindarios grandes (LNS) en todos los hilos, partiendo del resultado de
        # la fase 1. Medido (pruebas/benchmark_motor.py): mejor peso a 10-120 s que la cartera por defecto en
        # todos los casos; a cambio no se demuestra el óptimo ni se calcula cota inferior.
        modo = _modo()
        if modo == "lns":
            p.linearization_level = 0
            p.use_lns_only = True
        elif modo == "mix1":      # 1 trabajador completo (con LP, da cota) + el resto LNS
            p.num_full_subsolvers = 1
        elif modo == "mix2":      # 2 completos + resto LNS
            p.num_full_subsolvers = 2
        elif modo == "mix1lin0":
            p.num_full_subsolvers = 1; p.linearization_level = 0
        # "defecto": cartera por defecto de CP-SAT


def resolver(pb: dict, segundos=60.0, hilos=8, informar=None, parar: threading.Event | None = None, semilla=0):
    """Resuelve y devuelve el resultado (dict serializable).

    Fase 1: modelo ligero (solo restricciones duras) minimizando las no colocadas -> resultado completo rápido.
    Fase 2: modelo completo con la solución de la fase 1 como punto de partida (hint) y sin empeorar sus no
    colocadas; optimiza el peso hasta agotar el tiempo. Los eventos «solucion» de la fase 1 llevan peso None
    (aún no evaluado: el modelo ligero no calcula huecos)."""
    reloj = Reloj()
    segundos = float(segundos)
    ctl = {"fin": False, "parado": False, "limite": 0.0, "sol": None}

    def vigilar():
        while not ctl["fin"]:
            time.sleep(0.05)
            t = reloj.leer(); sol_ = ctl["sol"]
            if parar is not None and parar.is_set():
                ctl["parado"] = True
                if sol_ is not None:
                    sol_.StopSearch()
                if ctl["fin"]:
                    return
            elif sol_ is not None and t >= ctl["limite"]:
                sol_.StopSearch()
    threading.Thread(target=vigilar, daemon=True).start()
    if informar:
        informar({"evento": "fase", "texto": "Construyendo el modelo"})
    # Fase 1 en escalones (cada uno con su tiempo; un escalón INFEASIBLE se descarta al instante):
    #   1) todo colocado como restricción dura (factibilidad pura: lo más rápido cuando existe);
    #   2) sesiones lectivas, reuniones y complementarias duras; guardias minimizadas;
    #   3) todo minimizado (puede quedar algo sin colocar).
    # Con «Desechar guardias» el escalón 1 se omite (las guardias no impiden un resultado completo).
    escalones = [("todo", 0.35), ("lectivas", 0.35), ("nada", 0.70)]
    if pb.get("desechar_guardias"):
        escalones = escalones[1:]
    cb1 = None
    for nivel, frac in escalones:
        mod1 = Modelo(pb, ligero=True).construir()
        if informar and cb1 is None:
            informar({"evento": "fase", "texto": "Buscando un resultado completo",
                      "variables": len(mod1.m.Proto().variables), "restricciones": len(mod1.m.Proto().constraints)})
        for w, e, u, _k in mod1.no_col:
            if isinstance(e, int):
                continue
            es_guardia = isinstance(u, tuple) and u[0] == "guardia"
            if nivel == "todo" or (nivel == "lectivas" and not es_guardia):
                mod1.m.Add(e == 0)
        mod1.m.Minimize(mod1.nocol_expr)
        sol1 = cp_model.CpSolver(); _parametros(sol1, hilos, semilla, 1)
        previo = cb1
        cb1 = _Callback(mod1, informar, 0, fase=1); cb1.reloj = reloj
        if previo is not None:
            cb1.n, cb1.completos = previo.n, previo.completos
        resto = max(1.0, segundos - reloj.leer())
        tope = min(resto, max(5.0, segundos * frac)) if nivel != "nada" else max(1.0, segundos * frac - reloj.leer())
        ctl["limite"] = reloj.leer() + tope; ctl["sol"] = sol1
        e1 = sol1.Solve(mod1.m, cb1)
        if e1 in (cp_model.OPTIMAL, cp_model.FEASIBLE) or ctl["parado"] or reloj.leer() >= segundos:
            break
    ok1 = e1 in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    mod, sol, estado, cb = mod1, sol1, e1, cb1
    if ok1 and not ctl["parado"] and reloj.leer() < segundos:
        mejor_nc = int(sol1.ObjectiveValue())
        vals = [sol1.Value(v) for v in mod1.nucleo()]
        if informar:
            informar({"evento": "fase", "texto": TX("optimizando")})
        mod2 = Modelo(pb).construir(); m = mod2.m
        nuc = mod2.nucleo()
        if len(nuc) == len(vals):
            for v, x in zip(nuc, vals):
                m.AddHint(v, x)
        if not isinstance(mod2.nocol_expr, int):
            m.Add(mod2.nocol_expr <= mejor_nc)
        m.Minimize(mod2.nocol_expr + mod2.peso_expr)
        # Evaluación rápida del resultado de la fase 1 con el modelo completo (variables de decisión fijadas a la
        # pista): da su peso real a la ventana mientras arranca la optimización y completa la pista con las
        # variables auxiliares (huecos, penalizaciones...).
        if EVALUAR_FASE1 and len(nuc) == len(vals) and not ctl["parado"]:
            ev = cp_model.CpSolver(); ev.parameters.num_workers = 1
            ev.parameters.fix_variables_to_their_hinted_value = True
            ev.parameters.max_time_in_seconds = max(0.5, min(5.0, segundos - reloj.leer()))
            ctl["sol"] = ev; ctl["limite"] = segundos
            if ev.Solve(m) in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                pe = ev.Value(mod2.peso_expr) if not isinstance(mod2.peso_expr, int) else 0
                nce = ev.Value(mod2.nocol_expr) if not isinstance(mod2.nocol_expr, int) else 0
                if informar:
                    informar({"evento": "peso_provisional", "peso": pe, "no_colocadas_peso": nce,
                              "tiempo": round(reloj.leer(), 2)})
                m.ClearHints()
                for i in range(len(m.Proto().variables)):
                    m.AddHint(m.GetIntVarFromProtoIndex(i), ev.Value(m.GetIntVarFromProtoIndex(i)))
        sol2 = cp_model.CpSolver(); _parametros(sol2, hilos, semilla, 2)
        cb2 = _Callback(mod2, informar, 0, fase=2); cb2.reloj = reloj; cb2.n = cb1.n; cb2.completos = cb1.completos
        ctl["limite"] = max(reloj.leer() + 1.0, segundos); ctl["sol"] = sol2
        e2 = sol2.Solve(m, cb2)
        if e2 in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            mod, sol, estado, cb = mod2, sol2, e2, cb2
        else:
            cb1.n, cb1.completos = cb2.n, cb2.completos
    ctl["fin"] = True
    t = reloj.leer()
    nombre_estado = sol.StatusName(estado)
    if estado not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {"estado": nombre_estado, "tiempo": t, "sesiones": [], "no_colocadas": [], "guardias": [],
                "reuniones": [], "complementarias": [], "estadisticas": {"estado": nombre_estado, "tiempo": round(t, 2),
                "parado": ctl["parado"]}}
    V = sol.Value
    slots = pb["slots"]
    # ------------------------------------------------ extracción
    piezas = []
    for (u, x, seg, k) in mod.piezas:
        if V(x):
            ag = mod.alt_general.get(id(x))
            alts = [u["alt_general"]] if ag else u["alternativas"]
            elegidas = [next(c for c, w in mod.eleccion[(id(x), j)].items() if V(w))
                        for j in range(len(alts)) if (id(x), j) in mod.eleccion]
            piezas.append({"unidad": u["id"], "sesiones": u["sesiones"], "marco": slots[seg[0]]["marco"],
                           "dia": slots[seg[0]]["dia"], "tramos": [slots[s]["indice"] for s in seg], "slots": seg,
                           "aulas": ([] if ag else list(u["aulas_fijas"])) + elegidas, "pieza": k,
                           "buscar_aula": [c for j, c in enumerate(alts) if (id(x), j) not in mod.eleccion],
                           "aula_no_preferente": bool(ag)})
    _asignar_aulas(pb, piezas, mod.sa)
    nocol = []
    for w, e, u, k in mod.no_col:
        v = V(e)
        if v:
            if isinstance(u, dict):
                if isinstance(k, tuple):      # v piezas sin colocar de duración k[1]
                    nocol += [{"tipo": "sesion", "sesiones": u["sesiones"], "etiqueta": u["etiqueta"], "periodos": k[1]}
                              for _ in range(v)]
                else:
                    nocol.append({"tipo": "sesion", "sesiones": u["sesiones"], "etiqueta": u["etiqueta"],
                                  "periodos": v if k is None else u["piezas"][k]})
            else:
                nocol.append({"tipo": u[0], "nombre": u[1], "profesor": u[2] if len(u) > 2 else "", "cantidad": v,
                              **({"id": u[3]} if len(u) > 3 else {})})
    guard = [{"servicio": pb["guardias"][gi]["nombre"], "profesor": p, "marco": slots[s]["marco"], "dia": slots[s]["dia"],
              "tramo": slots[s]["indice"]} for gi, p, s, x in mod.vg if V(x)]
    reun = [{"reunion": pb["reuniones"][ri]["nombre"], "marco": slots[seg[0]]["marco"], "dia": slots[seg[0]]["dia"],
             "tramos": [slots[s]["indice"] for s in seg]} for ri, seg, x in mod.vr if V(x)]
    comp = [{"id": pb["complementarias"][ci]["id"], "tarea": pb["complementarias"][ci]["tarea"],
             "profesor": pb["complementarias"][ci]["profesor"], "marco": slots[s]["marco"], "dia": slots[s]["dia"],
             "tramo": slots[s]["indice"]} for ci, s, x in mod.vc if V(x)]
    resumen = defaultdict(int)
    for w, e, cat in mod.pen:
        v = V(e)
        if v:
            resumen[cat] += v
    peso = V(mod.peso_expr) if not isinstance(mod.peso_expr, int) else 0
    est = {"tiempo": round(t, 2), "estado": nombre_estado, "peso": peso,
           "no_colocadas": sum(1 for n in nocol if n["tipo"] == "sesion"),
           "periodos_no_colocados": sum(n.get("periodos", 0) for n in nocol if n["tipo"] == "sesion"),
           "guardias_no_colocadas": sum(n.get("cantidad", 0) for n in nocol if n["tipo"] == "guardia"),
           "peso_no_colocadas": V(mod.nocol_expr) if not isinstance(mod.nocol_expr, int) else 0,
           "resultados": cb.n, "completos": cb.completos,
           "cota": sol.BestObjectiveBound() if (not mod.ligero and _con_cota()) else None,
           "variables": len(mod.m.Proto().variables), "restricciones": len(mod.m.Proto().constraints),
           "resumen": dict(resumen), "parado": ctl["parado"], "optimo": nombre_estado == "OPTIMAL" and not mod.ligero,
           "sin_optimizar": mod.ligero}
    return {"estado": nombre_estado, "tiempo": t, "sesiones": piezas, "no_colocadas": nocol, "guardias": guard,
            "reuniones": reun, "complementarias": comp, "estadisticas": est, **({"parcial": pb["parcial"]} if pb.get("parcial") else {})}


def _asignar_aulas(pb, piezas, sa):
    """Asigna aulas concretas a las necesidades de alternativas con un pequeño modelo exacto (CP-SAT):
    cada necesidad recibe un aula de su conjunto, sin dos piezas en la misma aula en el mismo átomo de tiempo
    (respetando las aulas fijas). Si algo no cabe se deja sin aula con un aviso."""
    ocupadas = defaultdict(set)   # átomo -> aulas fijas
    for p in piezas:
        for s in p["slots"]:
            for a in sa[s]:
                ocupadas[a].update(p["aulas"])
    pend = [(p, cand, j) for p in piezas for j, cand in enumerate(p.pop("buscar_aula"))]
    if not pend:
        return
    m = cp_model.CpModel()
    por_aula_atomo = defaultdict(list)
    ys, sin = [], []
    for i, (p, cand, _j) in enumerate(pend):
        atoms = [a for s in p["slots"] for a in sa[s]]
        vs = {}
        for c in cand:
            if any(c in ocupadas[a] for a in atoms):
                continue
            v = m.NewBoolVar(""); vs[c] = v
            for a in atoms:
                por_aula_atomo[(c, a)].append(v)
        nada = m.NewBoolVar("")
        m.Add(sum(vs.values()) + nada == 1)
        ys.append(vs); sin.append(nada)
    for vs in por_aula_atomo.values():
        if len(vs) > 1:
            m.Add(sum(vs) <= 1)
    # sinCambioAula: las piezas de una misma unidad procuran la misma aula de su conjunto
    sin_cambio = {u["id"] for u in pb["unidades"] if u.get("sin_cambio_aula")}
    grupos = defaultdict(list)
    for (p, _c, j), vs in zip(pend, ys):
        if p["unidad"] in sin_cambio and not p.get("aula_no_preferente"):
            grupos[(p["unidad"], j)].append(vs)
    difs = []
    for lista in grupos.values():
        for v1, v2 in zip(lista, lista[1:]):
            for c in set(v1) | set(v2):
                dv = m.NewBoolVar(""); difs.append(dv)
                m.Add(dv >= (v1[c] if c in v1 else 0) - (v2[c] if c in v2 else 0))
    m.Minimize(1000 * sum(sin) + sum(difs))
    sol = cp_model.CpSolver(); sol.parameters.max_time_in_seconds = 20; sol.parameters.num_workers = 4
    st = sol.Solve(m)
    ok = st in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    for (p, cand, _j), vs, nada in zip(pend, ys, sin):
        elegido = next((c for c, v in vs.items() if ok and sol.Value(v)), None)
        if elegido is None:
            p.setdefault("avisos", []).append("Sin aula disponible en su conjunto")
        else:
            p["aulas"].append(elegido)
