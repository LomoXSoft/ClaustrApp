"""Definición de las listas del Planificador: columnas y filas."""
from __future__ import annotations
from .textos import TX
from dataclasses import dataclass
from typing import Callable
from . import modelo as M

DIAS_LARGOS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]


@dataclass
class DefLista:
    clave: str
    titulo: str          # texto del botón / tooltip
    menu: str            # nombre del 4º menú
    icono: str
    columnas: list[str]
    filas: Callable      # proyecto -> list[(objeto, [valores])]
    con_plantilla: bool = True


def _b(v):
    return {"true": "Sí", "false": "No"}.get(str(v).lower(), v or "")


def _num(x):
    return f"{x:g}" if isinstance(x, float) else str(x)


def _lectivas(p, campo, nombre):
    """Horas semanales; las sesiones simultáneas de un mismo bloque cuentan una vez."""
    tot, bloques = 0.0, set()
    for s in p.sesiones:
        if campo == "aulas":
            ok = nombre in s.aulas
        elif campo == "grupo":
            ok = s.grupo == nombre or nombre in s.otros_grupos
        else:
            ok = getattr(s, campo) == nombre
        if not ok:
            continue
        if s.bloque is not None and campo == "grupo":
            if s.bloque in bloques:
                continue
            bloques.add(s.bloque)
        tot += s.duracion
    return _num(tot)


def _integrantes(el):
    x = el.datos.get("_xml"); ints = x.find("integrantes") if x is not None else None
    out = []
    if ints is not None:
        for i in ints.findall("integrante"):
            n = i.find("nombre")
            out.append(((n.text if n is not None else i.text) or "").strip())
    return out


def _guardias_de(p, prof, recreo):
    tot = 0
    for g in p.guardias:
        if (g.datos.get("enRecreos", "false") == "true") != recreo:
            continue
        x = g.datos["_xml"].find("integrantes")
        for i in (x.findall("integrante") if x is not None else []):
            n = i.find("nombre")
            if n is not None and (n.text or "").strip() == prof:
                try:
                    tot += int(i.findtext("numeroDeGuardias", "0"))
                except ValueError:
                    pass
    return str(tot) if tot else ""


def f_profesores(p):
    return [(e, [e.nombre, e.datos.get("abreviatura", ""), e.datos.get("nombreCompleto", ""),
                 e.datos.get("departamento", ""), _lectivas(p, "profesor", e.nombre),
                 str(sum(1 for r in p.reuniones if e.nombre in _integrantes(r))) if p.reuniones else "",
                 _guardias_de(p, e.nombre, False), _guardias_de(p, e.nombre, True),
                 str(sum(1 for c in p.complementarias if c.datos.get("profesor") == e.nombre)) or "",
                 e.datos.get("claveExterna", e.datos.get("claveDeExportacion", "")),
                 e.datos.get("prioridad", "")]) for e in p.profesores]


def _posiciones(p, g):
    m = p.marcos.get(g.marco)
    if not m:
        return ""
    libres = sum(1 for t in m.tramos if t.tipo == "lectivo" and g.plantilla.get((m.id, t.dia, t.indice)) != M.PROHIBIDO)
    return str(libres)


def f_grupos(p):
    return [(e, [e.nombre, e.datos.get("abreviatura", ""), e.datos.get("cursoPerteneciente", ""),
                 e.datos.get("profesorTutor", ""), e.datos.get("aula", ""), e.marco,
                 _lectivas(p, "grupo", e.nombre), _posiciones(p, e)]) for e in p.grupos]


def f_materias(p):
    return [(e, [e.nombre, e.datos.get("abreviatura", ""), e.datos.get("nombreCompleto", ""),
                 e.datos.get("departamento", ""), _lectivas(p, "materia", e.nombre),
                 "Sí" if e.datos.get("esTutoria") == "true" else ""]) for e in p.materias]


def f_aulas(p):
    conj = {a: n for n, l in p.conjuntos_aulas.items() for a in l}
    return [(e, [e.nombre, e.datos.get("abreviatura", ""), e.datos.get("descripcion", ""),
                 "<dedicada>" if e.datos.get("dedicada") == "true" else "", conj.get(e.nombre, ""),
                 _lectivas(p, "aulas", e.nombre)]) for e in p.aulas]


