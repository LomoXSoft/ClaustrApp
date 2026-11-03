"""Pasos 1–6 de la versión sencilla: datos del centro (sobre el núcleo Planificador)."""
from PySide6.QtCore import Qt, QTime, QSettings
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit, QSpinBox,
                               QTimeEdit, QCheckBox, QComboBox, QTableWidgetItem, QInputDialog, QMessageBox,
                               QApplication, QRadioButton, QButtonGroup, QAbstractItemView, QSplitter, QDialog)
from .. import APP_NAME, VENDOR, AJUSTES
from .. import edicion as ED, periodos as PER, nolectivas as NL, pegar as PG
from ..xghc import leer_plantilla
from . import textos as T
from .comun import lbl, btn, tarjeta, tabla, fila_botones, horas_de, ElegirProfesores

AULA_GRUPO = "Aula del grupo"
PREF_TIPO = "Tipo: "


class Paso(QWidget):
    clave = ""

    def __init__(self, v):
        super().__init__(); self.v = v
        self.lay = QVBoxLayout(self); self.lay.setContentsMargins(24, 18, 24, 12); self.lay.setSpacing(10)
        _c, tit, ayuda = next(p for p in T.PASOS if p[0] == self.clave)
        self.lay.addWidget(lbl(tit, "titulo")); self.lay.addWidget(lbl(ayuda, "ayuda"))
        self._cargando = False

    @property
    def p(self):
        return self.v.p

    def cargar(self):
        pass

    def mas_opciones(self):
        pass

    def preguntar_texto(self, titulo, etiqueta, valor=""):
        t, ok = QInputDialog.getText(self, titulo, etiqueta, text=valor)
        return t.strip() if ok else None


