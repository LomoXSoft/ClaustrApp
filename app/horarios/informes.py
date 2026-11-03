"""Informes e impresión del Editor: modelo de tablas y dibujo con QPainter (PDF, impresora, vista previa).

La maquetación sigue los listados del centro (informe.md §7): cabecera con centro/localidad y título
«Horario semanal: …», subtítulo con el elemento, rejilla lunes-viernes con regleta de horas, recreos,
celdas «materia / grupo(s) o profesor(es) / aula», leyenda de optativas y pie discreto. Sin logotipos ajenos.
"""
from __future__ import annotations
from .textos import TX
import copy, html, os, re
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict, Counter
from PySide6.QtCore import Qt, QRectF, QMarginsF, QSizeF
from PySide6.QtGui import QPainter, QBrush, QColor, QFont, QFontMetricsF, QPen, QPageLayout, QPageSize, QImage, QPdfWriter
from PySide6.QtPrintSupport import QPrinter
from . import APP_NAME, VENDOR
from .modelo import INDIFERENTE, PREFERENTE, PROHIBIDO, NO_PREF1, NO_PREF2

MARCA = f"{APP_NAME} · {VENDOR}"
DIAS5 = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

OPC_DEF = {
    "presentacion": "uno",          # distintos | uno | completo (una tabla con el horario completo)
    "varias_por_pagina": False, "solo_ocupada": True, "tipo": "alumnos",
    "lista_asignaciones": False, "contadores": False, "desdobles": 3,
    "ident": {"materias": TX("codigo"), "alumnos": TX("codigo"), "profesores": TX("codigo"), "aulas": TX("codigo")},
    "ocultar_profesor": False, "ocultar_aula": False, "ocultar_materia": False, "centrar": True,
    "horas": "regleta",             # tabla | regleta | celda
    "tam": "normal", "fuente": "Nimbus Sans",
    "colorear": True, "letreros_recreo": True, "prohibiciones": False, "depto": True,
    "cab_usuario": True, "cab_localidad": True, "cab_titulo": True, "cab_semana": False,
    "pie_fecha": True, "pie_pagina": True, "pie_marca": True,
    "logo": "", "texto_pie": "", "mostrar_texto_pie": False,
    "centro": "Centro educativo", "localidad": "", "curso": "",
    "letreros": {"dias": DIAS5[:5], "recreo": "RECREO", "mediodia": "MEDIODÍA", "profesor": "Profesor", "aula": "Aula",
                 "materia": "Materia", "grupo": "Grupo", "guardia": "GUARDIA", "reunion": "REUNIÓN"},
    "lineas_v": True, "lineas_h": True, "color_lineas": "#555555", "color_texto": "#000000", "color_fondo": "#ffffff",
    # rejilla del Editor (Letreros y configuración)
    "botones_3d": False, "senala_fila": False, "senala_columna": False,
    "color_track_linea": "#d00000", "color_track_texto": "#ffffff",
}

# tipo -> (título del informe, vista del editor)
TIPOS = {
    "alumnos": ("Grupos de alumnos", "Grupos"), "profesores": ("Profesores", "Profesorado"), "aulas": ("Aulas", "Aulas"),
    "materias": ("Materias", None), "guardias": ("GUARDIA", "Guardias"), "recreo": ("Guardias de recreo", "Guardias"),
    "reuniones": ("REUNIÓN", "Reuniones"), "prof_libres": (TX("profs_libres"), None), "aulas_libres": (TX("aulas_libres"), None),
    "individual": ("Horario individual del profesor", "Profesorado"),
}
LISTADOS = {   # informes de lista (no rejilla)
    "asignaciones": "Asignaciones del profesorado", "equipos": TX("equipo_docente_cada_grupo"),
    "tutores_alumnos": "Tutores ordenados por los alumnos", "tutores_tutor": "Tutores ordenados por el tutor",
    "resumen_horas": "Resumen de las horas de los profesores", "estadistica_guardias": "Estadística de guardias",
    "equipos_curso": TX("equipo_docente_cada_curso"), "alumnos_subgrupos": "Alumnos y subgrupos",
    "preferencias": "Preferencias del profesorado", "firmas_aula": "Hoja de firmas por aula",
    "firmas_alumnos": "Hoja de firmas por grupo de alumnos", "firmas_profesor": "Hoja de firmas por profesor",
    "ausencias": "Hoja para anotar ausencias y sustituciones",
}


def opciones(doc=None, base=None):
    o = copy.deepcopy(OPC_DEF)
    for src in (base or {}), ((doc or {}).get("editor", {}).get("informes") or {}):
        for k, v in src.items():
            if isinstance(v, dict) and isinstance(o.get(k), dict):
                o[k].update(v)
            else:
                o[k] = v
    return o


@dataclass
class Celda:
    lineas: list
    color: str = ""
    recreo: bool = False


@dataclass
class Tabla:
    titulo: str
    subtitulo: str
    dias: list
    filas: list                      # [(entrada, salida, tipo)]
    celdas: dict = field(default_factory=dict)      # (fila, dia) -> [Celda]
    leyenda: list = field(default_factory=list)     # líneas de texto bajo la tabla
    resumen: list = field(default_factory=list)     # [(concepto, valor)]
    lista: bool = False              # celdas con listas largas (libres, guardias)
    cols: list = field(default_factory=list)        # informe de lista: cabeceras
    datos: list = field(default_factory=list)       # informe de lista: filas
    marcas: dict = field(default_factory=dict)      # (fila, dia) -> estado de la plantilla del profesor
    alto_fila: float = 5.5                          # informe de lista: alto de fila en mm (hojas de firmas: más)
    rejilla_lista: bool = False                     # informe de lista: trazar todas las líneas (impresos)
    anchos: list = field(default_factory=list)      # informe de lista: pesos de columna fijos


def _hm(minutos):
    return f"{minutos // 60}:{minutos % 60:02d}"


def _min(h):
    hh, mm = h.split(":")[:2]
    return int(hh) * 60 + int(mm)


