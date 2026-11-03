"""Modelo de datos de un archivo de configuración (.xghc)."""
from __future__ import annotations
from .textos import TX
from dataclasses import dataclass, field

# Estados de plantilla. Claves = valores tal como aparecen en el XML de .xghc.
# "indiferente" es la ausencia de entrada. "preferente"/"prefijado" son
# nombres provisionales (no aparecen en los ejemplos); cualquier otro valor
# desconocido se conserva tal cual.
INDIFERENTE = ""
PREFERENTE = "preferente"
PROHIBIDO = "prohibido"
NO_PREF1 = "preferentementeNo1"
NO_PREF2 = "preferentementeNo2"
PREFIJADO = "prefijado"
ESTADOS = [PREFERENTE, INDIFERENTE, PROHIBIDO, NO_PREF1, NO_PREF2, PREFIJADO]
NOMBRE_ESTADO = {
    PREFERENTE: "Preferente", INDIFERENTE: TX("da_igual"), PROHIBIDO: "Prohibida",
    NO_PREF1: "No preferente", NO_PREF2: TX("no_preferente_mas_peso"), PREFIJADO: "Prefijada",
}

Plantilla = dict  # (marco, dia, indice) -> estado


@dataclass
class Tramo:
    marco: str
    dia: int
    indice: int
    entrada: str
    salida: str
    tipo: str  # lectivo / recreo / ...
    clave: str = ""


@dataclass
class Marco:
    id: str
    nombre: str
    tramos: list[Tramo] = field(default_factory=list)

    @property
    def dias(self) -> list[int]:
        return sorted({t.dia for t in self.tramos})

    def filas(self) -> list[Tramo]:
        """Tramos del primer día, en orden (definen las filas de la rejilla)."""
        d0 = self.dias[0] if self.dias else 0
        return sorted((t for t in self.tramos if t.dia == d0), key=lambda t: t.indice)

    def lectivos_por_semana(self) -> int:
        return sum(1 for t in self.tramos if t.tipo == "lectivo")


@dataclass
class Elemento:
    """Elemento genérico de una lista (profesor, grupo, materia, aula...)."""
    nombre: str
    datos: dict = field(default_factory=dict)
    plantilla: Plantilla = field(default_factory=dict)
    marco: str = "A"


@dataclass
class Sesion:
    id: str
    materia: str
    grupo: str
    profesor: str
    tmp: str
    aulas: list[str]
    alternativas: list[str]
    tarea: str
    grupo_materia: str
    departamento: str
    duracion: float
    otros_grupos: list[str] = field(default_factory=list)
    en_distinto_dia: list[str] = field(default_factory=list)
    en_dias_seguidos: str = ""
    plantilla: Plantilla = field(default_factory=dict)
    bloque: str | None = None  # id del bloque de simultáneas
    marco: str = "A"
    xml: object = None            # elemento <sesion>
    xml_plantilla: object = None  # elemento que contiene su <plantilla> (la sesión o su bloque)


@dataclass
class Proyecto:
    ruta: str = ""
    version: str = ""
    marcos: dict[str, Marco] = field(default_factory=dict)
    profesores: list[Elemento] = field(default_factory=list)
    grupos: list[Elemento] = field(default_factory=list)
    materias: list[Elemento] = field(default_factory=list)
    aulas: list[Elemento] = field(default_factory=list)
    conjuntos_aulas: dict[str, list[str]] = field(default_factory=dict)
    cursos: list[Elemento] = field(default_factory=list)
    departamentos: list[Elemento] = field(default_factory=list)
    tareas: list[Elemento] = field(default_factory=list)
    reuniones: list[Elemento] = field(default_factory=list)
    guardias: list[Elemento] = field(default_factory=list)
    complementarias: list[Elemento] = field(default_factory=list)
    sesiones: list[Sesion] = field(default_factory=list)
    modificado: bool = False
    doc: object = None         # xghc.Documento (árbol XML con posiciones)
    contenedor: object = None  # xghc.Contenedor (prefijo/cola originales)

    def marco_de_grupo(self, grupo: str) -> str:
        for g in self.grupos:
            if g.nombre == grupo:
                return g.marco
        return next(iter(self.marcos), "A")
