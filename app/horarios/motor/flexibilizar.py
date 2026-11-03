"""«Depurador de condiciones»: flexibiliza condiciones estrictas del problema (no del archivo) antes del motor.

Opciones (claves de `flex`, ver horarios/depurador.py, diálogos 664/665 del planificador de referencia):
  proh_<tipo>   tipo ∈ materia, profesor, aula, tarea, sesion, grupo: prohibidos de esas plantillas -> no preferentes
                (en las sesiones lectivas; un tramo sigue prohibido si otra plantilla no conmutada lo prohíbe).
  proh_compl / proh_guardia / proh_reunion: se quitan los prohibidos de esas actividades (de cualquier origen).
  pref_sesion / pref_compl / pref_guardia / pref_reunion: prefijados -> preferentes (se quita la obligación).
  aula_distinta    : sinCambioAula deja de ser estricto.
  bl_distintos     : sin condición «en días distintos» entre bloques.
  bl_consecutivas  : «en días seguidos obligado» entre bloques pasa a preferente.
  no_alternos      : «permitirImpartanEnDiasSeguidos = prohibido» pasa a preferiblemente no.
  no_consecutivos  : «obligatoriamente» pasa a penalizar no seguidas.
  r_min / r_max / r_seguidas / r_perm_dia / r_perm_sem / r_libres / r_incompat: restricciones estrictas de profesores
                   pasan a preferencias (motor/restricciones.py).
  g_tardes / g_limite / g_huecos: se quitan tardesLibres / limiteOcupacionDia / noAdmiteHuecos de los grupos.
Devuelve un problema nuevo (copia profunda) y las líneas de «Anotación» (propias)."""
from __future__ import annotations
from ..textos import TX
import copy

TIPOS_UNIDAD = ("materia", "profesor", "aula", "tarea", "sesion", "grupo")
CRIT = {"materia": "enMateriasYTareas", "tarea": "enMateriasYTareas", "profesor": "enProfesores",
        "grupo": "enGrupos", "aula": "enMateriasYTareas", "sesion": "enSesionesLectivas"}
NOMBRE = {"materia": "materias", "profesor": "profesores", "aula": "aulas", "tarea": "tipos de tarea",
          "sesion": "sesiones lectivas", "grupo": "grupos de alumnos", "compl": "actividades complementarias",
          "guardia": "guardias", "reunion": "reuniones"}


def disponibles(pb: dict) -> set:
    """Opciones con efecto en este problema (las demás se muestran deshabilitadas)."""
    out = set()
    for u in pb["unidades"]:
        for orig in u.get("origen_prohibidos", {}).values():
            out |= {f"proh_{t}" for t, _n in orig}
        if u.get("prefijados"):
            out.add("pref_sesion")
        if u.get("sin_cambio_aula"):
            out.add("aula_distinta")
        if u.get("dias_seguidos") == "prohibido":
            out.add("no_alternos")
        if u.get("dias_seguidos") == "obligatoriamente":
            out.add("no_consecutivos")
    for clave, lista in (("compl", pb["complementarias"]), ("reunion", pb["reuniones"])):
        if any(x.get("prohibidos") for x in lista):
            out.add(f"proh_{clave}")
        if any(x.get("prefijados") for x in lista):
            out.add(f"pref_{clave}")
    for g in pb["guardias"]:
        if any(i.get("prohibidos") for i in g["integrantes"]):
            out.add("proh_guardia")
        if any(i.get("prefijados") for i in g["integrantes"]):
            out.add("pref_guardia")
    for cfg in pb.get("restr_prof", {}).values():
        if any(c.get("modo") == "estricto" for k, c in cfg.items() if k.startswith("min_")):
            out.add("r_min")
        if any(c.get("modo") == "estricto" for k, c in cfg.items() if k.startswith("max_")):
            out.add("r_max")
        if cfg.get("seguidas", {}).get("estricto"):
            out.add("r_seguidas")
        for k in ("perm_dia", "perm_sem"):
            if any(c["estricto"] for c in cfg.get(k, [])):
                out.add("r_" + k)
        if any(c["cantidad"] for c in cfg.get("libres", [])):
            out.add("r_libres")
        if any(c["estricto"] for c in cfg.get("incompat", [])):
            out.add("r_incompat")
    for cfg in pb.get("restr_grupo", {}).values():
        out |= {k for k, t in (("g_tardes", "tardes_libres"), ("g_limite", "limite_dia"), ("g_huecos", "sin_huecos")) if cfg.get(t)}
    if pb["distintos"]:
        out.add("bl_distintos")
    if any(s == "obligado" for *_ab, s in pb["distintos"]):
        out.add("bl_consecutivas")
    return out


