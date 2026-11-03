# ClaustrApp · Guía rápida

## 1. Primeros pasos
1. Abra el programa y elija **Archivo › Abrir** para cargar un archivo `.xghc` (formato XML-GHC), o
   **Archivo › Nuevo** para empezar de cero.
2. El programa no sobrescribe nunca el archivo original: al guardar propone una copia.
3. Pruebe primero con `ejemplos/SINT_instituto.xghc` (datos inventados).

## 2. Datos del centro
En la ventana principal, cada lista (materias, grupos, profesorado, aulas, sesiones…) tiene su solapa.
Doble clic sobre un elemento abre sus propiedades; las plantillas de horas se marcan con
«Puede», «Mejor no» y «No puede».

## 3. Calcular el horario
**Motor › Calcular horario** abre la ventana del motor. Se puede pausar y reanudar; cada resultado se
guarda como `.lphr` junto al archivo de datos. Si no salen horarios completos, **Motor › Depurar
condiciones** ayuda a localizar las condiciones que lo impiden.

## 4. Retocar el resultado
El editor de resultados permite mover, intercambiar y recolocar clases. Las celdas se colorean en verde
(sin problemas), ámbar (con avisos) o rojo (no se puede).

## 5. Versión sencilla
`--sencilla` abre un asistente con pasos: datos, condiciones, cálculo y retoques, con explicaciones en
lenguaje llano.

## 6. Informes
**Informes** genera PDF de horarios por grupo, profesor y aula, guardias y resúmenes.

## 7. DELPHOS
**Datos › Importar datos desde DELPHOS** lee el archivo descargado de DELPHOS; la exportación prepara el
archivo de vuelta.
