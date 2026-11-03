"""Intercambio con DELPHOS (Castilla-La Mancha). Ver delphos_spec.md §9 (entrada, confirmada con muestras) y §10
(salida, SIN CONFIRMAR) y delphos_mapeo.md.

Entrada: SERVICIO nomservicio="CONS_TRAMOS_HORARIOS" / SALIDAS / listasal seq=SECCION / listasal seq=SECCION_i /
salida dato=CAMPO. Variante principal (principal: GRUPOS, MATERIAS, PROFESORES, AULAS, TAREAS, INTERVALOS) y variante
KRONOWIN (opcional: GRUPOS, MATERIAS, PROFESORES, AULAS, ASIGNATURAS con N_HORAS en minutos, TRAMOS). El lector es
tolerante: secciones ausentes, campos vacíos, intervalos desordenados, contadores que no cuadran (incidencia, no error)
y también el envoltorio común grupo_datos/dato@nombre_dato.

Cada elemento importado guarda su clave en <claveDeExportacion> (tramos: <clavX>; profesores además <tomaDePosesion>).
La salida usa SOLO esas claves: los nombres pueden cambiarse libremente.
"""
from __future__ import annotations
import re
import xml.etree.ElementTree as ET
from collections import OrderedDict

GESTOR = "DELPHOS - Castilla - La Mancha"
ORIGEN = "DELPHOS"
MODOS = ("nuevo", "actualizar", "claves")     # 493: cargar nuevos datos / incremental sincronizada / solo claves
RECREO_MAX = 45                               # minutos: un intervalo más corto se propone como recreo


class ErrorDelphos(Exception):
    pass


class Incidencias:
    """Informe de la importación: avisos (se importa igualmente) y errores (no se importa ese elemento)."""

    def __init__(self):
        self.lineas = []          # (nivel, seccion, texto)
        self.cuentas = OrderedDict()

    def aviso(self, sec, txt):
        self.lineas.append(("aviso", sec, txt))

    def error(self, sec, txt):
        self.lineas.append(("error", sec, txt))

    def contar(self, k, n=1):
        self.cuentas[k] = self.cuentas.get(k, 0) + n

    @property
    def errores(self):
        return [l for l in self.lineas if l[0] == "error"]

    def texto(self):
        out = [f"{k}: {v}" for k, v in self.cuentas.items()]
        if self.lineas:
            out.append("")
            out += [f"[{n}] {s}: {t}" for n, s, t in self.lineas]
        return "\n".join(out)


# ---------------------------------------------------------------- lectura
def _min(h):
    """'8:25' / '08:25' / '505' (minutos) -> minutos desde las 00:00, o None."""
    h = (h or "").strip()
    m = re.fullmatch(r"(\d{1,2})[:.](\d{2})(?::\d{2})?", h)
    if m:
        return int(m[1]) * 60 + int(m[2])
    if h.isdigit():
        return int(h)
    return None


def hhmm(m):
    return f"{m // 60:02d}:{m % 60:02d}"


