"""Lógica del Editor de horarios (sin Qt): edición de un resultado .lphr.

Elementos del horario ("items"): cadenas "s:k" (pieza k de doc["sesiones"]), "g:k" (guardia), "r:k" (reunión),
"c:k" (complementaria) y "n:k" (entrada k de doc["no_colocadas"], la lista de "Sesiones sin hueco en el horario").

Las sesiones creadas desde el Editor ("Nuevas") no tocan el .xghc: se guardan como operaciones en
doc["editor"]["anadidos"] y se aplican en memoria sobre la configuración al abrir el resultado; así el
comprobador independiente y la proyección sobre el Planificador las ven igual que las originales.
"""
from __future__ import annotations
from .textos import TX
import copy, os, shutil, zlib
from collections import defaultdict
from . import xghc, resultado as RES, comprobador as CK, edicion as ED, nolectivas as NL
from .modelo import PREFIJADO, PROHIBIDO

DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
VISTAS = ["Profesorado", "Grupos", "Aulas", "Tareas", "Reuniones", "Guardias"]
PALETA = ["#c8a2c8", "#6cb4ee", "#d4d47a", "#a8d5ba", "#f4c28f", "#f2a7a7", "#b5b8e8", "#e6d690", "#9fd3d9",
          "#d9b38c", "#c2e0a0", "#e8b4d8", "#a0c4e8", "#f0e0a0", "#b8d8b8", "#d8c0f0"]
ROJO = "#ff5a5a"
# Diálogo 196 «Aspecto de las celdas» (doc["editor"]["celdas"])
CELDAS_DEF = {"ocultar_aula": False, "ocultar_materia": False, "ocultar_profesor": False, "ocultar_grupo": False,
              "duracion": False, "una_fila": False, "horas": "no",          # no | distintas | todas
              "desdobles": 4, "ocultar_separacion": False, "solo_entrada": False, "ocultar_vacias": False,
              "ocultar_recreos": False, "ocultar_mediodia": False,
              "ident": {"materias": "id", "alumnos": "id", "profesores": "id", "aulas": "id", "cursos": "id",
                        "departamentos": "id", "tareas": "id"}}


def _min(h):
    try:
        a, b = h.split(":")[:2]; return int(a) * 60 + int(b)
    except Exception:
        return 0


def _t(e, ruta, defecto=""):
    x = e.find(ruta) if e is not None else None
    return (x.text or "").strip() if x is not None and x.text else defecto


class ErrorEdicion(Exception):
    pass


class Motivo(str):
    """Mensaje de conflicto con causa estructurada: se muestra como texto, pero lleva `codigo` y `datos`
    para que otras vistas (p. ej. la versión sencilla) lo expliquen sin depender del texto."""

    def __new__(cls, texto, codigo, **datos):
        o = super().__new__(cls, texto); o.codigo = codigo; o.datos = datos
        return o


class Propuesta:
    """Resultado de simular una operación: documento nuevo y mensajes de conflicto."""
    def __init__(self, titulo, doc, mensajes, invalida=""):
        self.titulo, self.doc, self.mensajes, self.invalida = titulo, doc, mensajes, invalida

    @property
    def fisicos(self):
        return [m for m in self.mensajes if m[1]]


