"""Operaciones de edición sobre el árbol XML del .xghc.

El árbol XML es la fuente de verdad: cada operación lo modifica y la ventana
reconstruye el modelo (xghc.construir). Solo se tocan los nodos implicados, así
el archivo guardado difiere del original únicamente en lo editado.
"""
from __future__ import annotations
import copy
import re
import xml.etree.ElementTree as ET
from . import modelo as M

# Orden de los hijos tal como aparecen en los ejemplos de GHC (para insertar etiquetas nuevas).
ORDEN = {
    "profesor": ["nombre", "abreviatura", "nombreCompleto", "departamento", "claveDeExportacion", "email",
                 "tomaDePosesion", "daPracticas", "reduccionCargaLectiva", "mensaje", "plantilla", "opciones",
                 "prioridad", "horarioAsoc"],
    "grupo": ["nombre", "abreviatura", "nombreCompleto", "cursoPerteneciente", "claveDeExportacion", "numeroAlumnos",
              "profesorTutor", "huecosEnNoPreferentes", "tardesLibres", "limiteOcupacionDia", "noAdmiteHuecos",
              "eliminarHuecos", "plantilla", "aula", "gruposIncluidos"],
    "materia": ["nombre", "abreviatura", "nombreCompleto", "departamento", "claveDeExportacion", "plantilla",
                "esTutoria", "esDePractica"],
    "aula": ["nombre", "abreviatura", "claveDeExportacion", "numeroAlumnos", "dedicada", "ocupaDiaCompleto",
             "plantilla", "descripcion"],
    "sesion": ["materia", "grupo", "profesor", "duracionSemanal", "distribucionSemanal", "listaDeAulas",
               "listaDeAlternativas", "tarea", "grupoMateria", "departamento", "notas", "opciones", "plantilla",
               "otrosGrupos", "sesionesSimultaneas", "enDistintoDia"],
    "curso": ["nombre", "nombreCompleto", "claveDeExportacion", "materiasDelCurso"],
    "departamento": ["nombre", "nombreCompleto"],
    "tarea": ["nombre", "nombreCompleto", "claveDeExportacion", "requiereMateria", "requiereGrupo", "plantilla"],
    "tareas": ["tarea", "lectivaPorDefecto", "guardiaPorDefecto", "reunionPorDefecto"],
    "reunion": ["nombre", "numeroDeReuniones", "dobleDuracion", "tipoDeTarea", "lectiva", "plantilla", "integrantes"],
    "guardia": ["nombre", "tipoDeTarea", "enRecreos", "lectiva", "profesoresACadaHora", "integrantes", "plantilla"],
    "integrante": ["nombre", "numeroDeGuardias", "plantilla"],
    "profesoresACadaHora": ["cantidad", "tramo"],
    "complementaria": ["identificador", "tarea", "profesor", "lectiva", "plantilla", "intervalosSemanales",
                       "maxIntervalosDiarios", "noConsecutivos"],
    "datosGHC": ["version", "marcosDeHorario", "aulas", "conjuntoDeAulas", "tareas", "departamentos", "profesores",
                 "materias", "cursos", "grupos", "sesionesLectivas", "listasDeRelacion", "reuniones", "guardias",
                 "complementarias", "criterios", "otros"],
    "distribucionVariable": ["numSesiones", "numMaximoDeSesiones", "numMinimoDeSesiones", "penalizarSesionesSueltas",
                             "penalizarBloquesMaximos", "penalizarBloquesMinimos", "admitirBloquesDiscontinuos",
                             "distribucionInicial"],
    # <otros> según la plantilla de escritura del planificador de referencia
    "otros": ["restriccionesCD", "funcionesAdicionales", "mensajesIntercambio", "opciones", "notas", "gruposAlejados",
              "perfil", "claveXDias", "origenDatos", "extensiones"],
    "opcionesGenerales": ["contarHuecosMediodia", "desecharGuardias", "mantener5Sesiones"],
    "gruposAlejados": ["opciones", "listaDeGrupos"],
    "periodoLibreJornadaPartida": ["cantidad", "preferentes", "tipoDePeriodoLibre"],
}
OPC_PROFESOR = ["intervalosDePermanenciaSemanales", "intervalosDePermanenciaDiarios", "eliminarHuecos",
                "maximasHorasSeguidas", "penalizarAlrededorGuardiaRecreo", "periodosLibres",
                "periodoLibreJornadaPartida", "otrosPeriodosLibresJornadaPartida", "incompatibilidadEntreSesiones",
                "minimizarDiasOcupados", "considerarMaximasHorasDiariasSolamenteLectivas",
                "valorMaximasHorasCalculadoSolamenteLectivas", "considerarMinimasHorasDiariasSolamenteLectivas",
                "valorMinimasHorasCalculadoSolamenteLectivas", "considerarMaximasHorasDiarias",
                "valorMaximasHorasCalculado", "considerarMinimasHorasDiarias", "valorMinimasHorasCalculado",
                "maximoSesionesDiarias", "minimoSesionesDiarias"]
