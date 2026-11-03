#!/bin/sh
# Regresiones completas; registro en pruebas/regresiones.log
cd "$(dirname "$0")/.."
: > pruebas/regresiones.log
for t in textos_paquetes gui_textos_visibles motor_velocidad motor_ejemplos motor_proceso motor_opciones gui_criterios gui_informes gui_informes_nuevos gui_editor gui_edicion gui_opciones_generales gui_no_lectivas ida_vuelta gui_depurador gui_parcial gui_fundir gui_editor_retoques motor_restricciones motor_semanas motor_alejados gui_datos periodos_remap plantillas_semanas semanas_formato delphos_importar delphos_exportar gui_delphos gui_nuevo gui_sencilla e2e_sencilla gui_exportar_delphos capturar_motor; do
  [ -f pruebas/$t.py ] || continue
  echo "== $t" >> pruebas/regresiones.log
  QT_QPA_PLATFORM=offscreen timeout 900 ../venv/bin/python -u pruebas/$t.py  2>&1 | grep -v propagateSizeHints >> pruebas/regresiones.log
  echo "-- salida $t: $?" >> pruebas/regresiones.log
done
echo FIN >> pruebas/regresiones.log
