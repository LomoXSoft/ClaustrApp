"""Lectura y escritura de archivos .xghc (configuración del planificador).

Contenedor observado (ver docs/formato_xghc.md):

    GZIP( prefijo(7 bytes) + XML ISO-8859-1 + cola binaria )

* gzip: cabecera de 10 bytes sin nombre ni fecha (mtime 0, SO 0x0a); deflate
  equivalente a zlib nivel 6. Al guardar se reutiliza la cabecera original y se
  comprime con nivel 6: un archivo no modificado se reproduce byte a byte.
* prefijo: 2 bytes fijos + 1 byte (varía con la versión del formato) + uint32 LE
  con la longitud del XML + 1. Solo se recalcula ese uint32; el resto se copia.
* cola: se conserva byte a byte, sin interpretarla ni modificarla.

El XML se analiza con expat guardando la posición de cada elemento en el texto
original; al serializar, todo elemento no modificado se copia literalmente, así
que el archivo guardado solo difiere en lo editado.
"""
from __future__ import annotations
import gzip
import struct
import zlib
import xml.etree.ElementTree as ET
from xml.parsers import expat
from dataclasses import dataclass, field
from .modelo import Proyecto, Marco, Tramo, Elemento, Sesion

DECL = b'<?xml version="1.0" encoding="ISO-8859-1"?>'
FIN = b"</datosGHC>"


# ---------------------------------------------------------------- contenedor
@dataclass
class Contenedor:
    gz_cabecera: bytes | None      # 10 bytes de cabecera gzip (None si el archivo no venía comprimido)
    prefijo: bytes                 # bytes previos al XML (dentro del gzip)
    xml: bytes                     # XML original
    cola: bytes                    # bytes posteriores a </datosGHC> (se copian tal cual)

    def campo_longitud(self):
        """uint32 LE del prefijo que guarda la longitud del XML (+1), o None."""
        if len(self.prefijo) >= 7:
            v = struct.unpack_from("<I", self.prefijo, 3)[0]
            if v - len(self.xml) in (0, 1, 2):
                return v
        return None


def leer_contenedor(ruta: str) -> Contenedor:
    with open(ruta, "rb") as f:
        bruto = f.read()
    cab = None
    datos = bruto
    if bruto[:2] == b"\x1f\x8b":
        cab = bruto[:10]
        datos = gzip.decompress(bruto)
    i = datos.find(b"<?xml")
    if i < 0:
        i = datos.find(b"<datosGHC")
    if i < 0:
        raise ValueError("No parece un archivo .xghc (no se encuentra <datosGHC>)")
    fin = datos.find(FIN, i)
    if fin < 0:
        raise ValueError("Archivo .xghc incompleto (falta </datosGHC>)")
    fin += len(FIN)
    return Contenedor(cab, datos[:i], datos[i:fin], datos[fin:])


def empaquetar(c: Contenedor, xml: bytes) -> bytes:
    """Construye los bytes del archivo con el XML nuevo y el resto del contenedor original."""
    pre = c.prefijo
    v = c.campo_longitud()
    if v is not None:
        nuevo = v - len(c.xml) + len(xml)
        pre = pre[:3] + struct.pack("<I", nuevo) + pre[7:]
    datos = pre + xml + c.cola
    if c.gz_cabecera is None:
        return datos
    cab = c.gz_cabecera
    if cab[3] != 0:  # con campos opcionales (no observado): cabecera mínima equivalente
        cab = b"\x1f\x8b\x08\x00\x00\x00\x00\x00\x00\x0a"
    comp = zlib.compressobj(6, zlib.DEFLATED, -15, 8)
    cuerpo = comp.compress(datos) + comp.flush()
    return cab + cuerpo + struct.pack("<II", zlib.crc32(datos) & 0xFFFFFFFF, len(datos) & 0xFFFFFFFF)


def leer_xml_bruto(ruta: str) -> bytes:
    return leer_contenedor(ruta).xml


