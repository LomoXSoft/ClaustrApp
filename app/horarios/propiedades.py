"""Ventanas de Propiedades (sesiones, profesores, grupos, aulas y materias).

Cada control se enlaza con un campo del XML del .xghc mediante un "enlace". Al aceptar
(o pasar a Anterior/Siguiente) solo se escriben los campos cuyo valor ha cambiado, así
el archivo no recibe cambios que la usuaria no haya hecho.

Los controles sin correspondencia conocida en el formato (no vistos en los ejemplos) se
muestran deshabilitados con el aviso NO_PERSISTIDO y se registran en NO_PERSISTIDOS.
"""
from __future__ import annotations
from .textos import TX
import math
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QDialog, QTabWidget, QVBoxLayout, QHBoxLayout, QPushButton, QWidget, QLineEdit,
                               QComboBox, QCheckBox, QRadioButton, QSpinBox, QPlainTextEdit, QTreeWidget,
                               QTreeWidgetItem, QListWidget, QMessageBox, QLabel, QAbstractButton, QHeaderView)
from . import edicion as ED, modelo as M
from .formrc import PaginaRC, NO_PERSISTIDO, BotonIcono, fuente_dialogo

TXT_ANTERIOR, TXT_SIGUIENTE = TX("atras"), TX("adelante")
NO_PERSISTIDOS: dict[str, list[str]] = {}   # ventana/solapa -> textos de controles no persistidos


def _texto_control(pag: PaginaRC, cid: int) -> str:
    w = pag.c.get(cid)
    if isinstance(w, QAbstractButton) and w.text():
        return w.text()
    # buscar la etiqueta más cercana a la izquierda/encima
    if w is None:
        return str(cid)
    g = w.geometry(); mejor, dist = None, 1e9
    for l in pag.etiquetas:
        lg = l.geometry()
        if abs(lg.center().y() - g.center().y()) < 14 and lg.right() <= g.left() + 4:
            d = g.left() - lg.right()
            if d < dist:
                mejor, dist = l, d
        elif abs(lg.left() - g.left()) < 30 and 0 <= g.top() - lg.bottom() < 16 and dist > 50:
            mejor, dist = l, 50
    return mejor.text().replace("\n", " ") if mejor else str(cid)


def no_persistir(pag: PaginaRC, ventana: str, *ids):
    for i in ids:
        w = pag.c.get(i)
        if w is None:
            continue
        w.setEnabled(False); w.setToolTip(NO_PERSISTIDO)
        lst = NO_PERSISTIDOS.setdefault(f"{ventana} / {pag.titulo}", [])
        t = _texto_control(pag, i)
        if t not in lst:
            lst.append(t)


def solo_lectura(pag, *ids):
    for i in ids:
        w = pag.c.get(i)
        if isinstance(w, (QLineEdit, QPlainTextEdit)):
            w.setReadOnly(True); w.setStyleSheet("background:#f0f0f0;")


# ---------------------------------------------------------------- enlaces
class Enlace:
    def cargar(self, e): ...
    def guardar(self, arbol, e) -> bool: return False


class Texto(Enlace):
    def __init__(self, w, ruta, renombrar_lista=None):
        self.w, self.ruta, self.ren, self.v0 = w, ruta, renombrar_lista, None

    def valor(self):
        return self.w.currentText().split("  ~ ")[0].strip() if isinstance(self.w, QComboBox) else self.w.text().strip()

    def cargar(self, e):
        self.v0 = ED.leer(e, self.ruta, None)
        v = self.v0 or ""
        if isinstance(self.w, QComboBox):
            i = next((k for k in range(self.w.count()) if self.w.itemText(k).split("  ~ ")[0] == v), -1)
            if i >= 0:
                self.w.setCurrentIndex(i)
            else:
                self.w.setEditText(v) if self.w.isEditable() else (self.w.insertItem(0, v), self.w.setCurrentIndex(0))
        else:
            self.w.setText(v)

    def guardar(self, arbol, e):
        v = self.valor()
        if v == (self.v0 or ""):
            return False
        if self.ren:
            return ED.renombrar(arbol, self.ren, e, v)
        return ED.escribir(arbol, e, self.ruta, v)


class Casilla(Enlace):
    def __init__(self, w, ruta, si="true", no="false"):
        self.w, self.ruta, self.si, self.no, self.v0 = w, ruta, si, no, None

    def cargar(self, e):
        self.v0 = ED.leer(e, self.ruta, None)
        self.w.setChecked(self.v0 == self.si)
        if self.v0 is None:   # la etiqueta no existe en este elemento: no se crea
            self.w.setEnabled(False); self.w.setToolTip(NO_PERSISTIDO)

    def guardar(self, arbol, e):
        if self.v0 is None:
            return False
        v = self.si if self.w.isChecked() else self.no
        return v != self.v0 and ED.escribir(arbol, e, self.ruta, v)


class Radios(Enlace):
    """{widget: valor}; los radios cuyo valor es None no tienen valor conocido en el formato."""

    def __init__(self, mapa: dict, ruta, ventana_pag=None):
        self.mapa, self.ruta, self.v0 = mapa, ruta, None

    def cargar(self, e):
        self.v0 = ED.leer(e, self.ruta, None)
        for w, v in self.mapa.items():
            if v is None:
                w.setEnabled(False); w.setToolTip(NO_PERSISTIDO)
            w.setChecked(v is not None and v == self.v0)
        if self.v0 is None:
            for w in self.mapa:
                w.setEnabled(False); w.setToolTip(NO_PERSISTIDO)

    def guardar(self, arbol, e):
        if self.v0 is None:
            return False
        v = next((v for w, v in self.mapa.items() if w.isChecked() and v is not None), self.v0)
        return v != self.v0 and ED.escribir(arbol, e, self.ruta, v)


class Numero(Enlace):
    def __init__(self, w: QSpinBox, ruta, fmt=str, attr=None):
        self.w, self.ruta, self.fmt, self.attr, self.v0 = w, ruta, fmt, attr, None

    def _nodo(self, e):
        return ED.buscar(e, self.ruta)

    def cargar(self, e):
        n = self._nodo(e)
        if n is None:
            self.v0 = None; self.w.setEnabled(False); self.w.setToolTip(NO_PERSISTIDO); return
        self.v0 = n.get(self.attr) if self.attr else (n.text or "").strip()
        if isinstance(self.w, QLineEdit):
            self.w.setText(self.v0 or ""); return
        try:
            self.w.setValue(int(float(self.v0)))
        except (TypeError, ValueError):
            self.w.setValue(0)

    def _valor(self):
        if isinstance(self.w, QLineEdit):
            t = self.w.text().strip().replace(",", ".")
            try:
                return float(t)
            except ValueError:
                raise ValueError(f"Valor numérico no válido: «{self.w.text()}»")
        return self.w.value()

    def guardar(self, arbol, e):
        if self.v0 is None:
            return False
        v = self._valor()
        try:
            if float(self.v0) == float(v):
                return False
        except ValueError:
            pass
        if isinstance(self.w, QLineEdit) and self.fmt is str:
            v = f"{v:g}"
        n = self._nodo(e)
        if self.attr:
            n.set(self.attr, self.fmt(v))
        else:
            n.text = self.fmt(v)
        return True


# --- enlaces que pueden crear la etiqueta (tomadas de las plantillas de escritura del planificador de referencia)
class CasillaD(Casilla):
    """Casilla cuya etiqueta puede faltar: ausente = `defecto`; solo se escribe si cambia."""

    def __init__(self, w, ruta, defecto="false", si="true", no="false"):
        super().__init__(w, ruta, si, no); self.defecto = defecto

    def cargar(self, e):
        self.v0 = ED.leer(e, self.ruta, None)
        self.w.setEnabled(True); self.w.setToolTip("")
        self.w.setChecked((self.v0 if self.v0 is not None else self.defecto) == self.si)

    def guardar(self, arbol, e):
        v = self.si if self.w.isChecked() else self.no
        return v != (self.v0 if self.v0 is not None else self.defecto) and ED.escribir(arbol, e, self.ruta, v)


