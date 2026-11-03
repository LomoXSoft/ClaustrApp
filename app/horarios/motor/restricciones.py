"""Restricciones de profesores y grupos (opciones de profesor / grupo de datosGHC).

Se leen solo las etiquetas presentes en el archivo (si falta una etiqueta no se aplica la condición).
Modo: «estricto» -> condición dura; «optimizacionPreferente»/«ponderable» o estricto="false" -> preferencia
(penalización); «nada» -> se ignora.

Profesor (opciones):
  considerarMaximas/MinimasHorasDiarias[SolamenteLectivas] + valor...Calculado (automatico/unaHoraMas/unaHoraMenos)
      máximo/mínimo diario de ocupación (lectivas + guardias + reuniones + complementarias) o solo lectivas.
      Valor automático = ⌈total/días⌉ (máximo) y ⌊total/días⌋ (mínimo); el mínimo solo en los días con actividad.
  maximasHorasSeguidas [estricto]       sesiones lectivas continuadas sin hueco ni complementaria.
  intervalosDePermanenciaDiarios/Semanales [estricto] (pueden repetirse: uno estricto y otro a evitar).
  periodoLibreJornadaPartida / otrosPeriodosLibresJornadaPartida: cantidad (mínimo estricto) y preferentes
      de mañanas/tardes libres (solo marcos con mediodía).
  incompatibilidadEntreSesiones/salirUltimaEntrarPrimera[Lunes] (nIntervalos, tipo «prohibición» = estricto).
Grupo: tardesLibres, limiteOcupacionDia, noAdmiteHuecos (estrictas)."""
from __future__ import annotations
import math
from collections import defaultdict
from ..textos import TX

# Regla de «ocupación» (máximo/mínimo diario de ocupación del profesor): qué no lectivas cuentan además
# de las lectivas. Confirmado por la usuaria (1-11-2026): cuentan lectivas y no lectivas. La doc. XML-GHC habla de «computables»; el
# esquema no tiene esa marca; por defecto cuentan todas. Cambiar aquí afecta a motor, comprobador y límites.
OCUPACION_CUENTA = {"guardias", "reuniones", "complementarias"}

MODOS_DUROS = {"estricto"}
MODOS_PREF = {"optimizacionPreferente", "ponderable", "limitado", "ampliado"}


def _t(e, ruta, d=""):
    if e is None:
        return d
    x = e.find(ruta)
    return (x.text or "").strip() if x is not None and x.text else d


def _int(v, d=0):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return d


def leer(p) -> tuple[dict, dict]:
    rp, rg = {}, {}
    for e in p.profesores:
        x = e.datos.get("_xml"); op = x.find("opciones") if x is not None else None
        if op is None:
            continue
        r = {}
        for clave, tag in (("max_ocup", "considerarMaximasHorasDiarias"), ("max_lect", "considerarMaximasHorasDiariasSolamenteLectivas"),
                           ("min_ocup", "considerarMinimasHorasDiarias"), ("min_lect", "considerarMinimasHorasDiariasSolamenteLectivas")):
            modo = _t(op, tag)
            if modo and modo != "nada":
                vtag = tag.replace("considerar", "valor").replace("HorasDiarias", "HorasCalculado")
                r[clave] = {"modo": modo, "ajuste": _t(op, vtag, "automatico")}
        e_seg = op.find("maximasHorasSeguidas")
        if e_seg is not None and _int(e_seg.text, 0) > 0:
            r["seguidas"] = {"valor": _int(e_seg.text), "estricto": e_seg.get("estricto") == "true"}
        for clave, tag in (("perm_dia", "intervalosDePermanenciaDiarios"), ("perm_sem", "intervalosDePermanenciaSemanales")):
            v = [{"valor": _int(z.text), "estricto": z.get("estricto") == "true"} for z in op.findall(tag) if z.text]
            if v:
                r[clave] = v
        libres = []
        for z in [op.find("periodoLibreJornadaPartida")] + op.findall("otrosPeriodosLibresJornadaPartida/periodoLibreJornadaPartida"):
            if z is None:
                continue
            c, pf = _int(_t(z, "cantidad", "0")), _int(_t(z, "preferentes", "0"))
            if c or pf:
                libres.append({"tipo": _t(z, "tipoDePeriodoLibre", "indistintamente"), "cantidad": c, "preferentes": pf})
        if libres:
            r["libres"] = libres
        inc = []
        for tag, lunes in (("salirUltimaEntrarPrimera", False), ("salirUltimaEntrarPrimeraLunes", True)):
            z = op.find("incompatibilidadEntreSesiones/" + tag)
            if z is not None and (z.text or "").strip() == "true":
                inc.append({"lunes": lunes, "n": max(1, _int(z.get("nIntervalos", "1"), 1)),
                            "estricto": z.get("tipo", "").startswith("prohibici")})
        if inc:
            r["incompat"] = inc
        if r:
            rp[e.nombre] = r
    for e in p.grupos:
        x = e.datos.get("_xml")
        if x is None:
            continue
        r = {}
        if _int(_t(x, "tardesLibres", "0")):
            r["tardes_libres"] = _int(_t(x, "tardesLibres"))
        if _t(x, "limiteOcupacionDia"):
            r["limite_dia"] = _int(_t(x, "limiteOcupacionDia"))
        if _t(x, "noAdmiteHuecos") == "true":
            r["sin_huecos"] = True
        if r:
            rg[e.nombre] = r
    return rp, rg


