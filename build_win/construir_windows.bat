@echo off
rem ============================================================================
rem  Construye el programa para Windows 10/11 de 64 bits en un PC con Windows.
rem  El nombre, la versión y el instalador salen de la marca activa
rem  (app\horarios\recursos\marca*.json) y de app\horarios\__init__.py.
rem
rem  Requisitos: Python 3.12 de 64 bits (python.org) instalado.
rem  Opcional:   Inno Setup 6 (jrsoftware.org) para generar también el instalador.
rem  Uso:        doble clic en este archivo, o desde una consola en build_win:
rem                construir_windows.bat
rem  Resultado:  build_win\salida\<Nombre>-<versión>-win64.zip
rem              build_win\salida\<Nombre>-Setup-<versión>.exe (si hay Inno Setup)
rem              y sus SHA-256 en build_win\salida\SHA256.txt
rem ============================================================================
setlocal EnableExtensions
cd /d "%~dp0"

rem --- Python 3.12 de 64 bits (lanzador «py» o python del PATH)
set "PY="
py -3.12-64 -c "import sys" >nul 2>&1 && set "PY=py -3.12-64"
if not defined PY python -c "import sys,struct; sys.exit(0 if sys.version_info[:2]==(3,12) and struct.calcsize('P')==8 else 1)" >nul 2>&1 && set "PY=python"
if not defined PY (
  echo No se encuentra Python 3.12 de 64 bits. Instalelo desde https://www.python.org/downloads/windows/
  goto error
)

rem --- entorno aislado con dependencias fijadas
if not exist venv_win\Scripts\python.exe %PY% -m venv venv_win || goto error
set "VPY=%~dp0venv_win\Scripts\python.exe"
"%VPY%" -m pip install --disable-pip-version-check -q -r requisitos_windows.txt || goto error

rem --- nombre y versión
"%VPY%" info_marca.py "%TEMP%\marca_vars.cmd" || goto error
call "%TEMP%\marca_vars.cmd"
if not defined NOMBRE goto error
echo.
echo === Construyendo %NOMBRE% %VERSION% ===

rem --- PyInstaller (onedir)
"%VPY%" -m PyInstaller --noconfirm --clean horarios.spec || goto error

rem --- autoprueba: abrir el ejemplo SINT, motor, comprobador y PDF
set "EJ=..\ejemplos"
if not exist "%EJ%\SINT_instituto.xghc" set "EJ=..\dist\ejemplos"
set "AP=%TEMP%\%NOMBRE%_autoprueba"
if exist "%AP%" rmdir /s /q "%AP%"
dist\%NOMBRE%\%NOMBRE%.exe --autoprueba "%EJ%\SINT_instituto.xghc" "%AP%" 90
type "%AP%\autoprueba.txt"
findstr /c:"RESULTADO: OK" "%AP%\autoprueba.txt" >nul || (echo AUTOPRUEBA FALLIDA & goto error)

rem --- zip portable: carpeta del programa + LEEME + ejemplos
set "SAL=%~dp0salida"
set "PAQ=%SAL%\%NOMBRE%-%VERSION%-win64"
if exist "%PAQ%" rmdir /s /q "%PAQ%"
mkdir "%PAQ%" || goto error
xcopy /e /i /q "dist\%NOMBRE%" "%PAQ%\%NOMBRE%" >nul || goto error
copy /y LEEME.txt "%PAQ%\LEEME.txt" >nul
xcopy /i /q "%EJ%\SINT_instituto.*" "%PAQ%\ejemplos\" >nul
set "ZIP=%SAL%\%NOMBRE%-%VERSION%-win64.zip"
if exist "%ZIP%" del "%ZIP%"
powershell -NoProfile -Command "Compress-Archive -Path '%PAQ%\*' -DestinationPath '%ZIP%'" || goto error

rem --- instalador Inno Setup (opcional)
set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
set "SETUP="
if exist "%ISCC%" if defined APPID (
  "%ISCC%" /Q "/DMyAppName=%TITULO%" "/DMyAppExe=%NOMBRE%" "/DMyAppVersion=%VERSION%" "/DMyAppId=%APPID%" "/O%SAL%" instalador.iss || goto error
  set "SETUP=%SAL%\%NOMBRE%-Setup-%VERSION%.exe"
)
if not exist "%ISCC%" echo Inno Setup 6 no instalado: se omite el instalador, solo se genera el zip.

rem --- SHA-256
powershell -NoProfile -Command "Get-ChildItem '%SAL%' -File | Where-Object { $_.Extension -in '.zip','.exe' } | Get-FileHash -Algorithm SHA256 | ForEach-Object { '{0}  {1}' -f $_.Hash, (Split-Path $_.Path -Leaf) } | Tee-Object -FilePath '%SAL%\SHA256.txt'"
echo.
echo Listo. Archivos en %SAL%
pause
exit /b 0

:error
echo.
echo ERROR en la construccion. Revise los mensajes de arriba.
pause
exit /b 1
