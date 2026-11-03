"""Prueba offscreen de los retoques del Editor (webinar avanzado 4/4 + recursos) sobre SINTETICO_grande (solo SINT-*).

Cubre: diálogo 429 (todas las opciones → PDF), presentación de celdas 196, letreros (botones 3D, tracking,
«Todas de defecto»), VENTANAS (solapas especiales, barras, notificaciones, opciones de confirmación/aviso 781,
coloca iconos), EDICIÓN (buscar, seleccionar todo + copiar, cambiar nombres y claves 209/210 con unicidad,
marcos horarios), Recombinador 754/773, Sesiones sin hueco en el horario (Separar, Duplicar, asistente) y
guardar/recargar sin tocar el .xghc original. No imprime nombres reales.
"""
import sys, os, tempfile, shutil, hashlib, copy
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import _rutas as _R
from horarios.textos import TX
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QSettings
app = QApplication.instance() or QApplication(sys.argv)
QApplication.setOrganizationName("LomoXSoftPruebas")
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
QMessageBox.information = staticmethod(lambda *a, **k: None)
QMessageBox.warning = staticmethod(lambda *a, **k: None)
from horarios import APP_EDITOR, VENDOR, AJUSTES
from horarios import editor as E, informes as INF, informes_ui as IU, editor_modelo as EM
fallos = 0


def check(c, m):
    global fallos
    print(("OK   " if c else "FALLO") + " " + m); fallos += (not c)


R = _R.R; tmp = tempfile.mkdtemp()
for f in ("SINTETICO_grande.xghc", "SINTETICO_grande.lphr"):
    shutil.copy(os.path.join(R, f), tmp)
X = os.path.join(tmp, "SINTETICO_grande.xghc"); L = os.path.join(tmp, "SINTETICO_grande.lphr")
h0 = hashlib.md5(open(X, "rb").read()).hexdigest()
st = QSettings(VENDOR, AJUSTES); guard = {k: st.value(k) for k in st.allKeys() if k.startswith("editor/")}
w = E.VentanaEditor(L, X); w._no_modal = True; w._preguntar_proyeccion = False; w.show(); app.processEvents(); ed = w.ed
check("GHC" not in w.windowTitle() and w.windowTitle().startswith(APP_EDITOR), "título con la marca propia")

# ---- 429
pdfs = 0
for cid, tipo in IU.DialogoListadoPDF.TIPO_RADIO.items():
    for pres in ("uno", "completo"):
        o = copy.deepcopy(w._opc()); o["tipo"] = tipo; o["presentacion"] = pres; o["prohibiciones"] = True
        d = IU.DialogoListadoPDF(w, o); oo = d.opciones()
        ok = oo["tipo"] == tipo and oo["presentacion"] == pres
        tabs = INF.tablas_de(ed, tipo, oo)
        if tabs:
            r = os.path.join(tmp, f"{tipo}_{pres}.pdf"); INF.exportar_pdf(tabs, r, oo, [X, L]); pdfs += ok and os.path.getsize(r) > 500
check(pdfs >= 10, f"429: tipos × presentación (incl. completo y prohibiciones) generan PDF ({pdfs})")
d = IU.DialogoListadoPDF(w, w._opc())
check(all(c.isEnabled() for c in d.c.values() if hasattr(c, "isEnabled") and c.objectName() not in ("c57670",)), "429: ningún control deshabilitado")

# ---- 196
d = w.menu_opciones_celdas(); d.c[1091].setChecked(True); d.c[1092].setChecked(True); d.siempre(2)
v = d.valores(); d.close()
check(v["ocultar_aula"] and v["una_fila"] and v["ident"]["profesores"] == "completo", '196: casillas y «Siempre el nombre largo»')
ed.fijar_celdas(v); w.refrescar(); t = w._vista_actual().tabla()
txt = [t.item(r, c).text() for r in range(t.rowCount()) for c in range(t.columnCount()) if t.item(r, c) and t.item(r, c).text()]
check(txt and all("\n" not in x for x in txt), "196: una sola fila por celda")
w.deshacer() if hasattr(w, "deshacer") else ed.deshacer(); w.refrescar()
check(not ed.celdas()["una_fila"], "196: deshacer recupera la presentación")

# ---- letreros
o = w._opc(); o["botones_3d"] = True; o["senala_fila"] = True; o["color_track_linea"] = "#00aa00"
dl = IU.DialogoLetreros(w, o); check(dl.cb_extra["botones_3d"].isChecked(), "letreros: botones 3D habilitado")
dl.por_defecto(); oo = dl.opciones()
check(not oo["botones_3d"] and oo["color_track_linea"] == INF.OPC_DEF["color_track_linea"], "letreros: «Todas de defecto»")
w._fijar_opc(o); w.refrescar(); t = w._vista_actual().tabla(); t.setCurrentCell(1, 1); t._senalar(); app.processEvents()
check(t.verticalHeaderItem(1).background().color().name() == "#00aa00", "letreros: señala fila actual con el color de tracking")
w._fijar_opc(INF.OPC_DEF.copy())

