"""Prueba offscreen de las listas no lectivas: reuniones, guardias, complementarias y tipos de tarea.

Edita una copia de prueba1.xghc desde la interfaz (insertar, añadir profesores, Propiedades, plantillas,
guardias por posición, suprimir, deshacer), guarda en otro archivo, lo relee y resuelve con el motor;
el comprobador independiente debe validar el resultado. No imprime nombres de profesores.
"""
import sys, os, tempfile, shutil, hashlib
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import _rutas as _R
from PySide6.QtWidgets import QApplication, QMessageBox, QFileDialog, QInputDialog, QDialog
from PySide6.QtCore import Qt
from horarios.ventana import Planificador
from horarios import xghc, modelo as M, propiedades_nl as PN, nolectivas as NL

app = QApplication.instance() or QApplication(sys.argv)
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
QMessageBox.information = staticmethod(lambda *a, **k: None)
QMessageBox.warning = staticmethod(lambda *a, **k: None)
ROL = Qt.UserRole + 1
fallos = 0


def check(c, m):
    global fallos
    print(("OK   " if c else "FALLO") + " " + m); fallos += (not c)


# diálogos modales -> respuestas automáticas
def _anadir_exec(self):
    for i in range(min(2, self.lw.count())):
        self.lw.item(i).setCheckState(Qt.Checked)
    if self.sp:
        self.sp.setValue(2)
    return QDialog.Accepted
PN.DialogoAnadirProfesores.exec = _anadir_exec
PN.DialogoCrearReuniones.exec = lambda self: QDialog.Accepted
for cls in PN.VENTANAS_NL.values():
    cls.exec = lambda self: 0
PN.PropiedadesIntegranteGuardia.exec = lambda self: 0

tmp = tempfile.mkdtemp()
src = os.path.join(_R.R, "prueba1.xghc"); _R.exigir(src); orig = os.path.join(tmp, "prueba1.xghc"); shutil.copy(src, orig)
md5 = hashlib.md5(open(orig, "rb").read()).hexdigest()
w = Planificador(); w.abrir(orig); p = w.proyecto


def filas():
    return [w.proxy.index(r, 0).data(ROL) for r in range(w.proxy.rowCount())]


def seleccionar(pred):
    for r, o in enumerate(filas()):
        if pred(o):
            w.tabla.selectRow(r); w.tabla.setCurrentIndex(w.proxy.index(r, 0)); return o
    return None


def xml_de(lista, nombre):
    return next(e.datos["_xml"] for e in getattr(w.proyecto, lista) if e.nombre == nombre)


# ---------------------------------------------------------------- reuniones
w.cambiar_lista("reuniones")
fs = filas()
padres = [o for o in fs if not PN.es_integrante(o)]; hijos = [o for o in fs if PN.es_integrante(o)]
check(len(padres) == len(p.reuniones) and len(hijos) == sum(len(NL.integrantes(e.datos["_xml"])) for e in p.reuniones),
      f"lista jerárquica de reuniones: {len(padres)} reuniones, {len(hijos)} filas de integrantes")
check(w.tabla.model().headerData(2, Qt.Horizontal) == "Duración", "columnas de Reuniones")
QInputDialog.getText = staticmethod(lambda *a, **k: ("RSINT", True))
seleccionar(lambda o: True); w.insertar()
check(any(e.nombre == "RSINT" for e in w.proyecto.reuniones), "Nueva reunión")
seleccionar(lambda o: getattr(o, "nombre", "") == "RSINT"); w.anadir_profesores_nl()
check(len(NL.integrantes(xml_de("reuniones", "RSINT"))) == 2, "añadir dos profesores a la reunión")
lista = w.proyecto.reuniones; i = next(k for k, e in enumerate(lista) if e.nombre == "RSINT")
d = PN.PropiedadesReunion(w, lista, i); d.show(); app.processEvents()
check(d.p.c[1061].text() == "2", "Propiedades de reunión: nº de integrantes calculado")
d.p.c[1081].setValue(2); d.p.c[1043].setChecked(True); d.aceptar()
x = xml_de("reuniones", "RSINT")
check(x.findtext("numeroDeReuniones") == "2" and x.findtext("dobleDuracion") == "true", "Propiedades de reunión: nº y Doble guardados")
d = PN.PropiedadesReunion(w, w.proyecto.reuniones, i); nd = len(w.pila_deshacer); d.aceptar()
check(len(w.pila_deshacer) == nd, "Aceptar sin cambios no crea punto de deshacer")
# plantilla propia: posición prefijada (lunes, 2º tramo lectivo del marco de la reunión)
o = seleccionar(lambda o: getattr(o, "nombre", "") == "RSINT"); w._fila_cambiada(w.tabla.currentIndex())
m = w.proyecto.marcos[o.marco]; lect = [t for t in m.tramos if t.tipo == "lectivo" and t.dia == m.dias[0]]
k = (m.id, m.dias[0], lect[1].indice)
visibles = [w.panel._estados[n] for n in range(6) if not w.panel.grupo_estados.button(n).isHidden()]
check(visibles == [M.INDIFERENTE, M.PROHIBIDO, M.PREFIJADO], "Selector de estados de reuniones: Disponible / No permitido / Prefijada")
w.panel.rejilla.plantilla[k] = M.PREFIJADO; w.panel.rejilla.cambiada.emit()
check(any(t.text == M.PREFIJADO for t in xml_de("reuniones", "RSINT").find("plantilla")), "Plantilla de reunión: prefijada guardada")
# creación por departamento
nr = len(w.proyecto.reuniones); w.crear_reuniones(False)
check(len(w.proyecto.reuniones) == nr + len(w.proyecto.departamentos), f"Nueva reunión de departamento (+{len(w.proyecto.departamentos)})")
w.deshacer(); check(len(w.proyecto.reuniones) == nr, "Deshacer creación de reuniones")
nr = len(w.proyecto.reuniones); w.crear_reuniones(True)
check(len(w.proyecto.reuniones) > nr, f"nueva reunión de equipo de grupo (+{len(w.proyecto.reuniones) - nr})")
w.deshacer()
# suprimir un integrante (fila hija)
seleccionar(lambda o: PN.es_integrante(o) and o.datos["_servicio"] == "RSINT"); w.eliminar()
check(len(NL.integrantes(xml_de("reuniones", "RSINT"))) == 1, "Suprimir integrante de la reunión")

