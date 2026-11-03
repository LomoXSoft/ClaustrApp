"""Prueba offscreen del «Depurador de condiciones» (diálogos 664/665), su lanzamiento del motor con anotación,
la marca violeta «P» del Editor y el analizador de conflictos. Datos SINT-*, copias temporales, originales intactos.
Capturas: capturas/depurador.png, depurador_otras.png, motor_depurador.png, editor_flexibilizada.png, analizador.png."""
import sys, os, time, tempfile, shutil, hashlib, copy, json, faulthandler
faulthandler.dump_traceback_later(170, exit=True)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import _rutas as _R
from horarios.textos import TX
if __name__ == "__main__":
    import multiprocessing; multiprocessing.freeze_support()
    from PySide6.QtWidgets import QApplication, QMessageBox
    from PySide6.QtCore import QSettings
    tmp = tempfile.mkdtemp(prefix="lp_dep_")
    QSettings.setDefaultFormat(QSettings.IniFormat); QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, tmp)
    app = QApplication(sys.argv); app.setStyle("Fusion")
    QMessageBox.information = staticmethod(lambda *a, **k: None); QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
    from horarios.ventana import Planificador
    from horarios import depurador as DP, analizador as ANd, editor as E, resultado as RES
    from horarios.motor import problema, flexibilizar as F, analizador as AN
    from horarios.ventana_motor import VentanaMotor
    fallos = 0
    def check(c, m):
        global fallos
        print(("OK   " if c else "FALLO") + " " + m); fallos += (not c)
    CAP = _R.CAPG; os.makedirs(CAP, exist_ok=True)
    SRC = os.path.join(_R.R, "SINTETICO_grande.xghc"); h0 = hashlib.md5(open(SRC, "rb").read()).hexdigest()
    X = os.path.join(tmp, "SINTETICO_grande.xghc"); shutil.copy(SRC, X)
    w = Planificador(); w.abrir(X)
    check(w.a_depurador.text() == "Depurar condiciones...", "menú «Depurar condiciones...»")
    d = DP.DialogoDepurador(w); d.show(); app.processEvents()
    check(d.windowTitle() == "Depurador de condiciones", "título del diálogo 664")
    check(d.cajas["proh_profesor"].isEnabled() and not d.cajas["proh_materia"].isEnabled(), "habilitadas solo opciones con datos")
    check(d.b_lanzar.text() == TX("calcular_sin_condiciones_marcadas"), "botón cadena 879")
    d.grab().save(os.path.join(CAP, "depurador.png"))
    o = DP.DialogoOtras(d, d.disp, {}); o.show(); app.processEvents()
    check(o.cajas["proh_grupo"].isEnabled() and not o.cajas["bl_consecutivas"].isEnabled(), "665: grupos sí, consecutivas no")
    o.cajas["proh_grupo"].setChecked(True); o.grab().save(os.path.join(CAP, "depurador_otras.png")); d.otras = o.valores()
    d.cajas["proh_profesor"].setChecked(True)
    q, notas = d.preparar()
    check(sum(len(u["prohibidos"]) for u in q["unidades"]) < sum(len(u["prohibidos"]) for u in d.pb["unidades"]),
          "prohibidos conmutados en el problema")
    check(notas[0] == TX("pasa_todas_horas_prohibidas_plantillas") and "profesores" in notas[1],
          "anotación con cadena 318 y orígenes")
    check(problema.construir(w.proyecto)["unidades"][0]["prohibidos"] == d.pb["unidades"][0]["prohibidos"], "el proyecto no cambia")
    # motor real con autoguardado en la copia temporal
    vm = VentanaMotor(w.proyecto, None, segundos=15, hilos=4, autoguardar=True, pb=q, anotacion=notas, pb_original=d.pb)
    vm.resize(900, 720); vm.show(); t0 = time.time()
    while vm.doc is None and time.time() - t0 < 90:
        app.processEvents(); time.sleep(0.05)
    for _ in range(10):
        app.processEvents(); time.sleep(0.05)
    vm.tabs.setCurrentIndex(1); app.processEvents(); vm.grab().save(os.path.join(CAP, "motor_depurador.png"))
    check(vm.doc is not None and vm.doc["anotacion"][0].startswith(TX("cuidado_resultado_calculado_condiciones_obligatorias")), "resultado con «Anotación»")
    check("flexibilizadas" in vm.doc, "resultado con lista de sesiones flexibilizadas")
    lphr = vm.guardados[-1] if vm.guardados else None
    check(lphr and lphr.startswith(tmp) and lphr.endswith("R1.lphr"), f"autoguardado R1 en la copia ({lphr})")
    vm.cerrar_sin_preguntar = True if hasattr(vm, "cerrar_sin_preguntar") else None
    # violaciones: forzar en el problema original un prohibido donde quedó la primera pieza
    pb0 = copy.deepcopy(d.pb); doc = RES.cargar(lphr); pz = doc["sesiones"][0]
    from horarios.motor.mensajes import _slots_pieza
    u = next(x for x in pb0["unidades"] if x["id"] == pz["unidad"]); s = _slots_pieza(pb0, pz)[0]
    u["prohibidos"] = sorted(set(u["prohibidos"]) | {s}); u["origen_prohibidos"][str(s)] = [["profesor", "SINT-prueba"]]
    viol = F.violaciones(pb0, doc)
    check("s:0" in viol and "SINT-prueba" in viol["s:0"][0], "violaciones detecta el prohibido incumplido")
    doc["flexibilizadas"] = viol; L2 = os.path.join(tmp, "flex.lphr"); RES.guardar(doc, L2)
    ed = E.VentanaEditor(L2, X); ed.resize(1000, 700); ed.show(); app.processEvents()
    v = ed._vista_actual()
    g0 = ed.ed.items_de("Grupos", None) if False else None
    nombre = next(iter(u["grupos"]), None)
    if nombre:
        v.cb_vista.setCurrentText("Grupos"); app.processEvents(); v.cb_el.setCurrentText(nombre); app.processEvents()
    t = v.tabla(); marc = [c for c, lst in t.celdas.items() if "s:0" in lst]
    check(marc and not t.item(*marc[0]).icon().isNull() and "flexibilizada" in t.item(*marc[0]).toolTip(), "marca violeta «P» en el Editor")
    ed.grab().save(os.path.join(CAP, "editor_flexibilizada.png"))
    check(callable(getattr(ed, "anotacion", None)), "Editor: comando «Anotación»")
    # analizador: conflicto artificial (unidad de 2 piezas con un solo tramo libre)
    pba = copy.deepcopy(d.pb); ux = next(x for x in pba["unidades"] if len(x["piezas"]) >= 2)
    lect = [s_["id"] for s_ in pba["slots"] if s_["tipo"] == "lectivo" and s_["marco"] == ux["marco"]]
    ux["prohibidos"] = lect[1:]
    r = AN.analizar(pba, 60)
    check(r["estado"] == "infactible" and r["conjunto"] == [ux["id"]] and r["minimo"], f"analizador: conjunto mínimo {r}")
    check(AN.analizar(d.pb, 30)["estado"] == "factible", "analizador: datos originales factibles")
    da = ANd.DialogoAnalizador(w, pba, 30); da.show(); t0 = time.time()
    while da.t.isActive() and time.time() - t0 < 60:
        app.processEvents(); time.sleep(0.05)
    check(da.lista.count() == 1, "diálogo del analizador lista el conjunto"); da.grab().save(os.path.join(CAP, "analizador.png"))
    check(hashlib.md5(open(SRC, "rb").read()).hexdigest() == h0, "original intacto")
    print("FALLOS:", fallos); os._exit(1 if fallos else 0)
