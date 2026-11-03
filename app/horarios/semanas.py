"""Horarios de varias semanas («Varias semanas», ref. 622/625).

Representación (según XML-GHC, GHCFile.xsd): los días de los marcos se numeran seguidos para todas las semanas
(0..35 como máximo: hasta 6 semanas de hasta 6 días) y <datosGHC>/<periodos>/<periodo> (nombre, diaFin) agrupa los
días en semanas. En el .xghc que escribe este programa cada sesión conserva su <distribucionSemanal> (la distribución de UNA
semana, que se repite en cada semana asignada) y añade, si se le asignan semanas concretas:
  <enPeriodos><refPeriodo>s1</refPeriodo>…</enPeriodos>
  <mismaPosicionDistintosPeriodos>ignorar|preferente|obligatorio|procuraEvitar|prohibido</…>
(en el XML-GHC estándar ambos van dentro de <distribucionPeriodica>/<distribucionPeriodicaFija>; la conversión se
hará en el exportador). Sin <enPeriodos> la sesión se imparte en todas las semanas.
"""
from __future__ import annotations

MISMA = ["ignorar", "preferente", "obligatorio", "procuraEvitar", "prohibido"]


def _hijo(e, tag):
    return e.find(tag) if e is not None else None


def periodos(raiz, dias):
    """[(nombre, [días])] en orden. Sin <periodos>: una sola semana con todos los días."""
    dias = sorted(set(dias))
    px = _hijo(raiz, "periodos")
    lst = []
    for p in (px.findall("periodo") if px is not None else []):
        try:
            lst.append(((p.findtext("nombre") or "").strip(), int((p.findtext("diaFin") or "0").strip())))
        except ValueError:
            pass
    lst.sort(key=lambda x: x[1])
    if not lst:
        return [("s1", dias)]
    out, ini = [], -1
    for n, fin in lst:
        out.append((n, [d for d in dias if ini < d <= fin])); ini = fin
    resto = [d for d in dias if d > ini]
    if resto:
        out.append((f"s{len(out) + 1}", resto))
    return out


def num_semanas(raiz):
    px = _hijo(raiz, "periodos")
    return max(1, len(px.findall("periodo")) if px is not None else 0)


def de_sesion(sx, nombres):
    """(semanas en las que se imparte, modo de posición entre semanas)."""
    ep = _hijo(sx, "enPeriodos")
    refs = [(r.text or "").strip() for r in ep.findall("refPeriodo")] if ep is not None else []
    refs = [r for r in refs if r in nombres] if refs else list(nombres)
    modo = (sx.findtext("mismaPosicionDistintosPeriodos") or "ignorar").strip() if sx is not None else "ignorar"
    return refs, (modo if modo in MISMA else "ignorar")


def texto_en_semanas(sx, nombres):
    """Columna «En semanas» de la lista de sesiones: «s1 s2 - -»."""
    refs, _ = de_sesion(sx, nombres)
    return " ".join(n if n in refs else "-" for n in nombres)