def leer(datos: bytes | str, inc: Incidencias | None = None) -> dict:
    """Devuelve {"servidor", "fecha", "secciones": {SECCION: [ {CAMPO: valor} ]}}."""
    inc = inc if inc is not None else Incidencias()
    if isinstance(datos, str):
        with open(datos, "rb") as f:
            datos = f.read()
    try:
        raiz = ET.fromstring(datos)
    except ET.ParseError as e:
        raise ErrorDelphos(f"El archivo no es un XML válido: {e}") from e
    if raiz.tag != "SERVICIO":
        raise ErrorDelphos(f"No es un archivo de intercambio de DELPHOS (raíz <{raiz.tag}>, se esperaba <SERVICIO>).")
    out = {"servidor": (raiz.get("sisservidor") or "").strip(), "fecha": raiz.get("fecha", ""),
           "servicio": raiz.get("nomservicio", ""), "secciones": OrderedDict()}
    err = raiz.find("SALIDAS/ERROR")
    if err is not None:
        cod = {s.get("dato"): (s.text or "").strip() for s in err.findall("salida")}
        if cod.get("CN_ERROR", "0") not in ("", "0"):
            raise ErrorDelphos(f"DELPHOS informa de un error ({cod.get('CN_ERROR')}): {cod.get('TE_ERROR', '')}")
    sal = raiz.find("SALIDAS")
    if sal is not None:
        for sec in sal.findall("listasal"):
            nombre = (sec.get("seq") or "").strip().upper()
            filas = []
            for i, reg in enumerate(sec.findall("listasal"), 1):
                filas.append({(s.get("dato") or "").strip().upper(): (s.text or "").strip() for s in reg.findall("salida")})
                if (reg.get("seq") or "") != f"{nombre}_{i}":
                    inc.aviso(nombre, f"registro {i} con seq «{reg.get('seq')}»")
            n = next((s.text for s in sec.findall("salida") if s.get("dato") == "REGISTROS_RECUPERADOS"), None)
            if n is not None and (n or "").strip().isdigit() and int(n) != len(filas):
                inc.aviso(nombre, f"REGISTROS_RECUPERADOS={n.strip()} pero hay {len(filas)} registros")
            out["secciones"][nombre] = filas
    else:   # envoltorio común (Raíces): grupo_datos seq=SECCION / grupo_datos seq=X_i / dato nombre_dato=CAMPO
        for sec in raiz.iter("grupo_datos"):
            hijos = sec.findall("grupo_datos")
            if hijos and all(len(h.findall("dato")) for h in hijos):
                out["secciones"][(sec.get("seq") or "").upper()] = [
                    {(d.get("nombre_dato") or "").upper(): (d.text or "").strip() for d in h.findall("dato")} for h in hijos]
    if not out["secciones"]:
        raise ErrorDelphos("El archivo no contiene ninguna sección de datos.")
    v = out["servidor"].upper()
    out["variante"] = "KRONOWIN" if "KRONOWIN" in v or "ASIGNATURAS" in out["secciones"] else "PRINCIPAL"
    return out


# ---------------------------------------------------------------- importación
LISTAS_NUEVO = ("aulas", "conjuntoDeAulas", "tareas", "departamentos", "profesores", "materias", "cursos", "grupos",
                "sesionesLectivas", "listasDeRelacion", "reuniones", "guardias", "complementarias")


NOMBRE_MAX = 30          # NombreType del XSD


def _corto(n):
    return (n or "").strip()[:NOMBRE_MAX].strip()


def _unico(nombre, usados, clave):
    nombre = _corto(nombre)
    n = nombre or clave or "?"
    if n in usados:
        n = f"{nombre[:NOMBRE_MAX - len(clave) - 3]} ({clave})" if clave else n
        k = 2
        while n in usados:
            n = f"{nombre[:NOMBRE_MAX - len(clave) - 6]} ({clave}-{k})"; k += 1
    usados.add(n)
    return n


class _Destino:
    """Altas y actualizaciones de una lista del XML-GHC (por clave externa y, si no, por nombre)."""

    def __init__(self, raiz, lista, ED, arbol, modo, inc):
        self.raiz, self.lista, self.ED, self.arbol, self.modo, self.inc = raiz, lista, ED, arbol, modo, inc
        cont = ED.contenedor(raiz, lista)
        tag = ED.CONTENEDOR[lista][1]
        self.items = list(cont.findall(tag)) if cont is not None else []
        self.por_clave = {}
        for e in self.items:
            k = (e.findtext("claveDeExportacion") or "").strip()
            if k:
                self.por_clave.setdefault(k, e)
        self.por_nombre = {(e.findtext("nombre") or "").strip(): e for e in self.items}
        self.usados = set(self.por_nombre)
        self.altas = self.cambios = 0

    def poner(self, nombre, clave, campos):
        """campos: [(ruta, valor)] (valor None = no tocar). Devuelve (elemento, nombre final)."""
        ED = self.ED
        e = self.por_clave.get(clave) if clave else None
        if e is None and self.modo == "actualizar":
            e = self.por_nombre.get(_corto(nombre))
        if e is None:
            nombre = _unico(nombre, self.usados, clave)
            e = ED.insertar_elemento(self.arbol, self.lista, nombre)
            self.por_nombre[nombre] = e; self.altas += 1
        else:
            nombre = (e.findtext("nombre") or "").strip()     # se conserva el nombre de la usuaria
        if clave:
            self.por_clave[clave] = e
            if ED.escribir(self.arbol, e, "claveDeExportacion", clave):
                self.cambios += 1
        for ruta, v in campos:
            if v is not None and v != "" and ED.escribir(self.arbol, e, ruta, v):
                self.cambios += 1
        return e, nombre