class Generador:
    def __init__(self, ed, opc):
        self.ed, self.o = ed, opc
        self.p = ed.p
        self._occ = None

    # ------------------------------------------------------------- identificativos
    def _nom(self, cat, nombre):
        if self.o["ident"].get(cat) != "Nombre completo" or not nombre:
            return nombre
        lista = {"materias": self.p.materias, "alumnos": self.p.grupos, "profesores": self.p.profesores, "aulas": self.p.aulas}[cat]
        e = next((e for e in lista if e.nombre == nombre), None)
        return (e.datos.get("nombreCompleto") or nombre) if e else nombre

    def depto(self, prof):
        e = next((e for e in self.p.profesores if e.nombre == prof), None)
        return (e.datos.get("departamento") or "") if e else ""

    # ------------------------------------------------------------- contenido de celdas
    def lineas(self, item, vista):
        ed, o, L = self.ed, self.o, self.o["letreros"]
        obj = ed.obj(item); k = item[0]
        if k == "s":
            ss = [ed.ses[s] for s in obj["sesiones"] if s in ed.ses]
            mat = ", ".join(dict.fromkeys(self._nom("materias", s.materia) for s in ss))
            profs = list(dict.fromkeys(s.profesor for s in ss if s.profesor))
            grs = list(dict.fromkeys(g for s in ss for g in [s.grupo] + s.otros_grupos if g))
            aul = "\\".join(self._nom("aulas", a) for a in obj.get("aulas", []))
            lin = []
            if not o["ocultar_materia"]:
                lin.append(mat)
            if vista == "Grupos":
                if not o["ocultar_profesor"] and profs:
                    lin.append(", ".join(self._nom("profesores", x) for x in profs))
            elif vista == "Profesorado":
                lin.append(", ".join(self._nom("alumnos", g) for g in grs))
                otros = [x for x in profs if x != self._actual]
                if otros and not o["ocultar_profesor"]:
                    lin.append(", ".join(self._nom("profesores", x) for x in otros))
            elif vista == "Aulas":
                lin.append(", ".join(self._nom("alumnos", g) for g in grs))
                if not o["ocultar_profesor"] and profs:
                    lin.append(", ".join(self._nom("profesores", x) for x in profs))
            else:   # materias
                lin.append(", ".join(self._nom("alumnos", g) for g in grs))
                if not o["ocultar_profesor"] and profs:
                    lin.append(", ".join(self._nom("profesores", x) for x in profs))
            if vista != "Aulas" and not o["ocultar_aula"] and aul:
                lin.append(aul)
            return [x for x in lin if x]
        if k == "g":
            t = ed.tramos.get((obj["marco"], obj["dia"], obj["tramo"]))
            if t is not None and t.tipo != "lectivo":
                return ["REC", obj["servicio"]]
            return [L["guardia"], obj["servicio"]]
        if k == "r":
            return [L["reunion"], obj["reunion"]]
        return [obj.get("tarea", "")]

    def color(self, item):
        if not self.o["colorear"] or not self.ed.doc["editor"].get("con_colores", True):
            return ""
        return self.ed.color(self.ed.clave_color(item))

    # ------------------------------------------------------------- estructura de rejilla
    def _filas(self, marcos):
        filas = []
        for m in marcos:
            for t in self.p.marcos[m].filas():
                filas.append((m, t))
        return filas

    def _recortar(self, tabla, filas):
        if not self.o["solo_ocupada"]:
            return tabla
        usadas = sorted({f for (f, d) in tabla.celdas})
        if not usadas:
            return tabla
        a, b = usadas[0], usadas[-1]
        while a > 0 and filas[a - 1][1].tipo != "lectivo" and False:
            a -= 1
        mapa = {i: i - a for i in range(a, b + 1)}
        tabla.filas = tabla.filas[a:b + 1]
        tabla.celdas = {(mapa[f], d): v for (f, d), v in tabla.celdas.items()}
        tabla.marcas = {(mapa[f], d): v for (f, d), v in tabla.marcas.items() if f in mapa}
        return tabla

    def rejilla(self, titulo, subtitulo, items, vista, marcos=None):
        marcos = marcos or self.ed.marcos_de(vista if vista in ("Profesorado", "Grupos", "Aulas", "Reuniones", "Guardias") else "Grupos",
                                             subtitulo, items) if items else (marcos or [next(iter(self.p.marcos))])
        filas = self._filas(marcos)
        ndias = max(len(self.p.marcos[m].dias) for m in marcos)
        dias = (self.o["letreros"]["dias"] + DIAS5[5:])[:ndias]
        tb = Tabla(titulo, subtitulo, dias, [(t.entrada, t.salida, t.tipo) for _, t in filas])
        fila_de = {(m, t.indice): i for i, (m, t) in enumerate(filas)}
        grupos_celda = defaultdict(list)
        for it in items:
            for (m, d, idx) in self.ed.posiciones(it):
                i = fila_de.get((m, idx))
                if i is not None and d < ndias:
                    grupos_celda[(i, d)].append(it)
        leyenda = []
        for (i, d), its in sorted(grupos_celda.items()):
            if vista == "Grupos" and len(its) >= max(2, int(self.o["desdobles"])):
                n = len(leyenda) + 1
                aulas = "\\".join(dict.fromkeys(a for it in its for a in self.ed.obj(it).get("aulas", [])))
                tb.celdas[(i, d)] = [Celda(["(*) [op.%d]" % n] + ([aulas] if aulas and not self.o["ocultar_aula"] else []), "#f4f4f4")]
                for it in its:
                    ss = [self.ed.ses[s] for s in self.ed.obj(it).get("sesiones", []) if s in self.ed.ses]
                    leyenda.append(f"op.{n}: " + ", ".join(f"{self._nom('materias', s.materia)} – {self._nom('profesores', s.profesor)}" for s in ss))
                continue
            tb.celdas[(i, d)] = [Celda(self.lineas(it, vista), self.color(it), filas[i][1].tipo != "lectivo") for it in its]
        if leyenda:
            tb.leyenda = ["Optativas – Profesores – Materias"] + leyenda
        if self.o.get("prohibiciones") and vista == "Profesorado":
            e = next((e for e in self.p.profesores if e.nombre == getattr(self, "_actual", None)), None)
            for (m, d, idx), est in (e.plantilla.items() if e else []):
                i = fila_de.get((m, idx))
                if i is not None and d < ndias and est in MARCAS_PLANTILLA:
                    tb.marcas[(i, d)] = est
            if tb.marcas:
                tb.leyenda.append("Sombreado: " + " · ".join(MARCAS_PLANTILLA[k][1] for k in MARCAS_PLANTILLA
                                                              if k in set(tb.marcas.values())))
        return self._recortar(tb, filas)

    # ------------------------------------------------------------- tipos de informe
    def tablas(self, tipo, nombres=None):
        ed = self.ed; titulo = "Horario semanal: " + TIPOS[tipo][0]
        out = []
        if tipo in ("alumnos", "profesores", "aulas", "individual"):
            vista = TIPOS[tipo][1]
            els = nombres or ed.elementos(vista)
            if vista == "Profesorado" and self.o["depto"] and not nombres:
                els = sorted(els, key=lambda n: (self.depto(n).lower(), n))
            if vista == "Aulas" and not nombres:
                els = [a for a in els if ed.items_de("Aulas", a)]
            for n in els:
                self._actual = n
                its = ed.items_de(vista, n)
                sub = self._nom({"Grupos": "alumnos", "Profesorado": "profesores", "Aulas": "aulas"}[vista], n)
                if vista == "Profesorado" and self.o["depto"] and self.depto(n):
                    sub += " – " + self.depto(n).upper()
                tb = self.rejilla(titulo if tipo != "individual" else "Horario individual del profesor", sub, its, vista)
                if tipo == "individual" or self.o["contadores"]:
                    tb.resumen = self.resumen_profesor(n, its) if vista == "Profesorado" else self.contadores(its)
                if self.o["lista_asignaciones"]:
                    tb.leyenda += self.asignaciones_de(its)
                out.append(tb)
        elif tipo == "materias":
            for m in nombres or [e.nombre for e in self.p.materias]:
                its = [it for it in ed.items() if it[0] == "s" and any(ed.ses[s].materia == m for s in ed.obj(it)["sesiones"] if s in ed.ses)]
                if its:
                    out.append(self.rejilla("Horario semanal: Materias", self._nom("materias", m), its, "Materias", self._marcos(its)))
        elif tipo in ("guardias", "recreo"):
            for sv in nombres or ed.elementos("Guardias"):
                its = [it for it in ed.items_de("Guardias", sv)]
                if tipo == "recreo":
                    its = [it for it in its if self._es_recreo(it)]
                if not its:
                    continue
                tb = self.rejilla(titulo, sv, [], "Guardias", self._marcos(its)); tb.lista = True
                filas = {(f[0], f[1]): i for i, f in enumerate(tb.filas)}
                tb.celdas = {}
                full = self._filas(self._marcos(its))
                fi = {(m, t.indice): i for i, (m, t) in enumerate(full)}
                tb.filas = [(t.entrada, t.salida, t.tipo) for _, t in full]
                por = defaultdict(list)
                for it in its:
                    g = ed.obj(it); i = fi.get((g["marco"], g["tramo"]))
                    if i is not None:
                        por[(i, g["dia"])].append(self._nom("profesores", g["profesor"]))
                tb.celdas = {k: [Celda(sorted(v), "")] for k, v in por.items()}
                out.append(self._recortar(tb, full))
        elif tipo == "reuniones":
            its = [it for it in ed.items() if it[0] == "r"]
            if its:
                tb = self.rejilla(titulo, "Reuniones semanales", [], "Reuniones", self._marcos(its)); tb.lista = True
                full = self._filas(self._marcos(its)); fi = {(m, t.indice): i for i, (m, t) in enumerate(full)}
                tb.filas = [(t.entrada, t.salida, t.tipo) for _, t in full]
                por = defaultdict(list)
                for it in its:
                    for (m, d, idx) in ed.posiciones(it):
                        if (m, idx) in fi:
                            por[(fi[(m, idx)], d)].append(ed.obj(it)["reunion"])
                tb.celdas = {k: [Celda(sorted(dict.fromkeys(v)), self.color(its[0]))] for k, v in por.items()}
                out.append(self._recortar(tb, full))
        elif tipo in ("prof_libres", "aulas_libres"):
            out += self.libres("profesores" if tipo == "prof_libres" else "aulas")
        return out

    def _marcos(self, its):
        ms = []
        for it in its:
            for (m, d, i) in self.ed.posiciones(it):
                if m not in ms:
                    ms.append(m)
        return ms or [next(iter(self.p.marcos))]

    def _es_recreo(self, it):
        g = self.ed.obj(it); t = self.ed.tramos.get((g["marco"], g["dia"], g["tramo"]))
        return t is not None and t.tipo != "lectivo"

    def ocupacion(self):
        if self._occ is None:
            self._occ = defaultdict(set)
            for it, tp, nm, d, a, b in self.ed.ocupacion():
                self._occ[(tp, d)].add((a, b, nm))
        return self._occ

    def libres(self, tipo):
        tp = "profesor" if tipo == "profesores" else "aula"
        lista = self.p.profesores if tp == "profesor" else self.p.aulas
        occ = self.ocupacion(); out = []
        titulo = TX("profs_libres") if tp == "profesor" else TX("aulas_libres")
        m = next(iter(self.p.marcos)); marco = self.p.marcos[m]
        lect = [t for t in marco.filas() if t.tipo == "lectivo"]
        for n, t0 in enumerate(lect, 1):
            dias = (self.o["letreros"]["dias"] + DIAS5[5:])[:len(marco.dias)]
            tb = Tabla(titulo, f"{n}º periodo ({t0.entrada}-{t0.salida})", dias, [(t0.entrada, t0.salida, "lectivo")]); tb.lista = True
            for d in range(len(marco.dias)):
                t = self.ed.tramos.get((m, d, t0.indice))
                if t is None:
                    continue
                a, b = _min(t.entrada), _min(t.salida)
                ocup = {nm for (a2, b2, nm) in occ[(tp, d)] if a2 < b and a < b2}
                tb.celdas[(0, d)] = [Celda([self._nom("profesores" if tp == "profesor" else "aulas", e.nombre)
                                            for e in lista if e.nombre not in ocup], "")]
            out.append(tb)
        return out

    # ------------------------------------------------------------- resúmenes
    def _duracion(self, it):
        tot = 0
        for (m, d, i) in self.ed.posiciones(it):
            t = self.ed.tramos.get((m, d, i))
            if t is not None:
                tot += _min(t.salida) - _min(t.entrada)
        return tot

    def resumen_profesor(self, prof, its=None):
        its = its if its is not None else self.ed.items_de("Profesorado", prof)
        cats = {"Lectivas": [0, 0], "Complementarias": [0, 0], "Guardias": [0, 0], "Guardias de recreo": [0, 0], "Reuniones": [0, 0]}
        for it in its:
            k = it[0]
            c = {"s": "Lectivas", "c": "Complementarias", "r": "Reuniones"}.get(k) or ("Guardias de recreo" if self._es_recreo(it) else "Guardias")
            cats[c][0] += len(self.ed.posiciones(it)); cats[c][1] += self._duracion(it)
        filas = [(k, f"{v[0]} periodos · {_hm(v[1])} h") for k, v in cats.items() if v[0]]
        tot = [sum(v[0] for v in cats.values()), sum(v[1] for v in cats.values())]
        filas.append(("Total semanal", f"{tot[0]} periodos · {_hm(tot[1])} h"))
        return filas

    def contadores(self, its):
        c = Counter()
        for it in its:
            for lin in [self.lineas(it, "Materias")[:1]]:
                c[lin[0] if lin else "?"] += len(self.ed.posiciones(it))
        return [(k, f"{v} periodos") for k, v in sorted(c.items())]

    def asignaciones_de(self, its):
        c = Counter()
        for it in its:
            if it[0] != "s":
                continue
            ss = [self.ed.ses[s] for s in self.ed.obj(it)["sesiones"] if s in self.ed.ses]
            for s in ss:
                c[(s.materia, ", ".join([s.grupo] + s.otros_grupos), s.profesor)] += len(self.ed.posiciones(it))
        return (["Asignaciones:"] + [f"{m} · {g} · {p} · {n} p." for (m, g, p), n in sorted(c.items())]) if c else []

    # ------------------------------------------------------------- informes de lista
    def listado(self, tipo):
        ed = self.ed
        tb = Tabla(LISTADOS[tipo], "", [], [])
        if tipo == "asignaciones":
            tb.cols = ["Departamento", "Profesor", "Materia", "Grupo(s)", "Periodos"]
            c = Counter()
            for it in ed.items():
                if it[0] == "s":
                    for sid in ed.obj(it)["sesiones"]:
                        s = ed.ses.get(sid)
                        if s and s.profesor:
                            c[(self.depto(s.profesor), s.profesor, s.materia, ", ".join([s.grupo] + s.otros_grupos))] += len(ed.posiciones(it))
            tb.datos = [list(k) + [str(v)] for k, v in sorted(c.items())]
        elif tipo == "equipos":
            tb.cols = ["Grupo", "Materia", "Profesor"]
            vis = set()
            for it in ed.items():
                if it[0] == "s":
                    for sid in ed.obj(it)["sesiones"]:
                        s = ed.ses.get(sid)
                        if s:
                            for g in [s.grupo] + s.otros_grupos:
                                vis.add((g, s.materia, s.profesor or ""))
            tb.datos = [list(x) for x in sorted(vis)]
        elif tipo in ("tutores_alumnos", "tutores_tutor"):
            tb.cols = ["Grupo", "Tutor/a"] if tipo == "tutores_alumnos" else ["Tutor/a", "Grupo"]
            pares = [(g.nombre, g.datos.get("profesorTutor") or "") for g in self.p.grupos]
            tb.datos = [list(x) for x in sorted(pares)] if tipo == "tutores_alumnos" else [[b, a] for a, b in sorted(pares, key=lambda x: (x[1], x[0]))]
        elif tipo == "resumen_horas":
            tb.cols = ["Departamento", "Profesor", "Lectivas", "Complem.", "Guardias", "G. recreo", "Reuniones", "Total periodos", "Total horas"]
            for e in sorted(self.p.profesores, key=lambda e: (self.depto(e.nombre).lower(), e.nombre)):
                its = ed.items_de("Profesorado", e.nombre); v = defaultdict(int); mins = 0
                for it in its:
                    k = it[0]
                    c = {"s": "l", "c": "c", "r": "r"}.get(k) or ("gr" if self._es_recreo(it) else "g")
                    v[c] += len(ed.posiciones(it)); mins += self._duracion(it)
                tb.datos.append([self.depto(e.nombre), e.nombre, str(v["l"]), str(v["c"]), str(v["g"]), str(v["gr"]), str(v["r"]),
                                 str(sum(v.values())), _hm(mins)])
        elif tipo == "estadistica_guardias":
            servs = ed.elementos("Guardias")
            tb.cols = ["Profesor"] + servs + ["Recreo", "Total"]
            cnt = defaultdict(Counter)
            for it in ed.items():
                if it[0] == "g":
                    g = ed.obj(it)
                    cnt[g["profesor"]]["Recreo" if self._es_recreo(it) else g["servicio"]] += 1
            for prof in sorted(cnt):
                tb.datos.append([prof] + [str(cnt[prof][s]) for s in servs] + [str(cnt[prof]["Recreo"]), str(sum(cnt[prof].values()))])
        return tb


    # ------------------------------------------------------------- nuevos informes de lista
    def _sesiones_colocadas(self):
        """[(item, sesión, marco, día, [tramos])] de las sesiones lectivas colocadas."""
        out = []
        for it in self.ed.items():
            if it[0] != "s":
                continue
            o = self.ed.obj(it)
            for sid in o["sesiones"]:
                s = self.ed.ses.get(sid)
                if s:
                    out.append((it, s, o["marco"], o["dia"], list(o["tramos"])))
        return out

    def _franja(self, m, d, tramos):
        ts = [self.ed.tramos.get((m, d, t)) for t in tramos]
        ts = [t for t in ts if t is not None]
        return (f"{ts[0].entrada}-{ts[-1].salida}", _min(ts[0].entrada)) if ts else ("", 0)

    def _minutos(self, it):
        return self._duracion(it)

    def firmas(self, por):
        """Un impreso por cada día y cada aula / grupo / profesor para recoger las firmas (33033/33034/33072)."""
        dias = self.o["letreros"]["dias"] + DIAS5[5:]
        filas = defaultdict(list)
        for it, s, m, d, tramos in self._sesiones_colocadas():
            hora, orden = self._franja(m, d, tramos)
            aulas = self.ed.obj(it).get("aulas", []) or [""]
            grupos = ", ".join(self._nom("alumnos", g) for g in [s.grupo] + s.otros_grupos if g)
            claves = {"aula": [a for a in aulas if a], "alumnos": [g for g in [s.grupo] + s.otros_grupos if g],
                      "profesor": [s.profesor] if s.profesor else []}[por]
            for k in claves:
                filas[(k, d)].append((orden, hora, self._nom("materias", s.materia), grupos,
                                      self._nom("profesores", s.profesor), "\\".join(a for a in aulas if a)))
        # guardias y reuniones también se firman: se identifican en la columna de materia («GUARDIA …» / «REUNIÓN …»)
        tipo_rec = {"aula": "aula", "alumnos": "grupo", "profesor": "profesor"}[por]
        for it in self.ed.items():
            if it[0] not in "gr":
                continue
            o = self.ed.obj(it)
            tramos = [o["tramo"]] if it[0] == "g" else list(o["tramos"])
            hora, orden = self._franja(o["marco"], o["dia"], tramos)
            if it[0] == "g":
                que = f"GUARDIA {o.get('servicio', '')}".strip(); quien = [o["profesor"]]
            else:
                nombre = o.get("reunion") or o.get("nombre") or ""; que = f"REUNIÓN {nombre}".strip()
                quien = sorted(self.ed.integrantes_reunion(nombre))
            for tp, k in self.ed.recursos(it):
                if tp != tipo_rec:
                    continue
                prof = self._nom("profesores", k) if tp == "profesor" else ", ".join(self._nom("profesores", q) for q in quien)
                filas[(k, o["dia"])].append((orden, hora, que, "", prof, ""))
        titulo = {"aula": "Hoja de firmas por aula", "alumnos": "Hoja de firmas por grupo de alumnos",
                  "profesor": "Hoja de firmas por profesor"}[por]
        cat = {"aula": "aulas", "alumnos": "alumnos", "profesor": "profesores"}[por]
        out = []
        for (k, d) in sorted(filas, key=lambda x: (x[0].lower(), x[1])):
            tb = Tabla(titulo, f"{self._nom(cat, k)} – {dias[d] if d < len(dias) else d}", [], [])
            if por == "profesor":
                tb.cols = ["Hora", "Materia", "Grupo(s)", "Aula", "Firma"]
                tb.datos = [[h, mt, g, a, ""] for _o, h, mt, g, p, a in sorted(set(filas[(k, d)]))]
                tb.anchos = [12, 22, 22, 12, 32]
            else:
                tb.cols = ["Hora", "Materia", "Grupo(s)" if por == "aula" else "Aula", "Profesor/a", "Firma"]
                tb.datos = [[h, mt, g if por == "aula" else a, p, ""] for _o, h, mt, g, p, a in sorted(set(filas[(k, d)]))]
                tb.anchos = [12, 22, 18, 22, 26]
            tb.alto_fila = 11.0; tb.rejilla_lista = True
            out.append(tb)
        return out

    def ausencias(self):
        """Impreso por día para anotar ausencias y sustituciones (33004), con el profesorado de guardia de cada hora."""
        dias = self.o["letreros"]["dias"] + DIAS5[5:]
        m = next(iter(self.p.marcos)); marco = self.p.marcos[m]
        guardia = defaultdict(list)
        for it in self.ed.items():
            if it[0] == "g":
                g = self.ed.obj(it)
                if g["marco"] == m:
                    guardia[(g["dia"], g["tramo"])].append(self._nom("profesores", g["profesor"]))
        out = []
        for d in range(len(marco.dias)):
            tb = Tabla("Hoja para anotar ausencias y sustituciones", dias[d] if d < len(dias) else str(d), [], [])
            tb.cols = ["Hora", "Profesorado de guardia", "Profesor/a ausente", "Grupo", "Aula", "Sustituye", "Firma"]
            tb.anchos = [11, 30, 20, 10, 9, 20, 14]
            for t in marco.filas():
                if t.tipo != "lectivo":
                    continue
                tb.datos.append([f"{t.entrada}-{t.salida}", ", ".join(sorted(guardia.get((d, t.indice), []))), "", "", "", "", ""])
            tb.alto_fila = 10.0; tb.rejilla_lista = True
            out.append(tb)
        return out

    def equipos_curso(self):
        """Profesores de cada curso con su minutaje semanal (33049)."""
        curso = {g.nombre: (g.datos.get("cursoPerteneciente") or "") for g in self.p.grupos}
        c = defaultdict(int); grupos = defaultdict(set)
        for it, s, m, d, tramos in self._sesiones_colocadas():
            mins = sum(_min(t.salida) - _min(t.entrada) for t in (self.ed.tramos.get((m, d, x)) for x in tramos) if t)
            for cu in dict.fromkeys(curso.get(g, "") for g in [s.grupo] + s.otros_grupos if g):
                k = (cu or "(sin curso)", self.depto(s.profesor), s.profesor or "(sin profesor)", s.materia)
                c[k] += mins; grupos[k] |= {g for g in [s.grupo] + s.otros_grupos if g and curso.get(g, "") == cu}
        tb = Tabla(LISTADOS["equipos_curso"], "", [], [])
        tb.cols = ["Curso", "Departamento", "Profesor", "Materia", "Grupos", "Minutos/semana", "Horas"]
        tb.datos = [[cu, dp, self._nom("profesores", p), self._nom("materias", mt), ", ".join(sorted(grupos[k])), str(v), _hm(v)]
                    for k, v in sorted(c.items()) for (cu, dp, p, mt) in [k]]
        return tb

    def alumnos_subgrupos(self):
        """Alumnos individuales o subgrupos en cada grupo (33075): nº de alumnos, grupos incluidos y desdobles."""
        tb = Tabla(LISTADOS["alumnos_subgrupos"], "", [], [])
        tb.cols = ["Grupo", "Curso", "Nº alumnos", "Grupos incluidos / subgrupos", "Comparte sesiones con"]
        comparte = defaultdict(set)
        for s in self.ed.ses.values():
            gs = [g for g in [s.grupo] + s.otros_grupos if g]
            for g in gs:
                comparte[g] |= set(gs) - {g}
        for g in self.p.grupos:
            x = g.datos.get("_xml")
            inc = [(z.text or "").strip() for z in x.iter("grupoIncluido")] if x is not None else []
            if x is not None and not inc:
                gi = x.find("gruposIncluidos")
                inc = [(z.text or "").strip() for z in gi] if gi is not None else []
            tb.datos.append([self._nom("alumnos", g.nombre), g.datos.get("cursoPerteneciente") or "",
                             str(g.datos.get("numeroAlumnos") or ""), ", ".join(i for i in inc if i),
                             ", ".join(sorted(comparte.get(g.nombre, ())))])
        return tb

    def preferencias(self):
        """Preferencias cumplidas e incumplidas de cada profesor (32982), según su plantilla."""
        tb = Tabla(LISTADOS["preferencias"], "", [], [])
        tb.cols = ["Profesor", "Periodos ocupados", "En preferentes", "En indiferentes", "En no preferentes",
                   "En no pref. (mayor peso)", "En prohibidas", "Cumplidas", "Incumplidas", "% cumplido"]
        for e in sorted(self.p.profesores, key=lambda e: e.nombre.lower()):
            c = Counter()
            for it in self.ed.items_de("Profesorado", e.nombre):
                for pos in self.ed.posiciones(it):
                    c[e.plantilla.get(pos, INDIFERENTE)] += 1
            tot = sum(c.values())
            if not tot:
                continue
            inc = c[NO_PREF1] + c[NO_PREF2] + c[PROHIBIDO]
            tb.datos.append([e.nombre, str(tot), str(c[PREFERENTE]), str(c[INDIFERENTE]), str(c[NO_PREF1]), str(c[NO_PREF2]),
                             str(c[PROHIBIDO]), str(tot - inc), str(inc), f"{100 * (tot - inc) / tot:.0f} %"])
        return tb

    def completo(self, tipo, nombres=None):
        """«Todo el horario en una sola tabla»: una fila por elemento y una columna por día y periodo lectivo."""
        vista = TIPOS[tipo][1]; ed = self.ed
        cat = {"Grupos": "alumnos", "Profesorado": "profesores", "Aulas": "aulas"}[vista]
        els = nombres or ed.elementos(vista)
        dias = self.o["letreros"]["dias"] + DIAS5[5:]
        out = []
        for m in self.p.marcos:
            marco = self.p.marcos[m]
            lect = [t for t in marco.filas() if t.tipo == "lectivo"]
            cols = [(d, n, t) for d in range(len(marco.dias)) for n, t in enumerate(lect, 1)]
            tb = Tabla("Horario completo: " + TIPOS[tipo][0], f"Marco {m}" if len(self.p.marcos) > 1 else "", [], [])
            tb.cols = [TIPOS[tipo][0]] + [f"{dias[d][:2]}{n}" for d, n, _t in cols]
            tb.anchos = [14] + [5] * len(cols); tb.rejilla_lista = True
            for nm in els:
                self._actual = nm
                cel = {}
                for it in ed.items_de(vista, nm):
                    for (mm, d, idx) in ed.posiciones(it):
                        if mm == m:
                            lin = self.lineas(it, vista)
                            corto = lin[1] if vista == "Profesorado" and len(lin) > 1 else (lin[0] if lin else "")
                            if it[0] == "s" and vista != "Profesorado":
                                corto = lin[0] if lin else ""
                            cel.setdefault((d, idx), corto)
                if cel:
                    tb.datos.append([self._nom(cat, nm)] + [cel.get((d, t.indice), "") for d, _n, t in cols])
            if tb.datos:
                out.append(tb)
        return out


