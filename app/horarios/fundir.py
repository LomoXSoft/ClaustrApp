"""«Fundir archivos...» (menú [32984] «Añade al archivo abierto los datos de otro archivo»).

Texto del diálogo «Fundir» y mensaje final (cadena 230) según webinar_avanzado_3de4.
Reglas: prevalece el archivo abierto (marco horario, criterios, opciones generales y elementos ya existentes
con el mismo nombre); se añaden los elementos nuevos y las sesiones lectivas que no estén ya (comparando su
contenido sin el id), renumerando ids y referencias (días distintos, bloques de simultáneas)."""
from __future__ import annotations
from .textos import TX
import copy
import xml.etree.ElementTree as ET
from . import edicion as ED

TITULO = "Fundir"
TEXTO = ("A continuación se pedirá abrir otro archivo de configuración para fusionar sus datos con el del archivo "
         "actualmente abierto. El marco horario y el resto de opciones que prevalecen serán las del horario actual.")
SIN_INCIDENCIAS = TX("fusion_terminada_sin_problemas")

LISTAS = ["aulas", "tareas", "departamentos", "profesores", "materias", "cursos", "grupos",
          "reuniones", "guardias", "complementarias"]


def _firma(e, quitar_id=True):
    c = copy.deepcopy(e)
    if quitar_id:
        c.attrib.pop("id", None)
    for x in c.iter():
        x.text = (x.text or "").strip() or None; x.tail = None
    return ET.tostring(c)


def _nombre(e):
    return (e.findtext("nombre") or e.get("nombre") or "").strip()


def _marcos(raiz):
    return {m.get("id") or _nombre(m) for m in raiz.iter("marcoHorario")}


def fundir(arbol: ED.Arbol, otra) -> list[str]:
    """Fusiona la raíz XML `otra` en `arbol` (archivo actual). Devuelve la lista de incidencias."""
    raiz = arbol.raiz; inc = []
    marcos = _marcos(raiz); otros_marcos = _marcos(otra) - marcos
    if otros_marcos:
        inc.append(TX("marcos_archivo_anadido_no_estan") + ", ".join(sorted(otros_marcos)))
    # 1. listas con nombre
    añadidos = 0
    for lista in LISTAS:
        cont, item = ED.CONTENEDOR[lista]
        oc = otra.find(cont)
        if oc is None:
            continue
        c = raiz.find(cont)
        if c is None:
            c = ED.insertar_hijo(arbol, raiz, ED.nuevo(cont))
        existentes = {_nombre(e): e for e in c.findall(item) if _nombre(e)}
        firmas = {_firma(e) for e in c.findall(item)}
        for e in oc.findall(item):
            n = _nombre(e)
            if not n:              # sin nombre (complementarias, guardias): se añade si no hay una idéntica
                if _firma(e) not in firmas:
                    ED.insertar_hijo(arbol, c, copy.deepcopy(e)); firmas.add(_firma(e)); añadidos += 1
                continue
            if n in existentes:
                if _firma(existentes[n]) != _firma(e):
                    inc.append(f"{item.capitalize()} «{n}»: se mantienen los datos del horario actual.")
                continue
            ED.insertar_hijo(arbol, c, copy.deepcopy(e)); añadidos += 1
    # conjuntos de aulas
    oc = otra.find("conjuntoDeAulas")
    if oc is not None:
        c = raiz.find("conjuntoDeAulas")
        if c is None:
            c = ED.insertar_hijo(arbol, raiz, ED.nuevo("conjuntoDeAulas"))
        ya = {_nombre(e) for e in c}
        for e in oc:
            if _nombre(e) not in ya:
                ED.insertar_hijo(arbol, c, copy.deepcopy(e))
    # 2. sesiones
    sl = raiz.find("sesionesLectivas")
    if sl is None:
        sl = ED.insertar_hijo(arbol, raiz, ED.nuevo("sesionesLectivas"))
    firmas = {}
    for s in sl.findall("sesion"):
        firmas.setdefault(_firma(_sin_refs(s)), s.get("id"))
    sig = int(ED._siguiente_id(raiz)); mapa = {}; nuevas = []
    osl = otra.find("sesionesLectivas")
    for s in (osl.findall("sesion") if osl is not None else []):
        f = _firma(_sin_refs(s))
        if f in firmas:
            mapa[s.get("id")] = firmas[f]; continue
        mapa[s.get("id")] = str(sig); firmas[f] = str(sig); sig += 1
        nuevas.append(s)
    for s in nuevas:
        n = copy.deepcopy(s); n.set("id", mapa[s.get("id")]); _renumerar(n, mapa)
        ED.insertar_hijo(arbol, sl, n)
    # 3. bloques de simultáneas
    osim = otra.find("listasDeRelacion/simultaneas")
    if osim is not None:
        sim = ED.asegurar(arbol, raiz, "listasDeRelacion/simultaneas")
        ya = {tuple(sorted(x.text.strip() for x in b.iter("sesion"))) for b in sim.findall("bloqueDeSesiones")}
        for b in osim.findall("bloqueDeSesiones"):
            ids = [mapa.get((x.text or "").strip()) for x in b.iter("sesion")]
            if None in ids:
                inc.append(f"Bloque de simultáneas {b.get('id')}: referencia a sesiones inexistentes; se omite."); continue
            if tuple(sorted(ids)) in ya:
                continue
            n = copy.deepcopy(b); _renumerar(n, mapa); n.set("id", str(sig)); sig += 1
            ED.insertar_hijo(arbol, sim, n)
    # 4. referencias a elementos que faltan
    nombres = {l: set(ED.nombres(raiz, l)) for l in ("profesores", "grupos", "materias", "aulas")}
    for s in nuevas:
        for tag, l in (("profesor", "profesores"), ("grupo", "grupos"), ("materia", "materias")):
            v = (s.findtext(tag) or "").strip()
            if v and v not in nombres[l]:
                inc.append(f"Sesión {mapa[s.get('id')]}: {tag} «{v}» inexistente.")
    return inc


def _sin_refs(s):
    c = copy.deepcopy(s)
    for tag in ("enDistintoDia", "sesionesSimultaneas"):
        for x in c.findall(tag):
            c.remove(x)
    return c


def _renumerar(e, mapa):
    for tag in ("enDistintoDia", "sesionesSimultaneas", "sesiones"):
        for cont in ([e] if e.tag == tag else []) + list(e.iter(tag)):
            for x in cont.iter("sesion"):
                if x is not e and (x.text or "").strip() in mapa:
                    x.text = mapa[x.text.strip()]