class Bandera(Enlace):
    """Etiqueta o atributo que planificador de referencia solo escribe con valor «true»: ausente = desmarcado.
    Con `attr` actúa sobre un atributo del nodo `ruta` (que debe existir)."""

    def __init__(self, w, ruta, attr=None):
        self.w, self.ruta, self.attr, self.v0 = w, ruta, attr, False

    def _leer(self, e):
        n = ED.buscar(e, self.ruta)
        if self.attr:
            return n, (n is not None and n.get(self.attr) == "true")
        return n, (n is not None and (n.text or "").strip() == "true")

    def cargar(self, e):
        n, self.v0 = self._leer(e)
        self.w.setChecked(self.v0)
        ok = not self.attr or n is not None
        self.w.setEnabled(ok); self.w.setToolTip("" if ok else "Requiere tener asignado un tutor")

    def guardar(self, arbol, e):
        v = self.w.isChecked()
        if v == self.v0:
            return False
        if self.attr:
            n = ED.buscar(e, self.ruta)
            if n is None:
                return False
            if v:
                n.set(self.attr, "true")
            else:
                n.attrib.pop(self.attr, None)
            return True
        return ED.escribir(arbol, e, self.ruta, "true") if v else ED.borrar(arbol, e, self.ruta)


class NumeroD(Enlace):
    """Número cuya etiqueta (o atributo) puede faltar: ausente = `defecto`."""

    def __init__(self, w, ruta, defecto=0, attr=None):
        self.w, self.ruta, self.defecto, self.attr, self.v0 = w, ruta, defecto, attr, None

    def _efectivo(self):
        try:
            return int(float(self.v0)) if self.v0 not in (None, "") else self.defecto
        except ValueError:
            return self.defecto

    def cargar(self, e):
        n = ED.buscar(e, self.ruta)
        self.v0 = (n.get(self.attr) if self.attr else (n.text or "").strip()) if n is not None else None
        self.w.setEnabled(True); self.w.setToolTip("")
        if isinstance(self.w, QLineEdit):
            self.w.setText(str(self._efectivo()))
        else:
            self.w.setValue(self._efectivo())

    def _valor(self):
        if isinstance(self.w, QLineEdit):
            t = self.w.text().strip()
            if not t:
                return self.defecto
            try:
                return int(float(t.replace(",", ".")))
            except ValueError:
                raise ValueError(f"Valor numérico no válido: «{self.w.text()}»")
        return self.w.value()

    def guardar(self, arbol, e):
        v = self._valor()
        if v == self._efectivo():
            return False
        if self.attr:
            n = ED.buscar(e, self.ruta)
            if n is None:
                return False
            n.set(self.attr, str(v)); return True
        return ED.escribir(arbol, e, self.ruta, str(v))


class RadiosD(Radios):
    """Radios cuya etiqueta puede faltar (ausente = `defecto`)."""

    def __init__(self, mapa, ruta, defecto):
        super().__init__(mapa, ruta); self.defecto = defecto

    def cargar(self, e):
        self.v0 = ED.leer(e, self.ruta, None)
        ef = self.v0 if self.v0 is not None else self.defecto
        for w, v in self.mapa.items():
            w.setEnabled(v is not None); w.setToolTip("" if v is not None else NO_PERSISTIDO)
            w.setChecked(v is not None and v == ef)

    def guardar(self, arbol, e):
        ef = self.v0 if self.v0 is not None else self.defecto
        v = next((v for w, v in self.mapa.items() if w.isChecked() and v is not None), ef)
        return v != ef and ED.escribir(arbol, e, self.ruta, v)


class TipoPeriodo(Enlace):
    """opciones/periodosLibres/tipoDePeriodo: un único hijo (diasCompletos, losPrimerosIntervalos,
    losUltimosIntervalos o intervalosSeguidos) cuyo texto es el número de periodos."""

    def __init__(self, mapa: dict, num, ruta="opciones/periodosLibres/tipoDePeriodo"):
        self.mapa, self.num, self.ruta, self.v0 = mapa, num, ruta, None

    def cargar(self, e):
        n = ED.buscar(e, self.ruta)
        h = n[0] if n is not None and len(n) else None
        self.v0 = (h.tag, (h.text or "").strip()) if h is not None else None
        tag = self.v0[0] if self.v0 else "diasCompletos"
        for w, t in self.mapa.items():
            w.setEnabled(True); w.setToolTip(""); w.setChecked(t == tag)
        try:
            val = int(self.v0[1]) if self.v0 else 0
        except ValueError:
            val = 0
        self.num.setEnabled(True); self.num.setToolTip("")
        self.num.setText(str(val)) if isinstance(self.num, QLineEdit) else self.num.setValue(val)

    def guardar(self, arbol, e):
        tag = next((t for w, t in self.mapa.items() if w.isChecked()), "diasCompletos")
        t = self.num.text().strip() if isinstance(self.num, QLineEdit) else str(self.num.value())
        try:
            t = str(int(float(t or "0")))
        except ValueError:
            raise ValueError(f"Valor numérico no válido: «{t}»")
        if (tag, t) == (self.v0 or ("diasCompletos", "0")):
            return False
        n = ED.buscar(e, self.ruta)
        if n is None:
            ED.escribir(arbol, e, self.ruta + "/" + tag, t); return True
        for h in list(n):
            ED.quitar_hijo(arbol, n, h)
        ED.insertar_hijo(arbol, n, ED.nuevo(tag, t)); return True


class IconoEstricto(Enlace):
    """Botón chincheta/cara que guarda el atributo estricto="true" (ausente = preferente)."""

    def __init__(self, b, ruta):
        self.b, self.ruta, self.v0 = b, ruta, False
        b.clicked.connect(lambda: b.set_estricto(not b.estricto))

    def cargar(self, e):
        n = ED.buscar(e, self.ruta)
        self.v0 = n is not None and n.get("estricto") == "true"
        self.b.set_estricto(self.v0); self.b.setEnabled(n is not None)
        self.b.setToolTip("Pulse para alternar obligar (chincheta) / preferir (cara)" if n is not None
                          else "Sin valor en este profesor")

    def guardar(self, arbol, e):
        n = ED.buscar(e, self.ruta)
        if n is None or self.b.estricto == self.v0:
            return False
        if self.b.estricto:
            n.set("estricto", "true")
        else:
            n.attrib.pop("estricto", None)
        return True


class RadioBandera(Bandera):
    """Par de radios para una bandera «true»-only: `w` marca la bandera, `otro` la ausencia."""

    def __init__(self, w, otro, ruta):
        super().__init__(w, ruta); self.otro = otro

    def cargar(self, e):
        super().cargar(e); self.otro.setChecked(not self.v0)