def _vaciar(raiz, ED, arbol):
    for tag in LISTAS_NUEVO:
        c = raiz.find(tag)
        if c is None:
            continue
        for x in list(c):
            if tag == "tareas" and (x.tag != "tarea" or (x.findtext("nombre") or "").strip() in
                                    {(c.text or "").strip() for c in c if c.tag.endswith("PorDefecto")}):
                continue        # se conservan las tareas por defecto (lectiva, guardia, reunión)
            ED.quitar_hijo(arbol, c, x)


def intervalos(sec, inc):
    """INTERVALOS -> [(clave, ini, fin, es_recreo)] ordenados por hora de inicio."""
    out = []
    for f in sec:
        a, b = _min(f.get("INICIO")), _min(f.get("FIN"))
        k = f.get("CODIGO_DELPHOS", "")
        if a is None or b is None or b <= a:
            inc.error("INTERVALOS", f"intervalo {k}: horas no válidas «{f.get('INICIO')}»–«{f.get('FIN')}»"); continue
        out.append((k, a, b, b - a < RECREO_MAX))
    out.sort(key=lambda x: x[1])
    for x, y in zip(out, out[1:]):
        if y[1] < x[2]:
            inc.aviso("INTERVALOS", f"{hhmm(y[1])} se solapa con {hhmm(x[1])}–{hhmm(x[2])}")
        elif y[1] > x[2]:
            inc.aviso("INTERVALOS", f"hueco entre {hhmm(x[2])} y {hhmm(y[1])}")
    for k, a, b, r in out:
        if r:
            inc.aviso("INTERVALOS", f"{hhmm(a)}–{hhmm(b)} ({b - a} min) se propone como recreo; revíselo en «Modifique y "
                                    "añada los periodos»")
    return out


def _marco(raiz, ints, ED, arbol, modo, inc, dias=5):
    """Un solo marco (A) con los intervalos para los 5 días. En «actualizar» solo se ponen las claves a los periodos
    existentes que coincidan en hora."""
    md = raiz.find("marcosDeHorario")
    if md is None:
        md = ED.insertar_hijo(arbol, raiz, ED.nuevo("marcosDeHorario"), pos=1)
    mx = md.find("marcoHorario")
    if modo == "actualizar" and mx is not None:
        por_hora = {(t.findtext("horaEntrada") or "")[:5]: t for t in mx.findall("tramo")}
        n = 0
        for k, a, b, r in ints:
            for t in mx.findall("tramo"):
                if (t.findtext("horaEntrada") or "")[:5] == hhmm(a):
                    ED.escribir(arbol, t, "clavX", k); n += 1
        if not n and ints:
            inc.aviso("INTERVALOS", "ningún periodo del marco coincide en hora con los intervalos importados")
        return
    if mx is None:
        mx = ED.insertar_hijo(arbol, md, ED.nuevo("marcoHorario", attrib={"id": "A", "nombre": "Marco A", "claveX": "A"}))
    for t in list(mx.findall("tramo")):
        ED.quitar_hijo(arbol, mx, t)
    mid = mx.get("id", "A")
    for d in range(dias):
        for i, (k, a, b, r) in enumerate(ints):
            hijos = [ED.nuevo("submarco", mid), ED.nuevo("dia", str(d)), ED.nuevo("indice", str(i)),
                     ED.nuevo("horaEntrada", hhmm(a) + ":00"), ED.nuevo("horaSalida", hhmm(b) + ":00"),
                     ED.nuevo("Tipo", "recreo" if r else "lectivo"), ED.nuevo("clavX", k)]
            ED.insertar_hijo(arbol, mx, ED.nuevo("tramo", hijos=hijos), pos=len(mx))


