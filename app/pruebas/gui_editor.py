"""Prueba offscreen del Editor (réplica del editor de resultados) sobre una copia de prueba1.xghc + prueba1.lphr.

Cubre: abrir, menús, mover legal (arrastrar/soltar vía API de la rejilla), conflicto con Extraer,
extraer/agregar desde 'Sesiones sin hueco en el horario', extraer asignatura, cambiar el aula, nuevas sesiones,
deshacer/rehacer, guardar (con .bak) y recargar, comprobador válido tras ediciones legales, proyección
sobre el Planificador y el motor reproduciendo las posiciones prefijadas. No imprime nombres.
"""
import sys, os, tempfile, shutil, hashlib
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import _rutas as _R
from horarios.textos import TX
from collections import defaultdict
from PySide6.QtWidgets import QApplication, QMessageBox, QDialog
from PySide6.QtCore import Qt
from horarios import APP_EDITOR
from horarios.textos import MENUS_EDITOR
from horarios import editor as E, xghc, comprobador as CK, resultado as RES
from horarios.motor import problema, cpsat

app = QApplication.instance() or QApplication(sys.argv)
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
QMessageBox.information = staticmethod(lambda *a, **k: None)
QMessageBox.warning = staticmethod(lambda *a, **k: None)
fallos = 0


def check(c, m):
    global fallos
    print(("OK   " if c else "FALLO") + " " + m); fallos += (not c)


RAIZ = _R.R
tmp = tempfile.mkdtemp()
X = os.path.join(tmp, "p1.xghc"); L = os.path.join(tmp, "p1.lphr")
_R.exigir(os.path.join(RAIZ, "prueba1.xghc"), os.path.join(RAIZ, "prueba1_r.lphr"))
shutil.copy(os.path.join(RAIZ, "prueba1.xghc"), X); shutil.copy(os.path.join(RAIZ, "prueba1_r.lphr"), L)
h0 = hashlib.md5(open(X, "rb").read()).hexdigest()
# Esta prueba es del editor: las restricciones de profesor/grupo (probadas en motor_restricciones)
# se neutralizan para que las ediciones manuales no hagan infactible el prefijado.
from horarios.motor import restricciones as _R
_R.leer = lambda p: ({}, {})
abiertos = []
E.VentanaEditor.abrir_planificador = staticmethod(lambda r: abiertos.append(r))

w = E.VentanaEditor(L, X); w.show(); app.processEvents(); ed = w.ed
check(w.windowTitle() == f"{APP_EDITOR} - [p1.lphr]", "título de ventana")
check([a.text() for a in w.menuBar().actions()] == [m["t"].replace("&", "") for m in MENUS_EDITOR["129"]], "barra de menús con textos de recursos")
textos = [a.text() for a in w.acc.values()]
check(not any("Suscrip" in t for t in textos), "sin entradas de suscripción")
check(any(t.endswith("\tPróximamente") for t in textos), "lo no implementado marcado Próximamente")
check(ed.comprobar().valido, "resultado inicial válido")
v = w._vista_actual(); t = v.tabla()
check(v.tabs.tabText(0) == f"[{t.nombre}] ({t.vista})" and t.vista == "Grupos", "solapa '[elemento] (Grupos)'")
check(t.rowCount() > 0 and t.columnCount() == 5 and sum(1 for k in t.celdas) > 0, "rejilla días × tramos con celdas")
# vistas
for vis in E.VISTAS:
    v.cb_vista.setCurrentText(vis); app.processEvents()
check(v.cb_vista.currentText() == "Guardias", "selector de vistas recorre las 6")
v.cb_vista.setCurrentText("Grupos"); t = v.tabla()


def buscar_mov(legal):
    for it in ed.items():
        if it[0] != "s":
            continue
        for pos in sorted(ed.tramos):
            if ed.tramos[pos].tipo != "lectivo" or pos in ed.posiciones(it):
                continue
            pr = ed.proponer_mover(it, *pos)
            if pr.invalida:
                continue
            if legal and not pr.mensajes:
                return it, pos
            if not legal and any(x for _, x in pr.mensajes):
                return it, pos
    return None, None