def totales(pb) -> dict:
    """Carga semanal por profesor: {'lect': n, 'ocup': n}."""
    t = defaultdict(lambda: {"lect": 0, "ocup": 0})
    for u in pb["unidades"]:
        n = sum(u.get("piezas", [])) or u.get("variable", {}).get("total", 0)
        for pr in u["profesores"]:
            t[pr]["lect"] += n; t[pr]["ocup"] += n
    for g in (pb.get("guardias", []) if "guardias" in OCUPACION_CUENTA else []):
        for i in g.get("integrantes", []):
            t[i["profesor"]]["ocup"] += i.get("n", 0)
    for r in (pb.get("reuniones", []) if "reuniones" in OCUPACION_CUENTA else []):
        for pr in r.get("integrantes", []):
            t[pr]["ocup"] += r.get("n", 1) * r.get("duracion", 1)
    for c in (pb.get("complementarias", []) if "complementarias" in OCUPACION_CUENTA else []):
        t[c["profesor"]]["ocup"] += c.get("n", 0)
    return t


def limite(pb, pr, clave, cfg):
    tot = totales(pb)[pr]["lect" if clave.endswith("lect") else "ocup"]
    nd = max(1, len(pb["dias"].get(pb["marco_prof"].get(pr), [])))
    base = math.ceil(tot / nd) if clave.startswith("max") else tot // nd
    base += {"unaHoraMas": 1, "unaHoraMenos": -1}.get(cfg.get("ajuste"), 0)
    if cfg.get("modo") == "ampliado":
        base += 1
    return max(0, base)


def es_duro(cfg):
    return cfg.get("modo") in MODOS_DUROS


# ------------------------------------------------------------------ evaluación sobre un resultado
def ocupacion(pb, r):
    """Actividades de cada recurso en el resultado: {(tipo, nombre): [(slot, True | clase no lectiva)]} (slots en su propio marco)."""
    sid = {(s["marco"], s["dia"], s["indice"]): s["id"] for s in pb["slots"]}
    unid = {u["id"]: u for u in pb["unidades"]}
    reun = {x["nombre"]: x for x in pb.get("reuniones", [])}
    act = defaultdict(list)
    def ss(marco, dia, tramos):
        return [sid[(marco, dia, t)] for t in tramos if (marco, dia, t) in sid]
    for pz in r.get("sesiones", []):
        u = unid.get(pz["unidad"])
        if not u:
            continue
        for s in ss(pz["marco"], pz["dia"], pz["tramos"]):
            for pr in u["profesores"]:
                act[("P", pr)].append((s, True))
            for g in u["grupos"]:
                act[("G", g)].append((s, True))
    for g in r.get("guardias", []):
        act[("P", g["profesor"])] += [(s, "guardias") for s in ss(g["marco"], g["dia"], [g["tramo"]])]
    for x in r.get("reuniones", []):
        for pr in reun.get(x["reunion"], {}).get("integrantes", []):
            act[("P", pr)] += [(s, "reuniones") for s in ss(x["marco"], x["dia"], x["tramos"])]
    for c in r.get("complementarias", []):
        act[("P", c["profesor"])] += [(s, "complementarias") for s in ss(c["marco"], c["dia"], [c["tramo"]])]
    return act