def f_sesiones(p):
    # las sesiones de un mismo bloque de simultáneas se muestran juntas
    orden, visto = [], {}
    for s in p.sesiones:
        if s.bloque is None:
            orden.append([s])
        elif s.bloque in visto:
            visto[s.bloque].append(s)
        else:
            visto[s.bloque] = [s]; orden.append(visto[s.bloque])
    from . import semanas as SEM
    noms = []
    if SEM.num_semanas(p.doc.raiz) > 1 and p.marcos:
        noms = [n for n, _ in SEM.periodos(p.doc.raiz, next(iter(p.marcos.values())).dias)]
    filas = []
    for blq in orden:
        for s in blq:
            filas.append((s, ["", s.materia, s.grupo, s.profesor, s.tmp, " ".join(s.aulas),
                              " ".join(c for c in s.alternativas if c), " ".join(s.en_distinto_dia),
                              _b(s.en_dias_seguidos), " ".join(s.otros_grupos), s.departamento,
                              s.grupo_materia, s.tarea, SEM.texto_en_semanas(s.xml, noms) if noms else ""]))
    return filas


def f_marco(p):
    from . import semanas as SEM
    out = []
    for m in p.marcos.values():
        pers = SEM.periodos(p.doc.raiz, m.dias) if p.doc is not None else [("s1", m.dias)]
        nom_dia = {}
        for w, (n, ds) in enumerate(pers):
            for d in ds:
                nom_dia[d] = (f"{n} " if len(pers) > 1 else "") + DIAS_LARGOS[(d - ds[0] + (ds[0] % 7 if len(pers) == 1 else 0)) % 7]
        for t in sorted(m.tramos, key=lambda t: (t.dia, t.indice)):
            out.append((t, [m.nombre, nom_dia.get(t.dia, str(t.dia)), str(t.indice + 1),
                            t.entrada, t.salida, t.tipo, t.clave]))
    return out


def _simple(attr, *campos):
    def f(p):
        return [(e, [e.nombre] + [_b(e.datos.get(c, "")) for c in campos]) for e in getattr(p, attr)]
    return f


def f_cursos(p):
    out = []
    for e in p.cursos:
        x = e.datos["_xml"].find("materiasDelCurso")
        n = len(x.findall("materia")) if x is not None else 0
        out.append((e, [e.nombre, e.datos.get("nombreCompleto", ""), str(n),
                        str(sum(1 for g in p.grupos if g.datos.get("cursoPerteneciente") == e.nombre))]))
    return out


def f_departamentos(p):
    return [(e, [e.nombre, e.datos.get("nombreCompleto", ""),
                 str(sum(1 for x in p.profesores if x.datos.get("departamento") == e.nombre)),
                 str(sum(1 for x in p.materias if x.datos.get("departamento") == e.nombre))]) for e in p.departamentos]


HIJO = "      └ "     # sangría de las filas hijas (integrantes) en las listas jerárquicas


def filas_integrantes(p, el, lista):
    """Elementos hijos (uno por integrante) de una reunión o servicio de guardia."""
    from .xghc import leer_plantilla
    x = el.datos["_xml"]; ints = x.find("integrantes")
    out = []
    for ix in (ints.findall("integrante") if ints is not None else []):
        n = ix.find("nombre")
        nombre = ((n.text if n is not None else ix.text) or "").strip()
        pl = leer_plantilla(ix, el.marco) if lista == "guardias" else None
        out.append(M.Elemento(nombre=nombre, plantilla=pl, marco=el.marco,
                              datos={"_xml": ix, "_padre": x, "_tipo": "integrante", "_lista": lista,
                                     "_servicio": el.nombre,
                                     "numeroDeGuardias": (ix.findtext("numeroDeGuardias") or "").strip()}))
    return out


def _nombre_marco(p, m):
    mm = p.marcos.get(m)
    return (mm.nombre or m) if mm else m


def f_reuniones(p):
    out = []
    for e in p.reuniones:
        hijos = filas_integrantes(p, e, "reuniones")
        out.append((e, [e.nombre, e.datos.get("numeroDeReuniones", ""),
                        "Doble" if e.datos.get("dobleDuracion") == "true" else "Simple",
                        e.datos.get("tipoDeTarea", ""), _b(e.datos.get("lectiva", "")), str(len(hijos)),
                        _nombre_marco(p, e.marco)]))
        out += [(h, [HIJO + h.nombre, "", "", "", "", "", ""]) for h in hijos]
    return out


