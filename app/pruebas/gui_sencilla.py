"""Versión sencilla: selector, un test por paso (1–9), pegar (también en la clásica), alternar en caliente.
Solo datos SINT. --capturas guarda capturas/sencilla_real_*.png"""
import sys, os, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PySide6.QtWidgets import QApplication, QMessageBox, QFileDialog, QInputDialog
from PySide6.QtCore import QSettings
tmp = tempfile.mkdtemp()
QSettings.setDefaultFormat(QSettings.IniFormat); QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, tmp)
app = QApplication.instance() or QApplication(sys.argv); app.setStyle("Fusion")
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
QMessageBox.information = staticmethod(lambda *a, **k: None)
QMessageBox.warning = staticmethod(lambda *a, **k: None)
destino = os.path.join(tmp, "SINT_sencilla.xghc")
QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (destino, ""))
CAPT = "--capturas" in sys.argv
DIRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "capturas")
fallos = 0
def check(c, m):
    global fallos
    print(("OK   " if c else "FALLO") + " " + m, flush=True); fallos += (not c)
def foto(w, n):
    if CAPT:
        app.processEvents(); w.grab().save(os.path.join(DIRC, f"sencilla_real_{n}.png"))

def main():
    from horarios.sencilla import selector as SEL
    from horarios.sencilla.ventana import VentanaSencilla
    from horarios.sencilla import textos as T
    from horarios import pegar as PG, xghc

    # ---------------- selector
    check(SEL.version_guardada() is None, "selector: sin elección recordada al principio")
    d = SEL.SelectorVersion(); d.chk.setChecked(True); foto(d, "0_selector"); d.botones["sencilla"].click()
    check(d.eleccion == "sencilla" and SEL.version_guardada() == "sencilla", "selector: «Recordar mi elección» guarda la sencilla")
    check(SEL.preguntar(None, "clasica") == "clasica", "selector: --clasica manda sobre lo recordado")
    SEL.recordar("clasica", False); check(SEL.version_guardada() is None, "selector: sin recordar vuelve a preguntar")

    # ---------------- pegar (módulo)
    f = PG.filas_de_texto("Nombre\tNombre completo\tDepartamento\nSINT-P1\tSINT Profe Uno\tSINT-MAT\nSINT-P2\t\t\n")
    check(f == [["SINT-P1", "SINT Profe Uno", "SINT-MAT"], ["SINT-P2", "", ""]], "pegar: TSV con cabecera")
    check(PG.filas_de_texto("SINT 1A;SINT1;SINT Aula 1A") == [["SINT 1A", "SINT1", "SINT Aula 1A"]], "pegar: CSV con ;")

    w = VentanaSencilla(); w.resize(1250, 800); w.show(); app.processEvents()
    check(w.p is not None and w.windowTitle().startswith("Sin título"), "ventana: archivo nuevo sin título")
    check(w.lst.count() == 9 and [w.lst.item(i).text()[3:] for i in range(9)] == [p[1] for p in T.PASOS], "9 pasos en orden")

    # ---------------- paso 1
    c = w.pasos[0]; w.ir(0)
    c.ed_centro.setText("SINT Centro de pruebas"); c._guardar_centro()
    c.configurar(dias=[0, 1, 2, 3, 4], inicio="08:30", duracion=55, clases=6, recreo_tras=3, recreo_dur=30)
    check(len(c.tramos()) == 7 and c.tramos()[3] == ("11:15", "11:45", "recreo"), f"paso 1: tramos calculados {c.tramos()[:4]}")
    check(c.aplicar(), "paso 1: aplicar horario")
    m = next(iter(w.p.marcos.values()))
    check(m.lectivos_por_semana() == 30 and len(m.filas()) == 7, f"paso 1: marco con 30 lectivos/semana y 7 filas")
    c.cargar(); check(c.sp_n.value() == 6 and c.sp_rec.value() == 3 and c.sp_dur.value() == 55, "paso 1: relee el horario del archivo")
    foto(w, "1_centro")

    # ---------------- paso 2
    w.ir(1); pp = w.pasos[1]
    check(pp.lista.anadir("SINT-P0"), "paso 2: añadir profesor")
    r = pp.lista.pegar("SINT-P1\tSINT Profe Uno\tSINT-MAT\nSINT-P2\tSINT Profe Dos\tSINT-LEN\nSINT-P3\t\tSINT-MAT\nSINT-P4\t\tSINT-ING")
    check(r["nuevos"] == 4 and len(w.p.profesores) == 5, "paso 2: pegar 4 profesores")
    check({d.nombre for d in w.p.departamentos} >= {"SINT-MAT", "SINT-LEN", "SINT-ING"}, "paso 2: departamentos creados al pegar")
    check(pp.lista.fijar("SINT-P0", "nombre", "SINT-P5") and "SINT-P5" in [e.nombre for e in w.p.profesores], "paso 2: renombrar")
    check(pp.lista.quitar(["SINT-P5"]) and len(w.p.profesores) == 4, "paso 2: quitar")
    check(pp.lista.t.rowCount() == 4, "paso 2: tabla actualizada")
    foto(w, "2_profesorado")

    # ---------------- paso 3
    w.ir(2); pg = w.pasos[2]
    check(pg.crear_varios("SINT1", "A B") == 2, "paso 3: crear varios grupos (SINT1 A, B)")
    check(pg.lista.anadir("SINT2 A") and len(w.p.grupos) == 3, "paso 3: añadir grupo")
    check(pg.aulas.anadir("SINT Lab 1") and pg.aulas.anadir("SINT Lab 2"), "paso 3: añadir aulas")
    g = next(e for e in w.p.grupos if e.nombre == "SINT1 A")
    check(g.datos.get("cursoPerteneciente") == "SINT1" and g.datos.get("aula") == "Aula SINT1 A", "paso 3: curso y aula del grupo")
    foto(w, "3_grupos")

    # conjunto (tipo de aula) para «¿Dónde?» — se crea en el archivo como en la clásica
    from horarios import edicion as ED
    def conj(a):
        raiz = a.raiz; ca = raiz.find("conjuntoDeAulas")
        if ca is None:
            ca = ED.insertar_hijo(a, raiz, ED.nuevo("conjuntoDeAulas"))
        ED.insertar_hijo(a, ca, ED.nuevo("conjunto", attrib={"nombre": "SINT Laboratorios"}, hijos=[ED.nuevo("aula", "SINT Lab 1"), ED.nuevo("aula", "SINT Lab 2")]))
        return True
    w.editar(conj, "tipo de aula")

    # ---------------- paso 4
    w.ir(3); pm = w.pasos[3]
    check(pm.materias.pegar("SINT-MAT\tMatemáticas\nSINT-LEN\tLengua\nSINT-ING\tInglés\nSINT-FQ\tFísica")["nuevos"] == 4, "paso 4: pegar materias")
    pm.cb_grupo.setCurrentText("SINT1 A")
    for mat, prof, h, dn in (("SINT-MAT", "SINT-P1", 4, None), ("SINT-LEN", "SINT-P2", 4, None), ("SINT-ING", "SINT-P4", 3, None),
                             ("SINT-FQ", "SINT-P3", 2, "Tipo: SINT Laboratorios")):
        pm.anadir(mat, prof, h, dn)
    ss = pm.sesiones("SINT1 A")
    check(len(ss) == 4 and sum(int(x) for s in ss for x in s.tmp) == 13, "paso 4: 4 materias, 13 horas en SINT1 A")
    fq = next(s for s in ss if s.materia == "SINT-FQ")
    check(pm.donde(fq) == "Tipo: SINT Laboratorios", "paso 4: «¿Dónde?» muestra el tipo de aula (conjunto)")
    check("Tipo: SINT Laboratorios" in pm.opciones_donde() and "SINT Lab 1" in pm.opciones_donde(), "paso 4: opciones de ¿Dónde? (aulas y tipos)")
    check(pm.fijar(fq.id, "donde", "SINT Lab 2") and pm.donde(next(s for s in pm.sesiones('SINT1 A') if s.materia == 'SINT-FQ')) == "SINT Lab 2", "paso 4: cambiar ¿Dónde? a un aula")
    fq = next(s for s in pm.sesiones('SINT1 A') if s.materia == 'SINT-FQ')
    pm.fijar(fq.id, "donde", "Tipo: SINT Laboratorios")
    check(pm.copiar_a("SINT1 B") == 4 and len(pm.sesiones("SINT1 B")) == 4, "paso 4: copiar materias a otro grupo")
    for s in pm.sesiones("SINT1 B"):
        pm.fijar(s.id, "profesor", {"SINT-MAT": "SINT-P3", "SINT-LEN": "SINT-P2", "SINT-ING": "SINT-P4", "SINT-FQ": "SINT-P1"}[s.materia])
    s0 = pm.sesiones("SINT1 B")[0]
    check(pm.fijar(s0.id, "horas", 3) and sum(int(x) for x in next(s for s in pm.sesiones("SINT1 B") if s.id == s0.id).tmp) == 3, "paso 4: cambiar horas")
    pm.fijar(s0.id, "horas", 4)
    pm.cb_grupo.setCurrentText("SINT1 A"); pm.cargar_grupo(); check(pm.t.rowCount() == 4, "paso 4: tabla del grupo")
    foto(w, "4_materias")

    # ---------------- paso 5
    w.ir(4); pf = w.pasos[4]
    pf.cb_tipo.setCurrentText("Profesorado"); pf.cb_nombre.setCurrentText("SINT-P1"); pf.cargar_rejilla()
    mid = next(iter(w.p.marcos))
    idx = [t.indice for t in w.p.marcos[mid].filas() if t.tipo == "lectivo"]
    check(pf.pintar([(mid, 4, idx[-1]), (mid, 4, idx[-2])], "prohibido"), "paso 5: «No puede» viernes últimas horas")
    check(pf.pintar([(mid, 0, idx[0])], "preferente") and pf.pintar([(mid, 1, idx[0])], "preferentementeNo1"), "paso 5: «Prefiere» y «Mejor no»")
    pl = pf.plantilla()
    check(pl.get((mid, 4, idx[-1])) == "prohibido" and pl.get((mid, 0, idx[0])) == "preferente" and pl.get((mid, 1, idx[0])) == "preferentementeNo1",
          "paso 5: estados guardados en la plantilla del archivo")
    check(pf.pintar([(mid, 1, idx[0])], "") and (mid, 1, idx[0]) not in pf.plantilla(), "paso 5: volver a «Disponible»")
    check(pf.t.item(len(idx) - 1, 4).text() == "No puede", "paso 5: rejilla muestra el estado")
    foto(w, "5_preferencias")

    # ---------------- paso 6
    w.ir(5); pgu = w.pasos[5]
    sv = pgu.nueva_guardia("SINT Guardia")
    check(sv and pgu.profesores_guardia(sv, ["SINT-P1", "SINT-P2", "SINT-P3"], 1), "paso 6: servicio de guardias con 3 profesores")
    check(pgu.nueva_reunion("SINT Reunión CCP", ["SINT-P1", "SINT-P2"]) is not None and len(w.p.reuniones) == 1, "paso 6: nueva reunión")
    check(pgu.reuniones_auto("departamento") >= 3, "paso 6: reuniones por departamento")
    check(pgu.tg.rowCount() == 1 and pgu.tr.rowCount() == len(w.p.reuniones), "paso 6: tablas")
    check(pgu.quitar("reuniones", [r.nombre for r in w.p.reuniones[1:]]) and len(w.p.reuniones) == 1, "paso 6: quitar reuniones")
    foto(w, "6_guardias")

    # ---------------- deshacer compartido con la clásica
    n_antes = len(w.p.reuniones); w.deshacer(); check(len(w.p.reuniones) == n_antes + 2 or len(w.p.reuniones) > n_antes, "deshacer (núcleo compartido)")
    w.rehacer(); check(len(w.p.reuniones) == n_antes, "rehacer")

    # ---------------- paso 7
    w.ir(6); pgen = w.pasos[6]
    check(pgen.b_gen.isEnabled(), "paso 7: listo para generar")
    foto(w, "7_generar_antes")
    check(pgen.generar(segundos=15, hilos=4), "paso 7: motor lanzado (guarda antes el archivo)")
    check(os.path.exists(destino), "paso 7: archivo guardado como SINT_sencilla.xghc")
    import time
    t0 = time.time(); visto = []
    while pgen.terminado is None and time.time() - t0 < 120:
        app.processEvents(); time.sleep(0.05); visto.append(pgen.barra.value())
    check(pgen.terminado is True and w.editor is not None, "paso 7: horario generado y cargado")
    check(max(visto) > 0 and pgen.barra.value() == 100, "paso 7: progreso real")
    foto(w, "7_generar_fin")

    # ---------------- paso 8
    w.ir(7); pr = w.pasos[7]; ed = w.editor
    pr.cb_vista.setCurrentText("Grupo"); pr.cb_nombre.setCurrentText("SINT1 A"); pr.pintar()
    its = ed.items_de("Grupos", "SINT1 A"); it = next(i for i in its if i.startswith("s:"))
    pr.seleccionar(it)
    cols = set(pr.colores.values())
    check(cols and cols <= {T.COLOR_VERDE, T.COLOR_AMBAR, T.COLOR_ROJO} and T.COLOR_ROJO in cols, f"paso 8: semáforo calculado ({len(pr.colores)} horas)")
    foto(w, "8_revisar_semaforo")
    verdes = [p for p, c in pr.colores.items() if c != T.COLOR_ROJO]
    rojo = next(p for p, c in pr.colores.items() if c == T.COLOR_ROJO)
    col, mot = pr.explicar(rojo)
    check(col == T.COLOR_ROJO and mot and "No se puede" in pr.por_que.toPlainText() and not pr.b_mover.isEnabled(), f"paso 8: «¿Por qué no puedo…?» ({mot[0][:60]})")
    foto(w, "8_revisar_porque")
    check(not pr.mover(), "paso 8: sin «Forzar»: no mueve a rojo")
    if verdes:
        rc = next(k for k, v in pr.pos.items() if v == verdes[0])
        antes = list(ed.posiciones(it)); pr.seleccionar(it)
        check(pr.soltar(*rc) in (T.COLOR_VERDE, T.COLOR_AMBAR) and ed.posiciones(it) != antes, "paso 8: soltar en una hora permitida la mueve")
        pr.deshacer(); check(ed.posiciones(it) == antes, "paso 8: deshacer")
        pr.rehacer(); pr.deshacer()
    # intercambiar: con otra sesión del mismo grupo de 1 periodo
    otra = next((i for i in its if i.startswith("s:") and i != it and len(ed.posiciones(i)) == len(ed.posiciones(it))), None)
    if otra:
        pa, pb = min(ed.posiciones(it)), min(ed.posiciones(otra))
        pr.seleccionar(it); pr.explicar(pb)
        ok = pr.intercambiar()
        check(ok and min(ed.posiciones(it)) == pb and min(ed.posiciones(otra)) == pa if ok else "intercambiar" in pr.por_que.toPlainText(),
              "paso 8: intercambiar (o explica por qué no)")
        if ok:
            pr.deshacer()
    pr.seleccionar(it)
    r_ok = pr.recolocar(it, rojo, limite=4.0)
    check(r_ok or "no ha encontrado" in pr.por_que.toPlainText(), "paso 8: «Dejar que el programa la recoloque» (generación parcial)")
    check(ed.comprobar() is not None, "paso 8: comprobador tras los cambios")
    check(pr.guardar() and not ed.modificado, "paso 8: guardar cambios en el .lphr")
    foto(w, "8_revisar")

    # ---------------- paso 9
    w.ir(8); pi = w.pasos[8]
    for tipo in ("alumnos", "profesores", "aulas", "guardias"):
        ruta = os.path.join(tmp, f"{tipo}.pdf")
        pi.informe(tipo, ruta)
        check(os.path.exists(ruta) and os.path.getsize(ruta) > 1000 and open(ruta, "rb").read(5) == b"%PDF-", f"paso 9: PDF {tipo}")
    foto(w, "9_informes")

    # ---------------- pegar en la clásica y alternar en caliente
    n = w.cambiar_version("clasica"); app.processEvents()
    check(n.isVisible() and not w.isVisible() and n.proyecto is w.p, "alternar: clásica visible con el mismo proyecto")
    n.cambiar_lista("materias"); antes = len(n.proyecto.materias)
    r = n.pegar_listado("SINT-EF\tEducación Física\nSINT-MAT\tMatemáticas I")
    check(r and r["nuevos"] == 1 and r["actualizados"] == 1 and len(n.proyecto.materias) == antes + 1, "clásica: Pegar (ya no «próximamente»)")
    csvp = os.path.join(tmp, "grupos.csv"); open(csvp, "w", encoding="utf-8").write("Nombre;Curso;Aula\nSINT2 B;SINT2;\n")
    n.cambiar_lista("grupos"); r = n.leer_listado(csvp)
    check(r and r["nuevos"] == 1 and "SINT2 B" in [g.nombre for g in n.proyecto.grupos], "clásica: leer una lista CSV")
    n.cambiar_lista("aulas"); check(n.pegar_listado("x") is None, "clásica: Pegar fuera de las 3 listas avisa")
    vs = n.cambiar_version("sencilla"); app.processEvents()
    check(vs is w and w.isVisible() and not n.isVisible() and "SINT-EF" in [m.nombre for m in w.p.materias], "alternar: vuelta a la sencilla con los cambios")
    check(n.a_ver_sencilla is not None and w.a_ver_clasica is not None, "Ver › Versión en ambas ventanas")

    print(f"\n{fallos} fallos", flush=True)
    w.p.modificado = False
    sys.exit(1 if fallos else 0)


if __name__ == "__main__":
    main()
