# Projekt: RemStudio 3D

## Ziel
Windows-App, die Bilder/Zeichnungen (v. a. Comics) in druckfertige 3D-Wandbilder mit Rahmen verwandelt (STL für den
3D-Drucker) – so einfach bedienbar wie möglich. Open Source (MIT) auf GitHub: https://github.com/Remomniac/RemStudio-3D

## Aktueller Stand
- Version **1.0.0** veröffentlicht (GitHub-Release mit `RemStudio3D-Setup.exe` + Portable-ZIP).
- Funktionen komplett: KI-Hintergrund-Entfernung (Editor startet nach dem Laden), Motiv-Erkennung, Rahmenformen,
  automatische Stege, Druckbarkeits-Prüfung, Pinsel/Radierer/Steg, Rückplatte, Aufhängung, 3D-Vorschau,
  STL/SVG/PNG-Export mit Aufteilen, Projekte (`.remstudio`), GPU-Vorschau, dunkles Design (Orange), Englisch/Deutsch.
- Installer (Inno Setup 6.7, dunkel, pro Benutzer, en/de) und Build-Skript `build.bat` → EXE + Setup im Hauptordner.
- README englisch (`README.md`) + deutsch (`README.de.md`); GitHub-Beschreibung/Topics/Release-Text englisch.
- Doku-System nach `CLAUDE.md` eingerichtet (`docs/`), Schnelltest `tests/smoke_test.py` (alle grün).
- **Lokal committet, noch NICHT gepusht:** Bugfix F-026 (Kreisrahmen → 3D-Netz nicht geschlossen), `tests/`, Doku.

## Nächste Schritte
1. Nutzer fragen, ob Bugfix + Doku gepusht werden sollen → dann Version auf **1.0.1** erhöhen
   (`remstudio/__init__.py`), `build.bat`, Smoke-Test, Release `v1.0.1` mit Setup + Portable-ZIP (Ablauf: ANLEITUNG „Release“).
2. SmartScreen-Warnung (F-025): auf Wunsch SignPath-Foundation-Signierung vorbereiten (GitHub-Actions-Build +
   „Code Signing Policy“-Seite); Antrag stellt der Nutzer selbst auf signpath.org.

## Offene Fehler (Details in docs/FEHLER.md)
- F-025 – SmartScreen „Der Computer wurde durch Windows geschützt“ beim Installer (unsigniert) – 🟡 Workaround: „Weitere Informationen → Trotzdem ausführen“
- F-026 – Kreisrahmen: 3D-Netz nicht geschlossen – 🟢 gelöst, aber erst lokal (noch nicht in Release v1.0.0)

## Wichtige Dateien
- `app.py` – Start, Sprache/Locale, EXE-Selbsttest (`REMSTUDIO_SELFTEST`)
- `remstudio/main_window.py` – Hauptfenster, Vorschau-Steuerung, Undo, Projekte, Export-Dialog
- `remstudio/processing.py` – Bildverarbeitung (Maske, Stege, Analyse, Vorschau-Ebenen)
- `remstudio/mesh.py` / `export.py` – 3D-Netz, STL/SVG/PNG
- `remstudio/bgremove.py` / `bg_editor.py` – KI-Hintergrund-Entfernung + Editor
- `remstudio/i18n.py` – Übersetzungen (DE-Schlüssel → EN)
- `remstudio/theme.py` / `widgets.py` / `canvas.py` – Design, Bedienelemente, GPU-Vorschau
- `build.py`, `build.bat`, `RemStudio3D.spec`, `installer/RemStudio3D.iss` – Build + Installer
- `tests/smoke_test.py` – Schnelltest

## Testen
- `.venv\Scripts\python.exe tests\smoke_test.py` → „✅ Alle Tests bestanden“
- EXE: `set REMSTUDIO_SELFTEST=%TEMP%\st.txt` + `RemStudio3D.exe` → Datei beginnt mit `ok`

## Changelog (neueste oben, max. 15 Zeilen – Details in docs/LOG.md)
- 2026-10-10 – Doku-System (CLAUDE.md, docs/), Smoke-Test, Bugfix F-026 – lokal committet – siehe LOG.md
- 2026-10-10 – README englisch + deutsch, GitHub-Texte englisch – README*.md – siehe LOG.md
- 2026-10-10 – MIT-Lizenz – LICENSE, README – siehe LOG.md
- 2026-10-10 – GitHub-Upload, Tag + Release v1.0.0 – siehe LOG.md
- 2026-10-10 – Sprachen EN/DE, Installer, Build-Skript – i18n.py, installer/, build.py – siehe LOG.md
- 2026-10-10 – Umbenennung zu RemStudio 3D, neues Logo – alle Dateien – siehe LOG.md
- 2026-10-10 – Präzise Regler, Hintergrund-Schritt nach dem Laden – widgets.py, bg_editor.py – siehe LOG.md
- 2026-10-10 – GPU-Vorschau, dunkles Design, Orange – canvas.py, theme.py, main_window.py – siehe LOG.md
- 2026-10-10 – KI-Hintergrund-Entfernung + Editor – bgremove.py, bg_editor.py – siehe LOG.md
- 2026-10-10 – Erste Version (damals „RahmenStudio 3D“) – siehe LOG.md
