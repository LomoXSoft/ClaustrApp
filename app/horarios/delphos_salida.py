"""Exportación del horario a DELPHOS (Horario.xml). *** FORMATO SIN CONFIRMAR ***

No hay ninguna muestra real de la salida (delphos_spec.md §10). Se implementa la MEJOR HIPÓTESIS documentada:
el envoltorio de la entrada (§9.1) con la plantilla CONS_TRAMOS_HORARIOS:

    SERVICIO(siscliente, fecha, sisservidor, nomservicio)/ENTRADAS(C_ANNO, F_INICIO, F_FIN)?/SALIDAS/
      ERROR(CN_ERROR=0, TE_ERROR)/listasal seq=EMP(REGISTROS_RECUPERADOS)/listasal seq=EMP_i(X_EMPLEADO, F_TOMAPOS,
      listasal seq=TRAMO(REGISTROS_RECUPERADOS)/listasal seq=TRAMO_j(X_ACTIVIDAD, N_DIASEMANA, X_TRAMO, N_HORINI,
      N_HORFIN, X_DEPCENTRO, X_MATERIAOMC, X_UNIDAD))

Decisiones hipotéticas, todas configurables en Opciones (marcadas «SIN CONFIRMAR» en la documentación):
- horas en H:MM (como INTERVALOS de la entrada) o en minutos desde las 00:00;
- N_DIASEMANA según «Claves de los días» (otros/claveXDias; por defecto 1..5);
- un TRAMO por periodo y por grupo (sesión de dos periodos o con varios grupos -> varios TRAMO);
- guardias y otras tareas: X_ACTIVIDAD con la clave de la tarea, sin materia ni unidad;
- las fechas del curso (paso 7/7) van en ENTRADAS; codificación ISO-8859-1.
"""
from __future__ import annotations
import datetime, os
from dataclasses import dataclass, field
from xml.sax.saxutils import escape

SIN_CONFIRMAR = "Formato de salida a DELPHOS SIN CONFIRMAR (no se dispone de ningún Horario.xml real)."
DIAS = ("lunes", "martes", "miercoles", "jueves", "viernes", "sabado")
VERDE, AMBAR, ROJO = "verde", "ámbar", "rojo"


@dataclass
class Opciones:
    usar_clave: bool = True             # 1006 clave externa (si no, 1005 identificativo)
    guardias_recreo: bool = True        # 144/1016
    tarea_del_servicio: bool = True     # 144/1017
    horas: str = "hhmm"                 # "hhmm" | "minutos"
    dias: dict = field(default_factory=dict)         # 361: {0: "1", ...}
    profesores: set | None = None       # 425: None = todos
    anno: str = ""; inicio: str = ""; fin: str = ""  # 205
    subgrupos_con_grupo: bool = False   # 211/1017 (sin efecto: no hay subgrupos en el formato)


@dataclass
class Mensaje:
    nivel: str          # rojo / ámbar
    lista: str          # profesores, materias, ...
    nombre: str
    texto: str


def _clave(e):
    return (e.findtext("claveDeExportacion") or "").strip() if e is not None else ""