# ---------------------------------------------------------------------------------------------- 1
class PasoCentro(Paso):
    clave = "centro"

    def __init__(self, v):
        super().__init__(v)
        f, c = tarjeta(); self.lay.addWidget(f)
        g = QGridLayout(); c.addLayout(g)
        self.ed_centro = QLineEdit(); self.ed_localidad = QLineEdit()
        g.addWidget(QLabel("Nombre del centro:"), 0, 0); g.addWidget(self.ed_centro, 0, 1, 1, 3)
        g.addWidget(QLabel("Localidad:"), 1, 0); g.addWidget(self.ed_localidad, 1, 1, 1, 3)
        self.ed_centro.editingFinished.connect(self._guardar_centro); self.ed_localidad.editingFinished.connect(self._guardar_centro)
        f2, c2 = tarjeta(); self.lay.addWidget(f2)
        c2.addWidget(lbl("<b>Horario de clases</b> (igual todos los días; para horarios distintos cada día use «Más opciones…»)"))
        g2 = QGridLayout(); c2.addLayout(g2)
        self.dias = []
        hd = QHBoxLayout()
        for i, d in enumerate(T.DIAS[:6]):
            cb = QCheckBox(d); cb.setChecked(i < 5); self.dias.append(cb); hd.addWidget(cb)
        hd.addStretch(1)
        g2.addWidget(QLabel("Días lectivos:"), 0, 0); g2.addLayout(hd, 0, 1, 1, 3)
        self.t_inicio = QTimeEdit(QTime(8, 30)); self.t_inicio.setDisplayFormat("HH:mm")
        self.sp_dur = QSpinBox(); self.sp_dur.setRange(30, 120); self.sp_dur.setValue(55); self.sp_dur.setSuffix(" min")
        self.sp_n = QSpinBox(); self.sp_n.setRange(1, 12); self.sp_n.setValue(6)
        self.sp_rec = QSpinBox(); self.sp_rec.setRange(0, 11); self.sp_rec.setValue(3); self.sp_rec.setSpecialValueText("sin recreo")
        self.sp_rdur = QSpinBox(); self.sp_rdur.setRange(5, 60); self.sp_rdur.setValue(30); self.sp_rdur.setSuffix(" min")
        for r, (t, w) in enumerate((("Primera clase empieza a las:", self.t_inicio), ("Cada clase dura:", self.sp_dur),
                                    ("Clases al día:", self.sp_n), ("Recreo después de la clase nº:", self.sp_rec),
                                    ("El recreo dura:", self.sp_rdur)), start=1):
            g2.addWidget(QLabel(t), r, 0); g2.addWidget(w, r, 1)
        self.vista = tabla(["Periodo", "Entrada", "Salida"], 0); self.vista.setMaximumHeight(300)
        self.vista.setEditTriggers(QAbstractItemView.NoEditTriggers)
        g2.addWidget(self.vista, 1, 2, 6, 2)
        for w in (self.t_inicio,):
            w.timeChanged.connect(lambda *_: self._previa())
        for w in (self.sp_dur, self.sp_n, self.sp_rec, self.sp_rdur):
            w.valueChanged.connect(lambda *_: self._previa())
        c2.addLayout(fila_botones(None, btn("Aplicar este horario", self.aplicar, primario=True)))
        self.lay.addStretch(1)

    def _guardar_centro(self):
        st = QSettings(VENDOR, AJUSTES)
        st.setValue("sencilla/centro", self.ed_centro.text().strip()); st.setValue("sencilla/localidad", self.ed_localidad.text().strip())

    def cargar(self):
        st = QSettings(VENDOR, AJUSTES)
        self.ed_centro.setText(st.value("sencilla/centro", "") or ""); self.ed_localidad.setText(st.value("sencilla/localidad", "") or "")
        p = self.p
        if p and p.marcos:
            m = next(iter(p.marcos.values()))
            dias = set(m.dias)
            for i, cb in enumerate(self.dias):
                cb.setChecked(i in dias)
            fil = m.filas()
            lect = [t for t in fil if t.tipo == "lectivo"]
            if lect:
                hh, mm = (int(x) for x in lect[0].entrada.split(":")[:2]); self.t_inicio.setTime(QTime(hh, mm))
                self.sp_dur.setValue(max(30, min(120, PER._min(lect[0].salida) - PER._min(lect[0].entrada))))
                self.sp_n.setValue(len(lect))
                rec = [i for i, t in enumerate(fil) if t.tipo != "lectivo"]
                if rec:
                    self.sp_rec.setValue(sum(1 for t in fil[:rec[0]] if t.tipo == "lectivo"))
                    self.sp_rdur.setValue(max(5, min(60, PER._min(fil[rec[0]].salida) - PER._min(fil[rec[0]].entrada))))
                else:
                    self.sp_rec.setValue(0)
        self._previa()

    def tramos(self):
        """[(entrada, salida, tipo)] de un día según los controles."""
        t = self.t_inicio.time(); m = t.hour() * 60 + t.minute(); out = []
        hm = lambda x: f"{x // 60:02d}:{x % 60:02d}"
        for i in range(self.sp_n.value()):
            out.append((hm(m), hm(m + self.sp_dur.value()), "lectivo")); m += self.sp_dur.value()
            if self.sp_rec.value() and i + 1 == self.sp_rec.value() and i + 1 < self.sp_n.value():
                out.append((hm(m), hm(m + self.sp_rdur.value()), "recreo")); m += self.sp_rdur.value()
        return out

    def _previa(self):
        tr = self.tramos(); self.vista.setRowCount(len(tr)); n = 0
        for r, (a, b, tp) in enumerate(tr):
            n += tp == "lectivo"
            for c, x in enumerate((f"{n}ª clase" if tp == "lectivo" else "Recreo", a, b)):
                it = QTableWidgetItem(x)
                if tp != "lectivo":
                    it.setBackground(QColor("#ecebf3"))
                self.vista.setItem(r, c, it)

    def configurar(self, dias=None, inicio=None, duracion=None, clases=None, recreo_tras=None, recreo_dur=None):
        if dias is not None:
            for i, cb in enumerate(self.dias):
                cb.setChecked(i in dias)
        if inicio:
            h, m = (int(x) for x in inicio.split(":")); self.t_inicio.setTime(QTime(h, m))
        for w, x in ((self.sp_dur, duracion), (self.sp_n, clases), (self.sp_rec, recreo_tras), (self.sp_rdur, recreo_dur)):
            if x is not None:
                w.setValue(x)

    def aplicar(self):
        p = self.p
        if p is None:
            return False
        dias = [i for i, cb in enumerate(self.dias) if cb.isChecked()]
        if not dias:
            QMessageBox.information(self, APP_NAME, "Marque al menos un día lectivo."); return False
        mid = next(iter(p.marcos)) if p.marcos else "A"
        actuales = {}
        for t in (p.marcos[mid].tramos if mid in p.marcos else []):
            actuales.setdefault(t.dia, []).append(t)
        fs = [f for f in PER.filas(p) if f["marco"] != mid]
        for d in dias:
            prev = sorted(actuales.get(d, []), key=lambda t: t.indice)
            for j, (a, b, tp) in enumerate(self.tramos()):
                fs.append({"marco": mid, "dia": d, "entrada": a, "salida": b, "tipo": tp, "clave": "", "activo": True,
                           "orig": (mid, d, prev[j].indice) if j < len(prev) else None})
        ok = self.v.editar(lambda arbol: PER.aplicar(p, fs, ED, arbol), "horario de clases")
        self._guardar_centro(); self.v.estado("Horario de clases aplicado")
        return ok

    def mas_opciones(self):
        self.v.nucleo.periodos_marco(); self.v.refrescar()


