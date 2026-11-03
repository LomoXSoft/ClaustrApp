"""Prueba offscreen del diálogo «Opciones generales, valores de partida y otras acciones».
Trabaja siempre sobre copias en un directorio temporal; los originales no se tocan (se comprueba md5)."""
import sys, os, tempfile, shutil, hashlib, faulthandler, signal
faulthandler.register(signal.SIGUSR1)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import _rutas as _R
from PySide6.QtWidgets import QApplication, QMessageBox, QFileDialog
from PySide6.QtCore import QSettings
tmp = tempfile.mkdtemp()
QSettings.setDefaultFormat(QSettings.IniFormat)
QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, tmp)
from horarios.ventana import Planificador
from horarios import opciones_generales as OGM, edicion as ED

app = QApplication.instance() or QApplication(sys.argv)
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
QMessageBox.information = staticmethod(lambda *a, **k: None)
QMessageBox.warning = staticmethod(lambda *a, **k: None)
fallos = 0
def check(c, m):
    global fallos
    print(("OK   " if c else "FALLO") + " " + m); fallos += (not c)

ORIG = _R.disponibles(os.path.join(_R.R, "prueba1.xghc"), os.path.join(_R.R, "prueba2.xghc"))
md5 = {p: hashlib.md5(open(p, "rb").read()).hexdigest() for p in ORIG}