class PeriodoJornada(Enlace):
    """periodoLibreJornadaPartida (cantidad, preferentes) del tipo dado: «indistintamente» es el hijo directo de
    <opciones>; «tardes»/«mañanas» están dentro de <otrosPeriodosLibresJornadaPartida>."""

    def __init__(self, w_cant, w_pref, tipo, base="opciones"):
        self.wc, self.wp, self.tipo, self.base, self.v0 = w_cant, w_pref, tipo, base, None

    def _nodo(self, e):
        cont = ED.buscar(e, self.base if self.tipo == "indistintamente" else self.base + "/otrosPeriodosLibresJornadaPartida")
        if cont is None:
            return None
        return next((x for x in cont.findall("periodoLibreJornadaPartida")
                     if (x.findtext("tipoDePeriodoLibre") or "").strip() == self.tipo), None)

    @staticmethod
    def _num(t):
        try:
            return int(float((t or "0").strip() or 0))
        except ValueError:
            return 0

    def cargar(self, e):
        n = self._nodo(e)
        self.v0 = (self._num(n.findtext("cantidad")), self._num(n.findtext("preferentes"))) if n is not None else (0, 0)
        for w, v in zip((self.wc, self.wp), self.v0):
            w.setEnabled(True); w.setToolTip("")
            w.setText(str(v)) if isinstance(w, QLineEdit) else w.setValue(v)

    def _valor(self, w):
        return self._num(w.text()) if isinstance(w, QLineEdit) else w.value()

    def guardar(self, arbol, e):
        v = (self._valor(self.wc), self._valor(self.wp))
        if v == self.v0:
            return False
        n = self._nodo(e)
        if n is None:
            ruta = self.base if self.tipo == "indistintamente" else self.base + "/otrosPeriodosLibresJornadaPartida"
            ED.escribir(arbol, e, ruta + "/_tmp", "")       # crea los contenedores que falten
            cont = ED.buscar(e, ruta); ED.quitar_hijo(arbol, cont, cont.find("_tmp"))
            n = ED.insertar_hijo(arbol, cont, ED.nuevo("periodoLibreJornadaPartida", hijos=[
                ED.nuevo("cantidad", "0"), ED.nuevo("preferentes", "0"), ED.nuevo("tipoDePeriodoLibre", self.tipo)]))
        ED.escribir(arbol, n, "cantidad", str(v[0])); ED.escribir(arbol, n, "preferentes", str(v[1]))
        return True



def RADIOS_FRANJA(p):
    """«Franja horaria»: vocabulario misma / distinta / indiferente (plantilla del planificador de referencia)."""
    return {p.c[1214]: "distinta", p.c[1205]: "indiferente", p.c[1221]: "misma"}


def RADIOS_DIAS_SEGUIDOS(p):
    """«Impartir alguna en días alternos / todas en días consecutivos»: los cinco radios y los cinco valores de
    <permitirImpartanEnDiasSeguidos> que escribe planificador de referencia (indiferente, preferiblemente, prohibido,
    penalizaNoSeguidas, obligatoriamente), en el mismo orden en que aparecen en la ventana."""
    return {p.c[1043]: "indiferente", p.c[1044]: "preferiblemente", p.c[1060]: "prohibido",
            p.c[1046]: "penalizaNoSeguidas", p.c[1045]: "obligatoriamente"}


def _elementos_visibles(win):
    px = getattr(win, "proxy", None)
    if px is None:
        return None
    return [px.index(r, 0).data(Qt.UserRole + 1) for r in range(px.rowCount())]


def _f2(v):
    return f"{v:.2f}"


def _cargar_combo(cb: QComboBox, items, editable=False, vacio=True):
    cb.blockSignals(True); cb.clear()
    if vacio:
        cb.addItem("")
    cb.addItems(items); cb.setEditable(editable); cb.blockSignals(False)


SIN_CLAVES = (TX("no_hay_codigos_externos_cargados"))


def claves_externas(win, lista):
    """Catálogo de claves externas cargado en la ventana (delphos.catalogo): [(clave, descripción)]."""
    p = getattr(win, "proyecto", None)
    return list((getattr(p, "claves_externas", None) or {}).get(lista, []))


def conectar_claves(dlg, win, boton, combo, lista):
    """Botón «Mostrar los códigos externos en las listas desplegables»: rellena el combo de la clave con
    «clave  ~ descripción» (al guardar solo se escribe la clave). El texto actual se conserva."""
    def cargar():
        items = claves_externas(win, lista)
        if not items:
            QMessageBox.information(dlg, dlg.windowTitle(), SIN_CLAVES); return 0
        v = combo.currentText().split("  ~ ")[0].strip()
        combo.blockSignals(True); combo.clear(); combo.addItem("")
        combo.addItems([f"{k}  ~ {d}" for k, d in items])
        i = next((j for j in range(combo.count()) if combo.itemText(j).split("  ~ ")[0] == v), -1)
        combo.setCurrentIndex(i) if i >= 0 else combo.setEditText(v)
        combo.blockSignals(False)
        return len(items)
    boton.setEnabled(True); boton.setToolTip("")
    boton.clicked.connect(cargar)
    if claves_externas(win, lista):
        cargar()
    return cargar


def _con_nombre_largo(raiz, lista):
    cont, item = ED.CONTENEDOR[lista]
    c = raiz.find(cont)
    out = []
    for e in (c.findall(item) if c is not None else []):
        n, nl = ED.leer(e, "nombre", ""), ED.leer(e, "nombreCompleto", "")
        out.append(f"{n}  ~ {nl}" if nl and nl != n else n)
    return out


# ---------------------------------------------------------------- ventana base
class VentanaPropiedades(QDialog):
    """Ventana con solapas y botones Aceptar, Ayuda, <= Anterior, Siguiente =>."""

    aplicado = Signal()

    def __init__(self, win, elementos: list, indice: int, parent=None):
        super().__init__(parent or win)
        self.win, self.elementos, self.indice = win, elementos, indice
        self.setFont(fuente_dialogo())
        self.enlaces: list[tuple[Enlace, callable]] = []   # (enlace, función que da el elemento XML)
        self.tabs = QTabWidget(); self.tabs.setDocumentMode(False)
        lay = QVBoxLayout(self); lay.addWidget(self.tabs)
        bl = QHBoxLayout(); bl.addStretch(1)
        self.b_aceptar = QPushButton("Aceptar"); self.b_aceptar.setDefault(True)
        self.b_ayuda = QPushButton("Ayuda")
        self.b_ant = QPushButton(TXT_ANTERIOR); self.b_sig = QPushButton(TXT_SIGUIENTE)
        for b in (self.b_aceptar, self.b_ayuda, self.b_ant, self.b_sig):
            b.setMinimumWidth(80); bl.addWidget(b)
        lay.addLayout(bl)
        self.b_aceptar.clicked.connect(self.aceptar)
        self.b_ayuda.clicked.connect(lambda: QMessageBox.information(self, self.windowTitle(),
                                     "La ayuda estará disponible próximamente."))
        self.b_ant.clicked.connect(lambda: self.mover(-1)); self.b_sig.clicked.connect(lambda: self.mover(1))

    def pagina(self, rid, ventana_nombre):
        p = PaginaRC(rid, sin_botones=True)
        if 1520 in p.c or any(isinstance(w, QPushButton) and w.text() == "Opciones generales" for w in p.c.values()):
            for k, w in list(p.c.items()):
                if isinstance(w, QPushButton) and w.text() == "Opciones generales":
                    destino = {"106": "195", "107": "373", "666": "667"}.get(
                        str(rid), "196" if isinstance(self, PropiedadesSesion) else "218")
                    w.setToolTip(TX("opciones_generales_valores_partida_otras"))
                    w.clicked.connect(lambda _=False, d=destino: self.abrir_opciones(d))
        self.tabs.addTab(p, p.titulo)
        return p

    def abrir_opciones(self, pagina):
        """Botón «Opciones generales»: aplica lo pendiente, abre la hoja en la solapa correspondiente y recarga."""
        from .opciones_generales import DialogoOpcionesGenerales
        try:
            self.aplicar()
        except ValueError as ex:
            QMessageBox.warning(self, self.windowTitle(), str(ex)); return
        DialogoOpcionesGenerales(self.win, pagina, self).exec()
        self.reubicar(); self.cargar()

    def enlazar(self, enlace, obtener=None):
        self.enlaces.append((enlace, obtener or self.elemento_xml))
        return enlace

    # subclases
    def elemento_xml(self):
        raise NotImplementedError

    def titulo(self):
        return ""

    def cargar(self):
        for en, f in self.enlaces:
            en.cargar(f())
        self.setWindowTitle(self.titulo())
        self.b_ant.setEnabled(self.indice > 0); self.b_sig.setEnabled(self.indice < len(self.elementos) - 1)

    def hay_cambios(self):
        return True

    def aplicar(self) -> bool:
        """Escribe en el XML los valores modificados. Devuelve True si cambió algo."""
        cambios = []

        def hacer(arbol):
            for en, f in self.enlaces:
                if en.guardar(arbol, f()):
                    cambios.append(en)
            self.aplicar_extra(arbol, cambios)
            return bool(cambios)
        ok = self.win.editar(hacer, self.windowTitle(), refrescar=False)
        if cambios:
            self.aplicado.emit()
        return ok

    def aplicar_extra(self, arbol, cambios):
        pass

    def aceptar(self):
        try:
            self.aplicar()
        except ValueError as ex:
            QMessageBox.warning(self, self.windowTitle(), str(ex)); return
        self.accept()

    def mover(self, d):
        try:
            self.aplicar()
        except ValueError as ex:
            QMessageBox.warning(self, self.windowTitle(), str(ex)); return
        self.reubicar()
        self.indice = max(0, min(len(self.elementos) - 1, self.indice + d))
        self.cargar()

    def reubicar(self):
        """Tras aplicar, el modelo se ha reconstruido: tomar los objetos nuevos de la lista visible."""
        self.elementos = _elementos_visibles(self.win) or self.elementos


