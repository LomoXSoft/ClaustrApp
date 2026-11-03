"""Autoprueba del programa instalado (también del ejecutable de Windows):
    <ejecutable>.exe --autoprueba archivo.xghc carpeta_salida [segundos]
Abre el archivo en el planificador, lanza el motor en su proceso aparte, comprueba la solución, guarda el
.lphr, la abre en el editor y genera un PDF de horarios de grupos. Escribe autoprueba.txt en la carpeta."""
import os, sys, time, shutil, traceback


def ejecutar(xghc_ruta, salida, segundos=60):
    os.makedirs(salida, exist_ok=True)
    log = open(os.path.join(salida, "autoprueba.txt"), "w", encoding="utf-8")
    def info(t):
        log.write(t + "\n"); log.flush(); print(t, flush=True)
    ok = False
    try:
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication(sys.argv[:1])
        from . import __version__, APP_NAME, xghc, comprobador, resultado, informes as I
        from .ventana import Planificador
        from .motor import problema
        from .motor.proceso import MotorEnProceso
        info(f"{APP_NAME} {__version__} · autoprueba · {sys.platform} · congelado={getattr(sys, 'frozen', False)}")
        X = os.path.join(salida, os.path.basename(xghc_ruta)); shutil.copy(xghc_ruta, X)
        w = Planificador(); w._no_modal = True
        assert w.abrir(X), "no se pudo abrir el archivo"
        p = w.proyecto
        info(f"1 arranque y apertura: {len(p.profesores)} profesores, {len(p.grupos)} grupos, {len(p.sesiones)} sesiones")
        pb = problema.construir(p)
        m = MotorEnProceso(pb, segundos=segundos, hilos=4); t0 = time.time(); m.iniciar()
        while not m.resultado:
            m.eventos(); app.processEvents(); time.sleep(0.2)
            if time.time() - t0 > segundos + 120:
                raise RuntimeError("el motor no termina")
        r = m.resultado; e = r["estadisticas"]
        info(f"2 motor (proceso aparte): {time.time() - t0:.1f} s, no colocadas={e['no_colocadas']}, peso={e['peso']}")
        doc = resultado.crear(r, X, {"nombre": "cpsat", "segundos": segundos})
        L = os.path.splitext(X)[0] + resultado.EXTENSION; resultado.guardar(doc, L)
        inf = comprobador.comprobar(p, resultado.cargar(L))
        info(f"3 solución guardada en {os.path.basename(L)}; comprobador: válido={inf.valido}")
        from . import editor as E
        E.VentanaEditor.abrir_planificador = staticmethod(lambda r: None)
        ve = E.VentanaEditor(L, X); ed = ve.ed
        o = I.opciones(ed.doc, {"centro": "IES SINTÉTICO", "localidad": "Villaprueba", "curso": "2026-2027"})
        pdf = os.path.join(salida, "horarios_grupos.pdf")
        I.exportar_pdf(I.tablas_de(ed, "alumnos", o), pdf, o, [X, L])
        tam = os.path.getsize(pdf)
        info(f"4 PDF generado: {os.path.basename(pdf)} ({tam} bytes, cabecera={open(pdf, 'rb').read(5)!r})")
        from .sencilla.ventana import VentanaSencilla
        vs = VentanaSencilla(nucleo=w); vs.mostrar_desde_nucleo(); vs.ir(7); rv = vs.pasos[7]
        rv.cb_vista.setCurrentText("Grupo"); rv.pintar()
        it = next(i for i in vs.editor.items_de("Grupos", rv.cb_nombre.currentText()) if i.startswith("s:"))
        rv.seleccionar(it)
        pdf2 = vs.pasos[8].informe("profesores", os.path.join(salida, "sencilla_profesores.pdf"))
        tam2 = os.path.getsize(pdf2); vs.hide()
        info(f"5 versión sencilla: revisar ({len(rv.colores)} horas evaluadas), PDF {os.path.basename(pdf2)} ({tam2} bytes)")
        ok = inf.valido and e["no_colocadas"] == 0 and tam > 5000 and tam2 > 5000 and len(rv.colores) > 0
    except Exception:  # noqa: BLE001
        info("ERROR:\n" + traceback.format_exc())
    info("RESULTADO: " + ("OK" if ok else "FALLO"))
    log.close()
    return 0 if ok else 1
