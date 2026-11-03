# Cómo contribuir

- Abra una *issue* para avisar de errores o proponer cambios. Si es un error, indique la versión (menú «Ayuda») y los pasos para reproducirlo.
- Para un *pull request*:
  - incluya pruebas (`sh app/pruebas/regresiones.sh` no debe dar ningún `FALLO`) y una entrada en `CHANGELOG.md`;
  - siga el estilo del código y los textos en español; los textos de la interfaz van en `app/horarios/recursos/textos_propios.json`.
- **Nunca suba datos reales**: archivos `.xghc`, `.lphr` o de DELPHOS de un centro, ni nombres de profesores o alumnos. En las pruebas y capturas use solo datos inventados (prefijo `SINT`).
- No incluya material de otros programas de horarios (imágenes, iconos, textos ni diseños).
- Al contribuir, acepta que su aportación se distribuya bajo la licencia GPL-3.0-or-later del proyecto.