for src in ORIG:
    nombre = os.path.basename(src); cp = os.path.join(tmp, nombre); shutil.copy(src, cp)
    w = Planificador(); w.abrir(cp)
    raiz = lambda: w.proyecto.doc.raiz
    ser0 = w.proyecto.doc.serializar()
    d = OGM.DialogoOpcionesGenerales(w); d.show(); app.processEvents()
    check(d.tabs.count() == 10, f"{nombre}: 10 solapas ({[d.tabs.tabText(i) for i in range(d.tabs.count())]})")
    check(d.windowTitle() == OGM.TITULO, f"{nombre}: título de la cadena 273")
    nd = len(w.pila_deshacer); d.aplicar()
    check(len(w.pila_deshacer) == nd and w.proyecto.doc.serializar() == ser0, f"{nombre}: aplicar sin cambios no toca el XML")
    # 218: banderas de opcionesGenerales
    p = d.p
    p["218"].c[1111].setChecked(True); p["218"].c[1112].setChecked(True); d.aplicar()
    check(ED.leer(raiz(), "otros/opciones/opcionesGenerales/contarHuecosMediodia") == "true"
          and ED.leer(raiz(), "otros/opciones/opcionesGenerales/desecharGuardias") == "true", f"{nombre}: opcionesGenerales true")
    p["218"].c[1112].setChecked(False); d.aplicar()
    check(ED.buscar(raiz(), "otros/opciones/opcionesGenerales/desecharGuardias") is None, f"{nombre}: desecharGuardias se quita al desmarcar")
    # preferencias (QSettings)
    p["218"].c[1296].setChecked(False); p["218"].c[1055].setChecked(True); d.aplicar()
    check(not OGM.confirmar_suprimir() and int(OGM.preferencias().value("opciones/referencia/Aulas")) == 1,
          f"{nombre}: preferencias de confirmación y referencia en QSettings")
    p["218"].c[1296].setChecked(True); d.aplicar()
    # 196: valores iniciales de sesiones
    p["196"].c[1154].setChecked(False); p["196"].c[1060].setChecked(True); p["196"].c[1511].setChecked(True); d.aplicar()
    vs = "otros/opciones/valorInicialSesiones/"
    check(ED.leer(raiz(), vs + "penaSesionesAPrimera") == "false" and ED.leer(raiz(), vs + "permitirImpartanEnDiasSeguidos") == "prohibido"
          and ED.leer(raiz(), vs + "sinCambioAula") == "true", f"{nombre}: valorInicialSesiones escritos")
    p["196"].c[1064].click(); app.processEvents()
    ses = raiz().find("sesionesLectivas").findall("sesion")
    check(all(ED.leer(s, "opciones/permitirImpartanEnDiasSeguidos") == "prohibido" for s in ses),
          f"{nombre}: aplicar a toda la lista: días seguidos en {len(ses)} sesiones")
    p["196"].c[1065].click()
    check(all(ED.leer(s, "opciones/sinCambioAula") == "true" for s in ses), f"{nombre}: aplicar sinCambioAula")
    # nueva sesión hereda los valores iniciales
    w.cambiar_lista("sesiones"); w.tabla.selectRow(0); w.insertar()
    nueva = raiz().find("sesionesLectivas").findall("sesion")
    check(any(ED.leer(s, "opciones/penaSesionesAPrimera") == "false" for s in nueva), f"{nombre}: sesión nueva hereda valorInicialSesiones")
    # 667/195/373: valores iniciales de profesores
    vp = "otros/opciones/valorInicialProfesores/"
    p["667"].c[1349].setChecked(True); p["667"].c[1046].setChecked(True)
    p["195"].c[1074].setValue(2); p["195"].c[1214].setChecked(True); p["195"].c[1077].setValue(3)
    p["195"].c[1065].setValue(1); p["195"].c[1171].setChecked(True); p["195"].c[1382].setValue(2)
    p["373"].c[1064].setValue(4); p["373"].c[1509].set_estricto(True); p["373"].c[1080].setChecked(True)
    d.aplicar()
    r = raiz()
    check(ED.leer(r, vp + "considerarMinimasHorasDiariasSolamenteLectivas") == "estricto", f"{nombre}: considerar estricto")
    check(ED.leer(r, vp + "minimizarDiasOcupados") == "true", f"{nombre}: minimizarDiasOcupados")
    check(ED.leer(r, vp + "periodosLibres/cantidadDeDias") == "2" and ED.leer(r, vp + "periodosLibres/tipoDePeriodo/intervalosSeguidos") == "3",
          f"{nombre}: periodosLibres")
    t = [x for x in r.iter("periodoLibreJornadaPartida") if x.findtext("tipoDePeriodoLibre") == "tardes" and ED.buscar(r, "otros") is not None]
    check(ED.buscar(r, vp + "incompatibilidadEntreSesiones/entrarPrimeraSalirUltima").get("nIntervalos") == "2"
          and ED.leer(r, vp + "incompatibilidadEntreSesiones/entrarPrimeraSalirUltima") == "true", f"{nombre}: incompatibilidad con nIntervalos")
    mh = ED.buscar(r, vp + "maximasHorasSeguidas")
    check(mh.text.strip() == "4" and mh.get("estricto") == "true", f"{nombre}: maximasHorasSeguidas estricto")
    check(ED.leer(r, vp + "penalizarAlrededorGuardiaRecreo") == "true", f"{nombre}: penalizarAlrededorGuardiaRecreo")
    p["373"].c[1070].click(); p["195"].c[1073].click(); p["373"].c[1081].click()
    profs = raiz().find("profesores").findall("profesor")
    check(all(ED.buscar(x, "opciones/maximasHorasSeguidas") is not None and ED.buscar(x, "opciones/maximasHorasSeguidas").text.strip() == "4"
              for x in profs), f"{nombre}: aplicar máximas horas seguidas a {len(profs)} profesores")
    check(all(ED.leer(x, "opciones/incompatibilidadEntreSesiones/entrarPrimeraSalirUltima") == "true" for x in profs),
          f"{nombre}: aplicar incompatibilidad a profesores")
    check(all(ED.leer(x, "opciones/penalizarAlrededorGuardiaRecreo") == "true" for x in profs), f"{nombre}: aplicar guardias de recreo")
    p["373"].c[1065].setValue(3); p["373"].c[1071].click()
    check(all(ED.leer(x, "prioridad") == "3" for x in raiz().find("profesores").findall("profesor")), f"{nombre}: prioridad a todos")
    # 252 tareas iniciales
    cb = p["252"].c[1192]
    if cb.count() > 1:
        cb.setCurrentIndex(cb.count() - 1); txt = cb.currentText().split("  ~ ")[0].strip(); d.aplicar()
        check(ED.leer(raiz(), "tareas/lectivaPorDefecto") == txt, f"{nombre}: lectivaPorDefecto = {txt}")
    # 444 anotaciones
    p["444"].c[1293].setPlainText("SINT-nota de prueba"); d.aplicar()
    check(ED.leer(raiz(), "otros/notas") == "SINT-nota de prueba", f"{nombre}: otros/notas")
    # 938 alejados
    gs = [ED.leer(g, "nombre") for g in raiz().find("grupos").findall("grupo")][:2]
    p["938"].c[1099].addItems(gs); p["938"].c[1217].setChecked(True); p["938"].c[1102].setChecked(True); d.aplicar()
    ga = ED.buscar(raiz(), "otros/gruposAlejados")
    check([x.text for x in ga.find("listaDeGrupos")] == gs and ga.find("opciones/evitarDobleDesp").get("prohibir") == "true"
          and ED.leer(ga, "opciones/actualizarAlGenerar") == "true", f"{nombre}: grupos alejados {gs}")
    # 445 alumnos
    p["445"].c[1237].setValue(6); p["445"].c[1084].click()
    check(all(ED.leer(g, "limiteOcupacionDia") == "6" for g in raiz().find("grupos").findall("grupo")), f"{nombre}: limiteOcupacionDia a todos")
    # 503 operaciones
    p["503"].c[1103].click()
    check(not list(raiz().iter("noConsecutivas")), f"{nombre}: eliminar no consecutivas")
    p["503"].c[1105].click(); check(True, f"{nombre}: asignar departamentos (sin excepción)")
    n0 = len(raiz().find("sesionesLectivas")); p["503"].c[1107].click()
    check(len(raiz().find("sesionesLectivas")) >= n0, f"{nombre}: generar sesiones desde cursos ({n0}->{len(raiz().find('sesionesLectivas'))})")
    p["503"].c[1106].click(); check(True, f"{nombre}: eliminar materias y cursos no usados")
    p["503"].c[1108].click()
    check(all(not ED.leer(s, "profesor", "") for s in raiz().find("sesionesLectivas").findall("sesion")), f"{nombre}: quitar profesores")
    # deshacer hasta el principio devuelve el XML original
    while w.pila_deshacer:
        w.deshacer()
    check(w.proyecto.doc.serializar() == ser0, f"{nombre}: deshacer todo devuelve el XML original")
    # guardar copia y releer
    d.cargar(); p["218"].c[1111].setChecked(True); p["196"].c[1077].setChecked(True); d.aceptar()
    dest = os.path.join(tmp, "g_" + nombre); QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (dest, ""))
    w.guardar_como()
    if os.path.exists(dest):
        w2 = Planificador(); w2.abrir(dest)
        check(ED.leer(w2.proyecto.doc.raiz, "otros/opciones/valorInicialSesiones/considerarLunesViernesSeguidos") == "true",
              f"{nombre}: persistencia tras guardar y reabrir")
    # entradas desde ventana y propiedades
    check(not getattr(w.a_opciones, "proximamente", False) and w.a_opciones.isEnabled(), f"{nombre}: menú Opciones generales activo")
    w.close()

for pth in ORIG:
    check(hashlib.md5(open(pth, "rb").read()).hexdigest() == md5[pth], f"original intacto: {os.path.basename(pth)}")
print("FALLOS:", fallos); sys.exit(1 if fallos else 0)