def importar(raiz, pen: dict, ED, arbol, modo="nuevo", kro: dict | None = None, oferta=False,
             proponer_sesiones=True, inc: Incidencias | None = None) -> Incidencias:
    """Importa la variante principal (`pen`, de leer()) y, opcionalmente, cruza la KRONOWIN (`kro`).
    modo: «nuevo» (vacía las listas y carga), «actualizar» (importación incremental sincronizada: casa por clave
    externa y, si no, por nombre; refresca los demás campos y añade los nuevos) o «claves» (no toca el XML: devuelve el
    catálogo de claves en inc.claves). oferta=True importa también las materias de cursos sin grupos."""
    inc = inc if inc is not None else Incidencias()
    S = pen["secciones"]
    if pen.get("variante") == "KRONOWIN" and kro is None:
        kro, pen = pen, de_kronowin(pen)
        S = pen["secciones"]
        inc.aviso("ARCHIVO", "solo se ha aportado la variante KRONOWIN: no trae las horas de los intervalos ni los cursos")
    inc.claves = catalogo(pen, kro)
    pen_mats = {m.get("CLAVE", ""): m for m in S.get("MATERIAS", [])}
    if modo == "claves":
        for l, v in inc.claves.items():
            inc.contar(f"claves de {l}", len(v))
        return inc
    if modo == "nuevo":
        _vaciar(raiz, ED, arbol)
    D = lambda lista: _Destino(raiz, lista, ED, arbol, modo, inc)

    # cursos y materias (la clave de la materia es por curso)
    grupos = S.get("GRUPOS", [])
    mats = S.get("MATERIAS", [])
    cursos_con_grupo = {g.get("CODIGO_CURSO", "") for g in grupos}
    cursos = OrderedDict()
    for m in mats:
        c = m.get("CODIGO_CURSO", "")
        if c and c not in cursos:
            cursos[c] = (m.get("ABREVIATURA_CURSO") or c, m.get("DESCRIPCION_CURSO", ""))
    for c in sorted(cursos_con_grupo - set(cursos)):
        inc.aviso("GRUPOS", f"curso {c} sin materias en MATERIAS: se crea con su código como nombre")
        cursos[c] = (c, "")
    imp_cursos = [c for c in cursos if oferta or c in cursos_con_grupo]
    if len(imp_cursos) < len(cursos):
        inc.contar("cursos de la oferta sin grupos (no importados)", len(cursos) - len(imp_cursos))

    deps = OrderedDict()
    for f in mats + S.get("PROFESORES", []):
        d = f.get("DEPARTAMENTO", "")
        if d:
            deps.setdefault(d, None)
    dd = D("departamentos")
    for d in deps:
        deps[d] = dd.poner(d, "", [("nombreCompleto", d)])[1]
    if any(len(d) > NOMBRE_MAX for d in deps):
        inc.aviso("DEPARTAMENTO", f"nombres de departamento de más de {NOMBRE_MAX} caracteres: se acortan (el nombre "
                                  "completo se guarda aparte)")
    dep = lambda d: deps.get(d) if d else None
    inc.contar("departamentos", len(deps))

    dc = D("cursos"); nom_curso = {}
    for c in imp_cursos:
        e, n = dc.poner(cursos[c][0], c, [("nombreCompleto", cursos[c][1])])
        nom_curso[c] = (e, n)
    inc.contar("cursos", len(imp_cursos))

    dm = D("materias"); nom_mat = {}; sin_dep = 0
    for m in mats:
        c = m.get("CODIGO_CURSO", "")
        if c not in nom_curso:
            continue
        k = m.get("CLAVE", "")
        if not k:
            inc.error("MATERIAS", f"materia «{m.get('NOMBRE', '')}» sin CLAVE: no se importa"); continue
        ab = m.get("ABREVIATURA") or m.get("NOMBRE", "")[:4]
        e, n = dm.poner(f"{ab} {nom_curso[c][1]}", k, [("abreviatura", ab), ("nombreCompleto", m.get("NOMBRE")),
                                                       ("departamento", dep(m.get("DEPARTAMENTO")))])
        sin_dep += not m.get("DEPARTAMENTO")
        nom_mat[k] = (n, c)
        ce = nom_curso[c][0]
        mdc = ED.asegurar(arbol, ce, "materiasDelCurso")
        if not any((x.text or "").strip() == n for x in mdc.findall("materia")):
            ED.insertar_hijo(arbol, mdc, ED.nuevo("materia", n), pos=len(mdc))
    inc.contar("materias", len(nom_mat))
    if sin_dep:
        inc.aviso("MATERIAS", f"{sin_dep} materias sin departamento (se dejan sin él)")

    dg = D("grupos"); nom_grupo = {}
    for g in grupos:
        k = g.get("CLAVE", "")
        c = g.get("CODIGO_CURSO", "")
        e, n = dg.poner(g.get("NOMBRE") or k, k, [("cursoPerteneciente", nom_curso.get(c, (None, None))[1])])
        nom_grupo[k] = n
    inc.contar("grupos", len(grupos))

    dp = D("profesores"); nom_prof = {}; sin_dep = 0
    abrev = {f.get("X_EMPLEADO", ""): f.get("T_ABREV", "") for f in (kro or {}).get("secciones", {}).get("PROFESORES", [])}
    for f in S.get("PROFESORES", []):
        k = f.get("CLAVE", "")
        if not f.get("F_TOMA_POSESION"):
            inc.aviso("PROFESORES", f"profesor {k} sin F_TOMA_POSESION: hará falta para devolver el horario")
        e, n = dp.poner(f.get("NOMBRE") or k, k, [("abreviatura", abrev.get(k)), ("nombreCompleto", f.get("NOMBRE")),
                                                  ("departamento", dep(f.get("DEPARTAMENTO"))),
                                                  ("tomaDePosesion", f.get("F_TOMA_POSESION"))])
        sin_dep += not f.get("DEPARTAMENTO")
        nom_prof[k] = n
    inc.contar("profesores", len(nom_prof))
    if sin_dep:
        inc.aviso("PROFESORES", f"{sin_dep} profesores sin departamento")

    da = D("aulas")
    kaulas = {f.get("DEPCENTRO", ""): f for f in (kro or {}).get("secciones", {}).get("AULAS", [])}
    for f in S.get("AULAS", []):
        k = f.get("CLAVE", "")
        ka = kaulas.get(k, {})
        desc = ka.get("NOMBRE", "") + (f" (edificio {ka['EDIFICIO']})" if ka.get("EDIFICIO") else "")
        da.poner(f.get("IDENTIFICACION") or k, k, [("descripcion", desc.strip() or None)])
    inc.contar("aulas", len(S.get("AULAS", [])))
    rep = len(S.get("AULAS", [])) - len({f.get("IDENTIFICACION") for f in S.get("AULAS", [])})
    if rep > 0:
        inc.aviso("AULAS", f"{rep} identificaciones de aula repetidas: se distinguen añadiendo la clave")

    dt = D("tareas")
    for f in S.get("TAREAS", []):
        k = f.get("CODIGO_DELPHOS", "")
        campos = [("nombreCompleto", f.get("NOMBRE"))]
        for x, t in (("L_REQMATERIA", "requiereMateria"), ("L_REQUNIDAD", "requiereGrupo")):
            if f.get(x):
                campos.append((t, "true" if f[x].upper() == "S" else "false"))
        dt.poner(f.get("CLAVE") or k, k, campos)
    inc.contar("tareas", len(S.get("TAREAS", [])))

    ints = intervalos(S.get("INTERVALOS", []), inc)
    if not ints and kro is not None:
        inc.aviso("INTERVALOS", "sin horas de inicio: revise los periodos del marco")
    if ints:
        _marco(raiz, ints, ED, arbol, modo, inc)
        _comprobar_tramos(kro, ints, inc)
    inc.contar("intervalos", len(ints))

    o = ED.asegurar(arbol, raiz, "otros")
    ED.escribir(arbol, o, "origenDatos", ORIGEN)
    for i, d in enumerate(("lunes", "martes", "miercoles", "jueves", "viernes"), 1):
        if not ED.leer(o, f"claveXDias/{d}"):
            ED.escribir(arbol, o, f"claveXDias/{d}", str(i))

    if kro is not None and proponer_sesiones:
        proponer(raiz, kro, nom_grupo, nom_mat, ED, arbol, inc, D, pen_mats, dep)
    return inc


