# Cambios en ClaustrApp

Formato: cada versión con lo nuevo, lo cambiado y lo corregido. La versión sale de un único sitio:
`app/horarios/__init__.py` (`__version__`). Autor: **LomoXSoft**.

La 0.0.2 es la primera versión publicada en GitHub. La 0.0.1 fue una versión de prueba sin publicar; su historial de
git no forma parte de este repositorio.

## [0.0.2] — 2026-11-03

### Nuevo
- Primera versión pública de ClaustrApp, planificador de horarios escolares compatible con archivos XML-GHC.
- Datos del centro, condiciones y preferencias; cálculo con OR-Tools CP-SAT en un proceso aparte, con pausa y
  comprobador independiente; depurador de condiciones y analizador de conflictos.
- Editor del resultado, versión sencilla guiada, informes en PDF e intercambio con DELPHOS.
- Instituto inventado de ejemplo (`ejemplos/SINT_instituto.xghc`) y pruebas de regresión con datos sintéticos.

### Cambiado
- Textos de la interfaz propios, en `app/horarios/recursos/textos_propios.json`, con pruebas de claves y de textos
  visibles en todos los diálogos.
- Las estadísticas de los resultados (`.lphr`) se guardan con códigos neutros y se traducen al mostrarlas; los
  resultados anteriores se siguen abriendo.