def f_guardias(p):
    from .nolectivas import huecos_a_cubrir
    out = []
    for e in p.guardias:
        x = e.datos["_xml"].find("profesoresACadaHora")
        hijos = filas_integrantes(p, e, "guardias")
        asignadas = sum(int(h.datos["numeroDeGuardias"] or 0) for h in hijos if h.datos["numeroDeGuardias"].isdigit())
        variable = x is not None and x.find("tramo") is not None
        out.append((e, [e.nombre, e.datos.get("tipoDeTarea", ""),
                        "Recreos" if e.datos.get("enRecreos") == "true" else "Lectivas",
                        "Variable" if variable else (x.findtext("cantidad", "") if x is not None else ""),
                        f"{asignadas} / {huecos_a_cubrir(p, e)}", _b(e.datos.get("lectiva", "")),
                        _nombre_marco(p, e.marco)]))
        out += [(h, [HIJO + h.nombre, "", "", "", h.datos["numeroDeGuardias"], "", ""]) for h in hijos]
    return out


def f_complementarias(p):
    return [(e, [e.nombre, e.datos.get("tarea", ""), e.datos.get("profesor", ""), _b(e.datos.get("lectiva", "")),
                 e.datos.get("intervalosSemanales", ""), e.datos.get("maxIntervalosDiarios", ""),
                 _b(e.datos.get("noConsecutivos", "")), _nombre_marco(p, e.marco)]) for e in p.complementarias]


LISTAS = [
    DefLista("marco", "Marco horario", "MARCO", "l_marco",
             ["Marco", "Día", "Tramo", "Entrada", "Salida", "Tipo", TX("codigo_2")], f_marco, False),
    DefLista("materias", "Materias docentes", "MATERIAS", "l_materias",
             ["Materias", "Abreviatura", "Nombre completo", "Departamento", "Lectivas", "Tutoría"], f_materias),
    DefLista("grupos", "Grupos de alumnos", "GRUPOS", "l_grupos",
             ["Grupos", "Abreviatura", "Curso", "Profesor tutor", "Aula del grupo", "Marco", "Lectivas", "Posiciones"], f_grupos),
    DefLista("profesores", "Profesorado", "PROFESORADO", "l_profesores",
             ["Profesorado", "Abreviatura", "Nombre Largo", "Departamento", "Lectivas", "Reuniones", "Guardias",
              "Guardias de recreo", "Otras actividades", TX("codigo_externo"), "Prelación"], f_profesores),
    DefLista("aulas", "Aulas", "AULAS", "l_aulas",
             ["Aulas", "Abreviatura", "Descripción", TX("tipo_aula"), "Conjunto de aulas", "Lectivas"], f_aulas),
    DefLista("cursos", "Cursos", "CURSOS", "l_cursos",
             ["Cursos", "Nombre completo", "Materias", "Grupos"], f_cursos),
    DefLista("departamentos", "Departamentos", "DEPARTAMENTOS", "l_departamentos",
             ["Departamentos", "Nombre completo", "Profesores", "Materias"], f_departamentos, False),
    DefLista("tareas", "Tipos de tarea", "TAREAS", "l_tareas",
             ["Tareas", "Nombre completo", "Clave de exportación"], _simple("tareas", "nombreCompleto", "claveDeExportacion")),
    DefLista("sesiones", "Sesiones lectivas", TX("menu_sesiones"), "l_sesiones",
             ["", "Materia", "Grupo", "Profesorado", "Tmp", "Aula", "Conj.aulas", TX("dias_diferentes"),
              "En días seguidos", "Otros grupos", "Departamento", TX("codigo"), "Tarea", "En semanas"], f_sesiones),
    DefLista("reuniones", "Reuniones", "REUNIONES", "l_reuniones",
             ["Reuniones", "Nº de reuniones", "Duración", "Tarea", "Lectiva", "Nº integrantes", "Marco"], f_reuniones),
    DefLista("guardias", "Guardias", "GUARDIAS", "l_guardias",
             ["Guardias", "Tarea", "Tipo", "Profesores a cada hora", "Guardias (asignadas / huecos)", "Lectiva", "Marco"],
             f_guardias),
    DefLista("complementarias", "Sesiones complementarias", "COMPLEMENTARIAS", "l_complementarias",
             [TX("codigo"), "Tarea", "Profesor", "Lectiva", "Periodos semanales", "Máx. diarios", "Pueden no ser contiguos",
              "Marco"], f_complementarias),
]
POR_CLAVE = {d.clave: d for d in LISTAS}
