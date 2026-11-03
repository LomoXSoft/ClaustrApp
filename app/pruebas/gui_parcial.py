"""Prueba offscreen de «Calcular horario parcial» (diálogo 690) y del botón del Depurador «…ni los elementos filtrados».
Datos SINT-*, copia temporal. Captura capturas/parcial.png."""
import sys, os, time, tempfile, shutil, hashlib, faulthandler
faulthandler.dump_traceback_later(170, exit=True)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import _rutas as _R
from horarios.textos import TX
if __name__ == "__main__":
    import multiprocessing; multiprocessing.freeze_support()
    from PySide6.QtWidgets import QApplication, QMessageBox
    from PySide6.QtCore import QSettings, Qt
    tmp = tempfile.mkdtemp(prefix="lp_par_")
    QSettings.setDefaultFormat(QSettings.IniFormat); QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, tmp)
    app = QApplication(sys.argv); app.setStyle("Fusion")
    QMessageBox.information = staticmethod(lambda *a, **k: None)
    from horarios.ventana import Planificador
    from horarios import parcial as PD, depurador as DP, comprobador
    from horarios.motor import parcial as PA, problema
    from horarios.ventana_motor import VentanaMotor
    fallos = 0
    def check(c, m):
        global fallos
        print(("OK   " if c else "FALLO") + " " + m); fallos += (not c)
    SRC = os.path.join(_R.R, "SINTETICO_grande.xghc"); h0 = hashlib.md5(open(SRC, "rb").read()).hexdigest()
    X = os.path.join(tmp, os.path.basename(SRC)); shutil.copy(SRC, X)
    w = Planificador(); w.abrir(X)
    check(w.a_parcial.text() == TX("calcular_horario_parcial"), 'menú «Calcular horario parcial» (33225)')
    d = PD.DialogoParcial(w); d.show(); app.processEvents()
    check(d.windowTitle() == PD.TITULO and d.b_gen.text() == TX("calcular_horario_parcial_2") and d.b_ana.text() == "Análisis parcial",
          "título y botones del diálogo 690")
    n = d.l_gr.count(); check(n > 3 and len(d.seleccion()["grupos"]) == n, f"{n} grupos, todos marcados")
    PD._marcar(d.l_gr, False); check(d.seleccion()["grupos"] == [], "Desmarcar todos")
    for i in range(3):
        d.l_gr.item(i).setCheckState(Qt.Checked)
    PD._marcar(d.l_re, False); d.l_re.item(0).setCheckState(Qt.Checked); d.c_com.setChecked(False)
    d.grab().save(os.path.join(_R.CAPG, "parcial.png"))
    q = d.filtrar(); sel = d.seleccion()
    check(all(set(u["grupos"]) & set(sel["grupos"]) for u in q["unidades"]) and 0 < len(q["unidades"]) < len(d.pb["unidades"]),
          f"filtro: {len(q['unidades'])} de {len(d.pb['unidades'])} unidades")
    check(len(q["reuniones"]) == 1 and q["complementarias"] == [] and q["guardias"], "reuniones/guardias/complementarias")
    nota = PA.anotacion(d.pb, q)
    check(nota[0] == TX("cuidado_resultado_parcial") and any("Se ha omitido el horario del grupo." in x for x in nota)
          and TX("no_han_tenido_cuenta_actividades") in nota, "anotación (cadenas 337-341)")
    vm = VentanaMotor(w.proyecto, None, segundos=8, hilos=4, autoguardar=False, pb=q, anotacion=nota[1:], parcial=True); vm.show()
    t0 = time.time()
    while vm.doc is None and time.time() - t0 < 60:
        app.processEvents(); time.sleep(0.05)
    check(vm.doc and vm.doc["anotacion"][0] == TX("cuidado_resultado_parcial"), "resultado con anotación de parcial")
    check(vm.doc and vm.doc.get("parcial") and vm.informe and vm.informe.valido, f"comprobador válido sobre el parcial ({vm.informe.resumen() if vm.informe else None})")
    from horarios import resultado as RES
    lphr = os.path.join(tmp, "parcial.lphr"); RES.guardar(vm.doc, lphr); d2 = RES.cargar(lphr)
    check(d2.get("parcial") == vm.doc["parcial"] and comprobador.comprobar(w.proyecto, d2).valido,
          "clave «parcial» guardada y recuperada en .lphr; comprobador válido al reabrir")
    vm.close()
    # «Análisis parcial»
    from horarios import analizador as AZ
    def _exec(self):
        PD._marcar(self.l_gr, False)
        for i in range(3): self.l_gr.item(i).setCheckState(Qt.Checked)
        self.accion = "analizar"; return True
    PD.DialogoParcial.exec = _exec
    vistos = []; AZ.DialogoAnalizador.exec = lambda self: vistos.append(self) or 0
    q2 = PD.generar_parcial(w)
    ok = bool(vistos) and len(vistos[0].pb["unidades"]) == len(q2["unidades"]) < len(d.pb["unidades"])
    t0 = time.time()
    while ok and vistos[0].res is None and time.time() - t0 < 60:
        app.processEvents(); time.sleep(0.1)
    check(ok and vistos[0].res is not None, f"«Análisis parcial» lanza el analizador sobre el filtro ({vistos[0].res.get('estado') if ok and vistos[0].res else None})")
    dp = DP.DialogoDepurador(w); check(dp.b_filtr.isEnabled(), "Depurador: botón «…ni los elementos filtrados» habilitado")
    check(hashlib.md5(open(SRC, "rb").read()).hexdigest() == h0, "original intacto")
    print("FALLOS:", fallos); os._exit(1 if fallos else 0)