OPC_SESION = ["penaSesionesAPrimera", "penaSesionesAUltima", "penaSalirUltimaEntrarPrimera", "penaSesionMismaHora",
              "penaCoincidanPorLaTarde", "penaCoincidanDespuesDelRecreo", "noPermitirRecreosEntreSesiones",
              "recreosSeparanSesionesContinuas", "permitirImpartanEnDiasSeguidos", "considerarLunesViernesSeguidos",
              "sinCambioAula", "mismaPosicionDistintosPeriodos"]
ORDEN["valorInicialProfesores"] = OPC_PROFESOR
ORDEN["valorInicialSesiones"] = OPC_SESION
# <opciones> aparece en profesor, sesión, <otros> y <gruposAlejados>: sus hijos no se solapan
ORDEN["opciones"] = OPC_PROFESOR + OPC_SESION + ["opcionesGenerales", "valorInicialProfesores", "valorInicialSesiones",
                                                 "actualizarAlGenerar", "evitarDobleDesp"]

# Contenedor y etiqueta de cada lista editable
CONTENEDOR = {"profesores": ("profesores", "profesor"), "grupos": ("grupos", "grupo"),
              "materias": ("materias", "materia"), "aulas": ("aulas", "aula"), "cursos": ("cursos", "curso"),
              "departamentos": ("departamentos", "departamento"), "tareas": ("tareas", "tarea"),
              "sesiones": ("sesionesLectivas", "sesion"), "reuniones": ("reuniones", "reunion"),
              "guardias": ("guardias", "guardia"), "complementarias": ("complementarias", "complementaria")}

# Etiquetas hoja que referencian a un elemento de cada lista (para renombrar en cascada)
REFERENCIAS = {
    "profesores": {"profesor", "profesorTutor", "integrante"},
    "grupos": {"grupo"},
    "materias": {"materia"},
    "aulas": {"aula"},
    "cursos": {"cursoPerteneciente"},
    "departamentos": {"departamento"},
    "tareas": {"tarea", "tipoDeTarea"},
}


# ---------------------------------------------------------------- utilidades de árbol
class Arbol:
    def __init__(self, raiz):
        self.raiz = raiz
        self.padre = {c: p for p in raiz.iter() for c in p}

    def nivel(self, e):
        n = 0
        while e in self.padre:
            e = self.padre[e]; n += 1
        return n


def _indent(n):
    return "\n" + "\t" * n


def formatear(e, nivel):
    """Da a un subárbol nuevo el sangrado de GHC (tabuladores)."""
    if len(e):
        e.text = _indent(nivel + 1)
        for c in e:
            formatear(c, nivel + 1)
            c.tail = _indent(nivel + 1)
        e[-1].tail = _indent(nivel)
    elif e.text is None and e.tag in ("plantilla", "listaDeAulas", "listaDeAlternativas", "sesiones"):
        e.text = _indent(nivel)