# ---------------------------------------------------------------------------------------------- listas
class ListaSimple(QWidget):
    """Tabla editable de una lista del archivo (profesores, grupos, materias, aulas) con añadir/quitar/pegar."""
    def __init__(self, paso, lista, columnas, titulo_nuevo, extra=()):
        super().__init__(); self.paso, self.lista, self.columnas = paso, lista, columnas
        v = QVBoxLayout(self); v.setContentsMargins(0, 0, 0, 0)
        self.t = tabla([c[0] for c in columnas] + ["Horas de clase"] * (lista in ("profesores", "grupos")), 0)
        self.t.itemChanged.connect(self._cambiado); v.addWidget(self.t)
        self.titulo_nuevo = titulo_nuevo
        bs = [btn("Añadir…", self.anadir), btn("Quitar", self.quitar)]
        if lista in PG.LISTAS:
            bs.append(btn("Pegar desde hoja de cálculo", self.pegar))
        v.addLayout(fila_botones(*bs, *extra, None))
        self._cargando = False

    @property
    def v(self):
        return self.paso.v

    def elementos(self):
        p = self.v.p
        return getattr(p, self.lista) if p else []

    def cargar(self):
        self._cargando = True
        p = self.v.p; els = self.elementos(); self.t.setRowCount(len(els))
        horas = {}
        if p and self.lista in ("profesores", "grupos"):
            campo = "profesor" if self.lista == "profesores" else "grupo"
            for s in p.sesiones:
                horas[getattr(s, campo)] = horas.get(getattr(s, campo), 0) + horas_de(s.tmp)
        for r, e in enumerate(els):
            for c, (_t, campo) in enumerate(self.columnas):
                it = QTableWidgetItem(e.nombre if campo == "nombre" else str(e.datos.get(campo) or ""))
                it.setData(Qt.UserRole, e.nombre); self.t.setItem(r, c, it)
            if self.lista in ("profesores", "grupos"):
                it = QTableWidgetItem(str(horas.get(e.nombre, 0))); it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                self.t.setItem(r, len(self.columnas), it)
        self._cargando = False

    def _xml(self, nombre):
        e = next((e for e in self.elementos() if e.nombre == nombre), None)
        return e.datos.get("_xml") if e else None

    def _cambiado(self, it):
        if self._cargando or it.column() >= len(self.columnas):
            return
        nombre = it.data(Qt.UserRole); campo = self.columnas[it.column()][1]; valor = it.text().strip()[:30]
        x = self._xml(nombre)
        if x is None:
            return
        self.fijar(nombre, campo, valor)

    def fijar(self, nombre, campo, valor):
        x = self._xml(nombre); p = self.v.p
        if campo == "nombre":
            if not valor or valor in ED.nombres(p.doc.raiz, self.lista):
                self.v.refrescar(); return False
            return self.v.editar(lambda a: ED.renombrar(a, self.lista, x, valor), "cambiar nombre")

        def fn(a):
            if valor and campo in PG.AUX and valor not in ED.nombres(a.raiz, PG.AUX[campo]):
                ED.insertar_elemento(a, PG.AUX[campo], valor)
            return ED.escribir(a, x, campo, valor)
        return self.v.editar(fn, f"cambiar {campo}")

    def anadir(self, nombre=None):
        if nombre is None:
            nombre = self.paso.preguntar_texto(self.titulo_nuevo, "Nombre (identificativo corto):")
        if not nombre:
            return False
        nombre = nombre[:30]
        if nombre in ED.nombres(self.v.p.doc.raiz, self.lista):
            QMessageBox.information(self, APP_NAME, f"Ya existe «{nombre}»."); return False
        return self.v.editar(lambda a: ED.insertar_elemento(a, self.lista, nombre) is not None, f"añadir {nombre}")

    def seleccionados(self):
        filas = sorted({i.row() for i in self.t.selectedIndexes()})
        return [self.t.item(r, 0).data(Qt.UserRole) for r in filas if self.t.item(r, 0)]

    def quitar(self, nombres=None):
        nombres = nombres if nombres is not None else self.seleccionados()
        if not nombres:
            return False
        if QMessageBox.question(self, APP_NAME, f"¿Quitar {', '.join(nombres)}?") != QMessageBox.Yes:
            return False
        xs = [self._xml(n) for n in nombres]
        return self.v.editar(lambda a: [ED.eliminar_elemento(a, self.lista, x) for x in xs if x is not None] or True, "quitar")

    def pegar(self, texto=None):
        if texto is None:
            texto = QApplication.clipboard().text()
        filas = PG.filas_de_texto(texto)
        if not filas:
            QMessageBox.information(self, APP_NAME, "Copie primero las filas en la hoja de cálculo (Ctrl+C).\n"
                                    "Columnas: " + " · ".join(c[0] for c in self.columnas)); return None
        res = {}
        self.v.editar(lambda a: res.update(PG.aplicar(a, self.lista, filas)) or bool(res["nuevos"] or res["actualizados"]), "pegar")
        self.v.estado(f"Pegado: {res.get('nuevos', 0)} nuevos, {res.get('actualizados', 0)} actualizados")
        return res

    def mas_opciones(self):
        sel = self.seleccionados()
        self.v.propiedades_clasicas(self.lista, sel[0] if sel else None)


