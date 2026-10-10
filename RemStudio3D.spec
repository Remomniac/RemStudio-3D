# -*- mode: python ; coding: utf-8 -*-
# PyInstaller-Bauanleitung fuer RemStudio 3D
from PyInstaller.utils.hooks import collect_submodules

hidden = collect_submodules("pyqtgraph.opengl") + ["OpenGL.platform.win32", "OpenGL.arrays.numpymodule",
                                                    "OpenGL.arrays.ctypesarrays", "OpenGL.arrays.numbers"]
excludes = ["tkinter", "matplotlib", "scipy", "pandas", "IPython", "PySide6.QtWebEngineCore",
            "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick", "PySide6.QtQuick", "PySide6.QtQml",
            "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.QtMultimedia", "PySide6.QtPdf",
            "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtBluetooth", "PySide6.QtPositioning",
            "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtDesigner", "PySide6.QtNetwork"]

a = Analysis(["app.py"], pathex=[], binaries=[], datas=[("icon.ico", ".")], hiddenimports=hidden,
             hookspath=[], runtime_hooks=[], excludes=excludes, noarchive=False)
pyz = PYZ(a.pure)
import os

# Windows-Dateieigenschaften (Produktname, Version) – wird von build.py erzeugt
version_file = "version_info.txt" if os.path.exists("version_info.txt") else None
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="RemStudio3D", debug=False, strip=False, upx=False,
          console=False, icon="icon.ico", version=version_file,
          # Zusatzdateien liegen in einem klar benannten Ordner neben der EXE
          contents_directory="RemStudio3D_files")
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="RemStudio3D")