# ---------------------------------------------------------------- sesión
class PropiedadesSesion(VentanaPropiedades):
    """'Propiedades del bloque de sesiones de [Materia] ...'"""

    def __init__(self, win, elementos, indice, parent=None):
        super().__init__(win, elementos, indice, parent)
        V = "Propiedades del bloque de sesiones"
        raiz = win.proyecto.doc.raiz
        # 1. Asignaciones
        a = self.p_asig = self.pagina("223", V)
        lv: QTreeWidget = a.c[1055]
        lv.setHeaderLabels(["Materia", "Grupo", "Profesor", "Tmp", "Aula", "Conj.aulas", "Departamento"])
        lv.setSelectionMode(QTreeWidget.SingleSelection)
        lv.currentItemChanged.connect(lambda *_: self._linea_cambiada())
        _cargar_combo(a.c[1137], ED.nombres(raiz, "materias"))
        _cargar_combo(a.c[1138], ED.nombres(raiz, "grupos"))
        _cargar_combo(a.c[1139], ED.nombres(raiz, "profesores"))
        _cargar_combo(a.c[1141], ED.nombres(raiz, "aulas"))
        conj = raiz.find("conjuntoDeAulas")
        self.conjuntos = {c.get("nombre"): [(x.text or "").strip() for x in c.findall("aula")] for c in conj} if conj is not None else {}
        _cargar_combo(a.c[1142], [n for n in self.conjuntos if n])
        _cargar_combo(a.c[1190], ED.nombres(raiz, "tareas"))
        _cargar_combo(a.c[1192], ED.nombres(raiz, "departamentos"))
        _cargar_combo(a.c[1191], ["N"], vacio=False)
        solo_lectura(a, 1126, 1241)
        for cid, lista in ((1137, "materias"), (1139, "profesores"), (1190, "tareas"), (1192, "departamentos")):
            a.c[cid].currentTextChanged.connect(lambda t, c=cid, l=lista: self._nombre_largo(c, l, t))
        a.c[1142].currentTextChanged.connect(lambda t: a.c[1126].setText(" ".join(self.conjuntos.get(t, []))))
        no_persistir(a, V, 1074, 1403, 1280, 1143, 1144)
        self.enlazar(CasillaD(a.c[1511], "opciones/sinCambioAula"))
        self.enlazar(NumeroD(a.c[1239], "grupo", 0, attr="numeroAlumnos"))
        a.c[1191].setToolTip("Solo se ha visto el tipo «N» en los archivos de ejemplo")
        # 2. En días distintos
        d = self.p_dias = self.pagina("188", V)
        d.c[1055].setHeaderLabels(["Materia", "Grupo", "Profesor", "Tmp", "Nº"])
        d.c[1069].clicked.connect(self._anadir_dias); d.c[1070].clicked.connect(self._quitar_dias)
        # 3. Otras opciones
        self.p_opc = self.pagina("191", V)
        # 4. Más repartos
        o = self.p_dist = self.pagina("219", V)
        _cargar_combo(o.c[1161], [str(i) for i in range(1, 8)], vacio=False)
        _cargar_combo(o.c[1162], [str(i) for i in range(1, 8)], vacio=False)
        no_persistir(o, V, 1044, 1117, 1119, 1055, 1118)
        o.c[1324].setText("…"); o.c[1325].setText("…")
        o.c[1324].setEnabled(False); o.c[1325].setEnabled(False)
        # 5. Consecutivas
        c = self.p_cons = self.pagina("193", V)
        c.c[1055].setHeaderLabels(["Materia", "Grupo", "Profesor", "Tmp"])
        no_persistir(c, V, 1069, 1070, 1044, 1043, 1045, 1060, 1046, 1055)
        self._enlaces_fijos()
        self.cargar()

    # --- enlaces de opciones (comunes al bloque)
    def _enlaces_fijos(self):
        p = self.p_opc
        for cid, tag in ((1078, "penaSesionesAPrimera"), (1074, "penaSesionesAUltima"),
                         (1149, "penaSalirUltimaEntrarPrimera"), (1080, "penaCoincidanDespuesDelRecreo"),
                         (1075, "penaCoincidanPorLaTarde"), (1076, "noPermitirRecreosEntreSesiones"),
                         (1079, "recreosSeparanSesionesContinuas"), (1077, "considerarLunesViernesSeguidos")):
            self.enlazar(Casilla(p.c[cid], f"opciones/{tag}"))
        self.enlazar(Radios(RADIOS_FRANJA(p), "opciones/penaSesionMismaHora"))
        self.enlazar(Radios(RADIOS_DIAS_SEGUIDOS(p), "opciones/permitirImpartanEnDiasSeguidos"))
        d = self.p_dias
        # vocabulario de <enDiasSeguidos> en planificador de referencia: preferentemente / indistinto / obligado
        self.radios_seguidos = {d.c[1044]: "preferentemente", d.c[1043]: "indistinto", d.c[1060]: None,
                                d.c[1045]: "obligado"}
        lst = NO_PERSISTIDOS.setdefault(TX("propiedades_bloque_sesiones_dias_diferentes"), [])
        for w, v in self.radios_seguidos.items():
            if v is None and w.text() not in lst:
                lst.append(w.text())
        o = self.p_dist
        self.enlazar(Casilla(o.c[1167], "distribucionSemanal/distribucionVariable/penalizarBloquesMaximos"))
        self.enlazar(Casilla(o.c[1168], "distribucionSemanal/distribucionVariable/penalizarBloquesMinimos"))
        self.enlazar(Casilla(o.c[1160], "distribucionSemanal/distribucionVariable/admitirBloquesDiscontinuos"))

    # --- datos del bloque
    def sesion(self):
        return self.elementos[self.indice]

    def elemento_xml(self):
        return self.sesion().xml

    def bloque(self):
        s = self.sesion()
        if s.bloque is None:
            return [s]
        return [x for x in self.win.proyecto.sesiones if x.bloque == s.bloque]

    def titulo(self):
        return f"Propiedades del bloque de sesiones de {self.sesion().materia} ..."

    def _nombre_largo(self, cid, lista, t):
        destino = {1137: 1123, 1139: 1125, 1190: 1127, 1192: 1128}[cid]
        raiz = self.win.proyecto.doc.raiz
        c, item = ED.CONTENEDOR[lista]
        cont = raiz.find(c)
        e = next((x for x in (cont.findall(item) if cont is not None else []) if ED.leer(x, "nombre") == t), None)
        self.p_asig.c[destino].setText(ED.leer(e, "nombreCompleto", "") if e is not None else "")

    def cargar(self):
        a = self.p_asig
        self.lineas = self.bloque()
        self.valores = {}   # id sesión -> dict de valores editados
        lv = a.c[1055]; lv.blockSignals(True); lv.clear()
        for s in self.lineas:
            QTreeWidgetItem(lv, [s.materia, s.grupo, s.profesor, s.tmp, " ".join(s.aulas),
                                 " ".join(x for x in s.alternativas if x), s.departamento])
            self.valores[s.id] = self._leer_linea(s)
        for i in range(lv.columnCount()):
            lv.resizeColumnToContents(i)
        lv.blockSignals(False)
        self._linea_actual = None
        lv.setCurrentItem(lv.topLevelItem(self.lineas.index(self.sesion()) if self.sesion() in self.lineas else 0))
        self._linea_cambiada()
        # días distintos
        s = self.sesion()
        self.dias = list(s.en_distinto_dia); self.dias0 = list(self.dias)
        self._pintar_dias()
        for w, v in self.radios_seguidos.items():
            w.setChecked(v is not None and v == s.en_dias_seguidos); w.setEnabled(v is not None and bool(self.dias))
            if v is None:
                w.setToolTip(NO_PERSISTIDO)
        # distribuciones
        o = self.p_dist; x = s.xml
        var = x.find("distribucionSemanal/distribucionVariable")
        self.var0 = var is not None
        o.c[1060].setChecked(not self.var0); o.c[1043].setChecked(self.var0)
        partes = [(n.text or "").strip() for n in (x.findall("distribucionSemanal/distribucionFija/numSesiones") if not self.var0
                                                     else x.findall("distribucionSemanal/distribucionVariable/distribucionInicial/numSesiones"))]
        self.tmp0 = "".join(str(int(float(p))) for p in partes if p)
        o.c[1140].setText(self.tmp0)
        tot = sum(float(p) for p in partes if p) or s.duracion
        o.c[1040].setText(f"{tot:g}".replace(".", ","))
        self.tot0 = int(float(ED.leer(var, "numSesiones", "0"))) if var is not None else int(tot)
        o.c[1141].setText(str(self.tot0))
        self.max0 = ED.leer(var, "numMaximoDeSesiones", "") if var is not None else ""
        self.min0 = ED.leer(var, "numMinimoDeSesiones", "") if var is not None else ""
        o.c[1161].setCurrentText(self.max0 or str(max([int(float(p)) for p in partes if p] or [1])))
        o.c[1162].setCurrentText(self.min0 or "1")
        self._posibles()
        o.c[1141].textChanged.connect(lambda *_: self._posibles())
        for cid in (1161, 1162, 1141, 1167, 1168, 1160):
            o.c[cid].setEnabled(self.var0 or cid in (1161, 1162, 1141))
        super().cargar()
        for cid in (1167, 1168, 1160):   # sin distribución variable estas etiquetas no existen todavía
            if not self.var0:
                o.c[cid].setEnabled(False)

    def _posibles(self):
        o = self.p_dist
        try:
            tot = int(o.c[1141].text()); mx = int(o.c[1161].currentText()); mn = int(o.c[1162].currentText())
        except ValueError:
            return
        res = []

        def gen(rest, maxi, acc):
            if len(res) > 60 or len(acc) > 7:
                return
            if rest == 0:
                res.append("".join(map(str, acc))); return
            for k in range(min(maxi, rest), mn - 1, -1):
                gen(rest - k, k, acc + [k])
        gen(tot, mx, [])
        o.c[1088].clear(); o.c[1088].addItems(res)

    def _leer_linea(self, s):
        return {"materia": s.materia, "grupo": s.grupo, "profesor": s.profesor, "aula": (s.aulas or [""])[0],
                "conjunto": next((x for x in s.alternativas if x), ""), "tarea": s.tarea,
                "departamento": s.departamento, "grupoMateria": s.grupo_materia,
                "tipo": (s.xml.find("grupoMateria").get("tipo", "N") if s.xml.find("grupoMateria") is not None else "N")}

    def _guardar_linea_widgets(self):
        if self._linea_actual is None:
            return
        a = self.p_asig; v = self.valores[self._linea_actual.id]
        v.update(materia=a.c[1137].currentText(), grupo=a.c[1138].currentText(), profesor=a.c[1139].currentText(),
                 aula=a.c[1141].currentText(), conjunto=a.c[1142].currentText(), tarea=a.c[1190].currentText(),
                 departamento=a.c[1192].currentText(), grupoMateria=a.c[1103].text(), tipo=a.c[1191].currentText())

    def _linea_cambiada(self):
        a = self.p_asig
        self._guardar_linea_widgets()
        it = a.c[1055].currentItem()
        if it is None:
            return
        s = self.lineas[a.c[1055].indexOfTopLevelItem(it)]
        self._linea_actual = s; v = self.valores[s.id]
        for cid, k in ((1137, "materia"), (1138, "grupo"), (1139, "profesor"), (1141, "aula"), (1142, "conjunto"),
                       (1190, "tarea"), (1192, "departamento"), (1191, "tipo")):
            a.c[cid].setCurrentText(v[k]) if a.c[cid].findText(v[k]) >= 0 else (a.c[cid].addItem(v[k]), a.c[cid].setCurrentText(v[k]))
        a.c[1103].setText(v["grupoMateria"])
        a.c[1126].setText(" ".join(self.conjuntos.get(v["conjunto"], [])))

    # --- días distintos
    def _pintar_dias(self):
        lv = self.p_dias.c[1055]; lv.clear()
        por_id = {s.id: s for s in self.win.proyecto.sesiones}
        for i in self.dias:
            s = por_id.get(i)
            if s:
                QTreeWidgetItem(lv, [s.materia, s.grupo, s.profesor, s.tmp, s.id])
        for k in range(5):
            lv.resizeColumnToContents(k)

    def _anadir_dias(self):
        dlg = SeleccionSesiones(self.win.proyecto, excluir={self.sesion().id, *self.dias}, parent=self)
        if dlg.exec():
            for i in dlg.seleccion():
                if i not in self.dias:
                    self.dias.append(i)
            self._pintar_dias()
            for w, v in self.radios_seguidos.items():
                w.setEnabled(v is not None)
                if v is not None and not any(x.isChecked() for x in self.radios_seguidos):
                    w.setChecked(True)

    def _quitar_dias(self):
        lv = self.p_dias.c[1055]
        quitar = {it.text(4) for it in lv.selectedItems()}
        if quitar and QMessageBox.question(self, self.windowTitle(),
                                           TX("quitar_condicion_sesiones_dias_diferentes")) == QMessageBox.Yes:
            self.dias = [i for i in self.dias if i not in quitar]; self._pintar_dias()

    # --- aplicar
    def aplicar_extra(self, arbol, cambios):
        self._guardar_linea_widgets()
        # asignaciones línea a línea
        for s in self.lineas:
            v = self.valores[s.id]; v0 = self._leer_linea(s); x = s.xml
            for k in ("materia", "grupo", "profesor", "aula", "conjunto", "tarea", "departamento"):
                if v[k] != v0[k]:
                    ED.set_campo_sesion(arbol, x, k, v[k]); cambios.append(k)
            if v["grupoMateria"] != v0["grupoMateria"] and v["grupoMateria"] != ED.leer(x, "grupoMateria", ""):
                ED.escribir(arbol, x, "grupoMateria", v["grupoMateria"]); cambios.append("gm")
            gm = x.find("grupoMateria")
            if gm is not None and v["tipo"] and v["tipo"] != gm.get("tipo"):
                gm.set("tipo", v["tipo"]); cambios.append("tipo")
        # opciones comunes: copiar a las demás líneas del bloque lo cambiado en la principal
        principal = self.sesion().xml
        for s in self.lineas:
            if s.xml is principal:
                continue
            for en, _f in self.enlaces:
                if en in cambios and isinstance(en, (Casilla, Radios)):
                    val = ED.leer(principal, en.ruta)
                    if val is not None and ED.leer(s.xml, en.ruta) is not None:
                        ED.escribir(arbol, s.xml, en.ruta, val)
        # días distintos
        seg = next((v for w, v in self.radios_seguidos.items() if w.isChecked() and v), None)
        if self.dias != self.dias0 or (self.dias and seg and seg != self.sesion().en_dias_seguidos):
            ED.en_distinto_dia(arbol, principal, self.dias, seg if self.dias else None); cambios.append("edd")
        # distribución
        o = self.p_dist
        var = o.c[1043].isChecked()
        if var != self.var0:
            for s in self.lineas:
                ED.distribucion_variable(arbol, s.xml, var, int(o.c[1161].currentText()))
            cambios.append("var")
        tmp = o.c[1140].text().strip()
        if tmp != self.tmp0:
            if ED.parsear_tmp(tmp) is None:
                raise ValueError("Use el teclado para introducir la distribución semanal de las sesiones con una "
                                 "duración diaria entre 1 y 5. Por ejemplo, para tres sesiones semanales simples "
                                 "sería 111, ó para una triples y una doble, 32.")
            for s in self.lineas:
                ED.fijar_tmp(arbol, s.xml, ED.parsear_tmp(tmp))
            cambios.append("tmp")
        if var:
            for s in self.lineas:
                vx = s.xml.find("distribucionSemanal/distribucionVariable")
                if vx is None:
                    continue
                if o.c[1161].currentText() != (self.max0 or o.c[1161].currentText()) or (not self.var0):
                    ED.escribir(arbol, vx, "numMaximoDeSesiones", o.c[1161].currentText())
                if self.min0 and o.c[1162].currentText() != self.min0:
                    ED.escribir(arbol, vx, "numMinimoDeSesiones", o.c[1162].currentText())
                if o.c[1141].text().strip() != str(self.tot0) and o.c[1141].text().strip().isdigit():
                    ED.escribir(arbol, vx, "numSesiones", _f2(int(o.c[1141].text())))
                    ED.escribir(arbol, s.xml, "duracionSemanal", _f2(int(o.c[1141].text())))
            cambios.append("dist") if self.var0 and (o.c[1161].currentText() != self.max0 or o.c[1162].currentText() != self.min0) else None

    def reubicar(self):
        # tras reconstruir el modelo, sustituir las sesiones por las nuevas (mismo id)
        por_id = {s.id: s for s in self.win.proyecto.sesiones}
        self.elementos = [por_id.get(s.id, s) for s in self.elementos]


