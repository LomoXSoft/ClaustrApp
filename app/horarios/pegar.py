"""Pegar desde hoja de cálculo / leer listado externo (CSV) para profesorado, grupos y materias.
Columnas (la 1.ª obligatoria; se ignora una fila de cabecera):
  profesores: nombre · nombre completo · departamento
  grupos:     nombre · curso · aula
  materias:   nombre · nombre completo · departamento
Los nombres ya existentes se actualizan solo en las columnas no vacías; los nuevos se añaden al final."""
import csv, io
from . import edicion as ED

LISTAS = ("profesores", "grupos", "materias")
COLUMNAS = {"profesores": ["nombre", "nombreCompleto", "departamento"],
            "grupos": ["nombre", "cursoPerteneciente", "aula"],
            "materias": ["nombre", "nombreCompleto", "departamento"]}
CABECERAS = {"nombre", "identificativo", "profesor", "profesora", "profesorado", "grupo", "grupos", "materia", "materias"}
# lista auxiliar que debe existir para cada columna de referencia
AUX = {"departamento": "departamentos", "cursoPerteneciente": "cursos", "aula": "aulas"}


def filas_de_texto(texto: str) -> list[list[str]]:
    lineas = [l for l in (texto or "").replace("\r\n", "\n").replace("\r", "\n").split("\n") if l.strip()]
    if not lineas:
        return []
    m = lineas[0]
    sep = "\t" if "\t" in m else ";" if ";" in m else "," if "," in m else "\t"
    filas = [[c.strip() for c in r] for r in csv.reader(io.StringIO("\n".join(lineas)), delimiter=sep)]
    if filas and filas[0] and filas[0][0].strip().lower() in CABECERAS:
        filas = filas[1:]
    return [f for f in filas if f and f[0]]


def leer_archivo(ruta: str) -> list[list[str]]:
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            with open(ruta, encoding=enc) as f:
                return filas_de_texto(f.read())
        except UnicodeDecodeError:
            continue
    return []


def aplicar(arbol, lista: str, filas: list[list[str]]) -> dict:
    """Inserta/actualiza. Devuelve {'nuevos': n, 'actualizados': n, 'omitidos': [...]}."""
    if lista not in LISTAS:
        raise ValueError(f"Pegar no disponible para la lista «{lista}»")
    raiz = arbol.raiz; cols = COLUMNAS[lista]
    res = {"nuevos": 0, "actualizados": 0, "omitidos": []}
    cont = ED.contenedor(raiz, lista)
    existentes = {(e.findtext("nombre") or "").strip(): e for e in (list(cont) if cont is not None else [])}
    for f in filas:
        nombre = f[0][:30]
        if not nombre:
            continue
        e = existentes.get(nombre)
        nuevo = e is None
        if nuevo:
            e = ED.insertar_elemento(arbol, lista, nombre); existentes[nombre] = e
        cambio = False
        for tag, val in zip(cols[1:], f[1:]):
            if not val:
                continue
            val = val[:30]
            if tag in AUX and val not in ED.nombres(raiz, AUX[tag]):
                ED.insertar_elemento(arbol, AUX[tag], val)
            cambio |= bool(ED.escribir(arbol, e, tag, val))
        if nuevo:
            res["nuevos"] += 1
        elif cambio:
            res["actualizados"] += 1
        else:
            res["omitidos"].append(nombre)
    return res
