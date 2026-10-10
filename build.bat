@echo off
rem Baut RemStudio 3D: RemStudio3D.exe und RemStudio3D-Setup.exe im Hauptordner.
rem Hinweis: RemStudio 3D darf waehrend des Bauens nicht geoeffnet sein.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Richte Python-Umgebung ein ...
    python -m venv .venv || (echo Python 3.10+ wird benoetigt: https://www.python.org & pause & exit /b 1)
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt || (pause & exit /b 1)
)
".venv\Scripts\python.exe" -m pip install --quiet pyinstaller
".venv\Scripts\python.exe" build.py
pause
