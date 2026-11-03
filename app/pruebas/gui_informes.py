"""Prueba offscreen de INFORMES / IMPRESIÓN del Editor.

Genera cada informe (rejillas y listados) desde copias de SINTETICO_grande y prueba1, comprueba páginas con
pdfinfo y textos con pdftotext, ejercita los diálogos (429, 690, 139, 752, 784, Letreros, Cabeceras),
la presentación preliminar y la exportación «distintos documentos». Verifica que los originales no cambian.
No imprime nombres de personas.
"""
import sys, os, tempfile, shutil, hashlib, subprocess, re, faulthandler, signal
faulthandler.register(signal.SIGUSR1)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import _rutas as _R
from horarios.textos import TX
from PySide6.QtWidgets import QApplication, QMessageBox, QFileDialog, QDialog
from PySide6.QtPrintSupport import QPrintPreviewDialog
from horarios import APP_NAME, VENDOR
from horarios.textos import DIALOGOS, MENUS_EDITOR
from horarios import editor as E, informes as I, informes_ui as IU

app = QApplication.instance() or QApplication(sys.argv)
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
QMessageBox.information = staticmethod(lambda *a, **k: None)
QMessageBox.warning = staticmethod(lambda *a, **k: None)
IU.guardar_por_defecto({})
fallos = 0


def check(c, m):
    global fallos
    print(("OK   " if c else "FALLO") + " " + m); fallos += (not c)


def paginas(r):
    return int(re.search(r"Pages:\s+(\d+)", subprocess.run(["pdfinfo", r], capture_output=True, text=True).stdout).group(1))


def texto(r):
    return subprocess.run(["pdftotext", "-layout", r, "-"], capture_output=True, text=True).stdout


def md5(r):
    return hashlib.md5(open(r, "rb").read()).hexdigest()


RAIZ = _R.R; SAL = os.path.join(RAIZ, "informes_muestra"); os.makedirs(SAL, exist_ok=True)
orig = {f: md5(os.path.join(RAIZ, f)) for f in ("SINTETICO_grande.xghc", "SINTETICO_grande.lphr", "prueba1.xghc", "prueba1.lphr") if _R.hay(os.path.join(RAIZ, f))}
E.VentanaEditor.abrir_planificador = staticmethod(lambda r: None)