class Editor:
    def __init__(self, ruta_lphr: str, ruta_xghc: str | None = None):
        self.ruta = ruta_lphr
        self.doc = RES.cargar(ruta_lphr)
        conf = self.doc.get("configuracion", {}).get("archivo", "")
        self.ruta_xghc = ruta_xghc or os.path.join(os.path.dirname(os.path.abspath(ruta_lphr)), conf)
        if not os.path.exists(self.ruta_xghc):
            raise FileNotFoundError(f"No se encuentra la configuración {conf} junto al resultado.")
        self._normalizar(self.doc)
        self.pila_deshacer, self.pila_rehacer = [], []
        self.modificado = False
        self._cargar_proyecto()

    # ------------------------------------------------------------------ configuración + añadidos
    @staticmethod
    def _normalizar(doc):
        ed = doc.setdefault("editor", {})
        ed.setdefault("colores", {}); ed.setdefault("anadidos", []); ed.setdefault("con_colores", True)

    def _cargar_proyecto(self):
        p = xghc.cargar(self.ruta_xghc)
        self._aplicar_anadidos(p, self.doc["editor"]["anadidos"])
        self.p = xghc.construir(p.doc, p.ruta)
        self.ses = {s.id: s for s in self.p.sesiones}
        self.tramos = {(m.id, t.dia, t.indice): t for m in self.p.marcos.values() for t in m.tramos}
        self.reu_xml = {e.nombre: e.datos["_xml"] for e in self.p.reuniones}
        self.gua_xml = {e.nombre: e.datos["_xml"] for e in self.p.guardias}
        self.comp_xml = {_t(e.datos["_xml"], "identificador"): e.datos["_xml"] for e in self.p.complementarias}
        self._firma_anadidos = repr(self.doc["editor"]["anadidos"])

    @staticmethod
    def _aplicar_anadidos(p, ops):
        arbol = ED.Arbol(p.doc.raiz); raiz = arbol.raiz
        por_id = lambda sid: next((s for s in raiz.find("sesionesLectivas").findall("sesion") if s.get("id") == sid), None)
        for op in ops:
            k = op["op"]
            if k == "separar":                   # Separar: copia independiente de la sesión con las n sesiones fuera
                ref = por_id(op["ref"])
                if ref is not None:
                    c = copy.deepcopy(ref); c.set("id", op["id"]); sl = raiz.find("sesionesLectivas")
                    ED.insertar_hijo(arbol, sl, c, list(sl).index(ref) + 1)
                    for e, n in ((c, op["n"]), (ref, None)):
                        ns = e.find("distribucionSemanal/distribucionFija/numSesiones")
                        if ns is not None:
                            ns.text = str(op["n"] if n else max(0, int((ns.text or "1").strip() or 1) - op["n"]))
                continue
            if k in ("lectiva", "simultanea"):
                s = ED.insertar_sesion(arbol, materia=op["materia"], grupo=op["grupo"], profesor=op["profesor"],
                                       tarea=op.get("tarea") or "LEC")
                s.set("id", op["id"])
                n = int(op.get("periodos", 1))
                ED.escribir(arbol, s, "duracionSemanal", f"{n}.00")
                ns = s.find("distribucionSemanal/distribucionFija/numSesiones"); ns.text = str(n)
                for a in op.get("aulas", []):
                    ED.set_campo_sesion(arbol, s, "aula", a)
                if k == "simultanea":
                    ref = por_id(op["ref"])
                    if ref is not None:          # misma distribución semanal que la sesión de referencia
                        ds_ref = ref.find("distribucionSemanal"); ds = s.find("distribucionSemanal")
                        idx = list(s).index(ds); s.remove(ds); nd = copy.deepcopy(ds_ref); nd.tail = ds.tail
                        s.insert(idx, nd); arbol.padre[nd] = s
                        ED.escribir(arbol, s, "duracionSemanal", _t(ref, "duracionSemanal", "1.00"))
                    sim = raiz.find("listasDeRelacion/simultaneas")
                    if sim is None:
                        lr = raiz.find("listasDeRelacion") or ED.insertar_hijo(arbol, raiz, ED.nuevo("listasDeRelacion"))
                        sim = ED.insertar_hijo(arbol, lr, ED.nuevo("simultaneas"))
                    b = next((b for b in sim.findall("bloqueDeSesiones")
                              if any((x.text or "").strip() == op["ref"] for x in b.iter("sesion"))), None)
                    if b is None:
                        b = ED.insertar_hijo(arbol, sim, ED.nuevo("bloqueDeSesiones", attrib={"id": op["ref"]}, hijos=[
                            ED.nuevo("sesiones", hijos=[ED.nuevo("sesion", op["ref"])]), ED.nuevo("plantilla")]))
                    ED.insertar_hijo(arbol, b.find("sesiones"), ED.nuevo("sesion", op["id"]))
            elif k == "complementaria":
                c = NL.nueva_complementaria(arbol, op["tarea"], op["profesor"], semanales=op.get("periodos", 1),
                                            max_diarios=op.get("periodos", 1))
                ED.escribir(arbol, c, "identificador", op["id"])
            elif k == "guardia":
                g = next((g for g in raiz.find("guardias").findall("guardia") if _t(g, "nombre") == op["servicio"]), None)
                if g is None:
                    continue
                ix = NL.integrante_xml(g, op["profesor"])
                if ix is None:
                    NL.anadir_profesores(arbol, g, [op["profesor"]], op["n"])
                else:
                    n = int(_t(ix, "numeroDeGuardias", "0") or 0) + op["n"]
                    if n <= 0:
                        NL.quitar_profesor(arbol, g, op["profesor"])
                    else:
                        NL.poner_guardias(arbol, ix, n)
            elif k == "servicio":
                NL.nueva_guardia(arbol, op["nombre"], recreo=op.get("recreo", False), cantidad=op.get("cantidad", 1))
            elif k == "reunion":
                r = NL.nueva_reunion(arbol, op["nombre"], profesores=op.get("profesores", []))
                ED.escribir(arbol, r, "nombre", op["nombre"])
                ED.escribir(arbol, r, "numeroDeReuniones", str(op.get("n", 1)))
                ED.escribir(arbol, r, "dobleDuracion", "true" if op.get("doble") else "false")
            elif k == "ajustar":            # reduce el número de reuniones/complementarias de la configuración
                if op["lista"] == "reuniones":
                    x = next(x for x in raiz.find("reuniones").findall("reunion") if _t(x, "nombre") == op["nombre"])
                    campo = "numeroDeReuniones"
                else:
                    x = next(x for x in raiz.find("complementarias").findall("complementaria")
                             if _t(x, "identificador") == op["nombre"])
                    campo = "intervalosSemanales"
                n = int(_t(x, campo, "0") or 0) + op["n"]
                if n <= 0:
                    NL.eliminar(arbol, x)
                else:
                    ED.escribir(arbol, x, campo, str(n))
            elif k == "eliminar_sesion":
                s = por_id(op["id"])
                if s is not None:
                    ED.eliminar_sesion(arbol, s)
            elif k == "modificar":
                s = por_id(op["id"])
                if s is not None:
                    ED.set_campo_sesion(arbol, s, op["campo"], op["valor"])

    # ------------------------------------------------------------------ deshacer / rehacer
    def _instantanea(self):
        return copy.deepcopy(self.doc)

    def _restaurar(self, doc):
        self.doc = doc
        if repr(doc["editor"]["anadidos"]) != self._firma_anadidos:
            self._cargar_proyecto()

    def _confirmar(self, nuevo, texto):
        self.pila_deshacer.append((self._instantanea(), texto)); self.pila_rehacer.clear()
        self._restaurar(nuevo); self.modificado = True

    def deshacer(self):
        if not self.pila_deshacer:
            return None
        doc, txt = self.pila_deshacer.pop(); self.pila_rehacer.append((self._instantanea(), txt))
        self._restaurar(doc); self.modificado = True
        return txt

    def rehacer(self):
        if not self.pila_rehacer:
            return None
        doc, txt = self.pila_rehacer.pop(); self.pila_deshacer.append((self._instantanea(), txt))
        self._restaurar(doc); self.modificado = True
        return txt

    # ------------------------------------------------------------------ consultas
    @staticmethod
    def _lista(doc, item):
        k, i = item.split(":")
        nombre = {"s": "sesiones", "g": "guardias", "r": "reuniones", "c": "complementarias", "n": "no_colocadas"}[k]
        return doc[nombre], int(i)

    def obj(self, item, doc=None):
        lst, i = self._lista(doc or self.doc, item)
        return lst[i]

    def items(self, doc=None):
        doc = doc or self.doc
        for k, n in (("s", "sesiones"), ("g", "guardias"), ("r", "reuniones"), ("c", "complementarias")):
            for i in range(len(doc[n])):
                yield f"{k}:{i}"

    def posiciones(self, item, doc=None):
        o = self.obj(item, doc); k = item[0]
        if k in "sr":
            return [(o["marco"], o["dia"], t) for t in o["tramos"]]
        if k in "gc":
            return [(o["marco"], o["dia"], o["tramo"])]
        return []

    def integrantes_reunion(self, nombre):
        x = self.reu_xml.get(nombre)
        return [n for n in (NL.integrantes(x) if x is not None else []) if n]

    def recursos(self, item, doc=None):
        """{(tipo, nombre)} que ocupa el elemento: profesor, grupo, aula."""
        o = self.obj(item, doc); k = item[0]; out = set()
        if k in "sn" and (k == "s" or o.get("tipo") == "sesion"):
            for sid in o["sesiones"]:
                s = self.ses.get(sid)
                if s:
                    if s.profesor:
                        out.add(("profesor", s.profesor))
                    out |= {("grupo", g) for g in [s.grupo] + s.otros_grupos if g}
            out |= {("aula", a) for a in o.get("aulas", [])}
        elif k == "g" or (k == "n" and o.get("tipo") == "guardia"):
            out.add(("profesor", o["profesor"]))
        elif k == "c" or (k == "n" and o.get("tipo") == "complementaria"):
            out.add(("profesor", o["profesor"]))
        elif k == "r" or (k == "n" and o.get("tipo") == "reunion"):
            out |= {("profesor", n) for n in self.integrantes_reunion(o.get("reunion") or o.get("nombre"))}
        return out

    def intervalo(self, marco, dia, idx):
        t = self.tramos[(marco, dia, idx)]
        return dia, _min(t.entrada), _min(t.salida)

    def ocupacion(self, doc=None):
        """[(item, tipo, nombre, dia, ini, fin)]"""
        doc = doc or self.doc; out = []
        for it in self.items(doc):
            rec = self.recursos(it, doc)
            for pos in self.posiciones(it, doc):
                if pos in self.tramos:
                    d, a, b = self.intervalo(*pos)
                    out += [(it, tp, nm, d, a, b) for tp, nm in rec]
        return out

    def choques(self, doc=None):
        """Elementos con solape físico (profesor, grupo o aula doble) -> {item}"""
        doc = doc or self.doc
        por = defaultdict(list)
        for it, tp, nm, d, a, b in self.ocupacion(doc):
            por[(tp, nm, d)].append((a, b, it))
        malos = set()
        bloque = lambda it: (tuple(self.obj(it, doc).get("sesiones", [])) if it[0] == "s" else None)
        for lst in por.values():
            lst.sort()
            for i in range(len(lst)):
                for j in range(i + 1, len(lst)):
                    if lst[j][0] >= lst[i][1]:
                        break
                    if lst[i][2] != lst[j][2]:
                        malos |= {lst[i][2], lst[j][2]}
        return malos

    def descripcion(self, item, doc=None):
        o = self.obj(item, doc); k = item[0]
        if k == "s" or (k == "n" and o.get("tipo") == "sesion"):
            ss = [self.ses[sid] for sid in o["sesiones"] if sid in self.ses]
            mats = "/".join(dict.fromkeys(s.materia for s in ss)); grs = "/".join(dict.fromkeys(s.grupo for s in ss))
            return f"{mats} {grs}".strip()
        if k == "g" or o.get("tipo") == "guardia":
            return f"Guardia {o.get('servicio') or o.get('nombre')}"
        if k == "r" or o.get("tipo") == "reunion":
            return f"Reunión {o.get('reunion') or o.get('nombre')}"
        return f"{o.get('tarea') or o.get('nombre')} (complementaria)"

    def tarea_de(self, item, doc=None):
        o = self.obj(item, doc); k = item[0]
        if k == "s":
            return next((self.ses[s].tarea for s in o["sesiones"] if s in self.ses), "")
        if k == "g":
            return _t(self.gua_xml.get(o["servicio"]), "tipoDeTarea")
        if k == "r":
            return _t(self.reu_xml.get(o["reunion"]), "tipoDeTarea")
        return o.get("tarea", "")

    # ------------------------------------------------------------------ vistas
    def elementos(self, vista):
        if vista == "Profesorado":
            return [e.nombre for e in self.p.profesores]
        if vista == "Grupos":
            return [e.nombre for e in self.p.grupos]
        if vista == "Aulas":
            return [e.nombre for e in self.p.aulas]
        if vista == "Tareas":
            return [e.nombre for e in self.p.tareas]
        if vista == "Reuniones":
            return [e.nombre for e in self.p.reuniones]
        return [e.nombre for e in self.p.guardias]

    def nombre_largo(self, vista, nombre):
        lista = {"Profesorado": self.p.profesores, "Grupos": self.p.grupos, "Aulas": self.p.aulas,
                 "Tareas": self.p.tareas, "Reuniones": self.p.reuniones, "Guardias": self.p.guardias}[vista]
        e = next((e for e in lista if e.nombre == nombre), None)
        return (e.datos.get("nombreCompleto") or nombre) if e else nombre

    def items_de(self, vista, nombre):
        out = []
        for it in self.items():
            k = it[0]; o = self.obj(it)
            if vista == "Tareas":
                ok = self.tarea_de(it) == nombre
            elif vista == "Reuniones":
                ok = k == "r" and o["reunion"] == nombre
            elif vista == "Guardias":
                ok = k == "g" and o["servicio"] == nombre
            else:
                tp = {"Profesorado": "profesor", "Grupos": "grupo", "Aulas": "aula"}[vista]
                ok = (tp, nombre) in self.recursos(it)
            if ok:
                out.append(it)
        return out

    def marcos_de(self, vista, nombre, items=None):
        ms = sorted({self.obj(it)["marco"] for it in (items if items is not None else self.items_de(vista, nombre))})
        if not ms and vista == "Grupos":
            ms = [self.p.marco_de_grupo(nombre)]
        return [m for m in ms if m in self.p.marcos] or list(self.p.marcos)[:1]

    # ------------------------------------------------------------------ presentación de las celdas (196)
    def celdas(self, doc=None):
        o = copy.deepcopy(CELDAS_DEF); base = copy.deepcopy(getattr(self, "celdas_base", None) or {})
        propio = copy.deepcopy((doc or self.doc)["editor"].get("celdas") or {})
        o.update(base); o.update(propio)   # «Mantener los valores permanentes» < opciones del propio resultado
        o["ident"] = {**CELDAS_DEF["ident"], **base.get("ident", {}), **propio.get("ident", {})}
        return o

    def fijar_celdas(self, o):
        if o == self.celdas():
            return False
        nuevo = self._instantanea(); nuevo["editor"]["celdas"] = copy.deepcopy(o)
        self._confirmar(nuevo, "presentación de las celdas"); return True

    LISTAS_NOMBRES = ("materias", "alumnos", "profesores", "aulas", "cursos", "departamentos", "tareas",
                      "reuniones", "guardias", "guardiasRecreo")

    def lista_cat(self, cat):
        return {"materias": self.p.materias, "alumnos": self.p.grupos, "profesores": self.p.profesores,
                "aulas": self.p.aulas, "cursos": self.p.cursos, "departamentos": self.p.departamentos,
                "tareas": self.p.tareas, "reuniones": getattr(self.p, "reuniones", []),
                "guardias": getattr(self.p, "guardias", []), "guardiasRecreo": [g for g in self.p.guardias if "recreo" in (g.nombre + str(g.datos.get("tipo", ""))).lower()]}.get(cat, [])

    def nombres_de(self, cat):
        """Filas (original, identificativo, abreviatura, nombre completo) con los cambios de presentación aplicados."""
        ren = (self.doc["editor"].get("nombres") or {}).get(cat, {})
        out = []
        for e in self.lista_cat(cat):
            r = ren.get(e.nombre, {})
            out.append((e.nombre, r.get("nombre") or e.nombre, r.get("abreviatura", e.datos.get("abreviatura", "") or ""),
                        r.get("nombreCompleto", e.datos.get("nombreCompleto", "") or "")))
        return out

    def fijar_nombres(self, cat, cambios):
        """cambios = {original: {nombre, abreviatura, nombreCompleto}}. Solo presentación (no toca el .xghc).
        Devuelve un texto de error si se repiten identificativos (cadena 630), o None."""
        filas = {o: [i, a, c] for o, i, a, c in self.nombres_de(cat)}
        for o, v in cambios.items():
            if o in filas:
                filas[o] = [v.get("nombre", filas[o][0]).strip() or o, v.get("abreviatura", filas[o][1]), v.get("nombreCompleto", filas[o][2])]
        ids = [v[0] for v in filas.values()]
        if len(ids) != len(set(ids)):
            return TX("codigos_no_pueden_repetir")
        nuevo = self._instantanea(); dst = nuevo["editor"].setdefault("nombres", {}).setdefault(cat, {})
        base = {e.nombre: e for e in self.lista_cat(cat)}
        for o, (i, a, c) in filas.items():
            e = base[o]; r = {}
            if i != o: r["nombre"] = i
            if a != (e.datos.get("abreviatura", "") or ""): r["abreviatura"] = a
            if c != (e.datos.get("nombreCompleto", "") or ""): r["nombreCompleto"] = c
            if r: dst[o] = r
            else: dst.pop(o, None)
        if nuevo["editor"]["nombres"] == (self.doc["editor"].get("nombres") or {}) :
            return None
        self._confirmar(nuevo, "cambiar nombres y claves"); return None

    # --- marcos horarios (presentación): horas de entrada/salida, clave de los periodos, nombres
    def marco_pres(self):
        return self.doc["editor"].get("marcos") or {}

    def hora_tramo(self, m, t):
        h = self.marco_pres().get(m, {}).get("horas", {}).get(str(t.indice))
        return (h[0], h[1]) if h else (t.entrada, t.salida)

    def clave_tramo(self, m, t):
        return self.marco_pres().get(m, {}).get("claves", {}).get(str(t.indice), "")

    def nombre_marco(self, m):
        return self.marco_pres().get(m, {}).get("nombre") or m

    def fijar_marco(self, m, horas=None, claves=None, nombre=None):
        nuevo = self._instantanea(); d = nuevo["editor"].setdefault("marcos", {}).setdefault(m, {})
        for k, v in (("horas", horas), ("claves", claves), ("nombre", nombre)):
            if v is not None:
                d[k] = v
        if nuevo["editor"]["marcos"] == self.marco_pres():
            return False
        self._confirmar(nuevo, "marcos horarios"); return True

    def ident(self, cat, nombre, modo=None):
        """Nombre a mostrar según «Utilizar para referirse a las» (id | abrev | completo) y los cambios de nombre."""
        modo = modo or self.celdas()["ident"].get(cat, "id")
        lista = {"materias": self.p.materias, "alumnos": self.p.grupos, "profesores": self.p.profesores,
                 "aulas": self.p.aulas, "cursos": self.p.cursos, "departamentos": self.p.departamentos,
                 "tareas": self.p.tareas}.get(cat, [])
        e = next((e for e in lista if e.nombre == nombre), None)
        ren = (self.doc["editor"].get("nombres") or {}).get(cat, {}).get(nombre, {})
        if modo == "completo":
            return ren.get("nombreCompleto") or (e.datos.get("nombreCompleto") if e else "") or ren.get("nombre") or nombre
        if modo == "abrev":
            return ren.get("abreviatura") or (e.datos.get("abreviatura") if e else "") or ren.get("nombre") or nombre
        return ren.get("nombre") or nombre

    def texto_celda(self, item, vista, ocultar=()):
        o = self.obj(item); k = item[0]; c = self.celdas()
        oc = set(ocultar) | {x for x in ("aula", "materia", "profesor", "grupo") if c[f"ocultar_{x}"]}
        sep = " " if c["una_fila"] else "\n"
        lin = []
        if k == "s":
            ss = [self.ses[s] for s in o["sesiones"] if s in self.ses]
            mat = "/".join(dict.fromkeys(self.ident("materias", s.materia) for s in ss))
            prof = "/".join(dict.fromkeys(self.ident("profesores", s.profesor) for s in ss if s.profesor))
            gr = "/".join(dict.fromkeys(self.ident("alumnos", g) for s in ss for g in [s.grupo] + s.otros_grupos if g))
            aul = ", ".join(self.ident("aulas", a) for a in o.get("aulas", []))
            if "materia" not in oc:
                lin.append(mat.upper())
            if vista != "Profesorado" and "profesor" not in oc and prof:
                lin.append(prof)
            if vista != "Grupos" and "grupo" not in oc and gr:
                lin.append(gr)
            if vista != "Aulas" and "aula" not in oc and aul:
                lin.append(f"({aul})")
        elif k == "g":
            lin = ["GUARDIA", self.ident("profesores", o["profesor"]) if vista == "Guardias" else o["servicio"]]
        elif k == "r":
            lin = ["REUNIÓN", o["reunion"]]
        else:
            lin = [self.ident("tareas", o["tarea"])] + ([self.ident("profesores", o["profesor"])] if vista != "Profesorado" else [])
        tr = o.get("tramos") or ([o["tramo"]] if "tramo" in o else [])
        if c["duracion"] and tr:
            lin.append(f"[{len(tr)} p.]")
        if c["horas"] != "no" and tr and o.get("marco") in self.p.marcos:
            fil = {t.indice: t for t in self.p.marcos[o["marco"]].filas()}
            a, b = fil.get(min(tr)), fil.get(max(tr))
            if a and b and (c["horas"] == "todas" or len(tr) > 1 or (a.entrada, b.salida) != (a.entrada, a.salida)):
                lin.append(f"{a.entrada}-{b.salida}")
        return sep.join(x for x in lin if x)

    def clave_color(self, item):
        o = self.obj(item); k = item[0]
        if k == "s":
            return next((self.ses[s].materia for s in o["sesiones"] if s in self.ses), "")
        return {"g": "Guardia", "r": "Reunión", "c": "Complementaria"}[k]

    def color(self, clave):
        c = self.doc["editor"]["colores"].get(clave)
        if c:
            return c
        if clave in ("Guardia", "Reunión", "Complementaria"):
            return {"Guardia": "#dcdcdc", "Reunión": "#f6f0c8", "Complementaria": "#e2e8f0"}[clave]
        return PALETA[zlib.crc32(clave.encode("utf-8")) % len(PALETA)]

    def cambiar_color(self, clave, color):
        nuevo = self._instantanea(); nuevo["editor"]["colores"][clave] = color
        self._confirmar(nuevo, f"cambiar el color de {clave}")

    def recuperar_paleta(self):
        nuevo = self._instantanea(); nuevo["editor"]["colores"] = {}
        self._confirmar(nuevo, "recuperar la paleta original")

    def poner_quitar_colores(self):
        nuevo = self._instantanea(); nuevo["editor"]["con_colores"] = not nuevo["editor"].get("con_colores", True)
        self._confirmar(nuevo, "poner/quitar colores")

    # ------------------------------------------------------------------ simulación y conflictos
    def _errores(self, doc):
        inf = CK.comprobar(self.p, doc)
        return [e for e in inf.errores]

    def _texto_pos(self, marco, dia, idx):
        return f"{DIAS[dia] if dia < len(DIAS) else dia}, {idx + 1}ªhora"

    def mensajes(self, doc_antes, doc_despues, movidos):
        """Mensajes de conflicto que introduce el cambio. [(texto, item_extraible|None)]"""
        msgs = []
        antes = {it for it in self.choques(doc_antes)}
        occ = self.ocupacion(doc_despues)
        por = defaultdict(list)
        for it, tp, nm, d, a, b in occ:
            por[(tp, nm, d)].append((a, b, it))
        vistos = set()
        etiqueta = {"profesor": "(05) {pos}.- Ya está en esta posición el profesor {n}",
                    "grupo": "(06) {pos}.- Ya está en esta posición el grupo de alumnos {n}",
                    "aula": "(07) {pos}.- El aula {n} ya está ocupada en esta posición"}
        for mv in movidos:
            rec = self.recursos(mv, doc_despues)
            for pos in self.posiciones(mv, doc_despues):
                if pos not in self.tramos:
                    continue
                d, a, b = self.intervalo(*pos)
                for tp, nm in sorted(rec):
                    for a2, b2, it in por[(tp, nm, d)]:
                        if it in movidos or not (a2 < b and a < b2):
                            continue
                        clave = (tp, nm, it)
                        if clave in vistos:
                            continue
                        vistos.add(clave)
                        det = self.descripcion(it, doc_despues)
                        msgs.append((Motivo(etiqueta[tp].format(pos=self._texto_pos(*pos), n=nm) + f" ({det})",
                                            "choque_" + tp, nombre=nm, detalle=det), it))
        # reglas del comprobador (no físicas): solo las nuevas
        ea = defaultdict(int)
        for e in self._errores(doc_antes):
            ea[e] += 1
        for e in self._errores(doc_despues):
            if ea[e] > 0:
                ea[e] -= 1; continue
            if e[0].startswith("Solape de"):
                continue
            msgs.append((Motivo(f"(20) {e[0]}: {e[1]}", "regla", categoria=e[0], detalle=e[1]), None))
        return msgs

    def _simular(self, titulo, fn, movidos_fn):
        nuevo = self._instantanea()
        try:
            movidos = fn(nuevo)
        except ErrorEdicion as ex:
            return Propuesta(titulo, None, [], ex.args[0] if ex.args and isinstance(ex.args[0], Motivo) else str(ex))
        return Propuesta(titulo, nuevo, self.mensajes(self.doc, nuevo, movidos))

    def _cabe(self, marco, dia, idx, n):
        if marco not in self.p.marcos:
            raise ErrorEdicion(TX("ese_marco_horario_no_existe"))
        lect = sorted(t.indice for t in self.p.marcos[marco].tramos if t.dia == dia)
        idxs = list(range(idx, idx + n))
        for i in idxs:
            t = self.tramos.get((marco, dia, i))
            if t is None or t.tipo != "lectivo":
                raise ErrorEdicion(Motivo(f"No caben {n} periodos lectivos consecutivos a partir de esta posición.",
                                          "no_caben", n=n))
        return idxs

    def _titulo(self, dia, idx):
        return f"Agregando el {DIAS[dia] if dia < len(DIAS) else dia} a la {idx + 1}ª hora"

    def proponer_mover(self, item, marco, dia, idx):
        def fn(doc):
            o = self.obj(item, doc); k = item[0]
            if k == "s":
                o["marco"], o["dia"], o["tramos"] = marco, dia, self._cabe(marco, dia, idx, len(o["tramos"]))
            elif k == "r":
                o["marco"], o["dia"], o["tramos"] = marco, dia, self._cabe(marco, dia, idx, len(o["tramos"]))
            elif k == "c":
                self._cabe(marco, dia, idx, 1); o.update(marco=marco, dia=dia, tramo=idx)
            elif k == "g":
                t = self.tramos.get((marco, dia, idx))
                if t is None:
                    raise ErrorEdicion("Posición inexistente.")
                o.update(marco=marco, dia=dia, tramo=idx)
            return [item]
        return self._simular(self._titulo(dia, idx), fn, None)

    def _aulas_para(self, sids, marco, dia, idxs, doc):
        aulas = []
        for sid in sids:
            s = self.ses.get(sid)
            if not s:
                continue
            if s.aulas:
                aulas += s.aulas
            elif s.alternativas:
                ocup = {nm for it, tp, nm, d, a, b in self.ocupacion(doc) if tp == "aula"
                        and any(d == dia and a < self.intervalo(marco, dia, i)[2] and self.intervalo(marco, dia, i)[1] < b for i in idxs)}
                cand = [a for c in s.alternativas for a in self.p.conjuntos_aulas.get(c, [c])]
                libre = next((a for a in cand if a not in ocup and a not in aulas), cand[0] if cand else None)
                if libre:
                    aulas.append(libre)
        return list(dict.fromkeys(aulas))

    def _longitud(self, nc):
        if nc.get("tramos_len"):
            return int(nc["tramos_len"])
        per = int(nc.get("periodos", 1))
        s = self.ses.get(nc["sesiones"][0]) if nc.get("sesiones") else None
        if s is None or s.xml is None:
            return 1
        partes = sorted((int(float((x.text or "0").strip() or 0)) for x in s.xml.findall("distribucionSemanal/distribucionFija/numSesiones")), reverse=True)
        puestas = sorted(len(pz["tramos"]) for pz in self.doc["sesiones"] if s.id in pz["sesiones"])
        for L in puestas:
            if L in partes:
                partes.remove(L)
        cand = [x for x in partes if 0 < x <= per]
        return cand[0] if cand else 1

    def proponer_agregar(self, nitem, marco, dia, idx):
        """Agrega al horario una entrada de 'Sesiones sin hueco en el horario'."""
        nc0 = self.obj(nitem)

        def fn(doc):
            lst, i = self._lista(doc, nitem); nc = lst[i]; tipo = nc.get("tipo")
            if tipo == "sesion":
                L = self._longitud(nc); idxs = self._cabe(marco, dia, idx, L)
                pz = {"sesiones": list(nc["sesiones"]), "marco": marco, "dia": dia, "tramos": idxs,
                      "aulas": list(nc.get("aulas") or self._aulas_para(nc["sesiones"], marco, dia, idxs, doc)),
                      "aula_no_preferente": False}
                doc["sesiones"].append(pz); nuevo = f"s:{len(doc['sesiones']) - 1}"
                nc["periodos"] = int(nc.get("periodos", L)) - L
                nc.pop("tramos_len", None); nc.pop("aulas", None)
                vacia = nc["periodos"] <= 0
            elif tipo == "guardia":
                if (marco, dia, idx) not in self.tramos:
                    raise ErrorEdicion("Posición inexistente.")
                doc["guardias"].append({"servicio": nc["nombre"], "profesor": nc["profesor"], "marco": marco,
                                        "dia": dia, "tramo": idx})
                nuevo = f"g:{len(doc['guardias']) - 1}"; nc["cantidad"] = int(nc["cantidad"]) - 1; vacia = nc["cantidad"] <= 0
            elif tipo == "reunion":
                x = self.reu_xml.get(nc["nombre"]); L = 2 if _t(x, "dobleDuracion") == "true" else 1
                doc["reuniones"].append({"reunion": nc["nombre"], "marco": marco, "dia": dia,
                                         "tramos": self._cabe(marco, dia, idx, L)})
                nuevo = f"r:{len(doc['reuniones']) - 1}"; nc["cantidad"] = int(nc["cantidad"]) - 1; vacia = nc["cantidad"] <= 0
            else:
                self._cabe(marco, dia, idx, 1)
                doc["complementarias"].append({"id": nc.get("id", ""), "tarea": nc["nombre"], "profesor": nc["profesor"],
                                               "marco": marco, "dia": dia, "tramo": idx})
                nuevo = f"c:{len(doc['complementarias']) - 1}"; nc["cantidad"] = int(nc["cantidad"]) - 1; vacia = nc["cantidad"] <= 0
            if vacia:
                lst.pop(i)
            return [nuevo]
        return self._simular(self._titulo(dia, idx), fn, None)

    def confirmar(self, prop: Propuesta, extraer=(), texto="mover"):
        """Aplica la propuesta; antes extrae (a 'fuera del horario') los elementos indicados."""
        if prop.invalida or prop.doc is None:
            raise ErrorEdicion(prop.invalida or "Operación no válida")
        doc = prop.doc
        objs = [self.obj(it, doc) for it in extraer]
        for o, it in zip(objs, extraer):
            self._extraer_obj(doc, it[0], o)
        self._confirmar(doc, texto)

    # ------------------------------------------------------------------ extraer
    def _extraer_obj(self, doc, k, o):
        nombre = {"s": "sesiones", "g": "guardias", "r": "reuniones", "c": "complementarias"}[k]
        lst = doc[nombre]
        i = next(j for j, x in enumerate(lst) if x is o)
        lst.pop(i)
        nc = doc["no_colocadas"]
        if k == "s":
            nc.append({"tipo": "sesion", "sesiones": list(o["sesiones"]), "periodos": len(o["tramos"]),
                       "tramos_len": len(o["tramos"]), "aulas": list(o.get("aulas", [])),
                       "etiqueta": "extraída en el editor"})
        elif k == "g":
            e = next((x for x in nc if x.get("tipo") == "guardia" and x["nombre"] == o["servicio"] and x.get("profesor") == o["profesor"]), None)
            if e:
                e["cantidad"] = int(e["cantidad"]) + 1
            else:
                nc.append({"tipo": "guardia", "nombre": o["servicio"], "profesor": o["profesor"], "cantidad": 1})
        elif k == "r":
            e = next((x for x in nc if x.get("tipo") == "reunion" and x["nombre"] == o["reunion"]), None)
            if e:
                e["cantidad"] = int(e["cantidad"]) + 1
            else:
                nc.append({"tipo": "reunion", "nombre": o["reunion"], "profesor": "", "cantidad": 1})
        else:
            e = next((x for x in nc if x.get("tipo") == "complementaria" and x.get("id") == o.get("id")), None)
            if e:
                e["cantidad"] = int(e["cantidad"]) + 1
            else:
                nc.append({"tipo": "complementaria", "nombre": o["tarea"], "profesor": o["profesor"],
                           "id": o.get("id", ""), "cantidad": 1})

    def extraer(self, items, texto="extraer el contenido de la celda"):
        nuevo = self._instantanea()
        objs = [(it[0], self.obj(it, nuevo)) for it in items]
        for k, o in objs:
            self._extraer_obj(nuevo, k, o)
        self._confirmar(nuevo, texto)

    def piezas_asignatura(self, item):
        o = self.obj(item)
        if item[0] != "s":
            return [item]
        ss = [self.ses[s] for s in o["sesiones"] if s in self.ses]
        mats = {s.materia for s in ss}; grs = {g for s in ss for g in [s.grupo] + s.otros_grupos}
        out = []
        for i, pz in enumerate(self.doc["sesiones"]):
            s2 = [self.ses[s] for s in pz["sesiones"] if s in self.ses]
            if any(s.materia in mats and ({s.grupo} | set(s.otros_grupos)) & grs for s in s2):
                out.append(f"s:{i}")
        return out

    def extraer_asignatura(self, item):
        self.extraer(self.piezas_asignatura(item), "extraer toda la asignatura")

    # ------------------------------------------------------------------ aulas
    def ocupantes_aula(self, aula, marco, dia, idx, excluir=None):
        d, a, b = self.intervalo(marco, dia, idx)
        return [it for it, tp, nm, dd, a2, b2 in self.ocupacion() if tp == "aula" and nm == aula and dd == d
                and a2 < b and a < b2 and it != excluir]

    def estado_aulas(self, marco, dia, idx, excluir=None):
        """{aula: 'libre'|'ocupada'|'prohibida'}"""
        clave = (marco, dia, idx); out = {}
        for e in self.p.aulas:
            if self.ocupantes_aula(e.nombre, marco, dia, idx, excluir):
                out[e.nombre] = "ocupada"
            elif e.plantilla.get(clave) == PROHIBIDO:
                out[e.nombre] = "prohibida"
            else:
                out[e.nombre] = "libre"
        return out

    def cambiar_aula(self, item, origen, destino):
        """Mueve la pieza de `origen` a `destino`; si destino está ocupada, intercambia las aulas."""
        o = self.obj(item)
        if item[0] != "s" or origen not in o.get("aulas", []):
            raise ErrorEdicion("Seleccione un aula de origen de la sesión.")
        if destino == origen:
            return False
        pos = self.posiciones(item)
        otros = {it for p_ in pos for it in self.ocupantes_aula(destino, *p_, excluir=item)}
        nuevo = self._instantanea()
        mi = self.obj(item, nuevo); mi["aulas"] = [destino if a == origen else a for a in mi["aulas"]]
        mi["aula_no_preferente"] = False
        for it in otros:
            x = self.obj(it, nuevo)
            if it[0] == "s":
                x["aulas"] = [origen if a == destino else a for a in x["aulas"]]
        self._confirmar(nuevo, "intercambiar el aula" if otros else "mover al aula libre")
        return bool(otros)

    # ------------------------------------------------------------------ libres
    def libres(self, tipo, marco, dia, idx):
        """Profesores o aulas libres en la posición: [(nombre, prohibido)]"""
        d, a, b = self.intervalo(marco, dia, idx)
        tp = "profesor" if tipo == "profesores" else "aula"
        ocup = {nm for it, t2, nm, dd, a2, b2 in self.ocupacion() if t2 == tp and dd == d and a2 < b and a < b2}
        lista = self.p.profesores if tp == "profesor" else self.p.aulas
        return [(e.nombre, e.plantilla.get((marco, dia, idx)) == PROHIBIDO) for e in lista if e.nombre not in ocup]

    # ------------------------------------------------------------------ nuevas (añadidos)
    def _nuevo_id(self):
        usados = {s.id for s in self.p.sesiones} | {op.get("id") for op in self.doc["editor"]["anadidos"]}
        n = max([int(x) for x in usados if x and str(x).isdigit()] + [0]) + 1
        return str(n)

    def _anadir(self, op, nc, texto):
        nuevo = self._instantanea()
        nuevo["editor"]["anadidos"].append(op)
        if nc:
            nuevo["no_colocadas"].append(nc)
        self._confirmar(nuevo, texto)

    def nueva_lectiva(self, materia, grupo, profesor, periodos=1, aula="", tarea="LEC"):
        sid = self._nuevo_id()
        self._anadir({"op": "lectiva", "id": sid, "materia": materia, "grupo": grupo, "profesor": profesor,
                      "periodos": int(periodos), "aulas": [aula] if aula else [], "tarea": tarea},
                     {"tipo": "sesion", "sesiones": [sid], "periodos": int(periodos), "tramos_len": int(periodos),
                      "aulas": [aula] if aula else [], "etiqueta": "nueva en el editor"}, "nuevas sesiones lectivas")
        return sid

    def nueva_simultanea(self, item, materia, grupo, profesor, aula="", tarea="LEC"):
        """Nueva sesión simultánea (en otra aula) a la pieza `item`: se coloca con ella y con sus demás piezas."""
        o = self.obj(item)
        if item[0] != "s":
            raise ErrorEdicion("Seleccione una sesión lectiva colocada.")
        ref = o["sesiones"][0]; sid = self._nuevo_id()
        nuevo = self._instantanea()
        nuevo["editor"]["anadidos"].append({"op": "simultanea", "id": sid, "ref": ref, "materia": materia, "grupo": grupo,
                                            "profesor": profesor, "aulas": [aula] if aula else [], "tarea": tarea})
        for lst in (nuevo["sesiones"], nuevo["no_colocadas"]):
            for pz in lst:
                if ref in pz.get("sesiones", []):
                    pz["sesiones"].append(sid)
                    if aula and "aulas" in pz and aula not in pz["aulas"]:
                        pz["aulas"].append(aula)
        self._confirmar(nuevo, "nuevas simultáneas en otra aula")
        return sid

    def nueva_complementaria(self, profesor, tarea, periodos=1):
        cid = "E" + self._nuevo_id()
        self._anadir({"op": "complementaria", "id": cid, "tarea": tarea, "profesor": profesor, "periodos": int(periodos)},
                     {"tipo": "complementaria", "nombre": tarea, "profesor": profesor, "id": cid, "cantidad": int(periodos)},
                     "nueva complementaria")
        return cid

    def nueva_guardia(self, servicio, profesor, n=1):
        self._anadir({"op": "guardia", "servicio": servicio, "profesor": profesor, "n": int(n)},
                     {"tipo": "guardia", "nombre": servicio, "profesor": profesor, "cantidad": int(n)},
                     "nueva guardia a un servicio")

    def nuevo_servicio(self, nombre, recreo=False):
        self._anadir({"op": "servicio", "nombre": nombre, "recreo": recreo}, None, "nuevo servicio de guardias")

    def nueva_reunion(self, nombre, profesores, n=1, doble=False):
        if nombre in self.reu_xml:
            raise ErrorEdicion("Ya existe una reunión con ese identificativo.")
        self._anadir({"op": "reunion", "nombre": nombre, "profesores": list(profesores), "n": int(n), "doble": bool(doble)},
                     {"tipo": "reunion", "nombre": nombre, "profesor": "", "cantidad": int(n)}, "nueva reunión")

    def modificar_sesion(self, sid, campo, valor):
        """Modifica una sesión lectiva (profesor, aula, materia, tarea) en la configuración en memoria."""
        s = self.ses[sid]
        viejo = {"profesor": s.profesor, "materia": s.materia, "tarea": s.tarea, "aula": (s.aulas or [""])[0]}[campo]
        if viejo == valor:
            return False
        nuevo = self._instantanea()
        nuevo["editor"]["anadidos"].append({"op": "modificar", "id": sid, "campo": campo, "valor": valor})
        if campo == "aula":
            for lst in (nuevo["sesiones"], nuevo["no_colocadas"]):
                for pz in lst:
                    if sid in pz.get("sesiones", []) and "aulas" in pz:
                        pz["aulas"] = [valor if a == viejo else a for a in pz["aulas"]] if viejo in pz["aulas"] else pz["aulas"] + [valor]
        self._confirmar(nuevo, "modificar las sesiones")
        return True

    def eliminar_fuera(self, nitem):
        """Eliminar una entrada de 'Sesiones sin hueco en el horario' (y, en su caso, de la configuración en memoria)."""
        nuevo = self._instantanea(); lst, i = self._lista(nuevo, nitem); nc = lst.pop(i)
        ops = nuevo["editor"]["anadidos"]; t = nc.get("tipo")
        if t == "sesion":
            ids = set(nc["sesiones"])
            nuevo["sesiones"] = [pz for pz in nuevo["sesiones"] if not ids & set(pz["sesiones"])]
            nuevo["no_colocadas"] = [x for x in nuevo["no_colocadas"] if not ids & set(x.get("sesiones", []))]
            for sid in ids:
                ops.append({"op": "eliminar_sesion", "id": sid})
        elif t == "guardia":
            ops.append({"op": "guardia", "servicio": nc["nombre"], "profesor": nc["profesor"], "n": -int(nc["cantidad"])})
        elif t == "reunion":
            ops.append({"op": "ajustar", "lista": "reuniones", "nombre": nc["nombre"], "n": -int(nc["cantidad"])})
        else:
            ops.append({"op": "ajustar", "lista": "complementarias", "nombre": nc.get("id", ""), "n": -int(nc["cantidad"])})
        self._confirmar(nuevo, "eliminar")

    def separar_fuera(self, nitem):
        """Separar (cadena 178): independiza las sesiones fuera del horario del resto de sesiones de la asignatura."""
        nc = self.obj(nitem)
        if nc.get("tipo") != "sesion":
            raise ErrorEdicion("Solo se pueden separar sesiones lectivas.")
        colocadas = {sid for pz in self.doc["sesiones"] for sid in pz["sesiones"]}
        otras = [x for x in self.doc["no_colocadas"] if x is not nc and set(x.get("sesiones", [])) & set(nc["sesiones"])]
        if not (set(nc["sesiones"]) & colocadas) and not otras:
            raise ErrorEdicion("Estas sesiones ya son independientes del resto de la asignatura.")
        nuevo = self._instantanea(); lst, i = self._lista(nuevo, nitem); dst = lst[i]
        base = int(self._nuevo_id()); mapa = {}
        for j, sid in enumerate(dst["sesiones"]):
            mapa[sid] = str(base + j)
            nuevo["editor"]["anadidos"].append({"op": "separar", "ref": sid, "id": mapa[sid], "n": 1})
        dst["sesiones"] = [mapa[s] for s in dst["sesiones"]]; dst["etiqueta"] = "separada en el editor"
        self._confirmar(nuevo, "separar"); return list(mapa.values())

    def duplicar_fuera(self, nitem):
        """Duplicar (cadena 390): duplica la entrada seleccionada de 'Sesiones sin hueco en el horario'."""
        nc = self.obj(nitem); t = nc.get("tipo")
        if t != "sesion":
            nuevo = self._instantanea(); lst, i = self._lista(nuevo, nitem); c = copy.deepcopy(lst[i]); n = int(c.get("cantidad", 1))
            ops = nuevo["editor"]["anadidos"]
            if t == "guardia":
                ops.append({"op": "guardia", "servicio": c["nombre"], "profesor": c["profesor"], "n": n})
            elif t == "reunion":
                ops.append({"op": "ajustar", "lista": "reuniones", "nombre": c["nombre"], "n": n})
            else:
                ops.append({"op": "ajustar", "lista": "complementarias", "nombre": c.get("id", ""), "n": n})
            lst.insert(i + 1, c); self._confirmar(nuevo, "duplicar"); return []
        nuevo = self._instantanea(); lst, i = self._lista(nuevo, nitem)
        base = int(self._nuevo_id()); nuevas = []
        for j, sid in enumerate(nc["sesiones"]):
            s = self.ses.get(sid)
            if s is None:
                continue
            nid = str(base + j)
            op = {"op": "lectiva" if not nuevas else "simultanea", "id": nid, "materia": s.materia, "grupo": s.grupo,
                  "profesor": s.profesor, "periodos": int(nc.get("periodos", 1) or 1),
                  "aulas": list(s.aulas[:1]), "tarea": s.tarea or "LEC"}
            if nuevas:
                op["ref"] = nuevas[0]
            nuevo["editor"]["anadidos"].append(op); nuevas.append(nid)
        c = copy.deepcopy(lst[i]); c["sesiones"] = nuevas; c["etiqueta"] = "duplicada en el editor"
        lst.insert(i + 1, c); self._confirmar(nuevo, "duplicar"); return nuevas

    # ------------------------------------------------------------------ recombinador (asistente 754/773)
    def _mover_doc(self, doc, item, marco, dia, idx):
        o = self.obj(item, doc); k = item[0]
        if k in "sr":
            o["marco"], o["dia"], o["tramos"] = marco, dia, self._cabe(marco, dia, idx, len(o["tramos"]))
        elif k == "c":
            self._cabe(marco, dia, idx, 1); o.update(marco=marco, dia=dia, tramo=idx)
        elif k == "g":
            if (marco, dia, idx) not in self.tramos:
                raise ErrorEdicion("Posición inexistente.")
            o.update(marco=marco, dia=dia, tramo=idx)

    def _fisicos(self, doc, item, occ=None):
        """Elementos colocados que chocan físicamente (profesor, grupo o aula) con `item` en `doc`."""
        occ = occ if occ is not None else self.ocupacion(doc)
        mios = [(tp, nm, d, a, b) for it, tp, nm, d, a, b in occ if it == item]
        out = []
        for it, tp, nm, d, a, b in occ:
            if it != item and it not in out and any(tp == t2 and nm == n2 and d == d2 and a < b2 and a2 < b for t2, n2, d2, a2, b2 in mios):
                out.append(it)
        return out

    def celdas_marco(self, marco, n=1):
        return [(marco, t.dia, t.indice) for t in sorted(self.p.marcos[marco].tramos, key=lambda t: (t.dia, t.indice))
                if t.tipo == "lectivo" and all(self.tramos.get((marco, t.dia, t.indice + j)) is not None and
                                               self.tramos[(marco, t.dia, t.indice + j)].tipo == "lectivo" for j in range(n))]

    def _marco_item(self, item):
        o = self.obj(item)
        if item[0] != "n":
            return o["marco"]
        if o.get("tipo") == "sesion":
            s = self.ses.get(o["sesiones"][0]) if o.get("sesiones") else None
            if s:
                return self.marcos_de("Grupos", s.grupo)[0]
        return list(self.p.marcos)[0]

    def recombinar(self, item, destino=None, max_mov=3, prof_fijos=(), grupos_fijos=(), observar=None,
                   max_sol=4, limite=4.0, parar=None):
        """Busca hasta `max_sol` soluciones para colocar `item` en `destino` (o en cualquier celda de su marco)
        moviendo como máximo `max_mov` elementos que choquen. Devuelve [{doc, movs, restr, avisos}] ordenadas."""
        import time
        t0 = time.monotonic(); prof_fijos, grupos_fijos = set(prof_fijos), set(grupos_fijos)
        marco = destino[0] if destino else self._marco_item(item)
        L = self._longitud(self.obj(item)) if item[0] == "n" and self.obj(item).get("tipo") == "sesion" else \
            (len(self.obj(item)["tramos"]) if item[0] in "sr" else 1)
        destinos = [destino] if destino else self.celdas_marco(marco, L)
        crudas, firmas = [], set()

        def movible(it, doc):
            rec = self.recursos(it, doc)
            return not any((tp == "profesor" and nm in prof_fijos) or (tp == "grupo" and nm in grupos_fijos) for tp, nm in rec)

        def pendientes(doc, fijos):
            occ = self.ocupacion(doc); out = []
            for f in fijos:
                out += [x for x in self._fisicos(doc, f, occ) if x not in out]
            return out

        def rec(doc, fijos, movs):
            if time.monotonic() - t0 > limite or (parar and parar()) or len(crudas) >= 40:
                return
            pend = [x for x in pendientes(doc, fijos)]
            if not pend:
                firma = repr(sorted((m[0], m[2]) for m in movs))
                if firma not in firmas:
                    firmas.add(firma); crudas.append((doc, list(movs)))
                return
            if len(movs) >= max_mov or len(movs) + len(pend) > max_mov:
                return
            c = pend[0]
            if c in fijos or c[0] == "n" or not movible(c, doc):
                return
            desde = self.posiciones(c, doc)[0]; n = len(self.posiciones(c, doc))
            for p in self.celdas_marco(self.obj(c, doc)["marco"], n):
                if p == desde:
                    continue
                d2 = copy.deepcopy(doc)
                try:
                    self._mover_doc(d2, c, *p)
                except ErrorEdicion:
                    continue
                if any(x in fijos for x in self._fisicos(d2, c)):
                    continue
                rec(d2, fijos + [c], movs + [(c, desde, p)])
                if time.monotonic() - t0 > limite or len(crudas) >= 40:
                    return

        for dst in destinos:
            prop = self.proponer_agregar(item, *dst) if item[0] == "n" else self.proponer_mover(item, *dst)
            if prop.invalida or prop.doc is None:
                continue
            nuevo = item
            if item[0] == "n":
                tipo = self.obj(item).get("tipo")
                k, lst = {"sesion": ("s", "sesiones"), "guardia": ("g", "guardias"), "reunion": ("r", "reuniones")}.get(tipo, ("c", "complementarias"))
                nuevo = f"{k}:{len(prop.doc[lst]) - 1}"
            desde = self.posiciones(item)[0] if item[0] != "n" else None
            rec(prop.doc, [nuevo], [(item, desde, dst)])
            if time.monotonic() - t0 > limite or len(crudas) >= 40:
                break
        base = defaultdict(int)
        for e in self._errores(self.doc):
            base[e] += 1
        sols = []
        for doc, movs in sorted(crudas, key=lambda x: len(x[1]))[:12]:
            ea = dict(base); nuevos = []
            for e in self._errores(doc):
                if ea.get(e, 0) > 0:
                    ea[e] -= 1
                else:
                    nuevos.append(e)
            if observar is not None and any(e[0] in observar for e in nuevos):
                continue
            sols.append({"doc": doc, "movs": movs, "restr": len(nuevos), "avisos": sum(1 for m in movs[1:] if m[0][0] in "gr"),
                         "errores": nuevos})
        sols.sort(key=lambda x: (len(x["movs"]), x["restr"], x["avisos"]))
        self.tiempo_recombinar = time.monotonic() - t0
        return sols[:max_sol]

    def aplicar_solucion(self, sol):
        self._confirmar(copy.deepcopy(sol["doc"]), "recombinar")

    def categorias_restricciones(self):
        """Categorías de reglas del comprobador (para «Restricciones que se observarán estrictamente»)."""
        cats = []
        for e in self._errores(self.doc):
            if e[0] not in cats:
                cats.append(e[0])
        base = ["Prohibición de la plantilla", "Máximo diario", "Huecos", "Sesiones en distinto día", "Aula no válida"]
        return list(dict.fromkeys(cats + base))

    def descripcion_fuera(self, nitem):
        """Fila de la lista 'Sesiones sin hueco en el horario': Materia, Grupo, Profesorado, Tmp, Aula, Aulas Alter."""
        nc = self.obj(nitem); t = nc.get("tipo")
        if t == "sesion":
            ss = [self.ses[s] for s in nc["sesiones"] if s in self.ses]
            return ["/".join(dict.fromkeys(s.materia for s in ss)), "/".join(dict.fromkeys(s.grupo for s in ss)),
                    "/".join(dict.fromkeys(s.profesor for s in ss if s.profesor)), str(nc.get("periodos", "")),
                    ", ".join(nc.get("aulas") or [a for s in ss for a in s.aulas]),
                    ", ".join(a for s in ss for a in s.alternativas)]
        if t == "guardia":
            return [f"Guardia {nc['nombre']}", "", nc["profesor"], str(nc["cantidad"]), "", ""]
        if t == "reunion":
            return [f"Reunión {nc['nombre']}", "", f"{len(self.integrantes_reunion(nc['nombre']))} profesores",
                    str(nc["cantidad"]), "", ""]
        return [nc["nombre"], "", nc["profesor"], str(nc["cantidad"]), "", ""]

    # ------------------------------------------------------------------ guardar / validar
    def comprobar(self):
        return CK.comprobar(self.p, self.doc)

    def guardar(self, ruta=None):
        ruta = ruta or self.ruta
        if not ruta.lower().endswith(RES.EXTENSION):
            ruta += RES.EXTENSION
        if os.path.exists(ruta):
            shutil.copy2(ruta, ruta + ".bak")            # copia de seguridad previa
        doc = copy.deepcopy(self.doc)
        e = doc.setdefault("estadisticas", {})
        e["no_colocadas"] = sum(int(x.get("periodos", 0)) for x in doc["no_colocadas"] if x.get("tipo") == "sesion")
        e["editado"] = True
        RES.guardar(doc, ruta); self.ruta = ruta; self.modificado = False
        return ruta

    def recuperar_copia(self):
        bak = self.ruta + ".bak"
        if not os.path.exists(bak):
            raise ErrorEdicion("No hay copia de seguridad de este resultado.")
        nuevo = RES.cargar(bak); self._normalizar(nuevo)
        self._confirmar(nuevo, "recuperar copia de seguridad")

    # ------------------------------------------------------------------ proyección sobre el Planificador
    def proyectar(self, destino, lectivas=True, guardias=True):
        """Crea una copia de la configuración con las posiciones del resultado prefijadas (chinchetas)."""
        if os.path.abspath(destino) == os.path.abspath(self.ruta_xghc):
            raise ErrorEdicion("No se sobrescribe la configuración original; elija otro archivo.")
        p = xghc.cargar(self.ruta_xghc)
        self._aplicar_anadidos(p, self.doc["editor"]["anadidos"])
        cont = getattr(p, "contenedor", None)
        p = xghc.construir(p.doc, p.ruta)
        if getattr(p, "contenedor", None) is None:
            p.contenedor = cont
        arbol = ED.Arbol(p.doc.raiz)
        ses = {s.id: s for s in p.sesiones}
        n = 0

        def fijar(owner, posiciones, marco):
            nonlocal n
            pl = {k: v for k, v in xghc.leer_plantilla(owner, marco).items() if v != PREFIJADO}
            for k in posiciones:
                pl[k] = PREFIJADO
            if ED.volcar_plantilla(arbol, owner, pl, marco):
                n += 1
        if lectivas:
            por_owner = defaultdict(set); marco_owner = {}
            for pz in self.doc["sesiones"]:
                for sid in pz["sesiones"]:
                    s = ses.get(sid)
                    if s is not None:
                        por_owner[id(s.xml_plantilla)] |= {(pz["marco"], pz["dia"], t) for t in pz["tramos"]}
                        marco_owner[id(s.xml_plantilla)] = (s.xml_plantilla, s.marco)
            for k, pos in por_owner.items():
                fijar(marco_owner[k][0], pos, marco_owner[k][1])
            reu = {e.nombre: e for e in p.reuniones}
            pr = defaultdict(set)
            for r in self.doc["reuniones"]:
                pr[r["reunion"]] |= {(r["marco"], r["dia"], t) for t in r["tramos"]}
            for nm, pos in pr.items():
                if nm in reu:
                    fijar(reu[nm].datos["_xml"], pos, reu[nm].marco)
            com = {_t(e.datos["_xml"], "identificador"): e for e in p.complementarias}
            pc = defaultdict(set)
            for c in self.doc["complementarias"]:
                pc[c.get("id")].add((c["marco"], c["dia"], c["tramo"]))
            for cid, pos in pc.items():
                if cid in com:
                    fijar(com[cid].datos["_xml"], pos, com[cid].marco)
        if guardias:
            gua = {e.nombre: e for e in p.guardias}
            pg = defaultdict(set)
            for g in self.doc["guardias"]:
                pg[(g["servicio"], g["profesor"])].add((g["marco"], g["dia"], g["tramo"]))
            for (sv, prof), pos in pg.items():
                if sv in gua:
                    ix = NL.integrante_xml(gua[sv].datos["_xml"], prof)
                    if ix is not None:
                        fijar(ix, pos, gua[sv].marco)
        xghc.guardar(p, destino)
        return n
