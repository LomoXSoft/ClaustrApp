"""Pasos 7–9 de la versión sencilla: generar (motor real), revisar y ajustar (editor real), informes."""
import os, time
from PySide6.QtCore import Qt, QTimer, QMimeData, QSettings
from PySide6.QtGui import QColor, QDrag, QCursor
from PySide6.QtWidgets import (QHBoxLayout, QVBoxLayout, QComboBox, QLabel, QProgressBar, QTableWidget,
                               QTableWidgetItem, QAbstractItemView, QMessageBox, QFileDialog, QListWidget,
                               QListWidgetItem, QApplication, QSplitter, QWidget, QTextBrowser)
from .. import APP_NAME, VENDOR, AJUSTES
from .. import validacion as VAL, resultado as RES, comprobador
from . import textos as T
from .comun import lbl, btn, tarjeta, tabla, fila_botones
from .pasos_datos import Paso

TIEMPOS = [("Rápido (30 segundos)", 30), ("Normal (2 minutos)", 120), ("A fondo (10 minutos)", 600)]


def ruta_resultado(ruta_xghc):
    return os.path.splitext(ruta_xghc)[0] + RES.EXTENSION


# ---------------------------------------------------------------------------------------------- 7
class PasoGenerar(Paso):
    clave = "generar"

    def __init__(self, v):
        super().__init__(v)
        f, c = tarjeta(); self.lay.addWidget(f)
        c.addWidget(lbl("<b>Antes de empezar</b>")); self.lst = QListWidget(); self.lst.setMaximumHeight(200); c.addWidget(self.lst)
        h = QHBoxLayout(); h.addWidget(QLabel("Tiempo de búsqueda:")); self.cb_t = QComboBox()
        self.cb_t.addItems([t for t, _ in TIEMPOS]); self.cb_t.setCurrentIndex(1); h.addWidget(self.cb_t); h.addStretch(1)
        self.b_gen = btn("Generar el horario", lambda: self.generar(), primario=True); self.b_parar = btn("Parar", lambda: self.parar())
        self.b_parar.setEnabled(False); h.addWidget(self.b_gen); h.addWidget(self.b_parar); c.addLayout(h)
        f2, c2 = tarjeta(); self.lay.addWidget(f2)
        self.barra = QProgressBar(); self.barra.setRange(0, 100); c2.addWidget(self.barra)
        self.lbl_est = lbl("Pulse «Generar el horario» cuando los datos estén listos."); c2.addWidget(self.lbl_est)
        self.lay.addStretch(1)
        self.motor = None; self.timer = QTimer(self); self.timer.timeout.connect(self._sondear)
        self.segundos = 120; self.total = 0; self.terminado = None

    def cargar(self):
        self.lst.clear(); p = self.p
        if not p:
            return
        horas = sum(int(c) for s in p.sesiones for c in (s.tmp or "") if c.isdigit())
        filas = [(bool(p.marcos), f"Horario de clases: {sum(m.lectivos_por_semana() for m in p.marcos.values())} periodos lectivos por semana"),
                 (bool(p.profesores), f"{len(p.profesores)} profesores"), (bool(p.grupos), f"{len(p.grupos)} grupos"),
                 (bool(p.sesiones), f"{len(p.sesiones)} materias asignadas ({horas} horas de clase)")]
        sin_prof = sum(1 for s in p.sesiones if not s.profesor)
        if sin_prof:
            filas.append((None, f"{sin_prof} materias sin profesor (se colocarán igualmente)"))
        errores = [m for m in VAL.validar(p) if m[0] == VAL.ERROR]
        filas.append((not errores, "Datos sin errores" if not errores else f"{len(errores)} errores en los datos: {errores[0][1]}"))
        for ok, t in filas:
            it = QListWidgetItem(("✔  " if ok else "⚠  " if ok is None else "✖  ") + t)
            it.setForeground(QColor("#2e7d32" if ok else "#b26a00" if ok is None else "#c62828")); self.lst.addItem(it)
        self.b_gen.setEnabled(bool(p.sesiones) and not errores and self.motor is None)

    def generar(self, segundos=None, hilos=None):
        from ..motor.problema import construir
        from ..motor.proceso import MotorEnProceso
        p = self.p
        if not p or not p.sesiones:
            return False
        if p.modificado or not getattr(p, "ruta_guardado", None):
            self.v.estado("Hay que guardar el archivo antes de generar")
            if not self.v.guardar():
                return False
        p = self.p
        self.segundos = segundos or TIEMPOS[self.cb_t.currentIndex()][1]
        pb = construir(p); self.total = sum(1 for _ in pb.get("unidades", [])) or len(p.sesiones)
        self.motor = MotorEnProceso(pb, segundos=self.segundos, hilos=hilos or min(8, os.cpu_count() or 2))
        self.motor.iniciar(); self.t0 = time.time(); self.terminado = None
        self.barra.setValue(0); self.lbl_est.setText("Buscando un horario…")
        self.b_gen.setEnabled(False); self.b_parar.setEnabled(True); self.timer.start(200)
        return True

    def parar(self):
        if self.motor and self.motor.vivo():
            self.motor.parar(); self.lbl_est.setText("Deteniendo… se guardará el mejor horario encontrado.")

    def _sondear(self):
        if not self.motor:
            return
        for e in self.motor.eventos():
            ev = e.get("evento")
            if ev == "solucion":
                nc = e.get("no_colocadas", 0)
                self.lbl_est.setText(("Horario completo encontrado; mejorándolo…" if nc == 0 else
                                      f"Horario provisional: faltan {nc} clases por colocar; seguimos buscando…"))
            elif ev == "fase":
                self.lbl_est.setText(e.get("texto", ""))
            elif ev == "fin":
                self._fin(e["resultado"]); return
            elif ev == "error":
                self._parado(); QMessageBox.critical(self, APP_NAME, "Error en el motor:\n\n" + e.get("texto", "")[-1200:]); return
        self.barra.setValue(min(99, int(100 * (time.time() - self.t0) / max(1, self.segundos))))
        if not self.motor.vivo() and self.motor.resultado is None:
            self.motor.eventos()

    def _parado(self):
        self.timer.stop(); self.motor = None; self.b_parar.setEnabled(False); self.b_gen.setEnabled(True)

    def _fin(self, r):
        p = self.p; self._parado()
        if not r.get("sesiones") and r.get("estado") not in ("OPTIMAL", "FEASIBLE"):
            self.lbl_est.setText("No se ha encontrado ningún horario. Revise las preferencias «No puede» o dé más tiempo.")
            self.terminado = False; return
        doc = RES.crear(r, p.ruta, {"nombre": "cpsat", "segundos": self.segundos, "hilos": 0})
        L = ruta_resultado(p.ruta); RES.guardar(doc, L)
        self.v.cargar_resultado(L)
        est = r.get("estadisticas", {}); nc = est.get("no_colocadas", 0) + est.get("guardias_no_colocadas", 0)
        self.barra.setValue(100)
        self.lbl_est.setText("¡Horario generado! " + ("Todas las clases están colocadas." if nc == 0 else
                             f"Quedan {nc} elementos sin colocar: puede colocarlos en «Revisar y ajustar».")
                             + f"\nGuardado en {os.path.basename(L)}.")
        self.terminado = True
        self.v.estado("Horario generado")

    def mas_opciones(self):
        self.v.nucleo.opciones_generales(); self.v.refrescar()