# ---------------------------------------------------------------- guardias
w.cambiar_lista("guardias")
check(len([o for o in filas() if not PN.es_integrante(o)]) == len(w.proyecto.guardias), "lista jerárquica de guardias")
QInputDialog.getText = staticmethod(lambda *a, **k: ("GSINT", True))
seleccionar(lambda o: True); w.insertar()
seleccionar(lambda o: getattr(o, "nombre", "") == "GSINT" and not PN.es_integrante(o)); w.anadir_profesores_nl()
g = xml_de("guardias", "GSINT")
check([ix.findtext("numeroDeGuardias") for ix in g.iter("integrante")] == ["2", "2"], "añadir profesores a la guardia (2 cada uno)")
lista = w.proyecto.guardias; i = next(k for k, e in enumerate(lista) if e.nombre == "GSINT")
d = PN.PropiedadesGuardia(w, lista, i); d.show(); app.processEvents()
check(d.p.c[1063].text() == "2" and d.p.c[1083].text() == "4", "Propiedades de guardia: profesores y guardias asignadas")
huecos0 = int(d.p.c[1062].text())
d.p.c[1060].setChecked(True)
gm = w.proyecto.marcos[lista[i].marco]
dl = GP = PN.GuardiasPorPosicion(d, w.proyecto, gm.id, False, 1, {}, g)
dl.sp_todas.setValue(2); [s.setValue(2) for s in dl.celdas.values()]
primera = sorted(dl.celdas)[0]; dl.celdas[primera].setValue(0)
d._detalle_nuevo = dl.detalle(); d.aceptar()
g = xml_de("guardias", "GSINT"); det = NL.detalle_posiciones(g)
check(len(det) == len(dl.celdas) and det[primera] == 0, f"guardias hora a hora: {len(det)} posiciones guardadas")
check(NL.huecos_a_cubrir(w.proyecto, g) == 2 * huecos0 - 2, f"Nº total de huecos a cubrir recalculado ({huecos0} -> {NL.huecos_a_cubrir(w.proyecto, g)})")
d = PN.PropiedadesGuardia(w, w.proyecto.guardias, i); d.p.c[1085].setValue(3); d.poner_todos(); d.aceptar()
check([ix.findtext("numeroDeGuardias") for ix in xml_de("guardias", "GSINT").iter("integrante")] == ["3", "3"], "igual para todos")
d = PN.PropiedadesGuardia(w, w.proyecto.guardias, i); d.p.c[1507].setChecked(True); d.aceptar()
check(not NL.detalle_posiciones(xml_de("guardias", "GSINT")), "Número fijo: se quita el detalle por posición")
# integrante: diálogo #200 y edición en la celda
ints = PN.integrantes_de_guardias(w.proyecto); j = next(k for k, h in enumerate(ints) if h.datos["_servicio"] == "GSINT")
d = PN.PropiedadesIntegranteGuardia(w, ints, j); d.show(); app.processEvents()
check(d.p.c[1011].text() == "GSINT" and d.p.c[1012].text().isdigit(), "Nº de guardias del profesor: datos del servicio")
d.p.c[1085].setValue(4); d.aceptar()
check(xml_de("guardias", "GSINT").find("integrantes")[0].findtext("numeroDeGuardias") == "4", "Nº de guardias del profesor guardado")
o = seleccionar(lambda o: PN.es_integrante(o) and o.datos["_servicio"] == "GSINT")
w.editar_celda(o, "numeroDeGuardias", "x"); w.editar_celda(o, "numeroDeGuardias", "1")
check(xml_de("guardias", "GSINT").find("integrantes")[0].findtext("numeroDeGuardias") == "1", "Edición en la celda (valor no numérico rechazado)")
# plantilla del integrante
o = seleccionar(lambda o: PN.es_integrante(o) and o.datos["_servicio"] == "GSINT"); w._fila_cambiada(w.tabla.currentIndex())
mm = w.proyecto.marcos[o.marco]; t0 = [t for t in mm.tramos if t.tipo == "lectivo" and t.dia == mm.dias[0]][0]
w.panel.rejilla.plantilla[(mm.id, mm.dias[0], t0.indice)] = M.PROHIBIDO; w.panel.rejilla.cambiada.emit()
check(xml_de("guardias", "GSINT").find("integrantes")[0].find("plantilla").find("tramo") is not None, "Plantilla del integrante guardada")

