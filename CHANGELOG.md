# Cambios en ClaustrApp

Formato: cada versión con lo nuevo, lo cambiado y lo corregido. La versión sale de un único sitio:
`app/horarios/__init__.py` (`__version__`). Autor: **LomoXSoft**.

La 0.0.2 es la primera versión publicada en GitHub. La 0.0.1 fue una versión de prueba sin publicar; su historial de
git no forma parte de este repositorio.

## [0.0.3] — 2026-11-03

### Nuevo
- **Versión en la pantalla de carga**: el número se dibuja al arrancar a partir de `__version__`, sin regenerar la imagen.
- **Construcción para Windows en un clic**: `build_win\construir_windows.bat` crea un entorno aislado con las dependencias
  fijadas, construye con PyInstaller, ejecuta la autoprueba con el ejemplo inventado y genera
  `ClaustrApp-<versión>-win64.zip` (portable) y, si está instalado Inno Setup 6, `ClaustrApp-Setup-<versión>.exe`,
  con sus SHA-256.
- Instalador de Inno Setup (`build_win/instalador.iss`): Windows 10/11 de 64 bits, en Archivos de programa, con accesos
  directos; una versión nueva se instala encima de la anterior.

### Cambiado
- Se quitan las referencias al flujo automático de GitHub: el ejecutable se construye en un PC con Windows.

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
