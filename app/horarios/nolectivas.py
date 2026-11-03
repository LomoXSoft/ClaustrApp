"""Operaciones XML sobre las sesiones no lectivas: reuniones, guardias y complementarias.

Todas reciben un ED.Arbol y devuelven True (o el elemento creado) si cambian algo, para usarse
dentro de VentanaPrincipal.editar(). Mantienen el orden de etiquetas visto en los ejemplos.

Supuesto (no visto en los ejemplos): el detalle "Guardias hora a hora" se guarda como
<profesoresACadaHora><cantidad>N</cantidad><tramo dia=".." indice=".." marco="..">n</tramo>...</profesoresACadaHora>;
el motor y el comprobador lo leen igual.
"""
from __future__ import annotations
from . import edicion as ED

CONT = {"reuniones": ("reuniones", "reunion"), "guardias": ("guardias", "guardia"),
        "complementarias": ("complementarias", "complementaria")}


def _contenedor(arbol, lista):
    tag, _ = CONT[lista]
    c = arbol.raiz.find(tag)
    if c is None:
        c = ED.insertar_hijo(arbol, arbol.raiz, ED.nuevo(tag))
    return c


def _marco0(arbol):
    m = arbol.raiz.find("marcosDeHorario")
    x = m.find("marcoHorario") if m is not None else None
    return x.get("id", "A") if x is not None else "A"


def nombre_libre(arbol, lista, base):
    tag, item = CONT[lista]
    c = arbol.raiz.find(tag)
    usados = {(e.findtext("nombre") or "").strip() for e in (c.findall(item) if c is not None else [])}
    if base not in usados:
        return base
    k = 2
    while f"{base} {k}" in usados:
        k += 1
    return f"{base} {k}"


def integrantes(x) -> list[str]:
    ints = x.find("integrantes")
    out = []
    for ix in (ints.findall("integrante") if ints is not None else []):
        t = ix.findtext("nombre") if len(ix) else ix.text
        out.append((t or "").strip())
    return out


ETIQUETA_DEFECTO = {"Reuniones": "reunionPorDefecto", "Guardias": "guardiaPorDefecto", "Lectivas": "lectivaPorDefecto"}


def tarea_defecto(arbol, cual):
    """Tarea de partida (<tareas><reunionPorDefecto>/<guardiaPorDefecto>/<lectivaPorDefecto>)."""
    v = ED.leer(arbol.raiz, "tareas/" + ETIQUETA_DEFECTO[cual], None)
    if v:
        return v
    t = arbol.raiz.find("tareas/tarea")
    return (t.findtext("nombre") or "").strip() if t is not None else ""


# ---------------------------------------------------------------- creación
def nueva_reunion(arbol, nombre, tarea=None, marco=None, profesores=(), despues_de=None):
    c = _contenedor(arbol, "reuniones")
    r = ED.nuevo("reunion", attrib={"subMarco": marco or _marco0(arbol)}, hijos=[
        ED.nuevo("nombre", nombre_libre(arbol, "reuniones", nombre)), ED.nuevo("numeroDeReuniones", "1"),
        ED.nuevo("dobleDuracion", "false"), ED.nuevo("tipoDeTarea", tarea if tarea is not None else tarea_defecto(arbol, "Reuniones")),
        ED.nuevo("lectiva", "false"), ED.nuevo("plantilla"),
        ED.nuevo("integrantes", hijos=[ED.nuevo("integrante", p) for p in dict.fromkeys(profesores) if p])])
    pos = list(c).index(despues_de) + 1 if despues_de is not None and despues_de in list(c) else None
    ED.insertar_hijo(arbol, c, r, pos)
    return r


def nueva_guardia(arbol, nombre, tarea=None, marco=None, recreo=False, cantidad=1, despues_de=None):
    c = _contenedor(arbol, "guardias")
    g = ED.nuevo("guardia", attrib={"subMarco": marco or _marco0(arbol)}, hijos=[
        ED.nuevo("nombre", nombre_libre(arbol, "guardias", nombre)),
        ED.nuevo("tipoDeTarea", tarea if tarea is not None else tarea_defecto(arbol, "Guardias")),
        ED.nuevo("enRecreos", "true" if recreo else "false"), ED.nuevo("lectiva", "false"),
        ED.nuevo("profesoresACadaHora", hijos=[ED.nuevo("cantidad", str(cantidad))]),
        ED.nuevo("integrantes"), ED.nuevo("plantilla")])
    pos = list(c).index(despues_de) + 1 if despues_de is not None and despues_de in list(c) else None
    ED.insertar_hijo(arbol, c, g, pos)
    return g


def nueva_complementaria(arbol, tarea, profesor, marco=None, semanales=1, max_diarios=1, despues_de=None):
    c = _contenedor(arbol, "complementarias")
    ids = [int(x.findtext("identificador") or 0) for x in c.findall("complementaria")
           if (x.findtext("identificador") or "").strip().isdigit()]
    e = ED.nuevo("complementaria", attrib={"subMarco": marco or _marco0(arbol)}, hijos=[
        ED.nuevo("identificador", str(max(ids) + 1 if ids else 1)), ED.nuevo("tarea", tarea),
        ED.nuevo("profesor", profesor), ED.nuevo("lectiva", "false"), ED.nuevo("plantilla"),
        ED.nuevo("intervalosSemanales", str(semanales)), ED.nuevo("maxIntervalosDiarios", str(max_diarios)),
        ED.nuevo("noConsecutivos", "false")])
    pos = list(c).index(despues_de) + 1 if despues_de is not None and despues_de in list(c) else None
    ED.insertar_hijo(arbol, c, e, pos)
    return e


