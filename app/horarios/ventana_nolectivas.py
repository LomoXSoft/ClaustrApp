"""Planificador: acciones de las listas no lectivas (Reuniones, Guardias, Complementarias, Tipos de tarea).

Las listas Reuniones y Guardias se muestran jerárquicas: cada reunión/servicio va seguida de sus integrantes
(filas sangradas). El menú de cada lista sigue los menús 2003 (Reuniones) y 2004 (Guardias) del planificador de referencia.
"""
from __future__ import annotations
from .textos import TX
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QMessageBox, QInputDialog, QDialog
from . import APP_NAME, modelo as M, nolectivas as NL, edicion as ED
from .propiedades_nl import (VENTANAS_NL, PropiedadesIntegranteGuardia, DialogoAnadirProfesores,
                             DialogoCrearReuniones, GuardiasPorPosicion, es_integrante, integrantes_de_guardias)

ROL = Qt.UserRole + 1
NO_LECTIVAS = {"reuniones", "guardias", "complementarias"}
# estados de plantilla válidos por lista (los de las sesiones lectivas no aplican aquí)
ESTADOS = {"reuniones": [M.INDIFERENTE, M.PROHIBIDO, M.PREFIJADO],
           "guardias": [M.INDIFERENTE, M.PROHIBIDO, M.PREFIJADO],
           "complementarias": [M.INDIFERENTE, M.PROHIBIDO, M.PREFIJADO],
           "tareas": [M.INDIFERENTE, M.PROHIBIDO]}


