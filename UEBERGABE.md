# Übergabe an einen neuen Chat

Neuen Chat **in diesem Ordner** (`Documents\Claude\RemStudio Projekt`) starten und diesen Text einfügen:

```
Weiter mit Projekt RemStudio 3D (Projektordner: Documents\Claude\RemStudio Projekt). Lies zuerst PROGRESS.md und CLAUDE.md und befolge sie.
Details stehen in docs/LOG.md, docs/FEHLER.md, docs/ANLEITUNG.md, docs/ENTSCHEIDUNGEN.md.
Stand: v1.0.0 ist auf GitHub veröffentlicht (Remomniac/RemStudio-3D, Release mit Setup + Portable-ZIP, MIT, README EN/DE). Lokal Commits vor origin (Bugfix F-026 + tests/smoke_test.py + Doku), noch nicht gepusht.
Zuletzt geändert: remstudio/processing.py → process() (Mini-Löcher am Ende schließen), remstudio/mesh.py → mask_polygons() (Löcher ≤ 0,05 mm² ignorieren), tests/smoke_test.py neu, CLAUDE.md/PROGRESS.md/docs/ neu, Projektordner umbenannt zu „RemStudio Projekt“.
Als Nächstes: Nutzer fragen, ob gepusht + v1.0.1 veröffentlicht werden soll (Version in remstudio/__init__.py erhöhen, Smoke-Test, build.bat, Release mit Setup + Portable-ZIP – Ablauf in docs/ANLEITUNG.md „Release“, Text-Vorlage docs/release-notes/v1.0.0.md). Danach optional SignPath-Signierung vorbereiten (GitHub Actions + Code Signing Policy).
Offene Fehler: F-025 – SmartScreen beim Installer: „Der Computer wurde durch Windows geschützt … Herausgeber: Unbekannter Herausgeber“ (unsigniert; Workaround „Weitere Informationen → Trotzdem ausführen“).
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