def insertar_hijo(arbol: Arbol, padre, hijo, pos=None):
    """Inserta `hijo` en `padre` (en `pos` o según ORDEN) respetando el sangrado."""
    n = arbol.nivel(padre)
    if pos is None:
        orden = ORDEN.get(padre.tag)
        pos = len(padre)
        if orden and hijo.tag in orden:
            i = orden.index(hijo.tag)
            for j, c in enumerate(padre):
                if c.tag in orden and orden.index(c.tag) > i:
                    pos = j; break
    formatear(hijo, n + 1)
    if len(padre) == 0:
        padre.text = _indent(n + 1); hijo.tail = _indent(n)
    elif pos >= len(padre):
        ult = padre[-1]; hijo.tail = ult.tail; ult.tail = _indent(n + 1)
    else:
        hijo.tail = _indent(n + 1)
    padre.insert(pos, hijo)
    arbol.padre[hijo] = padre
    for c in hijo.iter():
        for d in c:
            arbol.padre[d] = c
    return hijo


def quitar_hijo(arbol: Arbol, padre, hijo):
    i = list(padre).index(hijo)
    if i == len(padre) - 1 and i > 0:
        padre[i - 1].tail = hijo.tail
    elif len(padre) == 1:
        padre.text = _indent(arbol.nivel(padre))
    padre.remove(hijo)


def nuevo(tag, texto=None, attrib=None, hijos=()):
    e = ET.Element(tag, attrib or {})
    e.text = texto
    for h in hijos:
        e.append(h)
    return e


def _seg(s):
    m = re.fullmatch(r'([\w]+)(?:\[@(\w+)="([^"]*)"\])?', s)
    return m.group(1), m.group(2), m.group(3)


def buscar(e, ruta):
    """Busca por ruta 'a/b[@attr="v"]'."""
    for s in ruta.split("/"):
        tag, at, v = _seg(s)
        e = next((c for c in e if c.tag == tag and (at is None or c.get(at) == v)), None)
        if e is None:
            return None
    return e


def leer(e, ruta, defecto=None):
    x = buscar(e, ruta)
    if x is None:
        return defecto
    return (x.text or "").strip()


def escribir(arbol: Arbol, e, ruta, valor):
    """Escribe el texto de la ruta, creando los nodos que falten. Devuelve True si cambió algo."""
    segs = ruta.split("/")
    for i, s in enumerate(segs):
        tag, at, v = _seg(s)
        x = next((c for c in e if c.tag == tag and (at is None or c.get(at) == v)), None)
        if x is None:
            x = insertar_hijo(arbol, e, nuevo(tag, None, {at: v} if at else None))
        e = x
    viejo = (e.text or "").strip() if len(e) == 0 else None
    if viejo == (valor or "") and e.text is not None:
        return False
    e.text = valor or ""
    return True


def asegurar(arbol: Arbol, e, ruta):
    """Devuelve el nodo de la ruta creando (en el orden de ORDEN) los contenedores que falten, sin texto."""
    for seg in ruta.split("/"):
        tag, at, v = _seg(seg)
        x = next((c for c in e if c.tag == tag and (at is None or c.get(at) == v)), None)
        if x is None:
            x = insertar_hijo(arbol, e, nuevo(tag, None, {at: v} if at else None))
        e = x
    return e