def eliminar(arbol, x):
    ED.quitar_hijo(arbol, arbol.padre[x], x)
    return True


# ---------------------------------------------------------------- integrantes
def anadir_profesores(arbol, x, nombres, n_guardias=1) -> bool:
    ya = set(integrantes(x))
    nuevos = [n for n in dict.fromkeys(nombres) if n and n not in ya]
    if not nuevos:
        return False
    ints = x.find("integrantes")
    if ints is None:
        ints = ED.insertar_hijo(arbol, x, ED.nuevo("integrantes"))
    for n in nuevos:
        if x.tag == "guardia":
            ix = ED.nuevo("integrante", hijos=[ED.nuevo("nombre", n), ED.nuevo("numeroDeGuardias", str(n_guardias)),
                                               ED.nuevo("plantilla")])
        else:
            ix = ED.nuevo("integrante", n)
        ED.insertar_hijo(arbol, ints, ix)
    return True


def quitar_profesor(arbol, x, nombre) -> bool:
    ints = x.find("integrantes")
    for ix in (list(ints.findall("integrante")) if ints is not None else []):
        t = ix.findtext("nombre") if len(ix) else ix.text
        if (t or "").strip() == nombre:
            ED.quitar_hijo(arbol, ints, ix)
            return True
    return False


def integrante_xml(g, nombre):
    ints = g.find("integrantes")
    for ix in (ints.findall("integrante") if ints is not None else []):
        if (ix.findtext("nombre") or "").strip() == nombre:
            return ix
    return None


def poner_guardias(arbol, ix, n) -> bool:
    return (ED.leer(ix, "numeroDeGuardias", None) or "") != str(n) and ED.escribir(arbol, ix, "numeroDeGuardias", str(n))


def poner_a_todos(arbol, g, n) -> bool:
    ints = g.find("integrantes")
    return any([poner_guardias(arbol, ix, n) for ix in (ints.findall("integrante") if ints is not None else [])])


# ---------------------------------------------------------------- profesores a cada hora
def detalle_posiciones(g) -> dict:
    pac = g.find("profesoresACadaHora")
    out = {}
    for tr in (pac.findall("tramo") if pac is not None else []):
        try:
            out[(tr.get("marco", g.get("subMarco", "A")), int(tr.get("dia", 0)), int(tr.get("indice", 0)))] = int((tr.text or "0").strip())
        except ValueError:
            pass
    return out


def fijar_detalle(arbol, g, detalle: dict | None) -> bool:
    """detalle None = número fijo (se quitan los tramos); dict = número variable por posición."""
    pac = g.find("profesoresACadaHora")
    if pac is None:
        pac = ED.insertar_hijo(arbol, g, ED.nuevo("profesoresACadaHora", hijos=[ED.nuevo("cantidad", "1")]))
    actual = detalle_posiciones(g)
    if (detalle or {}) == actual and (detalle is not None or not actual):
        return False
    for tr in list(pac.findall("tramo")):
        ED.quitar_hijo(arbol, pac, tr)
    for (m, d, i), n in sorted((detalle or {}).items()):
        ED.insertar_hijo(arbol, pac, ED.nuevo("tramo", str(n), {"dia": str(d), "indice": str(i), "marco": m}))
    return True


def huecos_a_cubrir(p, g) -> int:
    """Nº total de huecos del servicio = suma, en las posiciones válidas, de profesores a cada hora."""
    from . import modelo as M
    x = g.datos["_xml"] if hasattr(g, "datos") else g
    marco = x.get("subMarco") or next(iter(p.marcos), "A")
    m = p.marcos.get(marco)
    if m is None:
        return 0
    recreo = (x.findtext("enRecreos") or "").strip() == "true"
    cant = int((x.findtext("profesoresACadaHora/cantidad") or "1").strip() or 1)
    det = detalle_posiciones(x)
    from .xghc import leer_plantilla
    pl = leer_plantilla(x, marco)
    tot = 0
    for t in m.tramos:
        if (t.tipo == "recreo") if recreo else (t.tipo == "lectivo"):
            k = (marco, t.dia, t.indice)
            if pl.get(k) != M.PROHIBIDO:
                tot += det.get(k, cant)
    return tot


# ---------------------------------------------------------------- creación en lote (menú de la lista Reuniones)
def reuniones_departamento(arbol, p, departamento=None, nombre_completo=False) -> list:
    """«Crear reuniones de departamento»: una reunión por departamento con sus profesores actuales."""
    creadas = []
    for d in p.departamentos:
        if departamento and d.nombre != departamento:
            continue
        profs = [e.nombre for e in p.profesores if e.datos.get("departamento") == d.nombre]
        nombre = (d.datos.get("nombreCompleto") or d.nombre) if nombre_completo else d.nombre
        creadas.append(nueva_reunion(arbol, nombre, profesores=profs))
    return creadas


def reuniones_equipo(arbol, p, grupo=None, nombre_completo=False) -> list:
    """«Crear reuniones de equipos docentes»: profesores que imparten clase a cada grupo."""
    creadas = []
    for g in p.grupos:
        if grupo and g.nombre != grupo:
            continue
        profs = [s.profesor for s in p.sesiones if s.profesor and (s.grupo == g.nombre or g.nombre in s.otros_grupos)]
        if not profs:
            continue
        nombre = (g.datos.get("nombreCompleto") or g.nombre) if nombre_completo else g.nombre
        creadas.append(nueva_reunion(arbol, nombre, profesores=profs))
    return creadas