def _comprobar_tramos(kro, ints, inc):
    """KRONOWIN TRAMOS (CODIGO_DELPHOS, DIA=L1..V8, MINUTOS) confirma el orden y la duración."""
    if kro is None:
        return
    orden = {k: i for i, (k, a, b, r) in enumerate(ints)}
    dur = {k: b - a for k, a, b, r in ints}
    for f in kro["secciones"].get("TRAMOS", []):
        k, d, mn = f.get("CODIGO_DELPHOS", ""), f.get("DIA", ""), f.get("MINUTOS", "")
        m = re.fullmatch(r"([LMXJV])(\d+)", d)
        if k not in orden:
            inc.aviso("TRAMOS", f"tramo {k} ({d}) no está en INTERVALOS"); continue
        if m and int(m[2]) - 1 != orden[k]:
            inc.aviso("TRAMOS", f"tramo {k}: ordinal {m[2]} distinto del orden por hora ({orden[k] + 1})")
        if mn.isdigit() and int(mn) != dur[k]:
            inc.aviso("TRAMOS", f"tramo {k}: {mn} min en KRONOWIN y {dur[k]} min en INTERVALOS")


def de_kronowin(kro: dict) -> dict:
    """Secciones al de la variante principal a partir de la variante KRONOWIN sola (sin horas ni cursos con nombre)."""
    K = kro["secciones"]
    curso_de_grupo = {g.get("GRUPO", ""): g.get("ABREVIATURA", "") for g in K.get("GRUPOS", [])}
    curso_mat = {}
    for a in K.get("ASIGNATURAS", []):
        curso_mat.setdefault(a.get("MATERIA", ""), curso_de_grupo.get(a.get("GRUPO", ""), ""))
    mats, tareas = [], []
    for m in K.get("MATERIAS", []):
        k = m.get("MATERIA", "")
        if k[:1].upper() == "G" and k[1:].isdigit():
            tareas.append({"CODIGO_DELPHOS": k[1:], "CLAVE": m.get("COD", ""), "NOMBRE": m.get("NOMBRE", "")})
        elif curso_mat.get(k):
            c = curso_mat[k]
            mats.append({"CLAVE": k, "ABREVIATURA": m.get("COD", ""), "NOMBRE": m.get("NOMBRE", ""), "CODIGO_CURSO": c,
                         "ABREVIATURA_CURSO": c, "DESCRIPCION_CURSO": ""})
    return {"variante": "PRINCIPAL", "secciones": {
        "GRUPOS": [{"CLAVE": g.get("UNIDAD", ""), "NOMBRE": g.get("GRUPO", ""), "CODIGO_CURSO": g.get("ABREVIATURA", "")}
                   for g in K.get("GRUPOS", [])],
        "MATERIAS": mats, "TAREAS": tareas,
        "PROFESORES": [{"CLAVE": f.get("X_EMPLEADO", ""), "F_TOMA_POSESION": f.get("F_TOMAPOS", ""),
                        "NOMBRE": f.get("NOMBRE", "")} for f in K.get("PROFESORES", [])],
        "AULAS": [{"CLAVE": f.get("DEPCENTRO", ""), "IDENTIFICACION": f.get("ABREV", "")} for f in K.get("AULAS", [])]}}