class SeleccionSesiones(QDialog):
    """'Elegir sesiones lectivas'"""

    def __init__(self, proyecto, excluir=(), parent=None):
        super().__init__(parent)
        self.p = PaginaRC("192", self); self.setWindowTitle(self.p.titulo); self.setFixedSize(self.p.size())
        lv = self.p.c[1055]; lv.setHeaderLabels(["Materia", "Grupo", "Profesor", "Tmp", "Nº"])
        self.p.c[1071].addItems(["", "Grupo", "Materia", "Profesor"])
        self.todas = [s for s in proyecto.sesiones if s.id not in excluir]
        self.p.c[1071].currentTextChanged.connect(self._tipos)
        self.p.c[1072].currentTextChanged.connect(lambda *_: self._llenar())
        self.p.c[1069].setEnabled(False)
        self.p.c[1].clicked.connect(self.accept); self.p.c[2].clicked.connect(self.reject)
        self.p.c[57670].setEnabled(False)
        self.p.c[1367].clicked.connect(lv.selectAll)
        self._llenar()

    def _tipos(self, t):
        cb = self.p.c[1072]; cb.blockSignals(True); cb.clear()
        k = {"Grupo": "grupo", "Materia": "materia", "Profesor": "profesor"}.get(t)
        if k:
            cb.addItems(sorted({getattr(s, k) for s in self.todas}))
        cb.blockSignals(False); self._llenar()

    def _llenar(self):
        lv = self.p.c[1055]; lv.clear()
        k = {"Grupo": "grupo", "Materia": "materia", "Profesor": "profesor"}.get(self.p.c[1071].currentText())
        v = self.p.c[1072].currentText()
        for s in self.todas:
            if k and getattr(s, k) != v:
                continue
            QTreeWidgetItem(lv, [s.materia, s.grupo, s.profesor, s.tmp, s.id])
        for i in range(5):
            lv.resizeColumnToContents(i)

    def seleccion(self):
        return [it.text(4) for it in self.p.c[1055].selectedItems()]