MARCAS_PLANTILLA = {PROHIBIDO: ("#d0d0d0", "gris rayado = prohibido"), NO_PREF2: ("#f6d9c4", "salmón = no preferente (mayor peso)"),
                    NO_PREF1: ("#fbf0c8", "amarillo = no preferente"), PREFERENTE: ("#d9f2d9", "verde = preferente")}


def tablas_actual(ed, vista, nombre, opc):
    """Tablas de la vista actual del editor (Imprimir la tabla de ahora / Guardar la tabla de ahora en PDF)."""
    g = Generador(ed, opc)
    if vista == "Grupos":
        return g.tablas("alumnos", [nombre])
    if vista == "Profesorado":
        return g.tablas("individual" if opc.get("contadores") else "profesores", [nombre])
    if vista == "Aulas":
        return g.tablas("aulas", [nombre])
    if vista == "Guardias":
        return g.tablas("guardias", [nombre])
    if vista == "Reuniones":
        its = ed.items_de("Reuniones", nombre)
        return [g.rejilla("Horario semanal: REUNIÓN", nombre, its, "Reuniones", g._marcos(its))]
    its = ed.items_de(vista, nombre)
    return [g.rejilla(f"Horario semanal: {vista}", nombre, its, "Materias", g._marcos(its))]