class PasoProfesorado(Paso):
    clave = "profesorado"

    def __init__(self, v):
        super().__init__(v)
        self.lista = ListaSimple(self, "profesores", [("Nombre", "nombre"), ("Nombre completo", "nombreCompleto"),
                                                     ("Departamento", "departamento")], "Nuevo profesor",
                                 extra=[btn("Importar de Delphos…", lambda: self.v.importar_delphos())])
        self.lay.addWidget(self.lista)

    def cargar(self):
        self.lista.cargar()

    def mas_opciones(self):
        self.lista.mas_opciones()


class PasoGrupos(Paso):
    clave = "grupos"

    def __init__(self, v):
        super().__init__(v)
        sp = QSplitter(Qt.Vertical); self.lay.addWidget(sp, 1)
        w1 = QWidget(); l1 = QVBoxLayout(w1); l1.setContentsMargins(0, 0, 0, 0); l1.addWidget(lbl("<b>Grupos de alumnos</b>"))
        self.lista = ListaSimple(self, "grupos", [("Nombre", "nombre"), ("Curso", "cursoPerteneciente"), ("Su aula", "aula")],
                                 "Nuevo grupo", extra=[btn("Crear varios…", lambda: self.crear_varios())])
        l1.addWidget(self.lista); sp.addWidget(w1)
        w2 = QWidget(); l2 = QVBoxLayout(w2); l2.setContentsMargins(0, 0, 0, 0)
        l2.addWidget(lbl("<b>Aulas</b> (las aulas específicas: laboratorios, gimnasio…; las de grupo se crean solas)"))
        self.aulas = ListaSimple(self, "aulas", [("Nombre", "nombre"), ("Descripción", "descripcion")], "Nueva aula")
        l2.addWidget(self.aulas); sp.addWidget(w2)

    def cargar(self):
        self.lista.cargar(); self.aulas.cargar()

    def crear_varios(self, curso=None, letras=None):
        if curso is None:
            curso = self.preguntar_texto("Crear varios grupos", "Curso (p. ej. «1ESO»):")
            if not curso:
                return False
            letras = self.preguntar_texto("Crear varios grupos", "Letras de los grupos:", "A B C")
        letras = [x for x in (letras or "").replace(",", " ").split() if x]
        if not curso or not letras:
            return False
        filas = [[f"{curso} {l}", curso, f"Aula {curso} {l}"] for l in letras]
        res = {}
        self.v.editar(lambda a: res.update(PG.aplicar(a, "grupos", filas)) or bool(res["nuevos"]), "crear grupos")
        return res.get("nuevos", 0)

    def mas_opciones(self):
        self.lista.mas_opciones()