# ---------------------------------------------------------------- profesor
class PropiedadesProfesor(VentanaPropiedades):
    """'Propiedades del profesor [Nombre]'"""

    def __init__(self, win, elementos, indice, parent=None):
        super().__init__(win, elementos, indice, parent)
        V = "Propiedades del profesor"
        raiz = win.proyecto.doc.raiz
        i = self.p_id = self.pagina("178", V)
        self.enlazar(Texto(i.c[1062], "nombre", renombrar_lista="profesores"))
        self.enlazar(Texto(i.c[1259], "abreviatura"))
        self.enlazar(Texto(i.c[1061], "nombreCompleto"))
        i.c[1072].setEditable(True)
        self.enlazar(Texto(i.c[1072], "claveDeExportacion"))
        _cargar_combo(i.c[1170], _con_nombre_largo(raiz, "departamentos"))
        self.enlazar(Texto(i.c[1170], "departamento"))
        self.enlazar(Texto(i.c[1090], "tomaDePosesion"))
        self.enlazar(Texto(i.c[1314], "email"))
        no_persistir(i, V, 1392)
        self.cargar_claves = conectar_claves(self, win, i.c[1091], i.c[1072], "profesores")
        solo_lectura(i, 1059, 1069, 1076, 1070, 1078, 1073, 1071, 1074, 1075, 1079, 1080, 1011)
        # 2. Periodos libres
        p = self.p_pl = self.pagina("106", V)
        O = "opciones/"
        self.enlazar(Numero(p.c[1071], O + "periodosLibres/cantidadDeDias"))
        self.enlazar(PeriodoJornada(p.c[1077], p.c[1079], "indistintamente"))
        self.enlazar(TipoPeriodo({p.c[1045]: "diasCompletos", p.c[1046]: "losPrimerosIntervalos",
                                  p.c[1205]: "losUltimosIntervalos", p.c[1214]: "intervalosSeguidos"}, p.c[1069]))
        self.enlazar(PeriodoJornada(p.c[1065], p.c[1066], "tardes"))
        self.enlazar(PeriodoJornada(p.c[1067], p.c[1075], "mañanas"))
        inc = O + "incompatibilidadEntreSesiones/"
        self.botones_tipo = {}
        for chk, btn, tag, num in ((1171, 1234, "entrarPrimeraSalirUltima", 1382),
                                   (1172, 1235, "entrarPrimeraSalirTarde", None),
                                   (1206, 1236, "entrarPrimeraSalirUltimaManana", None),
                                   (1218, 1237, "entrarPrimeraSalirUltimaTarde", None),
                                   (1150, 1238, "salirUltimaMananaEntrarPrimeraTarde", None),
                                   (1216, 1239, "salirUltimaMananaTardeCompleta", None),
                                   (1217, 1240, "menosDeDosIntervalosLibres", None),
                                   (1149, 1233, "salirUltimaEntrarPrimera", 1381),
                                   (1151, 1241, "salirUltimaEntrarPrimeraLunes", 1386)):
            self.enlazar(Casilla(p.c[chk], inc + tag))
            if num:
                self.enlazar(Numero(p.c[num], inc + tag, attr="nIntervalos"))
            self.botones_tipo[btn] = inc + tag
            p.c[btn].setEnabled(False)
            p.c[btn].setToolTip("Estricto (chincheta) o preferente (cara): solo se muestra; " + NO_PERSISTIDO.lower())
        NO_PERSISTIDOS.setdefault(f"{V} / Periodos libres", []).append(
            "Iconos preferir/obligar de los periodos mutuamente excluyentes (solo lectura)")
        # 3. Compactación
        c = self.p_comp = self.pagina("107", V)
        self.enlazar(Casilla(c.c[1356], O + "eliminarHuecos"))
        self.enlazar(Numero(c.c[1063], O + 'intervalosDePermanenciaSemanales[@estricto="true"]'))
        self.enlazar(Numero(c.c[1082], O + 'intervalosDePermanenciaSemanales[@estricto="false"]'))
        self.enlazar(Numero(c.c[1068], O + 'intervalosDePermanenciaDiarios[@estricto="true"]'))
        self.enlazar(Numero(c.c[1084], O + 'intervalosDePermanenciaDiarios[@estricto="false"]'))
        self.enlazar(Numero(c.c[1064], O + "maximasHorasSeguidas"))
        self.enlazar(Numero(c.c[1065], "prioridad"))
        self.enlazar(IconoEstricto(c.c[1509], O + "maximasHorasSeguidas"))
        self.enlazar(Bandera(c.c[1074], O + "penalizarAlrededorGuardiaRecreo"))
        self.enlazar(IconoEstricto(c.c[1510], O + "penalizarAlrededorGuardiaRecreo"))
        asoc = sorted({(x.findtext("horarioAsoc") or "").strip() for x in raiz.iter("profesor")} - {""})
        _cargar_combo(c.c[1328], asoc, editable=True); c.c[1328].setEditable(True)
        self.enlazar(Texto(c.c[1328], "horarioAsoc"))
        # 4. Ocupación diaria
        od = self.p_od = self.pagina("666", V)
        od.regrupar([1470, 1043])
        self.enlazar(RadioBandera(od.c[1043], od.c[1470], O + "minimizarDiasOcupados"))
        for estr, pref, pond, tag in ((1349, 1208, 1061, "considerarMinimasHorasDiariasSolamenteLectivas"),
                                      (1207, 1357, 1060, "considerarMaximasHorasDiariasSolamenteLectivas"),
                                      (1350, 1209, 1062, "considerarMinimasHorasDiarias"),
                                      (1211, 1360, 1063, "considerarMaximasHorasDiarias")):
            self.enlazar(Radios({od.c[estr]: "estricto", od.c[pref]: "optimizacionPreferente", od.c[pond]: "ponderable"},
                                O + tag))
        for mas, eq, menos, tag in ((1205, 1214, 1221, "valorMinimasHorasCalculadoSolamenteLectivas"),
                                    (1206, 1215, 1222, "valorMaximasHorasCalculadoSolamenteLectivas"),
                                    (1210, 1216, 1223, "valorMinimasHorasCalculado"),
                                    (1212, 1217, 1224, "valorMaximasHorasCalculado")):
            self.enlazar(Radios({od.c[mas]: "unaHoraMas", od.c[eq]: "automatico", od.c[menos]: "unaHoraMenos"}, O + tag))
        # 5. Desideratas
        de = self.p_des = self.pagina("431", V)
        no_persistir(de, V, 1010)
        self.enlazar(NumeroD(de.c[1011], "reduccionCargaLectiva", 0))
        self.enlazar(Bandera(de.c[1077], "daPracticas"))
        self.cargar()

    def elemento_xml(self):
        return self.elementos[self.indice].datos["_xml"]

    def titulo(self):
        return f"Propiedades del profesor {ED.leer(self.elemento_xml(), 'nombre', '')}"

    def cargar(self):
        super().cargar()
        p = self.win.proyecto; e = self.elementos[self.indice]; nombre = e.nombre
        from .listas import _lectivas, _guardias_de, _integrantes
        i = self.p_id
        lect = float(_lectivas(p, "profesor", nombre))
        reun = sum(1 for r in p.reuniones if nombre in _integrantes(r))
        g = _guardias_de(p, nombre, False) or "0"; gr = _guardias_de(p, nombre, True) or "0"
        comp = sum(1 for c in p.complementarias if c.datos.get("profesor") == nombre)
        i.c[1059].setText(f"{lect:g}"); i.c[1069].setText(str(reun)); i.c[1070].setText(g); i.c[1073].setText(gr)
        i.c[1076].setText(str(comp)); i.c[1078].setText(f"{lect + reun + int(g) + comp:g}")
        tut = [gg.nombre for gg in p.grupos if gg.datos.get("profesorTutor") == nombre]
        i.c[1011].setText(", ".join(tut))
        marcos = list(p.marcos.values())
        for k, (lbl, ed) in enumerate(((1183, 1074), (1184, 1075), (1185, 1079), (1186, 1080))):
            vis = k < len(marcos)
            i.c[lbl].setVisible(vis); i.c[ed].setVisible(vis)
            if vis:
                m = marcos[k]
                libres = sum(1 for t in m.tramos if t.tipo == "lectivo" and e.plantilla.get((m.id, t.dia, t.indice)) != M.PROHIBIDO)
                i.c[lbl].setText(f"En marco {m.id}"); i.c[ed].setText(str(libres))
        if len(marcos) == 1:
            i.c[1183].setVisible(False); i.c[1074].setVisible(False)
            m = marcos[0]
            i.c[1071].setText(str(sum(1 for t in m.tramos if t.tipo == "lectivo" and e.plantilla.get((m.id, t.dia, t.indice)) != M.PROHIBIDO)))
        else:
            i.c[1071].setText("")
        # iconos estricto/preferente según el atributo tipo
        x = self.elemento_xml()
        for btn, ruta in self.botones_tipo.items():
            n = ED.buscar(x, ruta)
            self.p_pl.c[btn].set_estricto(n is not None and n.get("tipo") == "prohibición")
        # mínimo/máximo diario calculado
        dias = len(marcos[0].dias) if marcos else 5
        mn, mx = (math.floor(lect / dias), math.ceil(lect / dias)) if lect else (0, 0)
        for cid, v in ((1351, mn), (1352, mx), (1356, mn), (1361, mx)):
            self.p_od.c[cid].setText(str(v))
        # desideratas: sesiones asignadas
        lw = self.p_des.c[1055]; lw.clear()
        lw.addItems([f"{s.grupo_materia or s.materia + '/' + s.grupo}  ({s.tmp})" for s in p.sesiones if s.profesor == nombre])

    def reubicar(self):
        lst = self.win.proyecto.profesores
        self.elementos = lst