class Transferencia:
    """Reúne lo que se transfiere desde el editor (`ed`: editor_modelo.Editor)."""

    def __init__(self, ed, catalogo: dict | None = None):
        self.ed, self.p = ed, ed.p
        self.catalogo = catalogo or {}
        raiz = self.p.doc.raiz
        idx = lambda lista, tag: {(x.findtext("nombre") or "").strip(): x for x in (raiz.find(lista) or [])
                                  if x.tag == tag}
        self.x = {"profesores": idx("profesores", "profesor"), "grupos": idx("grupos", "grupo"),
                  "materias": idx("materias", "materia"), "aulas": idx("aulas", "aula"), "tareas": idx("tareas", "tarea")}
        self.cursos = {(c.findtext("nombre") or "").strip(): {(m.text or "").strip() for m in c.iter("materia")}
                       for c in (raiz.find("cursos") or [])}
        o = raiz.find("otros/claveXDias")
        self.dias_xml = {i: ((o.findtext(d) if o is not None else "") or "").strip() for i, d in enumerate(DIAS)}
        self.guardia_def = (raiz.findtext("tareas/guardiaPorDefecto") or "").strip()

    # ---------------------------------------------------------------- claves
    def clave(self, lista, nombre, op: Opciones):
        if not nombre:
            return ""
        return _clave(self.x[lista].get(nombre)) if op.usar_clave else nombre

    def dia(self, d, op):
        return op.dias.get(d) or self.dias_xml.get(d) or str(d + 1)

    # ---------------------------------------------------------------- recogida
    def filas(self, op: Opciones):
        """[(profesor, dict TRAMO)] en el orden del horario (profesor, día, hora)."""
        ed, out = self.ed, []
        T = ed.tramos

        def tramo(m, d, i):
            t = T.get((m, d, i))
            return t

        def hora(h):
            h = (h or "")[:5]
            if op.horas == "minutos" and ":" in h:
                a, b = h.split(":"); return str(int(a) * 60 + int(b))
            return h.lstrip("0") if h[:1] == "0" and len(h) == 5 else h

        def fila(prof, act, m, d, i, aula="", mat="", grupo="", tarea=""):
            t = tramo(m, d, i)
            if t is None:
                return
            out.append((prof, {"X_ACTIVIDAD": act, "N_DIASEMANA": self.dia(d, op), "X_TRAMO": t.clave or "",
                               "N_HORINI": hora(t.entrada), "N_HORFIN": hora(t.salida),
                               "X_DEPCENTRO": self.clave("aulas", aula, op), "X_MATERIAOMC": self.clave("materias", mat, op),
                               "X_UNIDAD": self.clave("grupos", grupo, op), "_dia": d, "_i": i, "_recreo": t.tipo == "recreo",
                               "_tarea": tarea}))

        doc = ed.doc
        for pz in doc.get("sesiones", []):
            for k, sid in enumerate(pz["sesiones"]):
                s = ed.ses.get(sid)
                if s is None or not s.profesor:
                    continue
                aula = (pz.get("aulas") or [""] * len(pz["sesiones"]))[k] if k < len(pz.get("aulas") or []) else ""
                grupos = [s.grupo] + [g for g in s.otros_grupos if g and g != s.grupo]
                act = self.clave("tareas", s.tarea, op)
                for i in pz["tramos"]:
                    for g in grupos:
                        fila(s.profesor, act, pz["marco"], pz["dia"], i, aula, s.materia, g, s.tarea)
        for g in doc.get("guardias", []):
            gx = ed.gua_xml.get(g["servicio"])
            t = tramo(g["marco"], g["dia"], g["tramo"])
            recreo = (t is not None and t.tipo == "recreo") or (gx is not None and (gx.findtext("enRecreos") or "") == "true")
            if recreo and not op.guardias_recreo:
                continue
            tarea = ((gx.findtext("tipoDeTarea") if gx is not None else "") or "").strip()
            if recreo and not op.tarea_del_servicio:
                tarea = self.guardia_def
            tarea = tarea or self.guardia_def
            fila(g["profesor"], self.clave("tareas", tarea, op), g["marco"], g["dia"], g["tramo"], tarea=tarea)
        for ri, r in enumerate(doc.get("reuniones", [])):
            tarea = ed.tarea_de(f"r:{ri}")
            for prof in ed.integrantes_reunion(r["reunion"]):
                for i in r["tramos"]:
                    fila(prof, self.clave("tareas", tarea, op), r["marco"], r["dia"], i, tarea=tarea)
        for c in doc.get("complementarias", []):
            fila(c["profesor"], self.clave("tareas", c.get("tarea", ""), op), c["marco"], c["dia"], c["tramo"],
                 tarea=c.get("tarea", ""))
        if op.profesores is not None:
            out = [f for f in out if f[0] in op.profesores]
        out.sort(key=lambda f: (f[0], f[1]["_dia"], f[1]["_i"]))
        return out

    def profesores(self, op=None):
        """425: [(nombre, clave, toma de posesión, nº de tramos)] de los profesores con algo asignado."""
        op = op or Opciones()
        cuenta = {}
        for prof, _f in self.filas(Opciones(**{**op.__dict__, "profesores": None})):
            cuenta[prof] = cuenta.get(prof, 0) + 1
        return [(n, self.clave("profesores", n, Opciones()), (self.x["profesores"].get(n).findtext("tomaDePosesion")
                 if self.x["profesores"].get(n) is not None else "") or "", c) for n, c in sorted(cuenta.items())]

    # ---------------------------------------------------------------- semáforo (749 y 689)
    def comprobar(self, op: Opciones):
        """Mensajes de precaución. Rojo: falta un dato que DELPHOS necesita. Ámbar: la clave no está en el catálogo
        cargado (si lo hay) o una incoherencia que conviene revisar. Devuelve (semáforo, [Mensaje])."""
        ms, vistos = [], set()

        def m(nivel, lista, nombre, texto):
            if (lista, nombre, texto) not in vistos:
                vistos.add((lista, nombre, texto)); ms.append(Mensaje(nivel, lista, nombre, texto))

        cat = {l: {k for k, _ in v} for l, v in self.catalogo.items()}
        filas = self.filas(op)
        usados = {"profesores": set(), "grupos": set(), "materias": set(), "aulas": set(), "tareas": set()}
        ed = self.ed
        for pz in ed.doc.get("sesiones", []):
            for k, sid in enumerate(pz["sesiones"]):
                s = ed.ses.get(sid)
                if s is None:
                    continue
                if not s.profesor:
                    m(AMBAR, "sesiones", f"{s.materia} {s.grupo}", "sesión sin profesor: no se transfiere"); continue
                if op.profesores is not None and s.profesor not in op.profesores:
                    continue
                usados["profesores"].add(s.profesor); usados["materias"].add(s.materia); usados["grupos"].add(s.grupo)
                usados["tareas"].add(s.tarea)
                for a in pz.get("aulas") or []:
                    if a:
                        usados["aulas"].add(a)
                gx = self.x["grupos"].get(s.grupo)
                cu = (gx.findtext("cursoPerteneciente") or "").strip() if gx is not None else ""
                if cu and cu in self.cursos and self.cursos[cu] and s.materia not in self.cursos[cu]:
                    m(AMBAR, "materias", s.materia, f"no figura entre las materias del curso {cu} del grupo {s.grupo}")
        for prof, f in filas:
            usados["profesores"].add(prof)
        if op.usar_clave:
            for lista, noms in usados.items():
                for n in sorted(x for x in noms if x):
                    k = self.clave(lista, n, op)
                    if not k:
                        m(ROJO, lista, n, "sin clave externa")
                    elif cat.get(lista) and k not in cat[lista]:
                        m(AMBAR, lista, n, f"la clave {k} no está entre las claves cargadas de DELPHOS")
            for n in sorted(usados["profesores"]):
                x = self.x["profesores"].get(n)
                if x is None or not (x.findtext("tomaDePosesion") or "").strip():
                    m(ROJO, "profesores", n, "sin fecha de toma de posesión (F_TOMAPOS)")
        for prof, f in filas:
            if not f["X_TRAMO"]:
                m(ROJO, "periodos", f"{f['N_DIASEMANA']} {f['N_HORINI']}", "periodo sin clave")
            elif cat.get("tramos") and f["X_TRAMO"] not in cat["tramos"]:
                m(AMBAR, "periodos", f["X_TRAMO"], "la clave del periodo no está entre las cargadas")
            if not f["X_ACTIVIDAD"] and op.usar_clave:
                t = f["_tarea"]
                m(ROJO, "tareas", t, "sin clave externa" if t in self.x["tareas"] else "la tarea no está en la lista de tareas")
        if not op.anno:
            m(AMBAR, "curso", "", "falta el año de inicio del curso (paso 7/7)")
        sem = ROJO if any(x.nivel == ROJO for x in ms) else AMBAR if ms else VERDE
        return sem, ms

    # ---------------------------------------------------------------- escritura
    def xml(self, op: Opciones, ahora=None) -> bytes:
        ahora = ahora or datetime.datetime.now()
        filas = self.filas(op)
        por_prof = {}
        for prof, f in filas:
            por_prof.setdefault(prof, []).append(f)
        e = lambda v: escape(str(v or ""))
        L = ['<?xml version="1.0" encoding="iso-8859-1"?>',
             f'<SERVICIO siscliente="GHC" fecha="{ahora:%d/%m/%Y %H:%M:%S}" sisservidor="DELPHOS" '
             f'nomservicio="CONS_TRAMOS_HORARIOS">',
             "<ENTRADAS>"]
        for k, v in (("C_ANNO", op.anno), ("F_INICIO", op.inicio), ("F_FIN", op.fin)):
            if v:
                L.append(f'<entrada dato="{k}">{e(v)}</entrada>')
        L += ["</ENTRADAS>", "<SALIDAS>",
              '<ERROR><salida dato="CN_ERROR">0</salida><salida dato="TE_ERROR">Servicio finalizado Correctamente</salida></ERROR>',
              '<listasal seq="EMP">', f'<salida dato="REGISTROS_RECUPERADOS">{len(por_prof)}</salida>']
        campos = ("X_ACTIVIDAD", "N_DIASEMANA", "X_TRAMO", "N_HORINI", "N_HORFIN", "X_DEPCENTRO", "X_MATERIAOMC", "X_UNIDAD")
        for i, (prof, fs) in enumerate(por_prof.items(), 1):
            x = self.x["profesores"].get(prof)
            L += [f'<listasal seq="EMP_{i}">', f'<salida dato="X_EMPLEADO">{e(self.clave("profesores", prof, op))}</salida>',
                  f'<salida dato="F_TOMAPOS">{e(x.findtext("tomaDePosesion") if x is not None else "")}</salida>',
                  '<listasal seq="TRAMO">', f'<salida dato="REGISTROS_RECUPERADOS">{len(fs)}</salida>']
            for j, f in enumerate(fs, 1):
                L.append(f'<listasal seq="TRAMO_{j}">' + "".join(f'<salida dato="{c}">{e(f[c])}</salida>' for c in campos)
                         + "</listasal>")
            L += ["</listasal>", "</listasal>"]
        L += ["</listasal>", "</SALIDAS>", "</SERVICIO>", ""]
        return "\n".join(L).encode("iso-8859-1", "xmlcharrefreplace")

    def exportar(self, ruta, op: Opciones):
        datos = self.xml(op)
        tmp = ruta + ".tmp"
        with open(tmp, "wb") as f:
            f.write(datos)
        os.replace(tmp, ruta)
        return datos