# --- mover legal
it, pos = buscar_mov(True)
check(it is not None, "hay un movimiento legal")
nd = len(ed.pila_deshacer)
check(w.soltar(it, pos) and ed.posiciones(it)[0] == pos, "mover (soltar) sin conflictos")
check(ed.comprobar().valido and not ed.choques(), "comprobador válido tras mover")
w.deshacer(); check(ed.posiciones(it)[0] != pos and len(ed.pila_deshacer) == nd, "deshacer el movimiento")
w.rehacer(); check(ed.posiciones(it)[0] == pos, "rehacer el movimiento")
# --- soltar desde la rejilla (API de drop)
t = w._vista_actual().tabla()
# --- conflicto + Extraer
it2, pos2 = buscar_mov(False)
vistos = {}
def exec_conf(self):
    vistos["titulo"] = self.windowTitle(); vistos["n"] = self.lst.topLevelItemCount()
    vistos["txt"] = self.lst.topLevelItem(0).text(0)[:4]
    while self.c[1058].isEnabled():
        self.extraer_sel()
    return QDialog.Accepted
E.DialogoConflictos.exec = exec_conf
nfuera = len(ed.doc["no_colocadas"])
check(w.soltar(it2, pos2), "mover con conflicto -> diálogo")
check(vistos.get("titulo", "").startswith("Moviendo") or vistos.get("titulo", "").startswith("Agregando"), "título del diálogo de conflictos")
check(vistos.get("txt") in ("(05)", "(06)", "(07)"), "mensaje con código (05)/(06)/(07)")
check(len(ed.doc["no_colocadas"]) > nfuera, "Extraer manda las sesiones en conflicto fuera del horario")
check(not ed.choques() and ed.comprobar().valido, "sin choques y válido tras Continuar con extracción")
# --- Cancelar no cambia nada
it3, pos3 = buscar_mov(False)
if it3:
    E.DialogoConflictos.exec = lambda self: QDialog.Rejected
    antes = ed.posiciones(it3)
    check(not w.soltar(it3, pos3) and ed.posiciones(it3) == antes, "Cancelar en el diálogo no mueve")
# --- Sesiones sin hueco en el horario: agregar de vuelta en hueco libre
f = w.sesiones_sin_colocar()
check(f.lst.topLevelItemCount() == len(ed.doc["no_colocadas"]) > 0, "lista de sesiones fuera del horario")
s_x = next(i for i in ed.items() if i[0] == "s"); hueco = ed.posiciones(s_x)[0]
ed.extraer([s_x]); f.refrescar(); n_item = f"n:{len(ed.doc['no_colocadas']) - 1}"
check(f.seleccionar(n_item), "la sesión extraída aparece en la lista")
pr = ed.proponer_agregar(n_item, *hueco)
check(not pr.invalida and not pr.mensajes, "agregar en su hueco no genera conflictos")
nf = len(ed.doc["no_colocadas"])
t = w._vista_actual().tabla()
check(w.soltar(n_item, hueco) and len(ed.doc["no_colocadas"]) < nf, 'Añadir al horario desde la lista')
check(ed.comprobar().valido, "válido tras agregar")
# --- extraer celda y asignatura
t = w._vista_actual().tabla(); (r, c), its = next(iter(t.celdas.items()))
t.setCurrentCell(r, c); n0 = len(ed.doc["no_colocadas"])
w.extraer_celda(); check(len(ed.doc["no_colocadas"]) > n0, TX("sacar_lo_hay_celda"))
w.deshacer()
s_it = next(i for i in ed.items() if i[0] == "s" and len(ed.piezas_asignatura(i)) > 1)
for (r, c), lst in w._vista_actual().tabla().celdas.items():
    pass
n_piezas = len(ed.piezas_asignatura(s_it)); ed.extraer_asignatura(s_it)
check(len(ed.doc["sesiones"]) > 0 and ed.comprobar().valido, f"Sacar toda la materia ({n_piezas} piezas) y válido")
w.deshacer()
# --- cambiar el aula
cand = None
for i in ed.items():
    o = ed.obj(i)
    if cand or i[0] != "s" or not o.get("aulas") or not any(ed.ses[sid].alternativas for sid in o["sesiones"]):
        continue
    for a_ in [a for a, e in ed.estado_aulas(*ed.posiciones(i)[0], excluir=i).items() if e == "libre" and a not in o["aulas"]]:
        if any(ed.estado_aulas(*pp, excluir=i)[a_] != "libre" for pp in ed.posiciones(i)):
            continue
        ed.cambiar_aula(i, o["aulas"][0], a_); ok = ed.comprobar().valido; ed.deshacer()
        if ok:
            cand = (i, o["aulas"][0], a_); break