# ---------------------------------------------------------------- diálogos simples (grupo, aula, materia)
class VentanaSimple(QDialog):
    """Grupo de alumnos / Aula / Materia: ventana única con sus propios botones."""

    RID = ""; LISTA = ""

    def __init__(self, win, elementos, indice, parent=None):
        super().__init__(parent or win)
        self.win, self.elementos, self.indice = win, elementos, indice
        self.p = PaginaRC(self.RID, self); self.setFixedSize(self.p.size()); self.setFont(fuente_dialogo())
        self.enlaces = []
        self.V = self.p.titulo
        raiz = win.proyecto.doc.raiz
        self.preparar(raiz)
        self.p.c[1].clicked.connect(self.aceptar); self.p.c[2].clicked.connect(self.reject)
        self.p.c[57670].clicked.connect(lambda: QMessageBox.information(self, self.windowTitle(),
                                        "La ayuda estará disponible próximamente."))
        self.p.c[1053].clicked.connect(lambda: self.mover(-1)); self.p.c[1054].clicked.connect(lambda: self.mover(1))
        if 1091 in self.p.c and 1071 in self.p.c:
            self.cargar_claves = conectar_claves(self, win, self.p.c[1091], self.p.c[1071], self.LISTA)
        if 1296 in self.p.c:
            self.p.c[1296].setEnabled(False)
        self.cargar()

    def enlazar(self, en):
        self.enlaces.append(en); return en

    def elemento_xml(self):
        return self.elementos[self.indice].datos["_xml"]

    def cargar(self):
        for en in self.enlaces:
            en.cargar(self.elemento_xml())
        self.setWindowTitle(f"{self.V}: {self.elementos[self.indice].nombre}")
        self.p.c[1053].setEnabled(self.indice > 0); self.p.c[1054].setEnabled(self.indice < len(self.elementos) - 1)
        self.calcular()

    def calcular(self):
        pass

    def aplicar(self):
        def hacer(arbol):
            return any([en.guardar(arbol, self.elemento_xml()) for en in self.enlaces])
        self.win.editar(hacer, self.windowTitle(), refrescar=False)

    def aceptar(self):
        self.aplicar(); self.accept()

    def mover(self, d):
        self.aplicar()
        self.elementos = _elementos_visibles(self.win) or getattr(self.win.proyecto, self.LISTA)
        self.indice = max(0, min(len(self.elementos) - 1, self.indice + d)); self.cargar()