# ---- VENTANAS
for cid, modo in ((32799, "lista"), (32846, "columnas"), (32772, "filas"), (32840, "recreo"), (32932, "cruce"),
                  (32908, "aulas_libres"), (32810, "prof_libres")):
    w.acc[cid].trigger(); app.processEvents(); t = w._vista_actual().tabla()
    check(getattr(t, "modo", None) == modo and t.rowCount() > 0 and t.columnCount() > 0, f"VENTANAS: nueva solapa «{E.TablaEspecial.NOMBRES[modo]}»")
for cid, tb in ((32948, "tb_edicion"), (32790, "tb_seleccion")):
    a = getattr(w, tb).isVisible(); w.acc[cid].trigger(); check(getattr(w, tb).isVisible() != a, f"VENTANAS: barra {tb}")
w.sel_vista.setCurrentText("Aulas"); check(w.sel_el.count() == len(ed.elementos("Aulas")), "barra de selección lista los elementos")
dn = w.notificaciones(); check(dn.isVisible() and w.lst_notif.count() >= 1, "VENTANAS: notificaciones")
for cid in (33081, 33086):
    a = w.acc[cid].isChecked(); w.acc[cid].trigger(); check(w.acc[cid].isChecked() != a, f"VENTANAS: opción {cid} conmutable")
w.opciones = {"aula"}; da = w.aviso_ocultos(); check(da is not None and "aula" in da.c[1020].text(), "aviso 781 de opciones que ocultan información")
da.close(); w.opciones = set()
w.coloca_iconos(); check(all(s.isMinimized() for s in w.mdi.subWindowList()), "VENTANAS: coloca iconos")
for s in w.mdi.subWindowList():
    s.showNormal()

# ---- EDICIÓN
nm = ed.elementos("Profesorado")[3]
check(w.buscar(nm[-4:]) is not None, "EDICIÓN: buscar"); check(w.buscar("ZZZ-no-existe") is None, "EDICIÓN: buscar sin resultado")
w.ir_a("Grupos", ed.elementos("Grupos")[0]); w.seleccionar_todo(); t = w._vista_actual().tabla()
vis = sum(1 for r in range(t.rowCount()) for c in range(t.columnCount()) if not t.isRowHidden(r) and t.item(r, c)
          and t.item(r, c).flags() & E.Qt.ItemIsSelectable)
check(len(t.selectedItems()) == vis, f"EDICIÓN: seleccionar todo (celdas visibles {len(t.selectedItems())}/{vis})"); w.copiar()
check(QApplication.clipboard().text().count("\n") == t.rowCount(), "copiar la tabla seleccionada")
for cid, (cat, _) in E.CAT_NOMBRES.items():
    w.acc[cid].trigger(); dn = w._dlg_nombres
    check(dn.lst.topLevelItemCount() == len(ed.lista_cat(cat)), f"209: lista {cat}"); dn.close()
w.acc[32824].trigger(); dn = w._dlg_nombres; dn.lst.topLevelItem(0).setSelected(True); di = dn.modificar(True)
otro = dn.filas[1][1]; di.c[1000].setText(otro)
check(di.aceptar() is False and di.error == TX("codigos_no_pueden_repetir"), "210: no se repiten identificativos (cadena 630)")
orig = dn.filas[0][0]; di.c[1000].setText("SINT-NUEVO-ID"); di.c[1018].setText("SINT Nombre completo"); check(di.aceptar(), "210: aceptar cambio")
check(ed.ident("profesores", orig) == "SINT-NUEVO-ID" and ed.ident("profesores", orig, "completo") == "SINT Nombre completo", "nombres: identificativo y nombre completo")
w.ir_a("Profesorado", orig); t = w._vista_actual().tabla()
cel = " ".join(t.item(r, c).text() for r in range(t.rowCount()) for c in range(t.columnCount()) if t.item(r, c))
check(w.buscar("SINT-NUEVO-ID") == ("Profesorado", orig), "buscar por el identificativo nuevo")
grp = ed.elementos("Grupos")
alg = next((g for g in grp if "SINT-NUEVO-ID" in " ".join(ed.texto_celda(it, "Grupos") for it in ed.items_de("Grupos", g))), None)
check(alg is not None, "las celdas muestran el identificativo nuevo")
dn.close()
for que, cid in (("horas", 32842), ("claves", 33008), ("nombres", 33015)):
    w.acc[cid].trigger(); dm = w._dlg_marcos
    if que == "horas":
        dm.tab.item(0, 1).setText("07:55")
    elif que == "claves":
        dm.tab.item(0, 1).setText("P1")
    else:
        dm.tab.item(0, 1).setText("SINT Marco")
    dm.aceptar()