# ---------------------------------------------------------------------------------------------- 8
class Rejilla(QTableWidget):
    """Horario de un grupo/profesor/aula con arrastrar y soltar."""
    def __init__(self, paso):
        super().__init__(0, 0); self.paso = paso
        self.setEditTriggers(QAbstractItemView.NoEditTriggers); self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setDragEnabled(True); self.setAcceptDrops(True); self.viewport().setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDrop); self.setWordWrap(True)

    def startDrag(self, acciones):
        it = self.currentItem()
        if it is None or not it.data(Qt.UserRole):
            return
        self.paso.seleccionar(it.data(Qt.UserRole))
        md = QMimeData(); md.setText(it.data(Qt.UserRole))
        d = QDrag(self); d.setMimeData(md); d.exec(Qt.MoveAction)

    def dragEnterEvent(self, e):
        e.acceptProposedAction() if e.mimeData().hasText() else e.ignore()

    def dragMoveEvent(self, e):
        e.acceptProposedAction()

    def dropEvent(self, e):
        idx = self.indexAt(e.position().toPoint())
        e.acceptProposedAction()
        if idx.isValid():
            self.paso.soltar(idx.row(), idx.column())


class PasoRevisar(Paso):
    clave = "revisar"
    VISTAS = {"Grupo": "Grupos", "Profesor": "Profesorado", "Aula": "Aulas"}

    def __init__(self, v):
        super().__init__(v)
        h = QHBoxLayout(); self.lay.addLayout(h)
        self.cb_vista = QComboBox(); self.cb_vista.addItems(list(self.VISTAS)); self.cb_nombre = QComboBox()
        h.addWidget(QLabel("Ver horario de:")); h.addWidget(self.cb_vista); h.addWidget(self.cb_nombre, 1)
        self.b_desh = btn("↶ Deshacer", lambda: self.deshacer()); self.b_reh = btn("↷ Rehacer", lambda: self.rehacer())
        self.b_guardar = btn("Guardar cambios", lambda: self.guardar(), primario=True)
        h.addWidget(self.b_desh); h.addWidget(self.b_reh); h.addWidget(self.b_guardar)
        self.cb_vista.currentTextChanged.connect(lambda *_: self._nombres()); self.cb_nombre.currentTextChanged.connect(lambda *_: self.pintar())
        self.lbl_estado = lbl(""); self.lay.addWidget(self.lbl_estado)
        sp = QSplitter(Qt.Horizontal); self.lay.addWidget(sp, 1)
        self.rej = Rejilla(self); sp.addWidget(self.rej)
        self.rej.cellClicked.connect(self._clic)
        der = QWidget(); dl = QVBoxLayout(der); dl.setContentsMargins(6, 0, 0, 0); sp.addWidget(der); sp.setSizes([760, 330])
        dl.addWidget(lbl("<b>¿Por qué no puedo…?</b>"))
        self.por_que = QTextBrowser(); self.por_que.setMinimumWidth(260); dl.addWidget(self.por_que, 1)
        self.b_mover = btn("Mover aquí", lambda: self.mover()); self.b_inter = btn("Intercambiar", lambda: self.intercambiar())
        self.b_recol = btn("Dejar que el programa la recoloque", lambda: self.recolocar())
        for b in (self.b_mover, self.b_inter, self.b_recol):
            dl.addWidget(b); b.setEnabled(False)
        dl.addWidget(lbl("<b>Sin colocar</b>")); self.lst_fuera = QListWidget(); self.lst_fuera.setMaximumHeight(150); dl.addWidget(self.lst_fuera)
        dl.addWidget(btn("Colocar la seleccionada", lambda: self.colocar_fuera()))
        leyenda = QHBoxLayout()
        for col, t in ((T.COLOR_VERDE, "Se puede"), (T.COLOR_AMBAR, "Se puede, con avisos"), (T.COLOR_ROJO, "No se puede")):
            l = QLabel(f"  {t}  "); l.setStyleSheet(f"background:{col};border-radius:4px;padding:2px"); leyenda.addWidget(l)
        leyenda.addStretch(1); self.lay.addLayout(leyenda)
        self.sel = None; self.destino = None; self.colores = {}; self.prop = None; self.pos = {}

    @property
    def ed(self):
        return self.v.editor

    def cargar(self):
        self._nombres()

    def _nombres(self):
        actual = self.cb_nombre.currentText(); self.cb_nombre.blockSignals(True); self.cb_nombre.clear()
        if self.ed:
            self.cb_nombre.addItems(self.ed.elementos(self.VISTAS[self.cb_vista.currentText()]))
            if actual:
                self.cb_nombre.setCurrentText(actual)
        self.cb_nombre.blockSignals(False); self.limpiar_seleccion(); self.pintar()

    def _marco(self):
        ed = self.ed; vista = self.VISTAS[self.cb_vista.currentText()]
        return ed.marcos_de(vista, self.cb_nombre.currentText())[0]

    def pintar(self):
        ed = self.ed; self.rej.clear(); self.pos = {}
        self.b_desh.setEnabled(bool(ed and ed.pila_deshacer)); self.b_reh.setEnabled(bool(ed and ed.pila_rehacer))
        if not ed or not self.cb_nombre.currentText():
            self.rej.setRowCount(0); self.rej.setColumnCount(0)
            self.lbl_estado.setText("Todavía no hay horario: vaya al paso «Generar»." if not ed else ""); return
        vista = self.VISTAS[self.cb_vista.currentText()]; nombre = self.cb_nombre.currentText()
        m = ed.p.marcos[self._marco()]; fil = m.filas(); dias = m.dias
        self.rej.setRowCount(len(fil)); self.rej.setColumnCount(len(dias))
        self.rej.setHorizontalHeaderLabels([T.DIAS[d] for d in dias])
        self.rej.setVerticalHeaderLabels([f"{t.entrada}\n{t.salida}" for t in fil])
        celdas = {}
        for it in ed.items_de(vista, nombre):
            for (mm, d, i) in ed.posiciones(it):
                if mm == m.id:
                    celdas.setdefault((d, i), []).append(it)
        for r, t in enumerate(fil):
            for c, d in enumerate(dias):
                self.pos[(r, c)] = (m.id, d, t.indice)
                its = celdas.get((d, t.indice), [])
                txt = "\n".join(ed.texto_celda(x, vista) for x in its[:2])
                cel = QTableWidgetItem(txt if t.tipo == "lectivo" or its else "Recreo")
                cel.setTextAlignment(Qt.AlignCenter); cel.setData(Qt.UserRole, its[0] if its else "")
                if t.tipo != "lectivo":
                    cel.setBackground(QColor("#ecebf3"))
                if (m.id, d, t.indice) in self.colores:
                    cel.setBackground(QColor(self.colores[(m.id, d, t.indice)]))
                if self.sel and self.sel in its:
                    cel.setForeground(QColor("#6c4fc9")); f = cel.font(); f.setBold(True); cel.setFont(f)
                self.rej.setItem(r, c, cel)
        self.rej.resizeRowsToContents()
        inf = ed.comprobar(); nfuera = len(ed.doc.get("no_colocadas", []))
        self.lbl_estado.setText(("✔ Horario correcto" if inf.valido else
                                 f"⚠ {len(inf.errores)} problemas: " + "; ".join(sorted(inf.cuentas)[:3]))
                                + (f" · {nfuera} sin colocar" if nfuera else ""))
        self.lst_fuera.clear()
        for i, nc in enumerate(ed.doc.get("no_colocadas", [])):
            it = QListWidgetItem(" · ".join(x for x in ed.descripcion_fuera(f"n:{i}")[:3] if x)); it.setData(Qt.UserRole, f"n:{i}")
            self.lst_fuera.addItem(it)

    # ---------------------------------------------------------------- semáforo
    def evaluar(self, item, pos):
        """(color, propuesta, motivos[]) de poner `item` en `pos`, según el comprobador:
        rojo = choque físico (profesor/grupo/aula) o regla estricta incumplida (errores del comprobador);
        ámbar = válido pero con avisos nuevos (preferencias «Mejor no», huecos…); verde = sin nada nuevo."""
        ed = self.ed
        prop = ed.proponer_agregar(item, *pos) if item.startswith("n:") else ed.proponer_mover(item, *pos)
        if prop.invalida:
            return T.COLOR_ROJO, prop, [T.explicar(prop.invalida)]
        if prop.mensajes:
            return T.COLOR_ROJO, prop, [T.explicar(m[0]) for m in prop.mensajes]
        from .. import comprobador as CK
        from collections import Counter
        if getattr(self, "_avisos_base", None) is None:
            self._avisos_base = Counter(tuple(a) for a in CK.comprobar(ed.p, ed.doc).avisos)
        nuevos = Counter(tuple(a) for a in CK.comprobar(ed.p, prop.doc).avisos) - self._avisos_base
        from ..editor_modelo import Motivo
        motivos = [T.explicar(Motivo(f"{a[0]}: {a[1]}" if len(a) > 1 else str(a[0]), "regla", categoria=a[0],
                                     detalle=a[1] if len(a) > 1 else "")) for a in nuevos.elements()]
        motivos += self._mejor_no(item, prop.doc)
        return (T.COLOR_AMBAR if motivos else T.COLOR_VERDE), prop, motivos

    def _mejor_no(self, item, doc):
        """Preferencias «Mejor no» de profesores, grupos y aulas en la nueva posición."""
        from ..xghc import leer_plantilla
        ed = self.ed; out = []
        listas = {"profesor": ed.p.profesores, "grupo": ed.p.grupos, "aula": ed.p.aulas}
        nombre_tipo = {"profesor": "el profesor", "grupo": "el grupo", "aula": "el aula"}
        for tp, nm in sorted(ed.recursos(item, doc)):
            e = next((x for x in listas[tp] if x.nombre == nm), None)
            x = e.datos.get("_xml") if e else None
            if x is None:
                continue
            for pos in ed.posiciones(item, doc):
                est = leer_plantilla(x, pos[0]).get(pos, "")
                if est.startswith("preferentementeNo"):
                    out.append(f"Es una hora marcada como «Mejor no» para {nombre_tipo[tp]} {nm}.")
                    break
        return out

    def seleccionar(self, item):
        """Calcula el color de cada celda del marco para `item` (lo que dice el comprobador)."""
        ed = self.ed; self.sel = item; self.destino = None; self.colores = {}; self._avisos_base = None
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            actuales = set(ed.posiciones(item)) if not item.startswith("n:") else set()
            for pos in self.pos.values():
                if pos in actuales or ed.tramos.get(pos) is None or ed.tramos[pos].tipo != "lectivo":
                    continue
                self.colores[pos] = self.evaluar(item, pos)[0]
        finally:
            QApplication.restoreOverrideCursor()
        self.por_que.setHtml(f"<p><b>{ed.descripcion(item)}</b> seleccionada.</p><p>Las horas en verde están libres; "
                             "en ámbar, se puede pero con avisos; en rojo, no se puede. Pulse una hora para ver por qué.</p>")
        for b in (self.b_mover, self.b_inter):
            b.setEnabled(False)
        self.b_recol.setEnabled(True); self.pintar()

    def limpiar_seleccion(self):
        self.sel = None; self.destino = None; self.colores = {}; self.prop = None
        for b in (self.b_mover, self.b_inter, self.b_recol):
            b.setEnabled(False)
        self.por_que.setHtml("<p>Pulse una clase del horario (o arrástrela) para ver a qué horas se puede mover.</p>")

    def _clic(self, r, c):
        it = self.rej.item(r, c); pos = self.pos.get((r, c))
        if self.sel and pos in self.colores:
            self.explicar(pos)
        elif it is not None and it.data(Qt.UserRole):
            self.seleccionar(it.data(Qt.UserRole))
        else:
            self.limpiar_seleccion(); self.pintar()

    def ocupantes(self, pos):
        ed = self.ed; vista = self.VISTAS[self.cb_vista.currentText()]
        return [it for it in ed.items_de(vista, self.cb_nombre.currentText()) if pos in ed.posiciones(it) and it != self.sel]

    def explicar(self, pos):
        ed = self.ed; color, prop, motivos = self.evaluar(self.sel, pos); self.destino = pos; self.prop = prop
        dia = T.DIAS[pos[1]]; hora = ed.tramos[pos].entrada
        tit = {T.COLOR_VERDE: "Se puede mover aquí sin problemas.", T.COLOR_AMBAR: "Se puede mover aquí, con estos avisos:",
               T.COLOR_ROJO: "No se puede poner aquí porque:"}[color]
        html = f"<p><b>{ed.descripcion(self.sel)}</b> → {dia} a las {hora}</p><p>{tit}</p>"
        if motivos:
            html += "<ul>" + "".join(f"<li>{m}</li>" for m in dict.fromkeys(motivos)) + "</ul>"
        occ = self.ocupantes(pos)
        if color == T.COLOR_ROJO:
            html += "<p>Puede <b>intercambiarla</b> con la clase que hay a esa hora o <b>dejar que el programa la recoloque</b> " \
                    "moviendo otras clases.</p>"
        self.por_que.setHtml(html)
        self.b_mover.setEnabled(color != T.COLOR_ROJO)
        self.b_inter.setEnabled(len(occ) == 1 and not self.sel.startswith("n:")); self.b_recol.setEnabled(True)
        return color, motivos

    # ---------------------------------------------------------------- acciones
    def soltar(self, r, c):
        pos = self.pos.get((r, c))
        if not self.sel or pos is None or pos not in self.colores:
            return None
        color, _m = self.explicar(pos)
        if color != T.COLOR_ROJO:
            self.mover()
        return color

    def mover(self):
        if not self.prop or self.prop.invalida:
            return False
        ed = self.ed; color = self.colores.get(self.destino)
        if color == T.COLOR_ROJO:
            return False                      # sin «Forzar»: nunca se coloca algo que no cabe
        ed.confirmar(self.prop, texto="mover"); self._hecho("Clase movida")
        return True

    def intercambiar(self):
        ed = self.ed; occ = self.ocupantes(self.destino) if self.destino else []
        if not self.sel or len(occ) != 1:
            return False
        a, b = self.sel, occ[0]
        pa, pb = min(ed.posiciones(a)), min(ed.posiciones(b))

        def fn(doc):
            from ..editor_modelo import ErrorEdicion
            oa, ob = ed.obj(a, doc), ed.obj(b, doc)
            for o, (m, d, i), it in ((oa, pb, a), (ob, pa, b)):
                if it[0] in "sr":
                    o["marco"], o["dia"], o["tramos"] = m, d, ed._cabe(m, d, i, len(o["tramos"]))
                else:
                    o.update(marco=m, dia=d, tramo=i)
            return [a, b]
        prop = ed._simular("Intercambiar", fn, None)
        if prop.invalida or prop.mensajes:
            motivos = [prop.invalida] if prop.invalida else [m[0] for m in prop.mensajes]
            self.por_que.setHtml("<p>No se pueden intercambiar porque:</p><ul>" +
                                 "".join(f"<li>{T.explicar(m)}</li>" for m in dict.fromkeys(motivos)) + "</ul>")
            return False
        ed.confirmar(prop, texto="intercambiar"); self._hecho("Clases intercambiadas")
        return True

    def recolocar(self, item=None, destino=None, limite=6.0):
        """Generación parcial: el programa busca dónde colocarla moviendo como mucho 3 clases."""
        ed = self.ed; item = item or self.sel; destino = destino if destino is not None else self.destino
        if not item:
            return False
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            sols = ed.recombinar(item, destino=destino, max_mov=3, max_sol=4, limite=limite)
        finally:
            QApplication.restoreOverrideCursor()
        sols = [s for s in sols if not s.get("errores")] or sols
        if not sols:
            self.por_que.setHtml("<p>El programa no ha encontrado forma de colocarla ahí moviendo como mucho 3 clases. "
                                 "Pruebe otra hora o vuelva a generar con más tiempo.</p>"); return False
        ed.aplicar_solucion(sols[0]); self._hecho(f"Recolocada (se han movido {len(sols[0].get('movs', []))} clases)")
        return True

    def colocar_fuera(self):
        it = self.lst_fuera.currentItem()
        return self.recolocar(it.data(Qt.UserRole), None) if it else False

    def _hecho(self, txt):
        self._avisos_base = None; self.limpiar_seleccion(); self.pintar(); self.v.estado(txt)

    def deshacer(self):
        if self.ed and self.ed.deshacer() is not None:
            self._hecho("Deshecho")

    def rehacer(self):
        if self.ed and self.ed.rehacer() is not None:
            self._hecho("Rehecho")

    def guardar(self):
        if self.ed:
            self.ed.guardar(); self.ed.modificado = False; self.v.estado("Cambios del horario guardados")
            return True
        return False

    def mas_opciones(self):
        self.v.abrir_editor_clasico()


