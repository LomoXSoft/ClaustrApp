@echo off
rem Construye el ejecutable para Windows 10/11 (PyInstaller onedir); el nombre sale de la marca activa.
rem Requisitos: Python 3.12 x64 en el PATH. Ejecutar desde la carpeta build_win.
setlocal
cd /d "%~dp0"
if not exist venv_win python -m venv venv_win || goto error
call venv_win\Scripts\activate.bat || goto error
python -m pip install --upgrade pip || goto error
python -m pip install -r requisitos_windows.txt || goto error
pyinstaller --noconfirm --clean horarios.spec || goto error
for /f "delims=" %%n in ('python -c "import sys; sys.path.insert(0, r'..\app'); from horarios.textos import MARCA; print(MARCA['nombre_archivo'])"') do set NOMBRE=%%n
rem Autoprueba: abrir SINT, motor, comprobador y PDF
dist\%NOMBRE%\%NOMBRE%.exe --autoprueba ..\ejemplos\SINT_instituto.xghc "%TEMP%\horarios_autoprueba" 60
type "%TEMP%\horarios_autoprueba\autoprueba.txt"
echo Listo: dist\%NOMBRE%
exit /b 0
:error
echo ERROR en la construccion
exit /b 1
