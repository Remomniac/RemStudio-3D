# Projekt: RemStudio 3D

## Ziel
Windows-App, die Bilder/Zeichnungen (v. a. Comics) in druckfertige 3D-Wandbilder mit Rahmen verwandelt (STL für den
3D-Drucker) – so einfach bedienbar wie möglich. Open Source (MIT) auf GitHub: https://github.com/Remomniac/RemStudio-3D

## Aktueller Stand
- Version **1.0.1** veröffentlicht (GitHub-Release mit `RemStudio3D-Setup.exe` + Portable-ZIP), enthält Bugfix F-026.
- Funktionen komplett: KI-Hintergrund-Entfernung (Editor startet nach dem Laden), Motiv-Erkennung, Rahmenformen,
  automatische Stege, Druckbarkeits-Prüfung, Pinsel/Radierer/Steg, Rückplatte, Aufhängung, 3D-Vorschau,
  STL/SVG/PNG-Export mit Aufteilen, Projekte (`.remstudio`), GPU-Vorschau, dunkles Design (Orange), Englisch/Deutsch.
- Installer (Inno Setup 6.7, dunkel, pro Benutzer, en/de) und Build-Skript `build.bat` → EXE + Setup im Hauptordner.
- README englisch (`README.md`) + deutsch (`README.de.md`) neu gestaltet: Banner, Launch-Video, 3D-Animation, Screenshots, eigene Icons
  (Bilder per `make_screenshots.py` → `docs/images/`); GitHub-Beschreibung/Topics/Release-Text englisch.
- Doku-System nach `CLAUDE.md` eingerichtet (`docs/`), Schnelltest `tests/smoke_test.py` (alle grün).
- Release-Texte liegen in `docs/release-notes/`.
- SignPath-Vorbereitung fertig, aber **zurückgestellt** – nur im lokalen Branch `signpath` (siehe ENTSCHEIDUNGEN).
- Projektordner heißt jetzt `RemStudio Projekt`; Übergabe-Prompt in `UEBERGABE.md`.

## Nächste Schritte
1. Nutzer lädt `docs/images/social-preview.png` in GitHub → Settings → Social preview hoch.
2. Wünsche des Nutzers abwarten. SignPath erst auf Wunsch fortsetzen (Branch `signpath` auf `main` rebasen).

## Offene Fehler (Details in docs/FEHLER.md)
- F-025 – SmartScreen „Der Computer wurde durch Windows geschützt“ beim Installer (unsigniert) – 🟡 Workaround: „Weitere Informationen → Trotzdem ausführen“
- F-027 – `cmd /c build.bat` aus Claudes PowerShell „nicht gefunden“ – 🟡 Workaround: `build.py` direkt
- F-032 – Video-Upload über die Browser-Erweiterung bricht ab – 🟡 Workaround: Nutzer zieht die Datei selbst in den GitHub-Editor

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
- `make_screenshots.py`, `docs/images/` – Bilder der GitHub-Seite
- `make_video.py` – Launch-Video (→ `RemStudio3D-launch.mp4`, nicht im Repo)

## Testen
- `.venv\Scripts\python.exe tests\smoke_test.py` → „✅ Alle Tests bestanden“
- EXE: `set REMSTUDIO_SELFTEST=%TEMP%\st.txt` + `RemStudio3D.exe` → Datei beginnt mit `ok`

## Changelog (neueste oben, max. 15 Zeilen – Details in docs/LOG.md)
- 2026-10-10 – Launch-Video in README EN/DE eingebunden – README*.md – siehe LOG.md
- 2026-10-10 – Launch-Video (englisch) per Code – make_video.py – siehe LOG.md
- 2026-10-10 – GitHub-Seite neu gestaltet (Bilder, Icons, README EN/DE); SignPath in Branch `signpath` zurückgestellt – siehe LOG.md
- 2026-10-10 – Release v1.0.1 (Bugfix F-026) – __init__.py, .gitignore, docs/release-notes/v1.0.1.md – siehe LOG.md
- 2026-10-10 – Projektordner → „RemStudio Projekt“, UEBERGABE.md, Release-Text-Vorlage – siehe LOG.md
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
