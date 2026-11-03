"""B3: exportación a DELPHOS (hipótesis CONS_TRAMOS_HORARIOS, SIN CONFIRMAR) sobre una copia de SINTETICO_grande:
semáforo, claves, guardias de recreo, filtro de profesores, fechas y reimportación del envoltorio con delphos.leer."""
import os, sys, shutil, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import _rutas as _R
from horarios import xghc, edicion as ED, editor_modelo as EM, delphos_salida as DS, delphos as DL

F = 0
def check(c, m):
    global F
    print(("OK   " if c else "FALLO"), m); F += (not c)

T = tempfile.mkdtemp()
for f in ("SINTETICO_grande.xghc", "SINTETICO_grande.lphr"):
    shutil.copy(f"{_R.R}/{f}", T)
X, R = os.path.join(T, "SINTETICO_grande.xghc"), os.path.join(T, "SINTETICO_grande.lphr")

ed = EM.Editor(R)
tr = DS.Transferencia(ed)
op = DS.Opciones(anno="2026")
sem, ms = tr.comprobar(op)
check(sem == DS.ROJO and any(m.texto == "sin clave externa" for m in ms), f"sin claves: semáforo rojo ({len(ms)} mensajes)")
op_id = DS.Opciones(usar_clave=False, anno="2026")
sem_id, ms_id = tr.comprobar(op_id)
check(not any(m.texto == "sin clave externa" for m in ms_id), "con el identificativo no se exigen claves")

# claves SINT para todo (como tras importar de DELPHOS)
p = xghc.cargar(X); a = ED.Arbol(p.doc.raiz); r = p.doc.raiz
for lista, tag, base in (("profesores", "profesor", 9000), ("grupos", "grupo", 3000), ("materias", "materia", 5000),
                         ("aulas", "aula", 7000), ("tareas", "tarea", 100)):
    for i, e in enumerate(r.find(lista).findall(tag)):
        ED.escribir(a, e, "claveDeExportacion", str(base + i))
        if tag == "profesor":
            ED.escribir(a, e, "tomaDePosesion", "01/09/2020")
ED.escribir(a, ED.insertar_elemento(a, "tareas", "JD"), "claveDeExportacion", "199")
xghc.guardar(p, X)
ed = EM.Editor(R)
cat = {"profesores": [(str(9000 + i), "") for i in range(len(r.find("profesores")) - 1)]}   # falta el último
tr = DS.Transferencia(ed, cat)
sem, ms = tr.comprobar(op)
check(sem == DS.AMBAR and any("no está entre las claves cargadas" in m.texto for m in ms), f"catálogo incompleto: ámbar ({len(ms)})")
tr.catalogo = {}
sem, ms = tr.comprobar(op)
check(sem in (DS.VERDE, DS.AMBAR) and not any(m.nivel == DS.ROJO for m in ms), f"con claves: sin rojos ({sem}, {len(ms)} ámbar)")

datos = tr.exportar(os.path.join(T, "Horario.xml"), op)
check(datos.startswith(b'<?xml version="1.0" encoding="iso-8859-1"?>'), "ISO-8859-1")
inc = DL.Incidencias()
lee = DL.leer(os.path.join(T, "Horario.xml"), inc)
check(not inc.lineas and "EMP" in lee["secciones"], "el envoltorio se relee sin avisos (contadores y seq correctos)")
filas = tr.filas(op)
n_ses = sum(len(pz["tramos"]) * (1 + len([g for g in ed.ses[s].otros_grupos if g and g != ed.ses[s].grupo]))
            for pz in ed.doc["sesiones"] for s in pz["sesiones"] if s in ed.ses and ed.ses[s].profesor)
check(sum(1 for _, f in filas if f["X_MATERIAOMC"]) == n_ses, f"un TRAMO por periodo y grupo ({n_ses})")
check([f["N_DIASEMANA"] for _, f in filas if f["_dia"] == 2][:1] == [tr.dias_xml[2] or "3"], "días según las claves de los días")
check(all(":" in f["N_HORINI"] for _, f in filas), "horas H:MM")
op2 = DS.Opciones(anno="2026", horas="minutos", dias={0: "L", 1: "M", 2: "X", 3: "J", 4: "V"})
f2 = tr.filas(op2)
check(all(f["N_HORINI"].isdigit() and f["N_DIASEMANA"] in "LMXJV" for _, f in f2), "opciones: minutos y claves de días")
rec = sum(1 for _, f in filas if f["_recreo"])
sin = sum(1 for _, f in tr.filas(DS.Opciones(guardias_recreo=False)) if f["_recreo"])
check(sin == 0 and rec >= sin, f"guardias de recreo opcionales ({rec} con, {sin} sin)")
profs = tr.profesores()
uno = {profs[0][0]}
check(len(profs) > 0 and {p for p, _ in tr.filas(DS.Opciones(profesores=uno))} == uno, f"425: {len(profs)} profesores, filtro")
x3 = tr.xml(DS.Opciones(anno="2026", inicio="08/09/2026", fin="22/06/2027")).decode("iso-8859-1")
check('dato="C_ANNO">2026' in x3 and 'dato="F_FIN">22/06/2027' in x3, "fechas del curso en ENTRADAS")
print("FALLOS:", F)