def copiar_nodo(arbol: Arbol, sp, destino, ruta_padre, tag, pred=None):
    """Copia los hijos `tag` (que cumplan `pred`) del nodo `sp` en destino/ruta_padre, sustituyendo los
    equivalentes. Devuelve True si cambió algo. Se usa en los botones «a toda la lista»."""
    if sp is None:
        return False
    fuentes = [x for x in sp if x.tag == tag and (pred is None or pred(x))]
    if not fuentes:
        return False
    dp = asegurar(arbol, destino, ruta_padre) if ruta_padre else destino
    viejos = [x for x in dp if x.tag == tag and (pred is None or pred(x))]
    norm = lambda x: re.sub(r"\s+", "", ET.tostring(x, encoding="unicode").split(">", 1)[0] + "".join(
        ET.tostring(c, encoding="unicode") for c in x) + (x.text or "").strip()) if x is not None else ""
    if len(viejos) == len(fuentes) and all(norm(a) == norm(b) for a, b in zip(viejos, fuentes)):
        return False
    pos = list(dp).index(viejos[0]) if viejos else None
    for v in viejos:
        quitar_hijo(arbol, dp, v)
    for k, f in enumerate(fuentes):
        c = copy.deepcopy(f); c.tail = None
        insertar_hijo(arbol, dp, c, None if pos is None else min(pos + k, len(dp)))
    return True


def borrar(arbol: Arbol, e, ruta):
    x = buscar(e, ruta)
    if x is None:
        return False
    padre = buscar(e, "/".join(ruta.split("/")[:-1])) if "/" in ruta else e
    quitar_hijo(arbol, padre, x)
    return True


# ---------------------------------------------------------------- Tmp (distribución semanal)
def parsear_tmp(texto):
    """'21' -> [2, 1]. Admite dígitos 1..9; devuelve None si no es válido."""
    t = (texto or "").strip()
    if not re.fullmatch(r"[1-9]{1,7}", t):
        return None
    return [int(c) for c in t]


def _f2(x):
    return f"{x:.2f}"


def fijar_tmp(arbol: Arbol, s, partes):
    """Establece una distribución semanal. Si es variable, cambia su distribución inicial."""
    ds = s.find("distribucionSemanal")
    if ds is None:
        ds = insertar_hijo(arbol, s, nuevo("distribucionSemanal"))
    var = ds.find("distribucionVariable")
    total = sum(partes)
    if var is not None:
        ini = var.find("distribucionInicial")
        if ini is not None:
            var.remove(ini)
        var_ini = nuevo("distribucionInicial", hijos=[nuevo("numSesiones", str(n)) for n in partes])
        insertar_hijo(arbol, var, var_ini)
        escribir(arbol, var, "numSesiones", _f2(total))
    else:
        fija = ds.find("distribucionFija")
        if fija is not None:
            quitar_hijo(arbol, ds, fija)
        insertar_hijo(arbol, ds, nuevo("distribucionFija", hijos=[nuevo("numSesiones", str(n)) for n in partes]))
    escribir(arbol, s, "duracionSemanal", _f2(total))


def distribucion_variable(arbol: Arbol, s, activar: bool, maximo=None):
    """Convierte la distribución fija <-> variable conservando el desglose."""
    ds = s.find("distribucionSemanal")
    if ds is None:
        return False
    var = ds.find("distribucionVariable"); fija = ds.find("distribucionFija")
    if activar and var is None and fija is not None:
        partes = [(n.text or "").strip() for n in fija.findall("numSesiones")]
        total = sum(float(x) for x in partes if x)
        quitar_hijo(arbol, ds, fija)
        hijos = [nuevo("numSesiones", _f2(total)),
                 nuevo("numMaximoDeSesiones", str(maximo or max(int(float(x)) for x in partes))),
                 nuevo("numMinimoDeSesiones", "1"), nuevo("penalizarBloquesMaximos", "false"),
                 nuevo("penalizarBloquesMinimos", "false"), nuevo("admitirBloquesDiscontinuos", "false"),
                 nuevo("distribucionInicial", hijos=[nuevo("numSesiones", x) for x in partes])]
        insertar_hijo(arbol, ds, nuevo("distribucionVariable", hijos=hijos))
        return True
    if not activar and var is not None:
        ini = var.find("distribucionInicial")
        partes = [(n.text or "").strip() for n in ini.findall("numSesiones")] if ini is not None else []
        if not partes:
            partes = [str(int(float(leer(var, "numSesiones", "1"))))]
        quitar_hijo(arbol, ds, var)
        insertar_hijo(arbol, ds, nuevo("distribucionFija", hijos=[nuevo("numSesiones", x) for x in partes]))
        return True
    return False


