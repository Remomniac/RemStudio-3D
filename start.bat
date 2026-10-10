@echo off
rem Startet RemStudio 3D direkt aus dem Quellcode (richtet beim ersten Mal alles ein).
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
    echo Erster Start: richte Python-Umgebung ein ...
    python -m venv .venv || (echo Python 3.10+ wird benoetigt: https://www.python.org & pause & exit /b 1)
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt || (pause & exit /b 1)
)
start "" ".venv\Scripts\pythonw.exe" app.py %*
