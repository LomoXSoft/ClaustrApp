"""Validación básica de la configuración (mensajes del panel izquierdo)."""
from . import modelo as M

AVISO, ERROR, INFO = "Avisos", "Errores", "Información"


def validar(p: M.Proyecto):
    msgs = []  # (tipo, texto, (lista, nombre))
    nombres = {
        "profesor": {e.nombre for e in p.profesores}, "grupo": {e.nombre for e in p.grupos},
        "materia": {e.nombre for e in p.materias}, "aula": {e.nombre for e in p.aulas},
    }
    for s in p.sesiones:
        for campo, lista in (("materia", "materias"), ("grupo", "grupos"), ("profesor", "profesores")):
            v = getattr(s, campo)
            if v and v not in nombres[campo]:
                msgs.append((ERROR, f"La sesión {s.id} usa {campo} inexistente: {v}", ("sesiones", s.id)))
        for a in s.aulas:
            if a and a not in nombres["aula"]:
                msgs.append((ERROR, f"La sesión {s.id} usa un aula inexistente: {a}", ("sesiones", s.id)))
    for g in p.grupos:
        m = p.marcos.get(g.marco)
        if not m:
            msgs.append((ERROR, f"El grupo {g.nombre} usa un marco inexistente: {g.marco}", ("grupos", g.nombre))); continue
        hab = sum(1 for t in m.tramos if t.tipo == "lectivo" and g.plantilla.get((m.id, t.dia, t.indice)) != M.PROHIBIDO)
        horas, bloques = 0.0, set()
        for s in p.sesiones:
            if s.grupo == g.nombre or g.nombre in s.otros_grupos:
                if s.bloque is not None:
                    if s.bloque in bloques:
                        continue  # las simultáneas ocupan las mismas horas
                    bloques.add(s.bloque)
                horas += s.duracion
        if horas > hab:
            msgs.append((AVISO, f"Hay demasiadas horas asignadas para el grupo: {g.nombre} ({horas:g} > {hab})", ("grupos", g.nombre)))
    for e in p.profesores:
        if not any(s.profesor == e.nombre for s in p.sesiones):
            msgs.append((AVISO, f"El profesor {e.nombre} no tiene sesiones lectivas", ("profesores", e.nombre)))
    msgs.append((INFO, f"{len(p.profesores)} profesores, {len(p.grupos)} grupos, {len(p.materias)} materias, "
                       f"{len(p.aulas)} aulas, {len(p.sesiones)} sesiones lectivas", None))
    return msgs