# ---------------------------------------------------------------- plantillas
def volcar_plantilla(arbol: Arbol, owner, plantilla: dict, marco_defecto="A"):
    """Escribe el dict de plantilla en <plantilla> de `owner` si difiere de lo que hay."""
    from .xghc import leer_plantilla
    if {k: v for k, v in leer_plantilla(owner, marco_defecto).items() if v} == {k: v for k, v in plantilla.items() if v}:
        return False
    pl = owner.find("plantilla")
    if pl is None:
        pl = insertar_hijo(arbol, owner, nuevo("plantilla"))
    for c in list(pl):
        pl.remove(c)
    n = arbol.nivel(pl)
    items = sorted(((k, v) for k, v in plantilla.items() if v), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2]))
    for (m, d, i), v in items:
        t = nuevo("tramo", v, {"dia": str(d), "indice": str(i), "marco": m})
        t.tail = _indent(n + 1); pl.append(t); arbol.padre[t] = pl
    if len(pl):
        pl.text = _indent(n + 1); pl[-1].tail = _indent(n)
    else:
        pl.text = _indent(n)
    return True


# ---------------------------------------------------------------- operaciones de lista
def contenedor(raiz, lista, crear_arbol=None):
    cont, _ = CONTENEDOR[lista]
    return raiz.find(cont)


def nombres(raiz, lista):
    c = contenedor(raiz, lista)
    _, item = CONTENEDOR[lista]
    return [leer(e, "nombre", "") for e in c.findall(item)] if c is not None else []


def insertar_elemento(arbol: Arbol, lista, nombre, despues_de=None):
    """Inserta un profesor/grupo/materia/aula/... con valores iniciales mínimos."""
    raiz = arbol.raiz
    c = contenedor(raiz, lista)
    cont, item = CONTENEDOR[lista]
    if c is None:
        c = insertar_hijo(arbol, raiz, nuevo(cont))
    e = nuevo(item, hijos=[nuevo("nombre", nombre)])
    if lista in ("profesores", "grupos", "materias", "aulas", "tareas"):
        e.append(nuevo("plantilla"))
    if lista == "aulas":
        e.insert(1, nuevo("dedicada", "false"))
    if lista == "profesores":
        vi = raiz.find("otros/opciones/valorInicialProfesores")
        op = copy.deepcopy(vi) if vi is not None else nuevo("opciones")
        op.tag = "opciones"; op.tail = None
        e.append(op); e.append(nuevo("prioridad", "1"))
    pos = None
    if despues_de is not None and despues_de in list(c):
        pos = list(c).index(despues_de) + 1
    insertar_hijo(arbol, c, e, pos)
    return e


def _siguiente_id(raiz):
    ids = [int(s.get("id")) for s in raiz.iter("sesion") if s.get("id", "").isdigit()]
    ids += [int(b.get("id")) for b in raiz.iter("bloqueDeSesiones") if b.get("id", "").isdigit()]
    return str(max(ids) + 1 if ids else 0)


def insertar_sesion(arbol: Arbol, despues_de=None, materia="", grupo="", profesor="", tarea="LEC"):
    raiz = arbol.raiz
    sl = raiz.find("sesionesLectivas")
    if sl is None:
        sl = insertar_hijo(arbol, raiz, nuevo("sesionesLectivas"))
    vi = raiz.find("otros/opciones/valorInicialSesiones")
    hijos = [nuevo("materia", materia), nuevo("grupo", grupo), nuevo("profesor", profesor),
             nuevo("duracionSemanal", "1.00"),
             nuevo("distribucionSemanal", hijos=[nuevo("distribucionFija", hijos=[nuevo("numSesiones", "1")])]),
             nuevo("listaDeAulas"), nuevo("listaDeAlternativas"), nuevo("tarea", tarea),
             nuevo("grupoMateria", f"{materia}/{grupo}" if materia and grupo else "", {"tipo": "N"})]
    if vi is not None:
        op = copy.deepcopy(vi); op.tag = "opciones"; hijos.append(op)
    hijos.append(nuevo("plantilla"))
    s = nuevo("sesion", attrib={"id": _siguiente_id(raiz)}, hijos=hijos)
    pos = None
    if despues_de is not None and despues_de in list(sl):
        pos = list(sl).index(despues_de) + 1
    insertar_hijo(arbol, sl, s, pos)
    return s