# ---------------------------------------------------------------------------------------------- 4
class PasoMaterias(Paso):
    clave = "materias"
    COLS = ["Materia", "Profesor", "Horas/semana", "¿Dónde?"]

    def __init__(self, v):
        super().__init__(v)
        sp = QSplitter(Qt.Horizontal); self.lay.addWidget(sp, 1)
        w1 = QWidget(); l1 = QVBoxLayout(w1); l1.setContentsMargins(0, 0, 0, 0); l1.addWidget(lbl("<b>Materias del centro</b>"))
        self.materias = ListaSimple(self, "materias", [("Nombre", "nombre"), ("Nombre completo", "nombreCompleto")], "Nueva materia")
        l1.addWidget(self.materias); sp.addWidget(w1)
        w2 = QWidget(); l2 = QVBoxLayout(w2); l2.setContentsMargins(0, 0, 0, 0)
        h = QHBoxLayout(); h.addWidget(lbl("<b>Grupo:</b>", envolver=False)); self.cb_grupo = QComboBox(); h.addWidget(self.cb_grupo, 1)
        l2.addLayout(h)
        self.cb_grupo.currentTextChanged.connect(lambda *_: self.cargar_grupo())
        self.t = tabla(self.COLS, 0); self.t.setEditTriggers(QAbstractItemView.NoEditTriggers); l2.addWidget(self.t)
        for col, ancho in ((1, 130), (2, 100), (3, 210)):
            self.t.setColumnWidth(col, ancho)
        l2.addLayout(fila_botones(btn("Añadir materia al grupo", lambda: self.anadir()), btn("Quitar", lambda: self.quitar()),
                                  btn("Copiar a otro grupo…", lambda: self.copiar_a()), None))
        sp.addWidget(w2); sp.setSizes([330, 700])

    def cargar(self):
        self.materias.cargar()
        p = self.p; actual = self.cb_grupo.currentText()
        self.cb_grupo.blockSignals(True); self.cb_grupo.clear()
        if p:
            self.cb_grupo.addItems([g.nombre for g in p.grupos])
            if actual:
                self.cb_grupo.setCurrentText(actual)
        self.cb_grupo.blockSignals(False)
        self.cargar_grupo()

    def sesiones(self, grupo=None):
        p = self.p; g = grupo or self.cb_grupo.currentText()
        return [s for s in p.sesiones if s.grupo == g] if p else []

    @staticmethod
    def donde(s):
        if s.aulas:
            return s.aulas[0]
        if s.alternativas:
            return PREF_TIPO + s.alternativas[0]
        return AULA_GRUPO

    def opciones_donde(self):
        p = self.p
        return [AULA_GRUPO] + [a.nombre for a in p.aulas] + [PREF_TIPO + c for c in p.conjuntos_aulas]

    def cargar_grupo(self):
        ss = self.sesiones(); p = self.p
        self.t.setRowCount(len(ss))
        for r, s in enumerate(ss):
            for c, (campo, opts, val) in enumerate((("materia", [m.nombre for m in p.materias], s.materia),
                                                    ("profesor", [""] + [x.nombre for x in p.profesores], s.profesor))):
                cb = QComboBox(); cb.addItems(opts)
                if val not in opts:
                    cb.addItem(val)
                cb.setCurrentText(val)
                cb.currentTextChanged.connect(lambda t, sid=s.id, cp=campo: self.fijar(sid, cp, t))
                self.t.setCellWidget(r, c, cb)
            spn = QSpinBox(); spn.setRange(1, 15); spn.setValue(max(1, horas_de(s.tmp)))
            spn.valueChanged.connect(lambda n, sid=s.id: self.fijar(sid, "horas", n)); self.t.setCellWidget(r, 2, spn)
            cb = QComboBox(); cb.addItems(self.opciones_donde()); cb.setCurrentText(self.donde(s))
            cb.currentTextChanged.connect(lambda t, sid=s.id: self.fijar(sid, "donde", t)); self.t.setCellWidget(r, 3, cb)
            self.t.setItem(r, 0, QTableWidgetItem()); self.t.item(r, 0).setData(Qt.UserRole, s.id)

    def _ses(self, sid):
        return next((s for s in self.p.sesiones if s.id == sid), None)

    def fijar(self, sid, campo, valor):
        s = self._ses(sid)
        if s is None:
            return False
        x = s.xml
        if campo in ("materia", "profesor"):
            return self.v.editar(lambda a: ED.set_campo_sesion(a, x, campo, valor), f"cambiar {campo}")
        if campo == "horas":
            n = int(valor)
            if horas_de(s.tmp) == n:
                return False
            # reparto sencillo: n sesiones de 1 hora (las distribuciones avanzadas se editan en «Más opciones…»)
            return self.v.editar(lambda a: ED.set_campo_sesion(a, x, "tmp", "1" * min(n, 9) if n <= 9 else "2" * (n // 2) + "1" * (n % 2)),
                                 "horas semanales")
        if campo == "donde":
            if valor == AULA_GRUPO:
                aula, conj = "", ""
            elif valor.startswith(PREF_TIPO):
                aula, conj = "", valor[len(PREF_TIPO):]
            else:
                aula, conj = valor, ""
            return self.v.editar(lambda a: bool(ED.set_campo_sesion(a, x, "aula", aula)) | bool(ED.set_campo_sesion(a, x, "conjunto", conj)),
                                 "cambiar dónde")
        raise KeyError(campo)

    def anadir(self, materia=None, profesor="", horas=None, donde=None, grupo=None):
        p = self.p; g = grupo or self.cb_grupo.currentText()
        if not g:
            QMessageBox.information(self, APP_NAME, "Cree antes algún grupo."); return None
        if materia is None:
            mats = [m.nombre for m in p.materias]
            if not mats:
                QMessageBox.information(self, APP_NAME, "Añada antes las materias del centro (lista de la izquierda)."); return None
            materia, ok = QInputDialog.getItem(self, "Añadir materia", f"Materia para {g}:", mats, 0, False)
            if not ok:
                return None
        nuevo = []
        tarea = p.tareas[0].nombre if p.tareas else "LEC"

        def fn(a):
            if materia not in ED.nombres(a.raiz, "materias"):
                ED.insertar_elemento(a, "materias", materia)
            s = ED.insertar_sesion(a, None, materia, g, profesor, tarea)
            if horas and horas > 1:
                ED.set_campo_sesion(a, s, "tmp", "1" * min(horas, 9))
            if donde and donde != AULA_GRUPO:
                if donde.startswith(PREF_TIPO):
                    ED.set_campo_sesion(a, s, "conjunto", donde[len(PREF_TIPO):])
                else:
                    ED.set_campo_sesion(a, s, "aula", donde)
            nuevo.append(s); return True
        self.v.editar(fn, "añadir materia al grupo")
        return nuevo[0] if nuevo else None

    def quitar(self, sids=None):
        if sids is None:
            filas = sorted({i.row() for i in self.t.selectedIndexes()})
            sids = [self.t.item(r, 0).data(Qt.UserRole) for r in filas if self.t.item(r, 0)]
        xs = [s.xml for s in self.p.sesiones if s.id in sids]
        if not xs:
            return False
        return self.v.editar(lambda a: [ED.quitar_hijo(a, a.padre[x], x) for x in xs] or True, "quitar materia del grupo")

    def copiar_a(self, destino=None):
        g = self.cb_grupo.currentText()
        if destino is None:
            otros = [x.nombre for x in self.p.grupos if x.nombre != g]
            if not otros:
                return 0
            destino, ok = QInputDialog.getItem(self, "Copiar materias", f"Copiar las materias de {g} (sin profesor) a:", otros, 0, False)
            if not ok:
                return 0
        ss = self.sesiones(g); tarea_def = self.p.tareas[0].nombre if self.p.tareas else "LEC"
        datos = [(s.materia, s.tmp, s.aulas[:1], s.alternativas[:1], s.tarea or tarea_def) for s in ss]

        def fn(a):
            for m, tmp, au, al, ta in datos:
                s = ED.insertar_sesion(a, None, m, destino, "", ta)
                ED.set_campo_sesion(a, s, "tmp", tmp or "1")
                if al:
                    ED.set_campo_sesion(a, s, "conjunto", al[0])
            return bool(datos)
        self.v.editar(fn, "copiar materias")
        return len(datos)

    def mas_opciones(self):
        filas = sorted({i.row() for i in self.t.selectedIndexes()})
        sid = self.t.item(filas[0], 0).data(Qt.UserRole) if filas and self.t.item(filas[0], 0) else None
        self.v.propiedades_clasicas("sesiones", sid)


# ---------------------------------------------------------------------------------------------- 5
class PasoPreferencias(Paso):
    clave = "preferencias"
    LISTAS = {"Profesorado": "profesores", "Grupos": "grupos", "Aulas": "aulas"}

    def __init__(self, v):
        super().__init__(v)
        h = QHBoxLayout(); self.lay.addLayout(h)
        self.cb_tipo = QComboBox(); self.cb_tipo.addItems(list(self.LISTAS)); self.cb_nombre = QComboBox()
        h.addWidget(QLabel("Ver:")); h.addWidget(self.cb_tipo); h.addWidget(self.cb_nombre, 1)
        self.cb_tipo.currentTextChanged.connect(lambda *_: self._nombres())
        self.cb_nombre.currentTextChanged.connect(lambda *_: self.cargar_rejilla())
        hb = QHBoxLayout(); self.lay.addLayout(hb); hb.addWidget(QLabel("Pincel:"))
        self.grupo_pincel = QButtonGroup(self); self.pinceles = {}
        for k, t, col in T.ESTADOS:
            rb = QRadioButton(t); rb.setStyleSheet(f"QRadioButton{{background:{col};padding:4px 8px;border-radius:5px}}")
            self.grupo_pincel.addButton(rb); self.pinceles[k] = rb; hb.addWidget(rb)
        self.pinceles["prohibido"].setChecked(True); hb.addStretch(1)
        self.lay.addWidget(lbl("Pulse o arrastre sobre las horas para pintarlas. Los pesos de «Prefiere» y «Mejor no» "
                               "se ajustan en «Más opciones…».", "ayuda"))
        self.t = tabla([], 0); self.t.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.t.setSelectionBehavior(QAbstractItemView.SelectItems); self.t.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.t.verticalHeader().setVisible(True); self.lay.addWidget(self.t, 1)
        self.t.itemSelectionChanged.connect(self._pintar_seleccion)
        self._celdas = {}

    def cargar(self):
        self._nombres()

    def _nombres(self):
        p = self.p; actual = self.cb_nombre.currentText()
        self.cb_nombre.blockSignals(True); self.cb_nombre.clear()
        if p:
            self.cb_nombre.addItems([e.nombre for e in getattr(p, self.LISTAS[self.cb_tipo.currentText()])])
            if actual:
                self.cb_nombre.setCurrentText(actual)
        self.cb_nombre.blockSignals(False); self.cargar_rejilla()

    def _owner(self):
        p = self.p
        lst = getattr(p, self.LISTAS[self.cb_tipo.currentText()]) if p else []
        e = next((e for e in lst if e.nombre == self.cb_nombre.currentText()), None)
        return e.datos.get("_xml") if e else None

    def _marco(self):
        return next(iter(self.p.marcos)) if self.p and self.p.marcos else "A"

    def plantilla(self):
        x = self._owner()
        return leer_plantilla(x, self._marco()) if x is not None else {}

    def cargar_rejilla(self):
        p = self.p; self._celdas = {}
        self.t.blockSignals(True); self.t.clear()
        if not p or not p.marcos or self._owner() is None:
            self.t.setRowCount(0); self.t.setColumnCount(0); self.t.blockSignals(False); return
        m = p.marcos[self._marco()]; fil = [t for t in m.filas() if t.tipo == "lectivo"]; dias = m.dias
        self.t.setColumnCount(len(dias)); self.t.setRowCount(len(fil))
        self.t.setHorizontalHeaderLabels([T.DIAS[d] for d in dias])
        self.t.setVerticalHeaderLabels([f"{t.entrada}-{t.salida}" for t in fil])
        pl = self.plantilla()
        for r, t in enumerate(fil):
            for c, d in enumerate(dias):
                k = (m.id, d, t.indice); est = T.EQUIVALENTE.get(pl.get(k, ""), pl.get(k, ""))
                it = QTableWidgetItem(T.TEXTO_ESTADO.get(est, "")); it.setTextAlignment(Qt.AlignCenter)
                it.setBackground(QColor(T.COLOR_ESTADO.get(est, "#ffffff"))); self.t.setItem(r, c, it)
                self._celdas[(r, c)] = k
        self.t.blockSignals(False)

    def pincel(self):
        return next(k for k, rb in self.pinceles.items() if rb.isChecked())

    def pintar(self, claves, estado=None):
        """Pinta las posiciones (marco, dia, indice) con el estado; conserva los estados avanzados no tocados."""
        estado = self.pincel() if estado is None else estado
        x = self._owner()
        if x is None or not claves:
            return False
        pl = dict(self.plantilla())
        for k in claves:
            if estado:
                pl[k] = estado
            else:
                pl.pop(k, None)
        ok = self.v.editar(lambda a: ED.volcar_plantilla(a, x, pl, self._marco()), "preferencias")
        return ok

    def _pintar_seleccion(self):
        sel = [self._celdas[(i.row(), i.column())] for i in self.t.selectedIndexes() if (i.row(), i.column()) in self._celdas]
        if sel and QApplication.mouseButtons() == Qt.NoButton:
            self.t.blockSignals(True); self.t.clearSelection(); self.t.blockSignals(False)
            self.pintar(sel)

    def mas_opciones(self):
        self.v.nucleo.criterios_ponderables(); self.v.refrescar()


# ---------------------------------------------------------------------------------------------- 6
class PasoGuardias(Paso):
    clave = "guardias"

    def __init__(self, v):
        super().__init__(v)
        f, c = tarjeta(); self.lay.addWidget(f, 1)
        c.addWidget(lbl("<b>Guardias</b>"))
        self.tg = tabla(["Servicio", "En recreos", "Profesores a cada hora", "Profesores (horas)"], 3)
        self.tg.setEditTriggers(QAbstractItemView.NoEditTriggers); c.addWidget(self.tg)
        c.addLayout(fila_botones(btn("Nuevo servicio…", lambda: self.nueva_guardia()),
                                 btn("Elegir profesores…", lambda: self.profesores_guardia()),
                                 btn("Quitar", lambda: self.quitar("guardias")), None))
        f2, c2 = tarjeta(); self.lay.addWidget(f2, 1)
        c2.addWidget(lbl("<b>Reuniones</b>"))
        self.tr = tabla(["Reunión", "Por semana", "Integrantes"], 2)
        self.tr.setEditTriggers(QAbstractItemView.NoEditTriggers); c2.addWidget(self.tr)
        c2.addLayout(fila_botones(btn("Nueva reunión…", lambda: self.nueva_reunion()),
                                  btn("Una por departamento", lambda: self.reuniones_auto("departamento")),
                                  btn("Una por equipo docente", lambda: self.reuniones_auto("equipo")),
                                  btn("Quitar", lambda: self.quitar("reuniones")), None))
        self.lay.addWidget(lbl("Las actividades complementarias y otras tareas no lectivas se definen en «Más opciones…».", "ayuda"))

    def cargar(self):
        p = self.p
        gs = p.guardias if p else []; self.tg.setRowCount(len(gs))
        for r, g in enumerate(gs):
            x = g.datos.get("_xml")
            ints = []
            for ix in (x.findall("integrantes/integrante") if x is not None else []):
                n = (ix.findtext("nombre") if len(ix) else ix.text) or ""
                k = ix.findtext("numeroDeGuardias") or ix.findtext("guardias") or ""
                ints.append(f"{n.strip()} ({k.strip()})" if k.strip() else n.strip())
            vals = [g.nombre, "Sí" if (x is not None and x.findtext("enRecreos") == "true") else "No",
                    (x.findtext("profesoresACadaHora/cantidad") if x is not None else "") or "", ", ".join(ints)]
            for cidx, val in enumerate(vals):
                it = QTableWidgetItem(val); it.setData(Qt.UserRole, g.nombre); self.tg.setItem(r, cidx, it)
        rs = p.reuniones if p else []; self.tr.setRowCount(len(rs))
        for r, g in enumerate(rs):
            x = g.datos.get("_xml")
            vals = [g.nombre, (x.findtext("numeroDeReuniones") if x is not None else "") or "1", ", ".join(NL.integrantes(x)) if x is not None else ""]
            for cidx, val in enumerate(vals):
                it = QTableWidgetItem(val); it.setData(Qt.UserRole, g.nombre); self.tr.setItem(r, cidx, it)

    def _xml(self, lista, nombre):
        e = next((e for e in getattr(self.p, lista) if e.nombre == nombre), None)
        return e.datos.get("_xml") if e else None

    def _sel(self, t):
        filas = sorted({i.row() for i in t.selectedIndexes()})
        return [t.item(r, 0).data(Qt.UserRole) for r in filas if t.item(r, 0)]

    def nueva_guardia(self, nombre=None, recreo=False, cantidad=1):
        if nombre is None:
            nombre = self.preguntar_texto("Nuevo servicio de guardias", "Nombre del servicio:", "Guardia")
        if not nombre:
            return None
        nuevo = []
        self.v.editar(lambda a: nuevo.append(NL.nueva_guardia(a, nombre, recreo=recreo, cantidad=cantidad)) or True, "nuevo servicio de guardias")
        return nuevo[0].findtext("nombre") if nuevo else None

    def profesores_guardia(self, servicio=None, profesores=None, horas=1):
        sel = self._sel(self.tg)
        servicio = servicio or (sel[0] if sel else (self.p.guardias[0].nombre if self.p.guardias else None))
        if not servicio:
            QMessageBox.information(self, APP_NAME, "Cree antes un servicio de guardias."); return False
        x = self._xml("guardias", servicio)
        if profesores is None:
            d = ElegirProfesores(self, f"Profesores de {servicio}", [e.nombre for e in self.p.profesores],
                                 NL.integrantes(x), con_numero=True)
            if d.exec() != QDialog.Accepted:
                return False
            profesores, horas = d.elegidos(), d.sp.value()

        def fn(a):
            ya = set(NL.integrantes(x)); cambio = False
            for n in ya - set(profesores):
                cambio |= NL.quitar_profesor(a, x, n)
            cambio |= NL.anadir_profesores(a, x, [n for n in profesores if n not in ya], horas)
            return cambio
        return self.v.editar(fn, "profesores de guardia")

    def nueva_reunion(self, nombre=None, profesores=None):
        if nombre is None:
            d = ElegirProfesores(self, "Nueva reunión", [e.nombre for e in self.p.profesores], nombre="Reunión")
            if d.exec() != QDialog.Accepted:
                return None
            nombre, profesores = d.ed_nombre.text().strip(), d.elegidos()
        if not nombre:
            return None
        nuevo = []
        self.v.editar(lambda a: nuevo.append(NL.nueva_reunion(a, nombre, profesores=profesores or ())) or True, "nueva reunión")
        return nuevo[0].findtext("nombre") if nuevo else None

    def reuniones_auto(self, cual):
        creadas = []
        f = NL.reuniones_departamento if cual == "departamento" else NL.reuniones_equipo
        self.v.editar(lambda a: bool(creadas.extend(f(a, self.p)) or creadas), f"reuniones de {cual}")
        if not creadas:
            QMessageBox.information(self, APP_NAME, "No hay datos suficientes (departamentos o materias asignadas).")
        return len(creadas)

    def quitar(self, lista, nombres=None):
        t = self.tg if lista == "guardias" else self.tr
        nombres = nombres if nombres is not None else self._sel(t)
        xs = [self._xml(lista, n) for n in nombres]
        if not xs:
            return False
        return self.v.editar(lambda a: [NL.eliminar(a, x) for x in xs if x is not None] or True, "quitar")

    def mas_opciones(self):
        sel = self._sel(self.tg) or self._sel(self.tr)
        self.v.propiedades_clasicas("guardias" if self._sel(self.tg) or not self._sel(self.tr) else "reuniones", sel[0] if sel else None)