# ---------------------------------------------------------------------------------------------- 9
class PasoInformes(Paso):
    clave = "informes"
    RAPIDOS = [("alumnos", "Horario por grupo"), ("profesores", "Horario por profesor"),
               ("aulas", "Horario por aula"), ("guardias", "Guardias")]

    def __init__(self, v):
        super().__init__(v)
        f, c = tarjeta(); self.lay.addWidget(f)
        c.addWidget(lbl("<b>Imprimir (PDF)</b>"))
        h = QHBoxLayout(); c.addLayout(h)
        for tipo, t in self.RAPIDOS:
            h.addWidget(btn(t, lambda tp=tipo: self.informe(tp)))
        h.addStretch(1)
        f2, c2 = tarjeta(); self.lay.addWidget(f2)
        c2.addWidget(lbl("<b>Delphos</b>: genera el archivo para importar el horario en Delphos."))
        c2.addLayout(fila_botones(btn("Enviar a Delphos…", lambda: self.delphos()), None))
        self.lbl = lbl(""); self.lay.addWidget(self.lbl); self.lay.addStretch(1)

    def cargar(self):
        self.lbl.setText("" if self.v.editor else "Todavía no hay horario: vaya al paso «Generar».")

    def informe(self, tipo, ruta=None):
        from .. import informes as I
        ed = self.v.editor
        if not ed:
            QMessageBox.information(self, APP_NAME, "Primero genere el horario."); return None
        nombre = dict(self.RAPIDOS)[tipo]
        if ruta is None:
            sug = os.path.join(os.path.dirname(ed.ruta), f"{nombre}.pdf")
            ruta, _ = QFileDialog.getSaveFileName(self, nombre, sug, "PDF (*.pdf)")
            if not ruta:
                return None
        st = QSettings(VENDOR, AJUSTES)
        base = {"tipo": tipo}
        if st.value("sencilla/centro", ""):
            base["centro"] = st.value("sencilla/centro")
        if st.value("sencilla/localidad", ""):
            base["localidad"] = st.value("sencilla/localidad")
        o = I.opciones(ed.doc, base)
        tablas = I.tablas_de(ed, tipo, o)
        I.exportar_pdf(tablas, ruta, o, [ed.ruta_xghc, ed.ruta])
        self.lbl.setText(f"PDF creado: {ruta}"); self.v.estado(f"{nombre}: {os.path.basename(ruta)}")
        return ruta

    def delphos(self, operar=None):
        from ..editor_delphos import AsistenteDelphos
        ed = self.v.editor
        if not ed:
            QMessageBox.information(self, APP_NAME, "Primero genere el horario."); return None
        self.asis = AsistenteDelphos(self, ed, None)
        r = self.asis.ejecutar(operar)
        if r:
            self.lbl.setText(f"Archivo para Delphos: {r}")
        return r

    def mas_opciones(self):
        self.v.abrir_editor_clasico()