class PropiedadesGrupo(VentanaSimple):
    RID = "177"; LISTA = "grupos"

    def preparar(self, raiz):
        c = self.p.c
        self.enlazar(Texto(c[1010], "nombre", renombrar_lista="grupos"))
        self.enlazar(Texto(c[1259], "abreviatura"))
        _cargar_combo(c[1245], ED.nombres(raiz, "cursos")); self.enlazar(Texto(c[1245], "cursoPerteneciente"))
        _cargar_combo(c[1247], ED.nombres(raiz, "aulas")); self.enlazar(Texto(c[1247], "aula"))
        _cargar_combo(c[1246], ED.nombres(raiz, "profesores")); self.enlazar(Texto(c[1246], "profesorTutor"))
        self.enlazar(Casilla(c[1075], "huecosEnNoPreferentes"))
        self.enlazar(Radios({c[1214]: "true", c[1221]: "false", c[1205]: None}, "eliminarHuecos"))
        self.enlazar(Texto(c[1061], "nombreCompleto"))
        c[1071].setEditable(True); self.enlazar(Texto(c[1071], "claveDeExportacion"))
        self.enlazar(NumeroD(c[1239], "numeroAlumnos", 0))
        self.enlazar(NumeroD(c[1237], "limiteOcupacionDia", 0))
        self.enlazar(NumeroD(c[1235], "tardesLibres", 0))
        for cid, at in ((1077, "imparteTodosLosDias"), (1074, "imparteAPrimeras"), (1076, "imparteAUltimas")):
            self.enlazar(Bandera(c[cid], "profesorTutor", attr=at))
        no_persistir(self.p, self.V, 1069)
        if c[1205].text() not in NO_PERSISTIDOS[f"{self.V} / {self.p.titulo}"]:
            NO_PERSISTIDOS[f"{self.V} / {self.p.titulo}"].append(c[1205].text())
        solo_lectura(self.p, 1059, 1060, 1062)
        # marcos
        marcos = list(self.win.proyecto.marcos.values())
        self.radios_marco = {}
        for k, rid in enumerate((1044, 1043, 1045, 1046)):
            if k < len(marcos):
                c[rid].setText(marcos[k].nombre or f"Marco {marcos[k].id}"); self.radios_marco[c[rid]] = marcos[k].id
            else:
                c[rid].setVisible(False)
        c[1179].setVisible(len(marcos) > 1)
        for rb in self.radios_marco:
            rb.setVisible(len(marcos) > 1)

    def cargar(self):
        super().cargar()
        x = self.elemento_xml(); self.marco0 = x.get("submarco")
        for rb, m in self.radios_marco.items():
            rb.setChecked(m == self.marco0)

    def aplicar(self):
        x = self.elemento_xml()
        nuevo = next((m for rb, m in self.radios_marco.items() if rb.isChecked()), self.marco0)

        def hacer(arbol):
            ch = any([en.guardar(arbol, x) for en in self.enlaces])
            if self.marco0 is not None and nuevo != self.marco0:
                x.set("submarco", nuevo); ch = True
            return ch
        self.win.editar(hacer, self.windowTitle(), refrescar=False)

    def calcular(self):
        from .listas import _lectivas, _posiciones
        e = self.elementos[self.indice]
        self.p.c[1059].setText(_lectivas(self.win.proyecto, "grupo", e.nombre))
        self.p.c[1060].setText(_posiciones(self.win.proyecto, e)); self.p.c[1062].setText("")


class PropiedadesAula(VentanaSimple):
    RID = "161"; LISTA = "aulas"

    def preparar(self, raiz):
        c = self.p.c
        self.enlazar(Texto(c[1010], "nombre", renombrar_lista="aulas"))
        self.enlazar(Texto(c[1259], "abreviatura"))
        self.enlazar(Radios({c[1043]: "true", c[1044]: "false"}, "dedicada"))
        self.enlazar(Texto(c[1061], "descripcion"))
        self.enlazar(NumeroD(c[1239], "numeroAlumnos", 0))
        c[1071].setEditable(True); self.enlazar(Texto(c[1071], "claveDeExportacion"))
        solo_lectura(self.p, 1059, 1060, 1062, 1063, 1064, 1065)

    def calcular(self):
        from .listas import _lectivas
        p = self.win.proyecto; e = self.elementos[self.indice]
        self.p.c[1059].setText(_lectivas(p, "aulas", e.nombre))
        m = p.marcos.get(e.marco) or (next(iter(p.marcos.values())) if p.marcos else None)
        if m:
            self.p.c[1060].setText(str(sum(1 for t in m.tramos if t.tipo == "lectivo" and e.plantilla.get((m.id, t.dia, t.indice)) != M.PROHIBIDO)))
        lw = self.p.c[1055]; lw.clear()
        lw.addItems([n for n, l in p.conjuntos_aulas.items() if e.nombre in l])


class PropiedadesMateria(VentanaSimple):
    RID = "176"; LISTA = "materias"

    def preparar(self, raiz):
        c = self.p.c
        self.enlazar(Texto(c[1010], "nombre", renombrar_lista="materias"))
        self.enlazar(Texto(c[1259], "abreviatura"))
        self.enlazar(Texto(c[1061], "nombreCompleto"))
        c[1071].setEditable(True); self.enlazar(Texto(c[1071], "claveDeExportacion"))
        _cargar_combo(c[1170], _con_nombre_largo(raiz, "departamentos")); self.enlazar(Texto(c[1170], "departamento"))
        self.enlazar(Casilla(c[1074], "esTutoria"))
        self.enlazar(Bandera(c[1075], "esDePractica"))
        solo_lectura(self.p, 1059)

    def calcular(self):
        from .listas import _lectivas
        p = self.win.proyecto; e = self.elementos[self.indice]
        self.p.c[1059].setText(_lectivas(p, "materia", e.nombre))
        lw = self.p.c[1055]; lw.clear()
        for cu in p.cursos:
            x = cu.datos["_xml"].find("materiasDelCurso")
            if x is not None and any((m.text or "").strip() == e.nombre for m in x.iter("materia")):
                lw.addItem(cu.nombre)


VENTANAS = {"sesiones": PropiedadesSesion, "profesores": PropiedadesProfesor, "grupos": PropiedadesGrupo,
            "aulas": PropiedadesAula, "materias": PropiedadesMateria}


def informe_no_persistidos() -> str:
    lineas = []
    for k in sorted(NO_PERSISTIDOS):
        lineas.append(f"- {k}: " + "; ".join(dict.fromkeys(NO_PERSISTIDOS[k])))
    return "\n".join(lineas)