w.ir_a("Grupos", grp[0]); t = w._vista_actual().tabla()
check(t.verticalHeaderItem(0).text().startswith("P1\n07:55"), "marcos horarios: horas de entrada y clave del periodo")
check(ed.nombre_marco(list(ed.p.marcos)[0]) == "SINT Marco", "marcos horarios: nombre del marco")

# ---- Fuera: Separar, Duplicar, asistente
s0 = ed.obj("s:3"); dst = (s0["marco"], s0["dia"], s0["tramos"][0])
ed.extraer(["s:0"]); w.refrescar(); it = f"n:{len(ed.doc['no_colocadas']) - 1}"
w.sesiones_sin_colocar(); df = w.findChildren(E.DialogoFuera)[0]
check(all(df.c[k].isEnabled() for k in (1501, 1094, 1095)), "166: Separar, Duplicar y asistente habilitados")
n0 = len(ed.doc["no_colocadas"]); df.seleccionar(it); nuevas = df.duplicar()
check(len(ed.doc["no_colocadas"]) == n0 + 1 and nuevas and all(s in ed.ses for s in nuevas), "Duplicar: nueva línea con sesiones nuevas")
df.seleccionar(it); sep = df.separar()
ref0 = ed.obj(it)["sesiones"]
check(sep and ref0 == sep and all(s in ed.ses for s in sep), "Separar: sesiones independientes")
df.seleccionar(it); df.separar(); check("independientes" in (getattr(df, "ultimo_aviso", "") or ""), "Separar: aviso si ya son independientes")
# ---- Recombinador
df.seleccionar(it); d = df.asistente(); check(isinstance(d, E.DialogoRecombinador) and d.c[1518].isVisible(), '754: abre el asistente («Cualquier celda del marco»)')
dr = d.ver_profesores(); dr._todas(E.Qt.Unchecked); dr.lst.topLevelItem(0).setCheckState(0, E.Qt.Checked); d.prof_fijos = set(e.nombre for e in ed.p.profesores) - dr.marcadas(); d._contadores(); dr.close()
check(str(len(ed.p.profesores) - 1) in d.c[1528].text(), "939: profesores inmovilizados")
d.prof_fijos = set(); d._contadores(); d.destino = dst; d.c[1000].setValue(2)
sols = d.buscar()
check(0 < len(sols) <= 4 and all(len(s["movs"]) <= 3 for s in sols), f"754: soluciones encontradas ({len(sols)})")
check("La solución  1  ha realizado" in d.c[1525].text(), "754: resumen de la solución")
ds = d.ver_solucion(); check(ds.windowTitle() == "Viendo los movimientos de la solución 1" and ds.tabs.count() == len(sols[0]["movs"]), "773: movimientos de la solución")
ds.tabs.setCurrentIndex(ds.tabs.count() - 1); check(ds.c[1527].text().startswith(f"Movimiento {ds.tabs.count()} "), "773: navegar movimientos")
nf = len(ed.doc["no_colocadas"]); fis0 = len(ed.choques(ed.doc)) if hasattr(ed, "choques") else 0
check(ds.aplicar() and len(ed.doc["no_colocadas"]) == nf - 1, "773: aplicar esta solución coloca la sesión")
check((len(ed.choques(ed.doc)) if hasattr(ed, "choques") else 0) <= fis0, "recombinación sin choques físicos nuevos")
w.deshacer() if hasattr(w, "deshacer") else ed.deshacer(); check(len(ed.doc["no_colocadas"]) == nf, "deshacer la recombinación")

# ---- guardar y recargar
ed.guardar(); ed2 = EM.Editor(L, X)
check(all(s in ed2.ses for s in sep + nuevas), "guardar/recargar: sesiones separadas y duplicadas")
check(ed2.ident("profesores", orig) == "SINT-NUEVO-ID", "guardar/recargar: nombres de presentación")
check(hashlib.md5(open(X, "rb").read()).hexdigest() == h0, ".xghc original intacto")
for k in [k for k in st.allKeys() if k.startswith("editor/")]:
    st.remove(k)
for k, v in guard.items():
    st.setValue(k, v)
shutil.rmtree(tmp, ignore_errors=True)
print(f"\n{fallos} fallos"); sys.exit(1 if fallos else 0)