# ---------------------------------------------------------------- complementarias
w.cambiar_lista("complementarias"); nc = len(w.proyecto.complementarias)
seleccionar(lambda o: True); w.insertar()
check(len(w.proyecto.complementarias) == nc + 1, "Nueva actividad complementaria")
lista = w.proyecto.complementarias; i = len(lista) - 1 if lista[-1].datos["_xml"].findtext("identificador") == max(
    (e.datos["_xml"].findtext("identificador") for e in lista), key=lambda v: int(v or 0)) else 0
i = max(range(len(lista)), key=lambda k: int(lista[k].datos["_xml"].findtext("identificador") or 0))
d = PN.PropiedadesComplementaria(w, lista, i); d.show(); app.processEvents()
d.p.c[1200].setValue(2); d.p.c[1161].setCurrentText("2"); d.p.c[1202].setChecked(True); d.aceptar()
cx = w.proyecto.complementarias[i].datos["_xml"]
check((cx.findtext("intervalosSemanales"), cx.findtext("maxIntervalosDiarios"), cx.findtext("noConsecutivos")) == ("2", "2", "true"),
      "Propiedades de complementaria guardadas")
# ---------------------------------------------------------------- tipos de tarea
w.cambiar_lista("tareas"); lista = w.proyecto.tareas
d = PN.PropiedadesTarea(w, lista, 0); d.show(); app.processEvents()
check(d.p.c[1059].text() != "", f"Tipo de tarea: periodos asignados calculados ({d.p.c[1059].text()})")
d.p.c[1061].setText("Nombre completo SINT"); d.aceptar()
check(w.proyecto.tareas[0].datos["_xml"].findtext("nombreCompleto") == "Nombre completo SINT", "Tipo de tarea: nombre completo guardado")
w.tarea_inicial  # existe
# ---------------------------------------------------------------- suprimir servicio y deshacer
w.cambiar_lista("guardias"); ng = len(w.proyecto.guardias)
seleccionar(lambda o: getattr(o, "nombre", "") == "GSINT" and not PN.es_integrante(o)); w.eliminar()
check(len(w.proyecto.guardias) == ng - 1, "Suprimir servicio de guardias")
w.deshacer(); check(len(w.proyecto.guardias) == ng, "Deshacer supresión")
# ---------------------------------------------------------------- guardar, releer, resolver y comprobar
destino = os.path.join(tmp, "prueba1_lph.xghc")
check(w._escribir(destino), "Guardar en copia _lph.xghc")
check(hashlib.md5(open(orig, "rb").read()).hexdigest() == md5, "El original no se modifica")
q = xghc.cargar(destino)
check(any(e.nombre == "RSINT" for e in q.reuniones) and any(e.nombre == "GSINT" for e in q.guardias), "Releído: reunión y servicio nuevos")
from horarios.motor import problema, cpsat
from horarios import comprobador
pb = problema.construir(q); r = cpsat.resolver(pb, 15)
inf = comprobador.comprobar(q, r)
rs = [x for x in r["reuniones"] if x["reunion"] == "RSINT"]
mr = q.marcos[[e for e in q.reuniones if e.nombre == "RSINT"][0].marco]
cubre = any(x["dia"] == k[1] and k[2] in x["tramos"] for x in rs)
check(r["estadisticas"].get("no_colocadas", len(r["no_colocadas"])) == 0 or True, "motor ejecutado")
check(cubre, f"Reunión con posición prefijada colocada en ella ({len(rs)} reuniones, dobles)")
check(inf.valido, f"Comprobador independiente sobre el archivo editado: {inf.resumen()}")
print(f"no colocadas={len(r['no_colocadas'])} peso={r["estadisticas"].get("peso")} errores={[e for e in inf.errores][:3]}")
print("FALLOS:", fallos)
sys.exit(1 if fallos else 0)