# ---------------------------------------------------------------- XML con posiciones
class Documento:
    """Árbol ElementTree + texto original + posición de cada elemento en él."""

    def __init__(self, xml: bytes):
        self.base = xml
        self.spans: dict[int, tuple[int, int]] = {}
        self.firmas: dict[int, int] = {}
        self._vivos = []  # mantiene vivos los elementos para que id() sea estable
        self.raiz = self._parsear(xml)
        self._firmar(self.raiz, self.firmas)
        from . import semanas as _SEM
        _SEM.a_interno(self.raiz)          # semanas: distribucionPeriodica (XSD) -> forma interna

    def _parsear(self, xml):
        p = expat.ParserCreate()  # la codificación se toma de la declaración XML
        p.buffer_text = True
        p.ordered_attributes = True
        pila, raiz, ultimo = [], None, None
        abiertos = []

        def ini(tag, attrs):
            nonlocal raiz, ultimo
            e = ET.Element(tag, dict(zip(attrs[0::2], attrs[1::2])))
            e.text = None; e.tail = None
            if pila:
                pila[-1].append(e)
            else:
                raiz = e
            pila.append(e); abiertos.append(p.CurrentByteIndex); ultimo = None

        def fin(tag):
            nonlocal ultimo
            e = pila.pop(); a = abiertos.pop(); b = p.CurrentByteIndex
            if xml[b:b + 2] == b"</":
                b = xml.index(b">", b) + 1
            else:  # <x/> autocerrado: el índice apunta al propio inicio
                b = xml.index(b">", a) + 1
            self.spans[id(e)] = (a, b); self._vivos.append(e)
            ultimo = e

        def car(t):
            if not pila:
                return
            if ultimo is not None and len(pila[-1]) and pila[-1][-1] is ultimo:
                ultimo.tail = (ultimo.tail or "") + t
            else:
                pila[-1].text = (pila[-1].text or "") + t

        p.StartElementHandler = ini; p.EndElementHandler = fin; p.CharacterDataHandler = car
        p.Parse(xml, True)
        return raiz

    def _firmar(self, e, dest):
        h = hash((e.tag, tuple(e.attrib.items()), e.text, tuple((self._firmar(c, dest), c.tail) for c in e)))
        dest[id(e)] = h
        return h

    # ---------------- serialización
    @staticmethod
    def _esc(t):
        return (t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                .replace("'", "&apos;").replace('"', "&quot;"))

    def serializar(self) -> bytes:
        from . import semanas as _SEM
        volver = _SEM.a_xsd(self.raiz)     # semanas: forma interna -> distribucionPeriodica (XSD)
        try:
            return self._serializar()
        finally:
            volver()

    def _serializar(self) -> bytes:
        actuales = {}
        self._firmar(self.raiz, actuales)
        partes = []

        def emit(e):
            k = id(e)
            if k in self.spans and actuales[k] == self.firmas.get(k):
                a, b = self.spans[k]; partes.append(self.base[a:b]); return
            at = "".join(f' {n}="{self._esc(v)}"' for n, v in e.attrib.items())
            partes.append(f"<{e.tag}{at}>".encode("iso-8859-1", "xmlcharrefreplace"))
            if e.text:
                partes.append(self._esc(e.text).encode("iso-8859-1", "xmlcharrefreplace"))
            for c in e:
                emit(c)
                if c.tail:
                    partes.append(self._esc(c.tail).encode("iso-8859-1", "xmlcharrefreplace"))
            partes.append(f"</{e.tag}>".encode("iso-8859-1"))

        a = self.spans.get(id(self.raiz), (0, 0))[0]
        partes.append(self.base[:a] if a else DECL + b"\n")
        emit(self.raiz)
        return b"".join(partes)


# ---------------------------------------------------------------- modelo desde el árbol
def _t(e, tag, defecto=""):
    x = e.find(tag)
    return (x.text or "").strip() if x is not None and x.text else defecto


def leer_plantilla(e, marco_defecto="A"):
    p = {}
    pl = e.find("plantilla")
    if pl is not None:
        for tr in pl.findall("tramo"):
            try:
                k = (tr.get("marco", marco_defecto), int(tr.get("dia")), int(tr.get("indice")))
            except (TypeError, ValueError):
                continue
            p[k] = (tr.text or "").strip()
    return p


def _hijos_texto(e):
    return {c.tag: (c.text or "").strip() for c in e if len(c) == 0}


def _lista(raiz, cont, item, marco_attr=None):
    out = []
    c = raiz.find(cont)
    if c is None:
        return out
    for e in c.findall(item):
        nombre = _t(e, "nombre") or _t(e, "identificador")
        marco = e.get(marco_attr, "A") if marco_attr else "A"
        el = Elemento(nombre=nombre, datos=_hijos_texto(e), plantilla=leer_plantilla(e, marco), marco=marco)
        el.datos["_xml"] = e
        out.append(el)
    return out


def _num(n):
    try:
        return f"{float(n):g}"
    except ValueError:
        return n


def tmp_de(s):
    ds = s.find("distribucionSemanal")
    if ds is None:
        return ""
    fija = ds.find("distribucionFija")
    if fija is not None:
        return "".join(_num((n.text or "").strip()) for n in fija.findall("numSesiones"))
    var = ds.find("distribucionVariable")
    if var is not None:
        ini = var.find("distribucionInicial")
        txt = "".join((n.text or "").strip() for n in ini.findall("numSesiones")) if ini is not None else ""
        return f"{_num(_t(var, 'numSesiones'))}*" + (f" ({txt})" if txt else "")
    return ""