check(cand is not None, "hay sesión con aula y aula libre")
dca = E.DialogoCambiarAula(w, cand[0])
dca.c[1031].setCurrentItem(next(dca.c[1031].topLevelItem(k) for k in range(dca.c[1031].topLevelItemCount()) if dca.c[1031].topLevelItem(k).text(0) == cand[2]))
check(dca.c[1039].text() == TX("pasar_aula_libre"), "botón 'Pasar al aula libre'")
dca.aplicar(); check(cand[2] in ed.obj(cand[0])["aulas"] and ed.comprobar().valido, "cambiar el aula -> válido")
w.deshacer()
# --- libres
pos = ed.posiciones("s:0")[0]
check(len(ed.libres("profesores", *pos)) > 0 and len(ed.libres("aulas", *pos)) > 0, "ver profesores/aulas libres")
# --- nueva lectiva (fuera del horario)
def exec_lect(self):
    self.c[1137].setCurrentIndex(0); self.c[1138].setCurrentIndex(0); self.c[1139].setCurrentIndex(0); E._pon(self.c[1140], 2)
    return QDialog.Accepted
E.DialogoLectiva.exec = exec_lect
nf = len(ed.doc["no_colocadas"]); w.nueva_lectiva()
check(len(ed.doc["no_colocadas"]) == nf + 1 and ed.doc["editor"]["anadidos"], "nueva Lectiva queda fuera del horario")
E.DialogoComplementaria.exec = lambda self: QDialog.Accepted
w.nueva_complementaria(); check(len(ed.doc["no_colocadas"]) == nf + 2, "nueva Complementaria")
check(ed.comprobar().valido, "válido con las nuevas sin colocar (se informan como no colocadas)")
# --- colores
k = ed.clave_color("s:0"); ed.cambiar_color(k, "#123456")
# --- guardar y recargar
r = w.guardar(); check(os.path.exists(L + ".bak") and os.path.exists(L), "guardar con copia previa .bak")
check(hashlib.md5(open(X, "rb").read()).hexdigest() == h0, "el .xghc original no se modifica")
pos_it = ed.posiciones(it); w2 = E.VentanaEditor(L, X); e2 = w2.ed
check(e2.posiciones(it) == pos_it and len(e2.doc["no_colocadas"]) == len(ed.doc["no_colocadas"]), "recargar conserva posiciones y fuera del horario")
check(e2.color(k) == "#123456", "color de asignatura persistente en el .lphr")
check(e2.comprobar().valido, "comprobador válido tras recargar (con añadidos aplicados)")
w2._preguntar_proyeccion = False; w2.close()
# --- proyección al cerrar
dest = os.path.join(tmp, "p1_proy.xghc")
E.DialogoProyectar.exec = lambda self: (self.ed_dest.setText(dest), QDialog.Accepted)[1]
w.close(); app.processEvents()
check(abiertos == [dest] and os.path.exists(dest), "al cerrar: proyectar y abrir el Planificador")
check(hashlib.md5(open(X, "rb").read()).hexdigest() == h0, "original intacto tras proyectar")
try:
    ed.proyectar(X); check(False, "rechaza sobrescribir el original")
except E.ErrorEdicion:
    check(True, "rechaza sobrescribir el original")
# --- motor sobre la configuración proyectada
p = xghc.cargar(dest); res = cpsat.resolver(problema.construir(p), 30)
d2 = RES.crear(res, dest)


def por_sesion(doc):
    out = defaultdict(set)
    for pz in doc["sesiones"]:
        for sid in pz["sesiones"]:
            out[sid] |= {(pz["marco"], pz["dia"], tt) for tt in pz["tramos"]}
    return out
a, b = por_sesion(ed.doc), por_sesion(d2)
mal = [sid for sid, pos in a.items() if not pos <= b.get(sid, set())]
if mal:
    print("  distintas:", len(mal), "de", len(a), "; ids en motor:", len(b), "; ejemplo", mal[0], sorted(a[mal[0]]), sorted(b.get(mal[0], [])), res["estadisticas"].get("no_colocadas"))
check(not mal, f"el motor respeta las posiciones prefijadas de las {len(a)} sesiones (las piezas que estaban fuera se colocan libremente)")
check(CK.comprobar(p, d2).valido, "comprobador válido en el resultado del motor")
shutil.rmtree(tmp, ignore_errors=True)
print(f"\n{fallos} fallos"); sys.exit(1 if fallos else 0)