class NoLectivasMixin:
    # ------------------------------------------------------------ utilidades
    def _obj_actual(self):
        idx = self.tabla.currentIndex()
        return idx.data(ROL) if idx.isValid() else None

    def _padre_actual(self):
        o = self._obj_actual()
        if o is None:
            return None
        if es_integrante(o):
            return o.datos["_padre"]
        return o.datos.get("_xml")

    def _seleccionar_xml(self, x):
        for r in range(self.proxy.rowCount()):
            o = self.proxy.index(r, 0).data(ROL)
            if isinstance(o, M.Elemento) and o.datos.get("_xml") is x:
                self.tabla.selectRow(r); self.tabla.setCurrentIndex(self.proxy.index(r, 0)); return

    def _seleccionar_nombre(self, nombre, padre_nombre=None):
        for r in range(self.proxy.rowCount()):
            o = self.proxy.index(r, 0).data(ROL)
            if isinstance(o, M.Elemento) and o.nombre == nombre and not es_integrante(o):
                self.tabla.selectRow(r); self.tabla.setCurrentIndex(self.proxy.index(r, 0)); return

    def preparar_items_nl(self, items, clave):
        """Filas padre en negrita; las hijas solo editables en «Nº guardias» (guardias)."""
        if clave not in ("reuniones", "guardias"):
            return
        o = items[0].data(ROL)
        if es_integrante(o):
            for j, it in enumerate(items):
                if not (clave == "guardias" and j == 4):
                    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                it.setForeground(Qt.darkGray if j else Qt.black)
        else:
            f = QFont(); f.setBold(True); items[0].setFont(f)

    # ------------------------------------------------------------ menú de la lista
    def acciones_nl(self, clave):
        A = self._accion
        if clave == "reuniones":
            return [A("Nueva reunión\tInsert", self.insertar),
                    A("Nueva reunión de departamento", lambda: self.crear_reuniones(False)),
                    A(TX("nueva_reunion_equipo_grupo"), lambda: self.crear_reuniones(True)),
                    A(TX("tarea_partida"), lambda: self.tarea_inicial("Reuniones")), None,
                    A("Añadir profesores\tAlt+Insert", self.anadir_profesores_nl), A("Modificar", self.propiedades), None,
                    A("Ir a la lista de profesores", lambda: self.cambiar_lista("profesores")), None,
                    self.a_eliminar, A(TX("vaciar_plantillas_reuniones"), lambda: self.limpiar_plantillas_nl("reuniones")),
                    self.a_propiedades, None, self.a_deshacer, self.a_rehacer]
        if clave == "guardias":
            return [A("Nuevo servicio de guardias\tInsert", self.insertar),
                    A("Añadir profesores\tAlt+Insert", self.anadir_profesores_nl),
                    A(TX("guardias_semanales_profesor"), self.propiedades),
                    A(TX("tarea_partida"), lambda: self.tarea_inicial("Guardias")), None,
                    A("Modificar", self.propiedades),
                    A("Ir a la lista de profesores", lambda: self.cambiar_lista("profesores")),
                    A(TX("indicar_profs_hora_hora"), self.detallar_nl), None,
                    self.a_eliminar, A(TX("vaciar_plantillas_guardias"), lambda: self.limpiar_plantillas_nl("guardias")),
                    self.a_propiedades, None, self.a_deshacer, self.a_rehacer]
        if clave == "complementarias":
            return [A("Nueva actividad complementaria\tInsert", self.insertar), None, self.a_eliminar, None,
                    self.a_propiedades, None, self.a_deshacer, self.a_rehacer]
        return None

    # ------------------------------------------------------------ insertar / suprimir
    def insertar_nl(self, clave):
        p = self.proyecto; ref = self._padre_actual()
        if clave == "reuniones":
            nombre, ok = QInputDialog.getText(self, "Nueva reunión", TX("codigo_reunion"))
            if not ok or not nombre.strip():
                return
            nuevo = []
            self.editar(lambda a: nuevo.append(NL.nueva_reunion(a, nombre.strip(), despues_de=ref)) or True, "nueva reunión")
        elif clave == "guardias":
            nombre, ok = QInputDialog.getText(self, "Nuevo servicio de guardias", TX("codigo_servicio"))
            if not ok or not nombre.strip():
                return
            nuevo = []
            self.editar(lambda a: nuevo.append(NL.nueva_guardia(a, nombre.strip(), despues_de=ref)) or True, "nuevo servicio de guardias")
        else:
            if not p.profesores or not p.tareas:
                QMessageBox.information(self, APP_NAME, "Defina antes algún profesor y algún tipo de tarea."); return
            o = self._obj_actual()
            prof = o.datos.get("profesor") if isinstance(o, M.Elemento) else p.profesores[0].nombre
            tarea = o.datos.get("tarea") if isinstance(o, M.Elemento) else p.tareas[0].nombre
            nuevo = []
            self.editar(lambda a: nuevo.append(NL.nueva_complementaria(a, tarea, prof, despues_de=ref)) or True, "nueva complementaria")
        if nuevo:
            self._seleccionar_nombre(nuevo[0].findtext("nombre") or nuevo[0].findtext("identificador"))
            self.propiedades()

    def eliminar_nl(self, clave):
        objs = []
        for idx in self.tabla.selectionModel().selectedRows():
            o = idx.data(ROL)
            if o is not None and o not in objs:
                objs.append(o)
        if not objs:
            return
        hijos = [o for o in objs if es_integrante(o)]; padres = [o for o in objs if not es_integrante(o)]
        partes = []
        if padres:
            partes.append(f"{len(padres)} {'servicio(s) de guardia' if clave == 'guardias' else 'reunión(es)' if clave == 'reuniones' else 'actividad(es)'}")
        if hijos:
            partes.append(f"{len(hijos)} integrante(s)")
        if QMessageBox.question(self, "Suprimir", f"¿Quiere suprimir {' y '.join(partes)}?") != QMessageBox.Yes:
            return

        def hacer(a):
            for h in hijos:
                if not any(h.datos["_padre"] is x.datos["_xml"] for x in padres):
                    NL.quitar_profesor(a, h.datos["_padre"], h.nombre)
            for x in padres:
                NL.eliminar(a, x.datos["_xml"])
            return True
        self.editar(hacer, "suprimir")

    # ------------------------------------------------------------ propiedades
    def propiedades_nl(self, clave, obj):
        p = self.proyecto
        if es_integrante(obj):
            if clave != "guardias":       # integrante de reunión: sus datos están en la lista de profesores
                self.cambiar_lista("profesores")
                for r in range(self.proxy.rowCount()):
                    if self.proxy.index(r, 0).data(ROL).nombre == obj.nombre:
                        self.tabla.selectRow(r); break
                return
            lista = integrantes_de_guardias(p)
            i = next(k for k, h in enumerate(lista) if h.datos["_xml"] is obj.datos["_xml"])
            dlg = PropiedadesIntegranteGuardia(self, lista, i)
        else:
            lista = getattr(p, clave)
            i = next(k for k, e in enumerate(lista) if e.datos["_xml"] is obj.datos["_xml"])
            dlg = VENTANAS_NL[clave](self, lista, i)
        self._dlg_propiedades = dlg
        dlg.exec()
        self._dlg_propiedades = None

    # ------------------------------------------------------------ acciones específicas
    def anadir_profesores_nl(self):
        x = self._padre_actual()
        if x is None:
            return
        guard = x.tag == "guardia"
        dlg = DialogoAnadirProfesores(self, self.proyecto, set(NL.integrantes(x)), con_guardias=guard)
        if dlg.exec() == QDialog.Accepted and dlg.elegidos():
            self.editar(lambda a: NL.anadir_profesores(a, x, dlg.elegidos(), dlg.n_guardias()), "añadir profesores")

    def detallar_nl(self):
        x = self._padre_actual()
        if x is None or x.tag != "guardia":
            return
        p = self.proyecto; marco = x.get("subMarco") or next(iter(p.marcos))
        cant = int((x.findtext("profesoresACadaHora/cantidad") or "1").strip() or 1)
        dlg = GuardiasPorPosicion(self, p, marco, (x.findtext("enRecreos") or "") == "true", cant,
                                  NL.detalle_posiciones(x), x)
        if dlg.exec() == QDialog.Accepted:
            self.editar(lambda a: NL.fijar_detalle(a, x, dlg.detalle()), "guardias por posición")

    def crear_reuniones(self, por_grupo):
        p = self.proyecto
        if not (p.grupos if por_grupo else p.departamentos):
            QMessageBox.information(self, APP_NAME, "No hay " + ("grupos de alumnos." if por_grupo else "departamentos.")); return
        dlg = DialogoCrearReuniones(self, p, por_grupo)
        if dlg.exec() != QDialog.Accepted:
            return
        sel, completo = dlg.opciones()
        hechas = []
        fn = NL.reuniones_equipo if por_grupo else NL.reuniones_departamento
        self.editar(lambda a: bool(hechas.extend(fn(a, p, sel, completo)) or hechas), "crear reuniones")
        self.statusBar().showMessage(f"Reuniones creadas: {len(hechas)}", 5000)

    def tarea_inicial(self, cual):
        """«Tarea de partida»: escribe <tareas><reunionPorDefecto>/<guardiaPorDefecto>."""
        p = self.proyecto
        nombres = [t.nombre for t in p.tareas]
        if not nombres:
            return
        actual = NL.tarea_defecto(ED.Arbol(p.doc.raiz), cual)
        t, ok = QInputDialog.getItem(self, TX("tarea_partida"), TX("tarea_nuevas_cual", cual=cual.lower()),
                                     nombres, nombres.index(actual) if actual in nombres else 0, False)
        if ok and t:
            ruta = "tareas/" + NL.ETIQUETA_DEFECTO[cual]
            self.editar(lambda a: (ED.leer(p.doc.raiz, ruta, None) or "") != t and ED.escribir(a, a.raiz, ruta, t),
                        "tipo de tarea inicial")

    def limpiar_plantillas_nl(self, clave):
        p = self.proyecto
        if QMessageBox.question(self, APP_NAME, f"¿Quiere vaciar las plantillas de todas las {'reuniones' if clave == 'reuniones' else 'guardias'}?") != QMessageBox.Yes:
            return

        def hacer(a):
            ch = False
            for e in getattr(p, clave):
                x = e.datos["_xml"]
                owners = [x] + (list(x.iter("integrante")) if clave == "guardias" else [])
                for o in owners:
                    if o.find("plantilla") is not None:
                        ch = ED.volcar_plantilla(a, o, {}, e.marco) or ch
            return ch
        self.editar(hacer, "limpiar plantillas")

    # ------------------------------------------------------------ panel de plantilla
    def mostrar_plantilla_nl(self, obj):
        p = self.proyecto; clave = self.lista_actual
        self.panel.set_estados(ESTADOS.get(clave))
        prof_pl = {e.nombre: e.plantilla for e in p.profesores}
        if es_integrante(obj):
            her = {k: v for k, v in prof_pl.get(obj.nombre, {}).items() if v == M.PROHIBIDO}
            if clave == "guardias":
                from .xghc import leer_plantilla
                for k, v in leer_plantilla(obj.datos["_padre"], obj.marco).items():
                    if v == M.PROHIBIDO:
                        her[k] = v
                self.panel.mostrar(obj.plantilla, f"{obj.nombre}  ·  {obj.datos['_servicio']}", obj.marco, her)
            else:   # integrante de reunión: plantilla del profesor, solo lectura
                self.panel.mostrar(prof_pl.get(obj.nombre, {}), f"{obj.nombre} (plantilla del profesor)", obj.marco,
                                   None, editable=False)
            return True
        if clave == "reuniones":
            her = {}
            for n in NL.integrantes(obj.datos["_xml"]):
                for k, v in prof_pl.get(n, {}).items():
                    if v == M.PROHIBIDO:
                        her[k] = v
            self.panel.mostrar(obj.plantilla, obj.nombre, obj.marco, her)
            return True
        if clave == "complementarias":
            her = {k: v for k, v in prof_pl.get(obj.datos.get("profesor", ""), {}).items() if v == M.PROHIBIDO}
            self.panel.mostrar(obj.plantilla, f"{obj.datos.get('tarea', '')}  ·  {obj.datos.get('profesor', '')}", obj.marco, her)
            return True
        return False