def eliminar_sesion(arbol: Arbol, s):
    raiz = arbol.raiz
    sid = s.get("id")
    quitar_hijo(arbol, arbol.padre[s], s)
    # referencias en días distintos de otras sesiones
    for otra in raiz.find("sesionesLectivas").findall("sesion"):
        edd = otra.find("enDistintoDia/sesiones")
        if edd is not None:
            for x in [x for x in edd.findall("sesion") if (x.text or "").strip() == sid]:
                quitar_hijo(arbol, edd, x)
            if len(edd) == 0:
                quitar_hijo(arbol, otra, otra.find("enDistintoDia"))
    # bloques de simultáneas
    sim = raiz.find("listasDeRelacion/simultaneas")
    if sim is not None:
        for b in list(sim.findall("bloqueDeSesiones")):
            ses = b.find("sesiones")
            if ses is None:
                continue
            for x in [x for x in ses.findall("sesion") if (x.text or "").strip() == sid]:
                quitar_hijo(arbol, ses, x)
            restantes = [(x.text or "").strip() for x in ses.findall("sesion")]
            if len(restantes) < 2:
                quitar_hijo(arbol, sim, b)
                for r in restantes:
                    o = next((o for o in raiz.find("sesionesLectivas").findall("sesion") if o.get("id") == r), None)
                    if o is not None and o.find("sesionesSimultaneas") is not None:
                        quitar_hijo(arbol, o, o.find("sesionesSimultaneas"))


def eliminar_elemento(arbol: Arbol, lista, e):
    """Elimina el elemento y vacía las referencias a él. Devuelve nº de referencias vaciadas."""
    nombre = leer(e, "nombre", "")
    quitar_hijo(arbol, arbol.padre[e], e)
    n = 0
    if lista == "profesores":     # un profesor suprimido deja de ser integrante de reuniones y guardias
        for ints in list(arbol.raiz.iter("integrantes")):
            for ix in list(ints.findall("integrante")):
                t = (ix.findtext("nombre") if len(ix) else ix.text) or ""
                if t.strip() == nombre:
                    quitar_hijo(arbol, ints, ix); n += 1
    return n + renombrar_referencias(arbol, lista, nombre, "")


def renombrar_referencias(arbol: Arbol, lista, viejo, nuevo_nombre):
    tags = REFERENCIAS.get(lista, set())
    n = 0
    for x in arbol.raiz.iter():
        if x.tag in tags and len(x) == 0 and (x.text or "").strip() == viejo:
            x.text = nuevo_nombre; n += 1
        elif x.tag == "integrante" and lista == "profesores":
            nn = x.find("nombre")
            if nn is not None and (nn.text or "").strip() == viejo:
                nn.text = nuevo_nombre; n += 1
    # el texto de los conjuntos de aulas usa <aula> (cubierto); identificativos grupo-materia por defecto
    if lista in ("materias", "grupos"):
        for s in arbol.raiz.iter("grupoMateria"):
            t = (s.text or "")
            partes = t.split("/")
            if viejo in partes:
                s.text = "/".join(nuevo_nombre if p == viejo else p for p in partes)
    return n


def renombrar(arbol: Arbol, lista, e, nuevo_nombre):
    viejo = leer(e, "nombre", "")
    if viejo == nuevo_nombre:
        return False
    escribir(arbol, e, "nombre", nuevo_nombre)
    renombrar_referencias(arbol, lista, viejo, nuevo_nombre)
    return True