def tablas_de(ed, tipo, opc, nombres=None):
    g = Generador(ed, opc)
    if tipo in LISTADOS:
        especiales = {"firmas_aula": lambda: g.firmas("aula"), "firmas_alumnos": lambda: g.firmas("alumnos"),
                      "firmas_profesor": lambda: g.firmas("profesor"), "ausencias": g.ausencias,
                      "equipos_curso": lambda: [g.equipos_curso()], "alumnos_subgrupos": lambda: [g.alumnos_subgrupos()],
                      "preferencias": lambda: [g.preferencias()]}
        return especiales[tipo]() if tipo in especiales else [g.listado(tipo)]
    if opc.get("presentacion") == "completo" and tipo in ("alumnos", "profesores", "aulas", "individual"):
        return g.completo("profesores" if tipo == "individual" else tipo, nombres)
    return g.tablas(tipo, nombres)


# ====================================================================== dibujo
MM = 10.0     # unidades lógicas por mm (trabajamos en décimas de milímetro)


def _pt(p):
    return p * 25.4 / 72 * MM


class Pintor:
    """Dibuja tablas en páginas A4 apaisadas (o el tamaño del dispositivo)."""
    def __init__(self, opc):
        self.o = opc
        self.fam = {"Nimbus Sans": "Nimbus Sans", "Century Gothic": "URW Gothic"}.get(opc.get("fuente"), "DejaVu Sans")
        self.esc = {"pequeno": 0.85, "pequeño": 0.85, "normal": 1.0, "grande": 1.18}.get(opc.get("tam"), 1.0)

    def fuente(self, pt, negrita=False, cursiva=False):
        f = QFont(self.fam); f.setPixelSize(max(1, round(_pt(pt)))); f.setBold(negrita); f.setItalic(cursiva)
        return f

    def paginar(self, tablas):
        """Agrupa tablas por página (2 por página si se pide y caben)."""
        if self.o.get("varias_por_pagina"):
            pags, i = [], 0
            while i < len(tablas):
                a = tablas[i]
                if i + 1 < len(tablas) and not a.cols and not tablas[i + 1].cols and len(a.filas) <= 9 and len(tablas[i + 1].filas) <= 9 \
                        and not a.leyenda and not tablas[i + 1].leyenda and not a.resumen and not tablas[i + 1].resumen:
                    pags.append([a, tablas[i + 1]]); i += 2
                else:
                    pags.append([a]); i += 1
            return pags
        out = []
        for t in tablas:
            por_pag = max(4, int(28 * 5.5 / max(1.0, t.alto_fila))) if t.cols else 0
            if t.cols and len(t.datos) > por_pag:      # listados largos: trocear
                for k in range(0, len(t.datos), por_pag):
                    c = copy.copy(t); c.datos = t.datos[k:k + por_pag]; out.append([c])
            else:
                out.append([t])
        return out

    def render(self, dispositivo, tablas, desde=0):
        pags = self.paginar(tablas)
        if not pags:
            pags = [[Tabla("Sin datos", "No hay tablas que presentar con las opciones elegidas", [], [])]]
        p = QPainter(dispositivo)
        try:
            for n, pag in enumerate(pags):
                if n:
                    dispositivo.newPage()
                self._pagina(p, dispositivo, pag, n + 1, len(pags))
        finally:
            p.end()
        return len(pags)

    def _pagina(self, p, dev, tablas, n, total):
        if isinstance(dev, QPrinter):
            r = dev.pageLayout().paintRectPixels(dev.resolution())
        else:
            r = dev.pageLayout().paintRectPixels(dev.resolution())
        wmm = r.width() / dev.resolution() * 25.4; hmm = r.height() / dev.resolution() * 25.4
        W, H = wmm * MM, hmm * MM
        p.setViewport(0, 0, r.width(), r.height()); p.setWindow(0, 0, round(W), round(H))
        p.setRenderHint(QPainter.Antialiasing); p.setRenderHint(QPainter.TextAntialiasing)
        o = self.o
        p.fillRect(QRectF(0, 0, W, H), QColor(o.get("color_fondo", "#ffffff")))
        y = self._cabecera(p, W, tablas[0], n, total)
        pie = 8 * MM
        alto = (H - y - pie) / len(tablas)
        for k, tb in enumerate(tablas):
            caja = QRectF(0, y + k * alto, W, alto - (3 * MM if len(tablas) > 1 else 0))
            if tb.cols:
                self._lista(p, caja, tb)
            else:
                self._tabla(p, caja, tb, sub=len(tablas) > 1 or True)
        self._pie(p, W, H, n, total)

    def _cabecera(self, p, W, tb, n, total):
        o = self.o; y = 0
        p.setPen(QColor("#000000"))
        izq = []
        if o.get("cab_usuario") and o.get("centro"):
            izq.append(o["centro"])
        if o.get("cab_localidad") and o.get("localidad"):
            izq.append(o["localidad"])
        logo_w = 0
        if o.get("logo") and os.path.exists(o["logo"]):
            img = QImage(o["logo"])
            if not img.isNull():
                h = 14 * MM; w = h * img.width() / max(1, img.height()); logo_w = w + 3 * MM
                p.drawImage(QRectF(0, 0, w, h), img)
        p.setFont(self.fuente(10, True))
        for i, t in enumerate(izq[:2]):
            p.setFont(self.fuente(10 if i == 0 else 9, i == 0))
            p.drawText(QRectF(logo_w, i * 5 * MM, W * 0.38, 5 * MM), Qt.AlignLeft | Qt.AlignVCenter, t)
        if o.get("cab_titulo"):
            p.setFont(self.fuente(13, True))
            p.drawText(QRectF(W * 0.25, 0, W * 0.5, 7 * MM), Qt.AlignCenter, tb.titulo)
        der = []
        if o.get("curso"):
            der.append(o["curso"])
        if o.get("cab_semana"):
            der.append("Semana: horario semanal")
        p.setFont(self.fuente(8))
        for i, t in enumerate(der):
            p.drawText(QRectF(W * 0.7, i * 4.5 * MM, W * 0.3, 4.5 * MM), Qt.AlignRight | Qt.AlignVCenter, t)
        y = 13 * MM
        p.setPen(QPen(QColor("#1f8a8a"), 0.35 * MM)); p.drawLine(0, y - 2 * MM, W, y - 2 * MM)
        return y

    def _pie(self, p, W, H, n, total):
        o = self.o; y = H - 6 * MM
        p.setPen(QPen(QColor("#9a9a9a"), 0.2 * MM)); p.drawLine(0, y, W, y)
        p.setFont(self.fuente(7)); p.setPen(QColor("#666666"))
        if o.get("pie_marca"):
            p.drawText(QRectF(0, y, W / 3, 6 * MM), Qt.AlignLeft | Qt.AlignVCenter, MARCA)
        if o.get("mostrar_texto_pie") and o.get("texto_pie"):
            p.drawText(QRectF(W / 4, y, W / 2, 6 * MM), Qt.AlignCenter, o["texto_pie"].replace("\n", " "))
        der = []
        if o.get("pie_fecha"):
            der.append(datetime.now().strftime("%d/%m/%Y %H:%M"))
        if o.get("pie_pagina"):
            der.append(f"Página {n} de {total}")
        p.drawText(QRectF(W * 2 / 3, y, W / 3, 6 * MM), Qt.AlignRight | Qt.AlignVCenter, "    ".join(der))

    # ------------------------------------------------------------- rejilla
    def _tabla(self, p, caja, tb, sub=True):
        o = self.o; L = o["letreros"]
        x0, y0, W = caja.x(), caja.y(), caja.width()
        p.setPen(QColor(o.get("color_texto", "#000"))); p.setFont(self.fuente(12 * self.esc, True))
        p.drawText(QRectF(x0, y0, W, 7 * MM), Qt.AlignLeft | Qt.AlignVCenter, tb.subtitulo)
        y0 += 8 * MM
        extra = len(tb.leyenda) + (len(tb.resumen) + 1 if tb.resumen else 0)
        pie_alto = min(caja.height() * 0.38, extra * 4.2 * MM * self.esc) if extra else 0
        if pie_alto and pie_alto < extra * 4.2 * MM * self.esc:     # no cabe: dos columnas
            pie_alto = min(caja.height() * 0.38, (extra + 1) // 2 * 4.2 * MM * self.esc)
        alto = caja.y() + caja.height() - y0 - pie_alto - (2 * MM if pie_alto else 0)
        if not tb.filas:
            return
        regla = 0 if o["horas"] == "celda" else 16 * MM
        cab = 7 * MM
        ndias = max(1, len(tb.dias)); cw = (W - regla) / ndias
        pesos = [1.0 if t[2] == "lectivo" else 0.42 for t in tb.filas]
        unidad = (alto - cab) / sum(pesos)
        if not tb.lista:
            unidad = min(unidad, 30 * MM)
        lin = QPen(QColor(o.get("color_lineas", "#555")), 0.25 * MM)
        # cabecera de días
        p.setFont(self.fuente(9 * self.esc, True))
        for d, nd in enumerate(tb.dias):
            r = QRectF(x0 + regla + d * cw, y0, cw, cab)
            p.fillRect(r, QColor("#e3f1f1")); p.setPen(QColor("#155e5e")); p.drawText(r, Qt.AlignCenter, nd)
        y = y0 + cab; fy = []
        for i, (e, s, tp) in enumerate(tb.filas):
            h = pesos[i] * unidad; fy.append((y, h)); y += h
        bottom = y
        # filas
        for i, (e, s, tp) in enumerate(tb.filas):
            yy, h = fy[i]
            if tp != "lectivo":
                p.fillRect(QRectF(x0 + regla, yy, W - regla, h), QColor("#eaf6f6"))
            if regla:
                p.setPen(QColor("#155e5e")); p.setFont(self.fuente(7.5 * self.esc))
                txt = f"{e}\n{s}" if tp == "lectivo" else f"{e}-{s}"
                p.drawText(QRectF(x0, yy, regla - 1 * MM, h), Qt.AlignRight | Qt.AlignVCenter, txt)
            if tp != "lectivo" and o.get("letreros_recreo") and not any((i, d) in tb.celdas for d in range(ndias)):
                p.setPen(QColor("#6a9a9a")); p.setFont(self.fuente(7 * self.esc, False, True))
                p.drawText(QRectF(x0 + regla, yy, W - regla, h), Qt.AlignCenter,
                           "   ".join([L["recreo"]] * 1))
        # prohibiciones y preferencias del profesor (opción «Reflejar las prohibiciones y preferencias»)
        for (i, d), est in tb.marcas.items():
            if i >= len(fy) or d >= ndias or est not in MARCAS_PLANTILLA:
                continue
            yy, h = fy[i]; r = QRectF(x0 + regla + d * cw, yy, cw, h)
            p.fillRect(r, QColor(MARCAS_PLANTILLA[est][0]))
            if est == PROHIBIDO:
                p.fillRect(r, QBrush(QColor("#9a9a9a"), Qt.BDiagPattern))
        # celdas
        for (i, d), cels in tb.celdas.items():
            if i >= len(fy) or d >= ndias:
                continue
            yy, h = fy[i]; r = QRectF(x0 + regla + d * cw, yy, cw, h)
            self._celda(p, r, cels, tb, tb.filas[i])
        # líneas
        p.setPen(lin)
        if o.get("lineas_h", True):
            p.drawLine(x0 + regla, y0, x0 + W, y0)
            for yy, h in fy:
                p.drawLine(x0 + (0 if regla else 0) + regla, yy, x0 + W, yy)
            p.drawLine(x0 + regla, bottom, x0 + W, bottom)
        if o.get("lineas_v", True):
            for d in range(ndias + 1):
                xx = x0 + regla + d * cw; p.drawLine(xx, y0, xx, bottom)
        # leyenda y resumen
        y = bottom + 2 * MM
        lineas = []
        if tb.resumen:
            lineas.append(("Resumen de horas", True))
            lineas += [(f"{a}: {b}", False) for a, b in tb.resumen]
        lineas += [(t, i == 0 and t.endswith("Materias")) for i, t in enumerate(tb.leyenda)]
        if lineas:
            fh = 4.0 * MM * self.esc
            disponibles = max(1, int((caja.y() + caja.height() - y) // fh))
            ncol = 1 if len(lineas) <= disponibles else min(3, -(-len(lineas) // disponibles))
            colw = W / ncol
            for k, (t, neg) in enumerate(lineas[:disponibles * ncol]):
                c, f = divmod(k, disponibles)
                p.setFont(self.fuente(7.5 * self.esc, neg)); p.setPen(QColor("#000"))
                p.drawText(QRectF(x0 + c * colw, y + f * fh, colw - 2 * MM, fh), Qt.AlignLeft | Qt.AlignVCenter,
                           QFontMetricsF(p.font()).elidedText(t, Qt.ElideRight, colw - 2 * MM))

    def _celda(self, p, r, cels, tb, fila):
        o = self.o
        n = len(cels)
        sub_h = r.height() / n
        for k, c in enumerate(cels):
            rr = QRectF(r.x(), r.y() + k * sub_h, r.width(), sub_h)
            if c.color:
                col = QColor(c.color)
                p.fillRect(rr.adjusted(0.2 * MM, 0.2 * MM, -0.2 * MM, -0.2 * MM), col)
            lineas = list(c.lineas)
            if o["horas"] == "celda" and not tb.lista:
                lineas = [f"{fila[0]}-{fila[1]}"] + lineas
            if tb.lista:
                self._texto_lista(p, rr.adjusted(0.8 * MM, 0.6 * MM, -0.8 * MM, -0.6 * MM), lineas)
            else:
                self._texto(p, rr.adjusted(0.8 * MM, 0.4 * MM, -0.8 * MM, -0.4 * MM), lineas)

    def _texto(self, p, r, lineas):
        """Texto centrado; reduce la letra hasta que quepa y recorta lo que no cabe (como el original)."""
        if not lineas:
            return
        pt = 8.5 * self.esc
        while pt > 5:
            f = self.fuente(pt); fm = QFontMetricsF(f)
            if fm.lineSpacing() * len(lineas) <= r.height() and max(fm.horizontalAdvance(t) for t in lineas) <= r.width():
                break
            pt -= 0.5
        f = self.fuente(pt); fm = QFontMetricsF(f); p.setFont(f); p.setPen(QColor(self.o.get("color_texto", "#000")))
        cabe = max(1, int(r.height() // fm.lineSpacing())); lineas = lineas[:cabe]
        tot = fm.lineSpacing() * len(lineas)
        y = r.y() + ((r.height() - tot) / 2 if self.o.get("centrar", True) else 0)
        for i, t in enumerate(lineas):
            f.setBold(i == 0); p.setFont(f)
            p.drawText(QRectF(r.x(), y + i * fm.lineSpacing(), r.width(), fm.lineSpacing()), Qt.AlignCenter,
                       QFontMetricsF(f).elidedText(t, Qt.ElideRight, r.width()))

    def _texto_lista(self, p, r, nombres):
        """Lista de nombres en columnas (profesores/aulas libres, guardias)."""
        if not nombres:
            return
        pt = 7.5 * self.esc
        while True:
            f = self.fuente(pt); fm = QFontMetricsF(f); lh = fm.lineSpacing()
            filas = max(1, int(r.height() // lh)); ncol = -(-len(nombres) // filas)
            ancho = max(fm.horizontalAdvance(t) for t in nombres) + 1.5 * MM
            if ncol * ancho <= r.width() or pt <= 4.5:
                break
            pt -= 0.5
        p.setFont(f); p.setPen(QColor(self.o.get("color_texto", "#000")))
        colw = r.width() / max(1, ncol)
        for k, t in enumerate(nombres):
            c, fi = divmod(k, filas)
            p.drawText(QRectF(r.x() + c * colw, r.y() + fi * lh, colw, lh), Qt.AlignLeft | Qt.AlignVCenter,
                       fm.elidedText(t, Qt.ElideRight, colw))

    # ------------------------------------------------------------- listados
    def _lista(self, p, caja, tb):
        x0, y0, W = caja.x(), caja.y(), caja.width()
        if tb.subtitulo:
            p.setPen(QColor(self.o.get("color_texto", "#000"))); p.setFont(self.fuente(12 * self.esc, True))
            p.drawText(QRectF(x0, y0, W, 7 * MM), Qt.AlignLeft | Qt.AlignVCenter, tb.subtitulo)
            y0 += 8 * MM
        cab_h = 5.5 * MM
        fh = tb.alto_fila * MM
        ncol = len(tb.cols)
        if ncol > 20:      # horario completo: letra más pequeña
            fh = min(fh, max(3.6 * MM, (caja.y() + caja.height() - y0 - cab_h) / max(1, len(tb.datos))))
        anchos = list(tb.anchos) if len(tb.anchos) == ncol else []
        for c in range(ncol if not anchos else 0):
            m = max([len(tb.cols[c])] + [len(r[c]) for r in tb.datos] or [4])
            anchos.append(max(6, min(40, m)))
        tot = sum(anchos); xs = [x0]
        for a in anchos:
            xs.append(xs[-1] + W * a / tot)
        pt_cab, pt = (8.5, 8) if ncol <= 20 else (6, 5.5)
        p.setFont(self.fuente(pt_cab * self.esc, True))
        p.fillRect(QRectF(x0, y0, W, cab_h), QColor("#e3f1f1"))
        for c, t in enumerate(tb.cols):
            p.setPen(QColor("#155e5e"))
            p.drawText(QRectF(xs[c] + 0.5 * MM, y0, xs[c + 1] - xs[c] - 1 * MM, cab_h),
                       (Qt.AlignCenter if ncol > 20 and c else Qt.AlignLeft) | Qt.AlignVCenter, t)
        p.setFont(self.fuente(pt * self.esc)); p.setPen(QColor("#000"))
        fm = QFontMetricsF(p.font())
        for i, fila in enumerate(tb.datos):
            y = y0 + cab_h + i * fh
            if i % 2 and not tb.rejilla_lista:
                p.fillRect(QRectF(x0, y, W, fh), QColor("#f6f6f6"))
            for c, t in enumerate(fila):
                al = (Qt.AlignCenter if ncol > 20 and c else Qt.AlignLeft) | Qt.AlignVCenter
                p.drawText(QRectF(xs[c] + 0.5 * MM, y, xs[c + 1] - xs[c] - 1 * MM, fh), al,
                           fm.elidedText(t, Qt.ElideRight, xs[c + 1] - xs[c] - 1 * MM))
        fondo = y0 + cab_h + len(tb.datos) * fh
        p.setPen(QPen(QColor("#999"), 0.2 * MM)); p.drawLine(x0, fondo, x0 + W, fondo)
        if tb.rejilla_lista:
            p.setPen(QPen(QColor("#777"), 0.2 * MM))
            for i in range(len(tb.datos) + 1):
                p.drawLine(x0, y0 + cab_h + i * fh, x0 + W, y0 + cab_h + i * fh)
            p.drawLine(x0, y0, x0 + W, y0)
            for xx in xs:
                p.drawLine(xx, y0, xx, fondo)


# ====================================================================== salida
def impresora_pdf(ruta, alta=True):
    pr = QPrinter(QPrinter.HighResolution if alta else QPrinter.ScreenResolution)
    pr.setOutputFormat(QPrinter.PdfFormat); pr.setOutputFileName(ruta)
    configurar_pagina(pr)
    pr.setCreator(MARCA); pr.setDocName(os.path.splitext(os.path.basename(ruta))[0])
    return pr


def configurar_pagina(pr):
    pr.setPageLayout(QPageLayout(QPageSize(QPageSize.A4), QPageLayout.Landscape, QMarginsF(10, 10, 10, 10), QPageLayout.Millimeter))


def _seguro(nombre):
    return re.sub(r"[^\w\-. ]+", "_", nombre).strip() or "tabla"


def exportar_pdf(tablas, ruta, opc, evitar=()):
    """Un solo PDF. Nunca sobrescribe los archivos de `evitar` (originales)."""
    if os.path.abspath(ruta) in {os.path.abspath(x) for x in evitar}:
        raise ValueError("No se sobrescribe un archivo original.")
    pr = impresora_pdf(ruta)
    return Pintor(opc).render(pr, tablas)


def exportar_distintos(tablas, carpeta, opc):
    """Un PDF por tabla y un índice HTML."""
    os.makedirs(carpeta, exist_ok=True)
    filas = []
    usados = Counter()
    for tb in tablas:
        base = _seguro(tb.subtitulo or tb.titulo); usados[base] += 1
        if usados[base] > 1:
            base += f"_{usados[base]}"
        nombre = base + ".pdf"
        exportar_pdf([tb], os.path.join(carpeta, nombre), opc)
        filas.append(f'<li><a href="{html.escape(nombre)}">{html.escape(tb.subtitulo or tb.titulo)}</a></li>')
    titulo = html.escape(tablas[0].titulo if tablas else "Horarios")
    with open(os.path.join(carpeta, "index.html"), "w", encoding="utf-8") as f:
        f.write(f"<!DOCTYPE html><html lang='es'><meta charset='utf-8'><title>{titulo}</title>"
                f"<body style='font-family:sans-serif'><h1>{titulo}</h1><ul>{''.join(filas)}</ul>"
                f"<p style='color:#888;font-size:small'>{html.escape(MARCA)}</p></body></html>")
    return len(filas)


def exportar_asignaciones_html(ed, carpeta, opc):
    """33080 «Páginas HTML con índice»: un índice y una página por profesor con sus asignaciones y minutaje semanal.
    Escribe solo dentro de `carpeta` (archivos propios: index.html y asignaciones_*.html)."""
    g = Generador(ed, opc)
    os.makedirs(carpeta, exist_ok=True)
    por = defaultdict(lambda: defaultdict(int))
    for it, s, m, d, tramos in g._sesiones_colocadas():
        if not s.profesor:
            continue
        mins = sum(_min(t.salida) - _min(t.entrada) for t in (ed.tramos.get((m, d, x)) for x in tramos) if t)
        por[s.profesor][(s.materia, ", ".join(x for x in [s.grupo] + s.otros_grupos if x))] += mins
    estilo = ("<style>body{font-family:sans-serif;margin:2em}table{border-collapse:collapse}"
              "td,th{border:1px solid #bbb;padding:3px 8px}th{background:#e3f1f1;color:#155e5e}"
              "td.n{text-align:right}.m{color:#888;font-size:small}</style>")
    usados = Counter(); filas = []
    for prof in sorted(por, key=lambda x: (g.depto(x).lower(), x.lower())):
        base = "asignaciones_" + _seguro(prof); usados[base] += 1
        if usados[base] > 1:
            base += f"_{usados[base]}"
        tot = sum(por[prof].values())
        cuerpo = "".join(f"<tr><td>{html.escape(g._nom('materias', mt))}</td><td>{html.escape(gr)}</td>"
                         f"<td class=n>{v}</td><td class=n>{_hm(v)}</td></tr>" for (mt, gr), v in sorted(por[prof].items()))
        nombre = html.escape(g._nom("profesores", prof)); dep = html.escape(g.depto(prof))
        with open(os.path.join(carpeta, base + ".html"), "w", encoding="utf-8") as f:
            f.write(f"<!DOCTYPE html><html lang='es'><meta charset='utf-8'><title>{nombre}</title>{estilo}<body>"
                    f"<p><a href='index.html'>&larr; Índice</a></p><h1>{nombre}</h1><p>{dep}</p>"
                    f"<table><tr><th>Materia</th><th>Grupo(s)</th><th>Minutos/semana</th><th>Horas</th></tr>{cuerpo}"
                    f"<tr><th colspan=2>Total</th><th class=n>{tot}</th><th class=n>{_hm(tot)}</th></tr></table>"
                    f"<p class=m>{html.escape(MARCA)}</p></body></html>")
        filas.append(f"<tr><td>{dep}</td><td><a href='{html.escape(base)}.html'>{nombre}</a></td>"
                     f"<td class=n>{tot}</td><td class=n>{_hm(tot)}</td></tr>")
    titulo = html.escape(LISTADOS["asignaciones"])
    with open(os.path.join(carpeta, "index.html"), "w", encoding="utf-8") as f:
        f.write(f"<!DOCTYPE html><html lang='es'><meta charset='utf-8'><title>{titulo}</title>{estilo}<body>"
                f"<h1>{titulo}</h1><p>{html.escape(opc.get('centro') or '')}</p>"
                f"<table><tr><th>Departamento</th><th>Profesor</th><th>Minutos/semana</th><th>Horas</th></tr>{''.join(filas)}</table>"
                f"<p class=m>{html.escape(MARCA)}</p></body></html>")
    return len(filas)
