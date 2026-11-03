"""Prueba offscreen de «Fundir archivos...» con dos copias sintéticas (SINT-*) de SINTETICO_grande.
A: sesiones id<170 y 15 reuniones; B: sesiones id>=150 (20 repetidas) y todas las reuniones. Nunca toca el original."""
import sys, os, tempfile, shutil, hashlib, faulthandler
faulthandler.dump_traceback_later(120, exit=True)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import _rutas as _R
from horarios.textos import TX
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QSettings
tmp = tempfile.mkdtemp(prefix="lp_fun_")
QSettings.setDefaultFormat(QSettings.IniFormat); QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, tmp)
app = QApplication(sys.argv)
mensajes = []
QMessageBox.information = staticmethod(lambda *a, **k: mensajes.append(a[2] if len(a) > 2 else "") or QMessageBox.Ok)
from horarios.ventana import Planificador
from horarios import xghc, edicion as ED, fundir as FU
from horarios.motor import problema
fallos = 0
def check(c, m):
    global fallos
    print(("OK   " if c else "FALLO") + " " + m); fallos += (not c)
SRC = os.path.join(_R.R, "SINTETICO_grande.xghc"); h0 = hashlib.md5(open(SRC, "rb").read()).hexdigest()
orig = xghc.cargar(SRC); r0 = orig.doc.raiz
n_ses = len(r0.find("sesionesLectivas")); n_blq = len(r0.findall("listasDeRelacion/simultaneas/bloqueDeSesiones"))
def copia(nombre, quitar, n_reun=None, tocar=None):
    p = xghc.cargar(SRC); a = ED.Arbol(p.doc.raiz)
    for s in [s for s in p.doc.raiz.find("sesionesLectivas") if quitar(int(s.get("id")))]:
        ED.eliminar_sesion(a, s)
    if n_reun is not None:
        c = p.doc.raiz.find("reuniones")
        for e in list(c)[n_reun:]:
            ED.quitar_hijo(a, c, e)
    if tocar:
        tocar(p.doc.raiz)
    ruta = os.path.join(tmp, nombre); xghc.guardar(p, ruta); return ruta
A = copia("SINT_A.xghc", lambda i: i >= 170, n_reun=15)
B = copia("SINT_B.xghc", lambda i: i < 150)
def otro_nombre(r):
    e = r.find("aulas")[0]; d = e.find("dedicada")
    d.text = "true" if (d.text or "").strip() == "false" else "false"
C = copia("SINT_C.xghc", lambda i: i < 150, tocar=otro_nombre)
n_a = len(xghc.cargar(A).doc.raiz.find("sesionesLectivas"))
w = Planificador(); w.abrir(A)
check(w.a_fundir.text() == TX("juntar_archivos") and w.a_fundir in w.menuBar().actions()[0].menu().actions(),
      'menú ARCHIVO › «Juntar archivos...»')
check(FU.TEXTO.startswith("A continuación se pedirá abrir otro archivo") and FU.SIN_INCIDENCIAS == TX("fusion_terminada_sin_problemas"),
      "textos del diálogo «Fundir» y cadena 230")
inc = w.fundir_archivos(B); r = w.proyecto.doc.raiz
check(inc == [] and mensajes[-1] == TX("fusion_terminada_sin_problemas"), f"fusión sin problemas ({inc[:3]})")
check(len(r.find("sesionesLectivas")) == n_ses, f"sesiones fundidas {len(r.find('sesionesLectivas'))} == {n_ses} (repetidas no duplicadas)")
check(len(r.findall("listasDeRelacion/simultaneas/bloqueDeSesiones")) == n_blq, "bloques de simultáneas renumerados")
check(len(r.find("reuniones")) == len(r0.find("reuniones")), "reuniones nuevas añadidas")
ids = [s.get("id") for s in r.find("sesionesLectivas")]; check(len(ids) == len(set(ids)), "ids de sesión únicos")
ok = all(x.text in set(ids) for b in r.iter("bloqueDeSesiones") for x in b.iter("sesion"))
check(ok, "referencias de bloques válidas")
pb = problema.construir(w.proyecto); check(len(pb["unidades"]) > 0, f"el problema se construye ({len(pb['unidades'])} unidades)")
check(w.pila_deshacer and w.pila_deshacer[-1][1] == TX("juntar_archivos_2"), "fusión deshacible")
w.deshacer(); check(len(w.proyecto.doc.raiz.find("sesionesLectivas")) == n_a, "Deshacer restaura el archivo A")
inc = w.fundir_archivos(C)
check(len(inc) == 1 and "se mantienen los datos del horario actual" in inc[0] and mensajes[-1].startswith("Incidencias"),
      f"prevalece el archivo actual con incidencia ({inc[:2]})")
check(hashlib.md5(open(SRC, "rb").read()).hexdigest() == h0, "original intacto")
print("FALLOS:", fallos); os._exit(1 if fallos else 0)