# ---------------------------------------------------------------- edición
def fijar_num_semanas(p, n, ED):
    """Pasa el horario a n semanas (1..6): replica los tramos de la semana 1 en cada marco y reescribe <periodos>."""
    from . import modelo as M
    n = max(1, min(6, int(n)))
    raiz = p.doc.raiz
    arbol = ED.Arbol(raiz)
    base = {}
    for m in p.marcos.values():
        pers = periodos(raiz, m.dias)
        d1 = pers[0][1] if pers else m.dias
        base[m.id] = [t for t in m.tramos if t.dia in d1]
    paso = max([len({t.dia for t in b}) for b in base.values()] + [1])
    md = raiz.find("marcosDeHorario")
    for mx in md.findall("marcoHorario"):
        mid = mx.get("id", "A")
        b = base.get(mid, [])
        dias1 = sorted({t.dia for t in b})
        xs = [t for t in mx.findall("tramo") if int(t.findtext("dia") or 0) not in dias1]
        for t in xs:
            ED.quitar_hijo(arbol, mx, t)
        modelos = {(int(t.findtext("dia") or 0), int(t.findtext("indice") or 0)): t for t in mx.findall("tramo")}
        import copy
        for w in range(1, n):
            for (d, i), t in sorted(modelos.items()):
                c = copy.deepcopy(t); c.find("dia").text = str(d + w * paso)
                ED.insertar_hijo(arbol, mx, c)
        p.marcos[mid].tramos = [t for t in p.marcos[mid].tramos if t.dia in dias1] + \
            [M.Tramo(marco=t.marco, dia=t.dia + w * paso, indice=t.indice, entrada=t.entrada, salida=t.salida,
                     tipo=t.tipo, clave=t.clave) for w in range(1, n) for t in base.get(mid, [])]
    _plantillas_semanas(raiz, num_semanas(raiz), n, paso,
                        {mid: sorted({t.dia for t in b}) for mid, b in base.items()}, ED, arbol)
    _recargar_plantillas(p)
    px = raiz.find("periodos")
    if px is not None:
        ED.quitar_hijo(arbol, raiz, px)
    if n > 1:
        px = ED.nuevo("periodos", hijos=[ED.nuevo("periodo", hijos=[ED.nuevo("nombre", f"s{w + 1}"),
                                                                    ED.nuevo("diaFin", str((w + 1) * paso - 1))])
                                         for w in range(n)])
        ED.insertar_hijo(arbol, raiz, px, pos=list(raiz).index(md))
    return n


def _plantillas_semanas(raiz, n_antes, n, paso, dias1, ED, arbol):
    """Las plantillas (<tramo marco dia indice> fuera de marcosDeHorario) se guardan por día absoluto, así que el
    formato admite una plantilla distinta por semana. Al añadir semanas se copia en ellas la plantilla de la semana 1;
    las semanas que ya existían conservan sus marcas; al quitar semanas se borran las marcas de sus días."""
    md = raiz.find("marcosDeHorario")
    excl = set(md.iter()) if md is not None else set()
    import copy
    defecto = next(iter(dias1)) if len(dias1) == 1 else "A"
    for padre in list(raiz.iter()):
        if padre in excl:
            continue
        trs = [t for t in padre if t.tag == "tramo" and t.get("dia") is not None and t.get("indice") is not None]
        if not trs:
            continue
        for t in trs:
            try:
                d = int(t.get("dia"))
            except ValueError:
                continue
            if d >= n * paso:
                ED.quitar_hijo(arbol, padre, t)
            elif d < paso and d in dias1.get(t.get("marco", defecto), range(paso)):
                for w in range(max(1, n_antes), n):
                    c = copy.deepcopy(t); c.set("dia", str(d + w * paso))
                    ED.insertar_hijo(arbol, padre, c, pos=list(padre).index(t) + 1)


def _recargar_plantillas(p):
    """Refresca en el modelo las plantillas leídas del XML (sesiones y elementos)."""
    from . import xghc
    for s in p.sesiones:
        x = getattr(s, "xml_plantilla", None)
        if x is not None:
            s.plantilla = xghc.leer_plantilla(x, s.marco)


def fijar_sesion(sx, refs, modo, ED, arbol, nombres):
    for tag in ("enPeriodos", "mismaPosicionDistintosPeriodos"):
        e = sx.find(tag)
        if e is not None:
            ED.quitar_hijo(arbol, sx, e)
    if refs and set(refs) != set(nombres):
        ED.insertar_hijo(arbol, sx, ED.nuevo("enPeriodos", hijos=[ED.nuevo("refPeriodo", r) for r in nombres if r in refs]))
    if modo and modo != "ignorar":
        ED.insertar_hijo(arbol, sx, ED.nuevo("mismaPosicionDistintosPeriodos", modo))