for base in [os.path.basename(b)[:-5] for b in _R.disponibles(*(os.path.join(RAIZ, n + ".xghc") for n in ("SINTETICO_grande", "prueba1")))]:
    tmp = tempfile.mkdtemp(); X = os.path.join(tmp, base + ".xghc"); L = os.path.join(tmp, base + ".lphr")
    shutil.copy(os.path.join(RAIZ, base + ".xghc"), X); shutil.copy(os.path.join(RAIZ, base + ".lphr"), L)
    w = E.VentanaEditor(L, X); w.show(); app.processEvents(); ed = w.ed; p = ed.p
    o = I.opciones(ed.doc, {"centro": "IES SINTÉTICO", "localidad": "Villaprueba", "curso": "2026-2027"})
    n_prof = len(p.profesores); n_gr = len(ed.elementos("Grupos"))
    esperado = {"alumnos": n_gr, "profesores": n_prof, "individual": n_prof, "materias": len(p.materias),
                "guardias": len(ed.elementos("Guardias")) or None, "reuniones": None}
    print(f"--- {base}")
    for tipo in list(I.TIPOS) + list(I.LISTADOS):
        tablas = I.tablas_de(ed, tipo, o)
        r = os.path.join(tmp if base == "prueba1" else SAL, f"{base}_{tipo}.pdf")
        I.exportar_pdf(tablas, r, o, [X, L])
        np_, tx = paginas(r), texto(r)
        ok = os.path.getsize(r) > 1000 and np_ >= 1 and f"{APP_NAME} · {VENDOR}" in tx and f"Página 1 de {np_}" in tx \
            and "IES SINTÉTICO" in tx and "Villaprueba" in tx
        if tipo in esperado and esperado[tipo] and tipo not in I.LISTADOS:
            ok = ok and np_ == esperado[tipo]
        check(ok, f"{base}: PDF {tipo} ({np_} págs.)")
        if tipo == "alumnos":
            check("Horario semanal: Grupos de alumnos" in tx and "Lunes" in tx and "Viernes" in tx and "RECREO" in tx, f"{base}: títulos, días y recreo")
            multi = any(len(lst) >= 3 for t_ in tablas for lst in [[1] * len(c) for c in t_.celdas.values()]) or \
                any(t_.leyenda for t_ in tablas)
            if multi:
                check("[op." in tx and "(*)" in tx, f"{base}: leyenda de optativas (*) [op.N]")
            else:
                print(f"     ({base}: sin celdas con desdobles; leyenda no aplicable)")
        if tipo == "individual":
            check("Total semanal" in tx and "Resumen de horas" in tx, f"{base}: resumen de horas del profesor")
        if tipo == "prof_libres":
            check(TX("profs_libres") in tx and "periodo" in tx, f"{base}: profesores libres por periodo")
        if tipo == "profesores" and base == "SINTETICO_grande":
            check(" – " in tx, "departamento en el subtítulo")
    # optativas: se simulan tres sesiones simultáneas en un grupo (sin tocar el documento)
    g0 = ed.elementos("Grupos")[0]; its = [x for x in ed.items_de("Grupos", g0) if x[0] == "s"][:3]
    real = ed.posiciones; fija = real(its[0])
    ed.posiciones = lambda it, _r=real: fija if it in its else _r(it)
    ro = os.path.join(tmp, "op.pdf"); I.exportar_pdf(I.tablas_de(ed, "alumnos", o, [g0]), ro, o); ed.posiciones = real
    tx = texto(ro); check("(*) [op.1]" in tx and "op.1:" in tx and "Optativas" in tx, f"{base}: celda «(*) [op.N]» y leyenda de optativas")
    # nunca sobre originales
    try:
        I.exportar_pdf(I.tablas_de(ed, "alumnos", o), X, o, [X, L]); check(False, "rechaza sobrescribir original")
    except ValueError:
        check(True, f"{base}: rechaza sobrescribir el .xghc original")
    # varias por página / solo ocupada / distintos documentos
    o2 = dict(o, varias_por_pagina=True); r2 = os.path.join(tmp, "dos.pdf"); I.exportar_pdf(I.tablas_de(ed, "alumnos", o2), r2, o2)
    check((n_gr + 1) // 2 <= paginas(r2) < n_gr, f"{base}: dos tablas por página")
    d3 = os.path.join(tmp, "distintos"); n = I.exportar_distintos(I.tablas_de(ed, "aulas", o), d3, o)
    check(n == len([f for f in os.listdir(d3) if f.endswith(".pdf")]) and os.path.exists(os.path.join(d3, "index.html")), f"{base}: un PDF por aula + índice")

    # ---------------- diálogos y menú
    for cid in (57609, 57607, 32802, 32793, 57606, 32778, 32977, 32978, 32818, 33096, 33002, 33001, 33028, 33027):
        a = w.acc.get(cid)
        check(a is not None and a.isEnabled() and "Próximamente" not in a.text(), f"{base}: menú {cid} activo")
    d = IU.DialogoListadoPDF(w, w._opc())
    check(d.windowTitle() == DIALOGOS["E429"]["titulo"] and d.c[1113].isEnabled() and d.c[1118].isEnabled() and d.c[1003].isChecked(), f"{base}: diálogo 429")
    d.c[1005].setChecked(True); d.c[1016].setChecked(True); d.c[1126].setChecked(True); oo = d.opciones()
    check(oo["tipo"] == "profesores" and oo["varias_por_pagina"] and oo["ocultar_profesor"], f"{base}: 429 devuelve opciones")
    d.rb_mat.setChecked(True); check(d.opciones()["tipo"] == "materias", f"{base}: radio Materias")
    # Transferir > Documentos PDF (flujo completo con diálogo aceptado)
    IU.DialogoListadoPDF.exec = lambda self: (self.c[1018].setChecked(True), 1)[1]
    salida = os.path.join(tmp, "transf.pdf")
    QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (salida, ""))
    r = w.transferir_pdf(); check(r and os.path.exists(salida) and "REUNIÓN" in texto(salida), f"{base}: Transferir > Documentos PDF (reuniones)")
    check(ed.doc["editor"]["informes"]["tipo"] == "reuniones", f"{base}: opciones guardadas en el documento")
    w.ed.deshacer(); w.refrescar()
    IU.DialogoTablaPDF.exec = lambda self: 1
    salida = os.path.join(tmp, "tabla.pdf"); r = w.guardar_tabla_pdf()
    check(r and paginas(salida) == 1 and "Horario semanal" in texto(salida), f"{base}: guardar la tabla en PDF (690)")
    # 139
    d = IU.DialogoImprimirListado(w, w._opc())
    check(d.windowTitle() == DIALOGOS["E139"]["titulo"] and d.c[1013].isChecked() and d.c[1004].count() == len(d.OPCIONES), f"{base}: diálogo 139")
    check(len(d.tablas()) == 1, f"{base}: 139 vista actual = 1 tabla")
    d.c[1045].setChecked(True); d.c[1004].setCurrentIndex([k for k, _ in d.OPCIONES].index("profesores"))
    check(len(d.tablas()) == n_prof, f"{base}: 139 listado todos los profesores")
    d.c[1015].setChecked(True); d.c[1007].setCurrentIndex(0); d.c[1008].setCurrentIndex(2)
    check(len(d.tablas()) == 3, f"{base}: 139 selección desde/hasta")
    if d.c[1009].count():
        d.c[1002].setChecked(True); dep = d.c[1009].currentText()
        check(len(d.tablas()) == sum(1 for e in p.profesores if e.datos.get("departamento") == dep), f"{base}: 139 por departamento")
    d.c[1004].setCurrentIndex([k for k, _ in d.OPCIONES].index("resumen_horas")); d.c[1005].setChecked(True)
    check(d.tablas()[0].titulo == "Resumen de las horas de los profesores", f"{base}: 139 resumen de horas")
    # 752, 784, letreros, cabeceras
    t = IU.DialogoTextoPie(w, "Texto SINT"); check(t.texto() == "Texto SINT", f"{base}: 752 texto al pie")
    i = IU.DialogoIdiomaLetreros(w); check(i.c[1001].isChecked() and not i.c[1006].isEnabled(), f"{base}: 784 idiomas (solo castellano)")
    lt = IU.DialogoLetreros(w, w._opc()); lt.ed[("dias", 0)].setText("LUN"); lt.ed[("recreo", None)].setText("PATIO"); lt.cb_v.setChecked(False)
    ol = lt.opciones(); check(ol["letreros"]["dias"][0] == "LUN" and not ol["lineas_v"], f"{base}: Letreros y configuración")
    w._fijar_opc(ol); t0 = w._vista_actual().tabla()
    check(t0.horizontalHeaderItem(0).text() == "LUN", f"{base}: letreros aplicados en la rejilla")
    rr = os.path.join(tmp, "let.pdf"); I.exportar_pdf(w.tablas_actuales(), rr, w._opc())
    check("LUN" in texto(rr) and "PATIO" in texto(rr), f"{base}: letreros en el PDF")
    w.ed.deshacer(); w.refrescar()
    c = IU.DialogoCabeceras(w, w._opc()); c.e_centro.setText("IES SINT"); c.cb["pie_marca"].setChecked(False)
    oc = c.opciones(); rr = os.path.join(tmp, "cab.pdf"); I.exportar_pdf(w.tablas_actuales(oc), rr, oc)
    check("IES SINT" in texto(rr) and "LomoXSoft" not in texto(rr), f"{base}: cabeceras y pies")
    # presentación preliminar
    w._no_modal = True; pv = w.presentacion_preliminar()
    check(isinstance(pv, QPrintPreviewDialog) and pv.windowTitle() == TX("vista_previa"), f"{base}: presentación preliminar")
    pv.show(); app.processEvents(); pv.close()
    # listados del menú INFORMES
    for cid, tipo in ((33002, "asignaciones"), (33001, "equipos"), (33028, "tutores_alumnos"), (33027, "tutores_tutor")):
        salida = os.path.join(tmp, f"m{cid}.pdf"); w.acc[cid].trigger(); app.processEvents()
        check(os.path.exists(salida) and I.LISTADOS[tipo].split()[0] in texto(salida), f"{base}: INFORMES {cid} ({tipo})")
    w.ed.modificado = False; w._preguntar_proyeccion = False; w.close()

for f, h in orig.items():
    check(md5(os.path.join(RAIZ, f)) == h, f"original {f} intacto")
print(f"\n{'TODO OK' if not fallos else str(fallos) + ' FALLOS'}")
sys.exit(1 if fallos else 0)
