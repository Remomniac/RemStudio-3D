# Übergabe an einen neuen Chat

Neuen Chat **in diesem Ordner** (`Documents\Claude\RemStudio Projekt`) starten und diesen Text einfügen:

```
Weiter mit Projekt RemStudio 3D (Projektordner: Documents\Claude\RemStudio Projekt). Lies zuerst PROGRESS.md und CLAUDE.md und befolge sie.
Details stehen in docs/LOG.md, docs/FEHLER.md, docs/ANLEITUNG.md, docs/ENTSCHEIDUNGEN.md.
Stand: v1.0.1 ist auf GitHub veröffentlicht (Remomniac/RemStudio-3D, Setup + Portable-ZIP, MIT). README EN/DE neu gestaltet mit Banner, eingebettetem Launch-Video (user-attachments-Link), GIF, Screenshots, eigenen SVG-Icons. Alles gepusht, main = origin/main. SignPath-Signierung ist fertig vorbereitet, aber auf Wunsch des Nutzers zurückgestellt: nur im lokalen Branch `signpath` (Commit 05def7e), nicht veröffentlicht.
Zuletzt geändert: README.md + README.de.md (Video-Link), make_screenshots.py (Bilder → docs/images/), make_video.py (Launch-Video → RemStudio3D-launch.mp4, nicht im Repo), Doku.
Als Nächstes: Wünsche des Nutzers abwarten. Offen beim Nutzer: docs/images/social-preview.png in GitHub → Settings → Social preview hochladen. SignPath nur auf ausdrücklichen Wunsch (Branch `signpath` auf main rebasen).
Offene Fehler: F-025 – SmartScreen „Der Computer wurde durch Windows geschützt … Unbekannter Herausgeber“ (unsigniert; Workaround „Weitere Informationen → Trotzdem ausführen“). F-027 – `cmd /c "build.bat"` aus Claudes PowerShell: „Der Befehl "build.bat" ist entweder falsch geschrieben oder konnte nicht gefunden werden.“ (Workaround: .venv/Scripts/python.exe build.py). F-032 – Video-Upload per Browser-Erweiterung: „The "file_upload" tool call was sent, but the connection was lost …“ (Workaround: Nutzer zieht Datei selbst in den GitHub-Editor, schickt den Link).
NICHT erneut probieren: Microsoft Artifact Signing als Privatperson (nur USA/Kanada); selbstsigniertes Zertifikat (hilft nicht); Installer per GUI-Automation mit echtem Zielordner testen (F-023); EXE bauen, während RemStudio3D.exe läuft (F-012); Tests gegen echte Einstellungen statt Profil RemStudio3D_test (F-011); Segoe-Fluent-Icons der App für GitHub-Bilder (Lizenz unklar → eigene SVGs); Video als Datei im Repo einbetten (GitHub zeigt nur hochgeladene user-attachments als Player); 6,5-MB-Upload über die Browser-Erweiterung (F-032); SignPath-Hinweise veröffentlichen, solange der Nutzer das nicht will.
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
