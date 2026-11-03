# -*- mode: python ; coding: utf-8 -*-
# PyInstaller onedir para Windows 10/11. Ejecutar desde esta carpeta: pyinstaller --noconfirm horarios.spec
# El nombre del ejecutable y los datos de versión salen de la marca activa (recursos/marca*.json).
import os, sys
from PyInstaller.utils.hooks import collect_all

APP = os.path.abspath(os.path.join(SPECPATH, "..", "app"))
sys.path.insert(0, APP)
from horarios import __version__
from horarios.textos import MARCA
NOMBRE = MARCA["nombre_archivo"]
V = tuple(int(x) for x in __version__.split(".")) + (0,)
VERSION_TXT = os.path.join(SPECPATH, "version_info_gen.txt")
os.makedirs(os.path.dirname(VERSION_TXT), exist_ok=True)
with open(VERSION_TXT, "w", encoding="utf-8") as f:
    f.write(f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={V}, prodvers={V}, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('0C0A04B0', [
      StringStruct('CompanyName', '{MARCA["autor"]}'),
      StringStruct('FileDescription', '{MARCA["nombre"]}'),
      StringStruct('FileVersion', '{__version__}'),
      StringStruct('InternalName', '{NOMBRE}'),
      StringStruct('LegalCopyright', '© {MARCA["autor"]}'),
      StringStruct('OriginalFilename', '{NOMBRE}.exe'),
      StringStruct('ProductName', '{MARCA["nombre"]}'),
      StringStruct('ProductVersion', '{__version__}')])]),
    VarFileInfo([VarStruct('Translation', [0x0C0A, 1200])])
  ]
)
""")
datas = [(os.path.join(APP, "horarios", "recursos"), os.path.join("horarios", "recursos"))]
binaries, hidden = [], ["horarios.autoprueba", "horarios.motor.proceso", "horarios.motor.cpsat"]
for paquete in ("ortools",):
    d, b, h = collect_all(paquete)
    datas += d; binaries += b; hidden += h
hidden += [m for m in __import__("PyInstaller.utils.hooks", fromlist=["collect_submodules"]).collect_submodules("horarios")]

a = Analysis([os.path.join(SPECPATH, "lanzador.py")], pathex=[APP], binaries=binaries, datas=datas,
             hiddenimports=hidden,
             excludes=["tkinter", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtQml",
                       "PySide6.QtQuick", "PySide6.Qt3DCore", "PySide6.QtMultimedia", "matplotlib", "IPython"],
             noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name=NOMBRE, console=False,
          icon=os.path.join(APP, "horarios", "recursos", "icon.ico"),
          version=VERSION_TXT, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name=NOMBRE)