# ---------------------------------------------------------------- formato en fichero (GHCFile.xsd)
# En memoria cada sesión guarda <distribucionSemanal> y, como hermanos, <enPeriodos> y <mismaPosicionDistintosPeriodos>
# (lo que leen el motor, el comprobador y las listas). En el fichero, con varias semanas, se escribe como en el XSD:
#   <distribucionPeriodica><distribucionPeriodicaFija><distribucionSemanal>…</distribucionSemanal>
#        <enPeriodos><refPeriodo>s1</refPeriodo>…</enPeriodos></distribucionPeriodicaFija></distribucionPeriodica>
#   (variable: <distribucionPeriodicaVariable><distribucionTotal>…</distribucionTotal><enPeriodos>…</enPeriodos>
#    [numMaximoDeSesionesEnPeriodo][numMinimoDeSesionesEnPeriodo]</distribucionPeriodicaVariable>)
# y <mismaPosicionDistintosPeriodos> queda como hermano (así lo define el XSD). Se lee también el formato provisional
# anterior (enPeriodos como hijo directo de la sesión).
_EXTRA = ("numMaximoDeSesionesEnPeriodo", "numMinimoDeSesionesEnPeriodo")


def a_interno(raiz):
    """Tras leer el fichero: distribucionPeriodica -> forma interna. Devuelve cuántas sesiones se convirtieron."""
    n = 0
    for sx in list(raiz.iter()):
        dp = sx.find("distribucionPeriodica")
        if dp is None or sx.find("distribucionSemanal") is not None or not len(dp):
            continue
        inner = dp[0]
        if inner.tag == "distribucionPeriodicaFija":
            ds = inner.find("distribucionSemanal")
        else:
            ds = inner.find("distribucionTotal")
            if ds is not None:
                ds.tag = "distribucionSemanal"
        if ds is None:
            continue
        ep = inner.find("enPeriodos")
        nuevos = [ds] + ([ep] if ep is not None else []) + [x for x in inner if x.tag in _EXTRA]
        i = list(sx).index(dp)
        for x in nuevos:
            inner.remove(x)
        if ds.tail is None or not ds.tail.strip():
            ds.tail = dp.tail
        sx.remove(dp)
        for j, x in enumerate(nuevos):
            sx.insert(i + j, x)
        n += 1
    return n


def a_xsd(raiz):
    """Antes de escribir (solo con <periodos>): forma interna -> distribucionPeriodica. Devuelve la función que
    deshace el cambio en el árbol (se escribe y se vuelve a la forma interna con los mismos objetos)."""
    import xml.etree.ElementTree as ET
    px = raiz.find("periodos")
    if px is None:
        return lambda: None
    noms = [(p.findtext("nombre") or "").strip() for p in px.findall("periodo")]
    ops = []
    for sx in list(raiz.iter()):
        ds = sx.find("distribucionSemanal")
        if ds is None or sx.tag in ("distribucionPeriodicaFija", "distribucionPeriodicaVariable") \
                or sx.find("distribucionPeriodica") is not None:
            continue
        hijos = list(sx)
        ep = sx.find("enPeriodos")
        extras = [x for x in sx if x.tag in _EXTRA]
        var = ds.find("distribucionVariable") is not None
        dp = ET.Element("distribucionPeriodica")
        inner = ET.SubElement(dp, "distribucionPeriodicaVariable" if var else "distribucionPeriodicaFija")
        ep2 = ep
        if ep2 is None:
            ep2 = ET.Element("enPeriodos")
            for nmb in noms:
                ET.SubElement(ep2, "refPeriodo").text = nmb
        dp.tail = ds.tail
        for x in [ds] + ([ep] if ep is not None else []) + extras:
            sx.remove(x)
        if var:
            ds.tag = "distribucionTotal"
        inner.append(ds); inner.append(ep2)
        for x in extras:
            inner.append(x)
        quedan = set(map(id, sx))
        sx.insert(sum(1 for x in hijos[:hijos.index(ds)] if id(x) in quedan), dp)
        ops.append((sx, hijos, ds, var, inner, ep2, ep, extras))

    def deshacer():
        for sx, hijos, ds, var, inner, ep2, ep, extras in reversed(ops):
            if var:
                ds.tag = "distribucionSemanal"
            for x in [ds, ep2] + extras:
                if x in list(inner):
                    inner.remove(x)
            for x in list(sx):
                sx.remove(x)
            for x in hijos:
                sx.append(x)
    return deshacer