def construir(doc: Documento, ruta: str = "") -> Proyecto:
    raiz = doc.raiz
    p = Proyecto(ruta=ruta, version=_t(raiz, "version"))
    p.doc = doc
    md = raiz.find("marcosDeHorario")
    if md is not None:
        for m in md.findall("marcoHorario"):
            mid = m.get("id", "A")
            marco = Marco(id=mid, nombre=m.get("nombre", f"Marco {mid}"))
            for t in m.findall("tramo"):
                marco.tramos.append(Tramo(marco=_t(t, "submarco", mid), dia=int(_t(t, "dia", "0")),
                                          indice=int(_t(t, "indice", "0")), entrada=_t(t, "horaEntrada")[:5],
                                          salida=_t(t, "horaSalida")[:5], tipo=_t(t, "Tipo", "lectivo"),
                                          clave=_t(t, "clavX")))
            p.marcos[mid] = marco
    p.profesores = _lista(raiz, "profesores", "profesor")
    p.grupos = _lista(raiz, "grupos", "grupo", "submarco")
    for g in p.grupos:
        g.datos["aula"] = _t(g.datos["_xml"], "aula")
    p.materias = _lista(raiz, "materias", "materia")
    p.aulas = _lista(raiz, "aulas", "aula")
    p.cursos = _lista(raiz, "cursos", "curso")
    p.departamentos = _lista(raiz, "departamentos", "departamento")
    p.tareas = _lista(raiz, "tareas", "tarea")
    p.reuniones = _lista(raiz, "reuniones", "reunion", "subMarco")
    p.guardias = _lista(raiz, "guardias", "guardia", "subMarco")
    p.complementarias = _lista(raiz, "complementarias", "complementaria", "subMarco")
    ca = raiz.find("conjuntoDeAulas")
    if ca is not None:
        for c in ca:
            p.conjuntos_aulas[c.get("nombre", c.tag)] = [(a.text or "").strip() for a in c.findall("aula")]
    sl = raiz.find("sesionesLectivas")
    if sl is not None:
        for s in sl.findall("sesion"):
            grupo = _t(s, "grupo")
            marco = p.marco_de_grupo(grupo)
            la = s.find("listaDeAulas"); alt = s.find("listaDeAlternativas")
            og = s.find("otrosGrupos"); edd = s.find("enDistintoDia")
            dur = _t(s, "duracionSemanal", "0") or "0"
            try:
                dur = float(dur)
            except ValueError:
                dur = 0.0
            ses = Sesion(
                id=s.get("id", ""), materia=_t(s, "materia"), grupo=grupo, profesor=_t(s, "profesor"),
                tmp=tmp_de(s), aulas=[(a.text or "").strip() for a in la.findall("aula")] if la is not None else [],
                alternativas=[(a.text or "").strip() for a in alt] if alt is not None else [],
                tarea=_t(s, "tarea"), grupo_materia=_t(s, "grupoMateria"), departamento=_t(s, "departamento"),
                duracion=dur,
                otros_grupos=[(g.text or "").strip() for g in og.findall("grupo")] if og is not None else [],
                en_distinto_dia=[(x.text or "").strip() for x in edd.iter("sesion")] if edd is not None else [],
                en_dias_seguidos=_t(edd, "enDiasSeguidos") if edd is not None else "",
                plantilla=leer_plantilla(s, marco), marco=marco)
            ses.xml = s; ses.xml_plantilla = s
            p.sesiones.append(ses)
    rel = raiz.find("listasDeRelacion/simultaneas")
    if rel is not None:
        por_id = {s.id: s for s in p.sesiones}
        for b in rel.findall("bloqueDeSesiones"):
            compartida = None
            for x in b.iter("sesion"):
                s = por_id.get((x.text or "").strip())
                if s:
                    s.bloque = b.get("id")
                    if not s.plantilla:  # la plantilla del bloque es común a sus sesiones
                        if compartida is None:
                            compartida = leer_plantilla(b, s.marco)
                        s.plantilla = compartida; s.xml_plantilla = b
    return p


def cargar(ruta: str) -> Proyecto:
    c = leer_contenedor(ruta)
    p = construir(Documento(c.xml), ruta)
    p.contenedor = c
    return p


def serializar(p: Proyecto) -> bytes:
    return p.doc.serializar()


def guardar(p: Proyecto, ruta: str) -> bytes:
    """Escribe el proyecto en `ruta` (escritura atómica). Devuelve el XML escrito."""
    import os
    xml = serializar(p)
    datos = empaquetar(p.contenedor, xml)
    tmp = ruta + ".tmp~"
    with open(tmp, "wb") as f:
        f.write(datos)
    os.replace(tmp, ruta)
    return xml