def evaluar(pb, r) -> list[tuple[bool, str, str]]:
    """Lista de incumplimientos (estricto, categoría, detalle)."""
    rp, rg = pb.get("restr_prof", {}), pb.get("restr_grupo", {})
    if not rp and not rg:
        return []
    act = ocupacion(pb, r); S = {s["id"]: s for s in pb["slots"]}
    par = r.get("parcial")
    out = []
    def solapa(s, iv):
        a = S[s]
        return any(a["dia"] == b["dia"] and a["ini"] < b["fin"] and b["ini"] < a["fin"] for b in iv)
    def fila_bool(iv, fila):
        return [1 if s is not None and solapa(s, iv) else 0 for s in fila]
    for pr, cfg in rp.items():
        if par:
            continue  # en un horario parcial la carga del profesor está incompleta
        marco = pb["marco_prof"].get(pr); dias = pb["dias"].get(marco, [])
        A = act.get(("P", pr), [])
        filas = {d: [s for s in pb["filas"].get(f"{marco}|{d}", []) if s is not None] for d in dias}
        spans = []
        for d in dias:
            todas = [S[s] for s, _l in A if S[s]["dia"] == d]; lect = [S[s] for s, l in A if l is True and S[s]["dia"] == d]
            cuenta = [S[s] for s, l in A if (l is True or l in OCUPACION_CUENTA) and S[s]["dia"] == d]
            for clave in ("max_ocup", "max_lect", "min_ocup", "min_lect"):
                if clave in cfg:
                    v = limite(pb, pr, clave, cfg[clave]); n = len(lect if clave.endswith("lect") else cuenta)
                    mal = n > v if clave.startswith("max") else (0 < len(todas) and n < v)
                    if mal:
                        out.append((es_duro(cfg[clave]), TX("cat_maximo_diario") if clave.startswith("max") else TX("cat_minimo_diario"),
                                    f"{pr} día {d}: {n} ({'máx' if clave.startswith('max') else 'mín'} {v})"))
            if "seguidas" in cfg:
                nolect = [S[s] for s, l in A if l is not True and S[s]["dia"] == d]
                run = mx = 0
                for s in pb["filas"].get(f"{marco}|{d}", []):
                    run = run + 1 if s is not None and solapa(s, lect) and not solapa(s, nolect) else 0
                    mx = max(mx, run)
                if mx > cfg["seguidas"]["valor"]:
                    out.append((cfg["seguidas"]["estricto"], TX("cat_horas_seguidas"), f"{pr} día {d}: {mx} > {cfg['seguidas']['valor']}"))
            bo = fila_bool(todas, filas[d])
            idx = [i for i, b in enumerate(bo) if b]
            span = (idx[-1] - idx[0] + 1) if idx else 0; spans.append(span)
            for c in cfg.get("perm_dia", []):
                if span > c["valor"]:
                    out.append((c["estricto"], TX("cat_permanencia_dia"), f"{pr} día {d}: {span} > {c['valor']}"))
        for c in cfg.get("perm_sem", []):
            if sum(spans) > c["valor"]:
                out.append((c["estricto"], TX("cat_permanencia_semana"), f"{pr}: {sum(spans)} > {c['valor']}"))
        jor = pb.get("jornada", {})
        for c in cfg.get("libres", []):
            libres = 0; aplicable = False
            for d in dias:
                partes = jor.get(f"{marco}|{d}", [])
                if len(partes) < 2:
                    continue
                aplicable = True
                todas = [S[s] for s, _l in A if S[s]["dia"] == d]
                lib = [not any(fila_bool(todas, pt)) for pt in partes[:2]]
                libres += {"mañanas": lib[0], "tardes": lib[1]}.get(c["tipo"], lib[0] or lib[1])
            if not aplicable:
                continue
            if libres < c["cantidad"]:
                out.append((True, TX("cat_medias_jornadas"), f"{pr}: {libres} < {c['cantidad']} ({c['tipo']})"))
            elif libres < c["preferentes"]:
                out.append((False, TX("cat_medias_jornadas"), f"{pr}: {libres} < {c['preferentes']} preferentes ({c['tipo']})"))
        for c in cfg.get("incompat", []):
            iv = [S[s] for s, _l in A]
            for a, b in _pares_incompat(dias, c["lunes"]):
                if any(fila_bool(iv, filas[a][-c["n"]:])) and any(fila_bool(iv, filas[b][:c["n"]])):
                    out.append((c["estricto"], TX("cat_ultima_primera"), f"{pr} días {a}-{b}"))
    for g, cfg in rg.items():
        if par and g not in par.get("grupos", []):
            continue
        marco = pb["marco_grupo"].get(g); dias = pb["dias"].get(marco, [])
        iv = [S[s] for s, _l in act.get(("G", g), [])]
        tl = 0; aplicable = False
        for d in dias:
            fila = [s for s in pb["filas"].get(f"{marco}|{d}", []) if s is not None]; b = fila_bool(iv, fila)
            if "limite_dia" in cfg and sum(b) > cfg["limite_dia"]:
                out.append((True, "Ocupación máxima del grupo", f"{g} día {d}: {sum(b)} > {cfg['limite_dia']}"))
            if cfg.get("sin_huecos"):
                idx = [i for i, x in enumerate(b) if x]
                if idx and idx[-1] - idx[0] + 1 > len(idx):
                    out.append((True, "Huecos del grupo (no admite huecos)", f"{g} día {d}"))
            partes = pb.get("jornada", {}).get(f"{marco}|{d}", [])
            if len(partes) >= 2:
                aplicable = True
                tl += not any(fila_bool(iv, partes[1]))
        if cfg.get("tardes_libres") and aplicable and tl < cfg["tardes_libres"]:
            out.append((True, "Tardes libres del grupo", f"{g}: {tl} < {cfg['tardes_libres']}"))
    return out


def _pares_incompat(dias, lunes):
    if lunes:
        return [(dias[-1], dias[0])] if len(dias) >= 5 else []
    return list(zip(dias, dias[1:]))