# ---------------------------------------------------------------- campos de sesión
def set_campo_sesion(arbol: Arbol, s, campo, valor):
    """campo: materia, grupo, profesor, aula, conjunto, tmp, grupoMateria, tarea, departamento."""
    if campo in ("materia", "grupo"):
        viejo_m, viejo_g = leer(s, "materia", ""), leer(s, "grupo", "")
        cambio = escribir(arbol, s, campo, valor)
        gm = buscar(s, "grupoMateria")
        if cambio and gm is not None and (gm.text or "").strip() == f"{viejo_m}/{viejo_g}":
            m, g = (valor, viejo_g) if campo == "materia" else (viejo_m, valor)
            gm.text = f"{m}/{g}"
        return cambio
    if campo in ("profesor", "grupoMateria", "tarea", "departamento"):
        return escribir(arbol, s, campo, valor)
    if campo in ("aula", "conjunto"):
        tag, hijo = ("listaDeAulas", "aula") if campo == "aula" else ("listaDeAlternativas", "conjuntoAlternativo")
        la = s.find(tag)
        if la is None:
            la = insertar_hijo(arbol, s, nuevo(tag))
        actual = [(a.text or "").strip() for a in la.findall(hijo)]
        if (actual[:1] or [""])[0] == valor and len(actual) <= 1:
            return False
        primero = la.find(hijo)
        if valor and primero is not None:
            primero.text = valor
        elif valor:
            insertar_hijo(arbol, la, nuevo(hijo, valor))
        elif primero is not None:
            quitar_hijo(arbol, la, primero)
        return True
    if campo == "tmp":
        partes = parsear_tmp(valor)
        if partes is None:
            raise ValueError("La distribución semanal debe expresarse con cifras de 1 a 9, p. ej. 111, 21 ó 3.")
        fijar_tmp(arbol, s, partes)
        return True
    raise KeyError(campo)


def en_distinto_dia(arbol: Arbol, s, ids: list[str], seguidos: str | None):
    """Fija la lista de sesiones en días distintos (relación simétrica, como en GHC)."""
    raiz = arbol.raiz
    sid = s.get("id")
    por_id = {x.get("id"): x for x in raiz.find("sesionesLectivas").findall("sesion")}
    antes = [(x.text or "").strip() for x in s.iter("sesion") if x is not s] if s.find("enDistintoDia") is not None else []

    def poner(ses, lista, seg):
        edd = ses.find("enDistintoDia")
        if not lista:
            if edd is not None:
                quitar_hijo(arbol, ses, edd)
            return
        if edd is None:
            edd = insertar_hijo(arbol, ses, nuevo("enDistintoDia", hijos=[nuevo("sesiones")] +
                                                ([nuevo("enDiasSeguidos", seg)] if seg else [])))
        cont = edd.find("sesiones")
        actuales = [(x.text or "").strip() for x in cont.findall("sesion")]
        if actuales != lista:
            for x in list(cont):
                cont.remove(x)
            cont.text = None
            for i in lista:
                insertar_hijo(arbol, cont, nuevo("sesion", i))
        if seg is not None:
            if seg:
                escribir(arbol, edd, "enDiasSeguidos", seg)
            else:
                borrar(arbol, edd, "enDiasSeguidos")

    poner(s, ids, seguidos)
    for o in set(antes) - set(ids):
        x = por_id.get(o)
        if x is not None:
            l = [(y.text or "").strip() for y in x.findall("enDistintoDia/sesiones/sesion")]
            poner(x, [i for i in l if i != sid], None)
    for o in set(ids) - set(antes):
        x = por_id.get(o)
        if x is not None:
            l = [(y.text or "").strip() for y in x.findall("enDistintoDia/sesiones/sesion")]
            if sid not in l:
                poner(x, l + [sid], seguidos if x.find("enDistintoDia") is None else None)
