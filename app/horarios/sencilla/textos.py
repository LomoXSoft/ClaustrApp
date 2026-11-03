"""Textos y glosario de la versión sencilla (lenguaje llano)."""
import re

PASOS = [
    ("centro", "Centro y horas", "Nombre del centro, días lectivos y horario de clases y recreos."),
    ("profesorado", "Profesorado", "Quién da clase en el centro."),
    ("grupos", "Grupos", "Los grupos de alumnos (1º ESO A, 2º ESO B…)."),
    ("materias", "Materias y quién da qué", "Para cada grupo: qué materias tiene, cuántas horas y con quién."),
    ("preferencias", "Preferencias", "Cuándo prefiere o no puede dar clase cada profesor, grupo o aula."),
    ("guardias", "Guardias y reuniones", "Servicios de guardia y reuniones fijas (departamento, equipos…)."),
    ("generar", "Generar", "El programa busca el mejor horario posible."),
    ("revisar", "Revisar y ajustar", "Arrastre las clases para cambiarlas de hora; el programa le avisa."),
    ("informes", "Informes y Delphos", "Imprima los horarios o envíelos a Delphos."),
]

# 4 estados de preferencia (valor interno del archivo -> texto llano, color)
ESTADOS = [("", "Disponible", "#ffffff"), ("preferente", "Prefiere", "#bfe8c4"),
           ("preferentementeNo1", "Mejor no", "#ffe3a3"), ("prohibido", "No puede", "#f5b5b5")]
TEXTO_ESTADO = {k: t for k, t, _ in ESTADOS}
COLOR_ESTADO = {k: c for k, _, c in ESTADOS}
# los estados avanzados (preferentementeNo2, prefijado) se conservan y se muestran como su equivalente
EQUIVALENTE = {"preferentementeNo2": "preferentementeNo1", "prefijado": "preferente"}

DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

GLOSARIO = {
    "Sesión": "Una clase semanal de una materia con un grupo y un profesor.",
    "Tipo de aula": "Un conjunto de aulas equivalentes (p. ej. «Laboratorios»): el programa elige una libre.",
    "Guardia": "Hora en la que un profesor queda disponible para cubrir ausencias.",
    "Hueco": "Hora libre entre dos clases del mismo día.",
}

COLOR_VERDE, COLOR_AMBAR, COLOR_ROJO = "#bfe8c4", "#ffe3a3", "#f5b5b5"


def explicar(msg: str) -> str:
    """Traduce un mensaje del comprobador/editor a lenguaje llano."""
    cod = getattr(msg, "codigo", None)
    if cod:                              # causa estructurada (editor_modelo.Motivo): no depende del texto
        d = msg.datos
        if cod == "choque_profesor":
            return f"El profesor {d['nombre']} ya tiene clase a esa hora ({d['detalle']})."
        if cod == "choque_grupo":
            return f"El grupo {d['nombre']} ya tiene clase a esa hora ({d['detalle']})."
        if cod == "choque_aula":
            return f"El aula {d['nombre']} está ocupada a esa hora ({d['detalle']})."
        if cod == "no_caben":
            return f"No caben {d['n']} horas seguidas a partir de ahí."
        if cod == "regla":
            cat, det = d.get("categoria", ""), d.get("detalle", "")
            if cat == "Tmp incumplido":
                return ("Esa materia ya tendría dos clases el mismo día." if "mismo día" in det
                        else "No respeta el reparto de horas de la materia en la semana.")
            if cat.startswith(("Tramo prohibido", "Prohibición de la plantilla")):
                return f"Es una hora marcada como «No puede»: {det}"
    # mensajes sin causa estructurada (texto libre)
    m = re.sub(r"^\(\d+\)\s*", "", msg or "")
    m = re.sub(r"^[^.]*?\.-\s*", "", m)
    reglas = [
        (r"Ya está en esta posición el profesor (.+?) \((.*)\)$", r"El profesor \1 ya tiene clase a esa hora (\2)."),
        (r"Ya está en esta posición el grupo de alumnos (.+?) \((.*)\)$", r"El grupo \1 ya tiene clase a esa hora (\2)."),
        (r"El aula (.+?) ya está ocupada en esta posición \((.*)\)$", r"El aula \1 está ocupada a esa hora (\2)."),
        (r"Tmp incumplido: .*dos piezas el mismo día.*", "Esa materia ya tendría dos clases el mismo día."),
        (r"Tmp incumplido: .*", "No respeta el reparto de horas de la materia en la semana."),
        (r"Prohibici[oó]n de la plantilla.*?: (.*)", r"Es una hora marcada como «No puede»: \1"),
        (r"No caben (\d+) periodos.*", r"No caben \1 horas seguidas a partir de ahí."),
    ]
    for a, b in reglas:
        if re.search(a, m):
            return re.sub(a, b, m)
    return m