def proponer(raiz, kro, nom_grupo, nom_mat, ED, arbol, inc, D, pen_mats=None, dep=lambda d: None):
    """KRONOWIN ASIGNATURAS (GRUPO, MATERIA, N_HORAS en minutos semanales) -> una sesión por grupo y materia con
    N_HORAS/60 sesiones de un periodo. Profesor y aula no vienen (CAULA vacío)."""
    K = kro["secciones"]
    unidad = {}
    for g in K.get("GRUPOS", []):
        unidad.setdefault(g.get("GRUPO", ""), g.get("UNIDAD", ""))
    lect = (raiz.findtext("tareas/lectivaPorDefecto") or "LEC").strip()
    existentes = {((s.findtext("materia") or "").strip(), (s.findtext("grupo") or "").strip())
                  for s in raiz.iter("sesion")}
    n_ses = 0
    for a in K.get("ASIGNATURAS", []):
        g = nom_grupo.get(unidad.get(a.get("GRUPO", ""), ""))
        mk = a.get("MATERIA", "")
        if mk[:1].upper() == "G":
            continue
        if g is None:
            inc.aviso("ASIGNATURAS", f"grupo «{a.get('GRUPO')}» no importado: se omite la materia {mk}"); continue
        if mk not in nom_mat:
            pm = (pen_mats or {}).get(mk)
            if pm is None:
                inc.aviso("ASIGNATURAS", f"materia {mk} no está en MATERIAS: se omite ({g})"); continue
            dm = D("materias")
            ab = pm.get("ABREVIATURA", "")
            e, n = dm.poner(f"{ab} {pm.get('ABREVIATURA_CURSO') or pm.get('CODIGO_CURSO', '')}", mk,
                            [("abreviatura", ab), ("nombreCompleto", pm.get("NOMBRE")), ("departamento", dep(pm.get("DEPARTAMENTO")))])
            nom_mat[mk] = (n, pm.get("CODIGO_CURSO", ""))
            inc.aviso("ASIGNATURAS", f"{g}: la materia {n} es de otro curso (optativa o unidad mixta); revísela")
        m = nom_mat[mk][0]
        h = a.get("N_HORAS", "")
        if not h.isdigit() or int(h) <= 0:
            inc.aviso("ASIGNATURAS", f"{g} / {m}: N_HORAS vacío; indique las sesiones a mano"); continue
        n = int(h) / 60
        if n != int(n):
            inc.aviso("ASIGNATURAS", f"{g} / {m}: {h} min no es múltiplo de 60; se redondea a {max(1, round(n))} sesiones")
        n = max(1, round(n))
        if (m, g) in existentes:
            inc.contar("sesiones ya existentes (no se duplican)"); continue
        s = ED.insertar_sesion(arbol, materia=m, grupo=g, profesor="", tarea=lect)
        partes = [1] * n
        if n > 5:                                    # DistribucionType: como mucho 5 piezas (una por día)
            partes = [n // 5 + (i < n % 5) for i in range(5)]
            inc.aviso("ASIGNATURAS", f"{g} / {m}: {n} sesiones semanales; se agrupan en {'+'.join(map(str, partes))}")
        ED.fijar_tmp(arbol, s, partes)
        pr = s.find("profesor")
        if pr is not None and not (pr.text or "").strip():
            ED.quitar_hijo(arbol, s, pr)          # sin profesor: el XSD no admite el nombre vacío
        existentes.add((m, g)); n_ses += 1
    inc.contar("sesiones propuestas (sin profesor)", n_ses)


def catalogo(pen, kro=None) -> dict:
    """Claves externas por lista: {lista: [(clave, descripción)]} (para «Cargar los códigos externos»)."""
    out = OrderedDict((l, []) for l in ("profesores", "grupos", "materias", "cursos", "aulas", "tareas", "tramos"))
    S = (pen or {}).get("secciones", {}) if pen else de_kronowin(kro)["secciones"] if kro else {}
    for g in S.get("GRUPOS", []):
        out["grupos"].append((g.get("CLAVE", ""), g.get("NOMBRE", "")))
    vistos = set()
    for m in S.get("MATERIAS", []):
        out["materias"].append((m.get("CLAVE", ""), f"{m.get('ABREVIATURA', '')} {m.get('ABREVIATURA_CURSO', '')} - {m.get('NOMBRE', '')}"))
        c = m.get("CODIGO_CURSO", "")
        if c and c not in vistos:
            vistos.add(c); out["cursos"].append((c, m.get("ABREVIATURA_CURSO") or m.get("DESCRIPCION_CURSO", "")))
    for f in S.get("PROFESORES", []):
        out["profesores"].append((f.get("CLAVE", ""), f.get("NOMBRE", "")))
    for f in S.get("AULAS", []):
        out["aulas"].append((f.get("CLAVE", ""), f.get("IDENTIFICACION", "")))
    for f in S.get("TAREAS", []):
        out["tareas"].append((f.get("CODIGO_DELPHOS", ""), f"{f.get('CLAVE', '')} - {f.get('NOMBRE', '')}"))
    for f in S.get("INTERVALOS", []):
        out["tramos"].append((f.get("CODIGO_DELPHOS", ""), f"{f.get('INICIO', '')}-{f.get('FIN', '')}"))
    return out
