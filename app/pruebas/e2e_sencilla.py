"""Extremo a extremo: centro SINT desde cero en la versión sencilla → generar → revisar → PDF → abrirlo en la
clásica (nueva ventana, archivo del disco) y comprobar que es idéntico (configuración y horario)."""
import sys, os, tempfile, time, json
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PySide6.QtWidgets import QApplication, QMessageBox, QFileDialog
from PySide6.QtCore import QSettings
tmp = tempfile.mkdtemp()
QSettings.setDefaultFormat(QSettings.IniFormat); QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, tmp)
app = QApplication.instance() or QApplication(sys.argv); app.setStyle("Fusion")
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
QMessageBox.information = staticmethod(lambda *a, **k: None)
QMessageBox.warning = staticmethod(lambda *a, **k: None)
X = os.path.join(tmp, "SINT_e2e.xghc")
QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (X, ""))
fallos = 0
def check(c, m):
    global fallos
    print(("OK   " if c else "FALLO") + " " + m, flush=True); fallos += (not c)


def main():
    from horarios.sencilla.ventana import VentanaSencilla
    from horarios.ventana import Planificador
    from horarios.editor_modelo import Editor
    from horarios import resultado as RES, comprobador, xghc
    w = VentanaSencilla(); w.show(); app.processEvents()
    c = w.pasos[0]; c.configurar(dias=[0, 1, 2, 3, 4], inicio="09:00", duracion=60, clases=5, recreo_tras=3, recreo_dur=30); c.aplicar()
    w.ir(1); w.pasos[1].lista.pegar("\n".join(f"SINT-E{i}\t\tSINT-D{i % 3}" for i in range(1, 7)))
    w.ir(2); w.pasos[2].crear_varios("SINTE", "A B C")
    w.ir(3); pm = w.pasos[3]; pm.materias.pegar("SINT-M1\nSINT-M2\nSINT-M3\nSINT-M4")
    asign = {"SINTE A": ["SINT-E1", "SINT-E2", "SINT-E3", "SINT-E4"], "SINTE B": ["SINT-E2", "SINT-E3", "SINT-E5", "SINT-E6"],
             "SINTE C": ["SINT-E1", "SINT-E4", "SINT-E5", "SINT-E6"]}
    for g, profs in asign.items():
        for k, pr in enumerate(profs):
            pm.anadir(f"SINT-M{k + 1}", pr, (5, 4, 3, 3)[k], None, g)
    w.ir(4); pf = w.pasos[4]; pf.cb_tipo.setCurrentText("Profesorado"); pf.cb_nombre.setCurrentText("SINT-E1"); pf.cargar_rejilla()
    mid = next(iter(w.p.marcos)); pf.pintar([(mid, 0, 0), (mid, 0, 1)], "prohibido")
    w.ir(5); g = w.pasos[5].nueva_guardia("SINT Guardia E"); w.pasos[5].profesores_guardia(g, ["SINT-E5", "SINT-E6"], 2)
    check(len(w.p.sesiones) == 12 and len(w.p.profesores) == 6 and len(w.p.grupos) == 3, "centro SINT creado desde cero")
    w.ir(6); gen = w.pasos[6]; gen.cargar(); check(gen.generar(segundos=12, hilos=4), "generar lanzado")
    t0 = time.time()
    while gen.terminado is None and time.time() - t0 < 120:
        app.processEvents(); time.sleep(0.05)
    check(gen.terminado is True and w.editor is not None, "horario generado")
    ed = w.editor; inf = ed.comprobar()
    check(not ed.doc.get("no_colocadas") and inf.valido, f"horario completo y válido según el comprobador ({len(inf.errores)} errores)")
    # «No puede» respetado
    pos_e1 = [p for it in ed.items_de("Profesorado", "SINT-E1") for p in ed.posiciones(it)]
    check(not any(p[1] == 0 and p[2] in (0, 1) for p in pos_e1), "preferencia «No puede» respetada")
    w.ir(7); rv = w.pasos[7]; rv.cb_vista.setCurrentText("Grupo"); rv.cb_nombre.setCurrentText("SINTE A"); rv.pintar()
    it = next(i for i in ed.items_de("Grupos", "SINTE A") if i.startswith("s:")); rv.seleccionar(it)
    destino = next((p for p, col in rv.colores.items() if col != "#f5b5b5"), None)
    if destino:
        rc = next(k for k, v in rv.pos.items() if v == destino); rv.soltar(*rc)
    check(destino is None or destino in ed.posiciones(it), "revisar: clase movida arrastrando")
    rv.guardar()
    w.ir(8); pdf = os.path.join(tmp, "grupos.pdf"); w.pasos[8].informe("alumnos", pdf)
    check(open(pdf, "rb").read(5) == b"%PDF-", "informe PDF por grupo")
    check(w.guardar() and not w.p.modificado, "archivo guardado")
    bytes_x = open(X, "rb").read(); L = os.path.splitext(X)[0] + ".lphr"; doc_l = RES.cargar(L)
    # ---- clásica: ventana nueva, abriendo los archivos del disco
    cl = Planificador(); cl.abrir(X)
    check(cl.proyecto is not None and cl.proyecto.doc.serializar() == w.p.doc.serializar(), "clásica: misma configuración que la sencilla")
    X2 = os.path.join(tmp, "SINT_e2e_clasica.xghc"); xghc.guardar(cl.proyecto, X2)
    check(open(X2, "rb").read() == bytes_x, "clásica: al guardarlo produce un archivo idéntico byte a byte")
    ed2 = Editor(L, X)
    check(json.dumps(ed2.doc["sesiones"], sort_keys=True) == json.dumps(ed.doc["sesiones"], sort_keys=True), "clásica: mismo horario (.lphr)")
    check(comprobador.comprobar(cl.proyecto, doc_l).valido, "clásica: el comprobador da el horario por válido")
    # ---- y alternando en caliente: misma instancia
    n = w.cambiar_version("clasica"); check(n.proyecto is w.p and n.proyecto.doc.serializar() == cl.proyecto.doc.serializar(),
                                            "alternar en caliente: misma configuración")
    print(f"\n{fallos} fallos", flush=True)
    sys.exit(1 if fallos else 0)


if __name__ == "__main__":
    main()
