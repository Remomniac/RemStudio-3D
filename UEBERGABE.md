# Übergabe an einen neuen Chat

Neuen Chat **in diesem Ordner** (`Documents\Claude\RemStudio Projekt`) starten und diesen Text einfügen:

```
Weiter mit Projekt RemStudio 3D (Projektordner: Documents\Claude\RemStudio Projekt). Lies zuerst PROGRESS.md und CLAUDE.md und befolge sie.
Details stehen in docs/LOG.md, docs/FEHLER.md, docs/ANLEITUNG.md, docs/ENTSCHEIDUNGEN.md.
Stand: v1.0.1 ist auf GitHub veröffentlicht (Remomniac/RemStudio-3D, Release mit Setup + Portable-ZIP, MIT, README EN/DE), enthält Bugfix F-026. Alles gepusht.
Zuletzt geändert: remstudio/__init__.py (__version__ 1.0.1), .gitignore (Portable-ZIP), docs/release-notes/v1.0.1.md, Doku.
Als Nächstes: auf Wunsch SignPath-Signierung vorbereiten (GitHub Actions + Code Signing Policy), sonst Nutzerwünsche abwarten. Release-Ablauf: docs/ANLEITUNG.md „Release“.
Offene Fehler: F-025 – SmartScreen beim Installer: „Der Computer wurde durch Windows geschützt … Herausgeber: Unbekannter Herausgeber“ (unsigniert; Workaround „Weitere Informationen → Trotzdem ausführen“). F-027 – `cmd /c "build.bat"` aus Claudes PowerShell: „Der Befehl "build.bat" ist entweder falsch geschrieben oder konnte nicht gefunden werden.“ (Workaround: .venv/Scripts/python.exe build.py).
NICHT erneut probieren: Microsoft Artifact Signing als Privatperson (nur USA/Kanada); selbstsigniertes Zertifikat (hilft nicht); Installer per GUI-Automation mit echtem Zielordner testen (F-023); EXE bauen, während RemStudio3D.exe läuft (F-012); Tests gegen echte Einstellungen statt Profil RemStudio3D_test (F-011).
```

## Was in diesem Ordner liegt
| Datei/Ordner | Wofür |
|---|---|
| `CLAUDE.md` | Arbeitsregeln für Claude (inkl. Projektinfos in §8) |
| `PROGRESS.md` | Kurzüberblick: Ziel, Stand, nächste Schritte – wird beim Start gelesen |
| `docs/` | `LOG.md` (Protokoll), `FEHLER.md` (Fehler-Datenbank), `ANLEITUNG.md` (alle Werkzeuge), `ENTSCHEIDUNGEN.md`, `release-notes/` |
| `remstudio/`, `app.py` | Programmcode |
| `tests/smoke_test.py` | Schnelltest |
| `build.bat`, `build.py`, `RemStudio3D.spec`, `installer/` | Programm + Installer bauen |
| `RemStudio3D.exe` + `RemStudio3D_files/` | fertiges Programm (direkt startbar) |
| `RemStudio3D-Setup.exe` | fertiger Installer |
| `.venv/` | Python-Umgebung (nicht in Git) |
| `.git/` | Git-Verlauf, verbunden mit github.com/Remomniac/RemStudio-3D |