def aplicar(pb: dict, flex: dict) -> tuple[dict, list[str]]:
    q = copy.deepcopy(pb); notas = []
    on = {k for k, v in flex.items() if v} & disponibles(pb)
    tipos = {t for t in TIPOS_UNIDAD if f"proh_{t}" in on}
    if tipos:
        for u in q["unidades"]:
            nuevos = []
            for s in u["prohibidos"]:
                orig = u["origen_prohibidos"].get(str(s), [])
                if orig and all(t in tipos for t, _n in orig):
                    for t, _n in orig:
                        d = u["nopref"].setdefault(CRIT[t], {}); d[str(s)] = max(d.get(str(s), 0), 2)
                else:
                    nuevos.append(s)
            u["prohibidos"] = nuevos
    otros = [c for c in ("compl", "guardia", "reunion") if f"proh_{c}" in on]
    for c in otros:
        for x in (q["complementarias"] if c == "compl" else q["reuniones"] if c == "reunion"
                  else [i for g in q["guardias"] for i in g["integrantes"]]):
            x["prohibidos"] = []
    if tipos or otros:
        notas.append(TX("pasa_todas_horas_prohibidas_plantillas"))
        notas.append("  (" + ", ".join(NOMBRE[t] for t in list(TIPOS_UNIDAD) + ["compl", "guardia", "reunion"]
                                      if t in tipos or t in otros) + ")")
    pref = [c for c in ("sesion", "compl", "guardia", "reunion") if f"pref_{c}" in on]
    for c in pref:
        for x in (q["unidades"] if c == "sesion" else q["complementarias"] if c == "compl" else q["reuniones"]
                  if c == "reunion" else [i for g in q["guardias"] for i in g["integrantes"]]):
            x["prefijados"] = []
    if pref:
        notas.append(TX("pasa_todas_horas_fijadas_plantillas"))
        notas.append("  (" + ", ".join(NOMBRE[c] for c in pref) + ")")
    if "aula_distinta" in on:
        for u in q["unidades"]:
            u["sin_cambio_aula"] = False
        notas.append(TX("ha_dejado_usar_otra_aula"))
    if "bl_distintos" in on:
        q["distintos"] = []
        notas.append("Eliminadas condiciones entre distintos bloques de sesiones lectivas: en días distintos.")
    elif "bl_consecutivas" in on:
        q["distintos"] = [[a, b, "preferentemente" if s == "obligado" else s] for a, b, s in q["distintos"]]
        notas.append("Eliminadas condiciones entre distintos bloques de sesiones lectivas: consecutivas.")
    for clave, de, a, txt in (("no_alternos", "prohibido", "preferiblemente", "No obligar estrictamente a impartirse en días alternos."),
                              ("no_consecutivos", "obligatoriamente", "penalizaNoSeguidas", "No obligar estrictamente a impartirse en días consecutivos.")):
        if clave in on:
            for u in q["unidades"]:
                if u["dias_seguidos"] == de:
                    u["dias_seguidos"] = a
            notas.append("Eliminadas condiciones sobre las sesiones de cada bloque: " + txt)
    # restricciones de profesores (estrictas -> preferencias) y de grupos (se quitan)
    TXT = {"r_min": "Mínimo lectivo diario", "r_max": "Máximo lectivo diario", "r_seguidas": "Máximo de lectivas seguidas",
           "r_perm_dia": TX("permanencia_maxima_dia"), "r_perm_sem": TX("permanencia_maxima_semana"),
           "r_libres": "Mañanas o tardes libres", "r_incompat": "Periodos mutuamente excluyentes"}
    rp = [k for k in TXT if k in on]
    for cfg in q.get("restr_prof", {}).values():
        for k, c in cfg.items():
            if (k.startswith("min_") and "r_min" in on) or (k.startswith("max_") and "r_max" in on):
                if c.get("modo") == "estricto":
                    c["modo"] = "optimizacionPreferente"
        if "r_seguidas" in on and "seguidas" in cfg:
            cfg["seguidas"]["estricto"] = False
        for k in ("perm_dia", "perm_sem"):
            if "r_" + k in on:
                for c in cfg.get(k, []):
                    c["estricto"] = False
        if "r_libres" in on:
            for c in cfg.get("libres", []):
                c["preferentes"] = max(c["preferentes"], c["cantidad"]); c["cantidad"] = 0
        if "r_incompat" in on:
            for c in cfg.get("incompat", []):
                c["estricto"] = False
    if rp:
        notas.append("Condiciones de profesores consideradas solo como preferencias: " + ", ".join(TXT[k] for k in rp) + ".")
    gq = {"g_tardes": ("tardes_libres", "Quitar tardes libres no prefijadas."),
          "g_limite": ("limite_dia", "Quitar el límite de la ocupación máxima diaria de cada grupo."),
          "g_huecos": ("sin_huecos", "Permitir periodos libres que formen huecos en el horario del grupo.")}
    for k, (t, txt) in gq.items():
        if k in on:
            for cfg in q.get("restr_grupo", {}).values():
                cfg.pop(t, None)
            notas.append("Grupos de alumnos: " + txt)
    return q, notas


def violaciones(pb_orig: dict, doc: dict) -> dict:
    """Sesiones del resultado que incumplen una condición estricta original (prohibido o prefijado):
    {"s:k": [motivos]} (k = índice de la pieza en doc["sesiones"]). El Editor pinta la marca violeta «P»."""
    from .mensajes import _slots_pieza
    unid = {u["id"]: u for u in pb_orig["unidades"]}
    usado = {}
    out = {}
    piezas_u = {}
    for k, pz in enumerate(doc.get("sesiones", [])):
        u = unid.get(pz.get("unidad"))
        if not u:
            continue
        piezas_u.setdefault(u["id"], []).append(k)
        ss = _slots_pieza(pb_orig, pz)
        usado.setdefault(u["id"], set()).update(ss)
        mal = [s for s in ss if s in set(u["prohibidos"])]
        if mal:
            orig = sorted({f"{t} {n}" for s in mal for t, n in u["origen_prohibidos"].get(str(s), [])})
            if True:
                out.setdefault(f"s:{k}", []).append("Tramo prohibido por plantilla: " + ", ".join(orig))
    for u in pb_orig["unidades"]:
        falta = [s for s in u.get("prefijados", []) if s not in usado.get(u["id"], set())]
        if falta:
            for k in piezas_u.get(u["id"], []):
                out.setdefault(f"s:{k}", []).append("No ocupa su posición prefijada")
    return out
