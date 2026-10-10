# Anleitung – RemStudio 3D

> Alle Befehle im Projektordner `<PROJEKT>` ausführen (Windows; Git-Bash oder Eingabeaufforderung).
> `<GH>` = GitHub CLI: `gh` bzw. `%LOCALAPPDATA%\Microsoft\WinGet\Packages\GitHub.cli_Microsoft.Winget.Source_8wekyb3d8bbwe\bin\gh.exe`
> `<ISCC>` = Inno-Setup-Compiler: `%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe`

---

## Programm bedienen (für Nutzer)
**Wofür:** Bild → druckbares 3D-Wandbild mit Rahmen (STL).
**So geht's:**
1. Bild per Drag & Drop, „Open image / Bild öffnen“ oder Strg+V laden.
2. Hintergrund-Editor startet automatisch (KI entfernt den Hintergrund) → prüfen, ggf. mit 🟢/🔴 nachmalen → „Continue/Weiter“ (oder „Keep background/Hintergrund behalten“).
3. Rechts ① Bildart wählen, Regler (Schwelle, Linien dicker/dünner, Flecken entfernen) anpassen.
4. ② Rahmenform und Größe, ③ Motiv platzieren (Werkzeug „Motiv“: ziehen, Mausrad = Größe).
5. „Check/Prüfung“-Kasten beachten (lose Teile → blaue Stege, orange = zu dünn, lila = zu enge Lücke).
6. „Export 3D file / 3D-Datei exportieren“ → STL im Slicer öffnen.
**Bedienhilfen:** Leertaste halten = Ansicht verschieben · Mausrad = Zoom · `[` `]` = Pinselgröße · Strg+Z/Y = Rückgängig/Wiederholen · Shift beim Ziehen = Feinjustierung · Zahl anklicken und eintippen · Mausrad nur über der Zahl ändert Werte · F1 = Kurzanleitung.
**Im Code:** `remstudio/main_window.py` → `MainWindow`

## Sprache umschalten
**Wofür:** Oberfläche Englisch (Standard) oder Deutsch.
**So geht's:** oben rechts auf **EN/DE** (oder ☰ → „Language / Sprache“) → Sprache wählen → Neustart bestätigen.
**Technik:** Einstellung `language` (`en`/`de`) in `HKCU\Software\RemStudio\RemStudio3D`; wird beim Start in `app.py` → `main()` gelesen (setzt auch Zahlenformat + Qt-Standardknöpfe).
**Neue Texte übersetzen:** deutschen Text im Code schreiben, im Wörterbuch `remstudio/i18n.py` → `EN` eintragen (`"Deutsch": "English"`). Dynamische Texte: `T("… {n} …", n=wert)`. Prüfen: Smoke-Test („Englische Oberfläche vollständig übersetzt“).
**Im Code:** `remstudio/i18n.py` → `T()`, `translate_tree()`, `num()`, `help_text()`; `main_window.py` → `_set_language()`

## Einstellungen (Registry)
**Wo:** `HKEY_CURRENT_USER\Software\RemStudio\RemStudio3D`
| Schlüssel | Bedeutung |
|---|---|
| `language` | `en` / `de` |
| `use_gpu` | `true`/`false` – Vorschau über OpenGL (☰ → „Use graphics card …“), wirkt nach Neustart |
| `bg_auto_open` | `true`/`false` – Hintergrund-Editor nach dem Laden öffnen |
| `bg_model` | zuletzt gewähltes KI-Modell |
| `bg_visibility` | Durchsichtigkeit des entfernten Hintergrunds im Editor (0–100) |
| `last_dir`, `export_dir` | zuletzt benutzte Ordner |
| `persistent` | JSON mit gemerkten Werten (Druckbett, Qualität, Farben, Dicken …) |
**Test-Profil:** `HKCU\Software\RemStudio\RemStudio3D_test` (nur für Tests).

## KI-Modelle (Hintergrund-Entfernung)
**Wofür:** automatische Freistellung des Motivs.
**Wo:** `%LOCALAPPDATA%\RemStudio\models\*.onnx`; Download beim ersten Gebrauch von `https://github.com/danielgatis/rembg/releases/download/v0.0.0/<name>.onnx`.
**Modelle:** `isnet-anime` (Standard, Comic/Anime, ~176 MB) · `isnet-general-use` (Fotos, ~179 MB) · `u2netp` (klein, ~5 MB).
**Im Code:** `remstudio/bgremove.py` → `MODELS`, `ai_mask()`, `download_model()`, `grabcut()`, `refine()`, `composite()`

## Aus dem Quellcode starten – `start.bat`
**Wofür:** Programm ohne Bauen starten (Entwicklung).
**Voraussetzungen:** Python 3.10+ (`python` im PATH) beim ersten Start.
**Aufruf:**
    start.bat [bilddatei]        # richtet beim ersten Mal .venv ein (pip install -r requirements.txt)
    .venv\Scripts\python.exe app.py [bilddatei]
**Umgebungsvariablen:** `REMSTUDIO_NO_GL=1` (ohne OpenGL), `REMSTUDIO_SELFTEST=<datei>` (Selbsttest, siehe unten).
**Im Code:** `app.py` → `main()`

## Schnelltest – `tests/smoke_test.py`
**Wofür:** prüft ohne Bedienung: 3D-Netze geschlossen (alle Rahmenformen), keine losen Teile, Vorschau, Pinsel + Undo/Redo, GPU-Verschieben schnell, Projekt speichern/laden, Export STL+SVG, KI-Erkennung (falls Modell vorhanden), englische Oberfläche vollständig übersetzt.
**Voraussetzungen:** `.venv` eingerichtet. Läuft unsichtbar (offscreen, ohne OpenGL), nutzt das Test-Einstellungsprofil.
**Aufruf:**
    .venv\Scripts\python.exe tests\smoke_test.py            # alles (~1–2 min)
    .venv\Scripts\python.exe tests\smoke_test.py --no-gui   # nur Bildverarbeitung + 3D-Netz
**Beispiel:**
    → ✅ 3D-Netz geschlossen: circle, Rückplatte=False, motiv – 29912 Dreiecke
    → …
    → ✅ Alle Tests bestanden          (Exit-Code 0; bei Fehlern „❌ n Test(s) fehlgeschlagen“, Exit 1)
**Typische Fehler:** `UnicodeEncodeError` in der Konsole → `set PYTHONIOENCODING=utf-8` (F-008).
**Im Code:** `tests/smoke_test.py` → `test_core()`, `test_gui()`

## Bauen – `build.bat` / `build.py`
**Wofür:** erzeugt `RemStudio3D.exe` (+ Ordner `RemStudio3D_files`) und den Installer `RemStudio3D-Setup.exe` im Projektordner.
**Voraussetzungen:** `.venv`; Inno Setup 6.7+ (für den Installer; per `winget install JRSoftware.InnoSetup --scope user`); **RemStudio 3D darf nicht laufen** (F-012).
**So geht's:** `build.bat` doppelklicken (installiert bei Bedarf PyInstaller) – oder:
    .venv\Scripts\python.exe build.py
**Ablauf:** 1. `version_info.txt` aus `remstudio/__init__.py` erzeugen · 2. PyInstaller mit `RemStudio3D.spec` (Work/Dist in `%TEMP%\RemStudio3D-build`) · 3. EXE + `RemStudio3D_files` in den Projektordner kopieren · 4. `<ISCC> /Q /DSourceDir=… /DAppVersion=… installer\RemStudio3D.iss`
**Beispiel:**
    → == 1/3 Programm bauen (Version 1.0.0) … == 3/3 Installer bauen …
    → Fertig: …\RemStudio3D.exe  …\RemStudio3D-Setup.exe
**Typische Fehler:** „RemStudio3D.exe läuft noch“ → Programm schließen (F-012); `UnicodeDecodeError` (F-021, gelöst); `cmd /c build.bat` „nicht gefunden“ bei automatisiertem Aufruf → `build.py` direkt starten (F-027).
**Nur Installer neu bauen** (wenn das Programm unverändert ist):
    "<ISCC>" /Q "/DSourceDir=%TEMP%\RemStudio3D-build\dist\RemStudio3D" /DAppVersion=1.0.0 installer\RemStudio3D.iss
**Im Code:** `build.py` → `main()`, `is_running()`, `find_iscc()`, `write_version_info()`; `RemStudio3D.spec`; `installer/RemStudio3D.iss`

## EXE-Selbsttest
**Wofür:** prüft, ob die gebaute EXE startet, rechnet, 3D anzeigt, exportiert und die KI lädt.
**Aufruf (Git-Bash):**
    REMSTUDIO_SELFTEST="$TEMP/st.txt" ./RemStudio3D.exe; cat "$TEMP/st.txt"
**Beispiel:** → `ok shown=True items3d=1 files=2 ai_fg=0%` (ai_fg 0 % ist beim Beispielbild normal – keine Figur)
**Im Code:** `app.py` → `_selftest()`

## Logo und Installer-Bilder – `make_icon.py`
**Wofür:** erzeugt `icon.ico` (alle Größen 16–256) und `icon.png`; mit `--installer` die Bilder in `installer/`.
**Aufruf:**
    .venv\Scripts\python.exe make_icon.py              # icon.ico + icon.png
    .venv\Scripts\python.exe make_icon.py --installer  # zusätzlich installer\wizard_*.bmp
**Im Code:** `make_icon.py` → `render()`, `write_ico()`, `render_wizard_large()`, `render_wizard_small()`

## Bilder für die GitHub-Seite – `make_screenshots.py`
**Wofür:** erzeugt alle Bilder der README (Banner, „So geht's“, Rahmenformen, drehende 3D-Animation, Programm-Screenshots, Social-Preview) automatisch neu – z. B. nach Design-Änderungen.
**Voraussetzungen:** `.venv`; für `rotate.gif` zusätzlich Pillow (`.venv\Scripts\python.exe -m pip install pillow`, nur Werkzeug, nicht Teil des Programms). Für den Hintergrund-Editor-Screenshot muss das KI-Modell „isnet-anime“ schon heruntergeladen sein (sonst ohne KI-Ergebnis).
**So geht's:** Befehl starten, **nicht klicken**, solange Programmfenster kurz aufgehen (ca. 1–2 Minuten). Ergebnis in `docs/images/`.
**Aufruf / Optionen:**
    .venv\Scripts\python.exe make_screenshots.py                      # alles, Englisch + Deutsch
    .venv\Scripts\python.exe make_screenshots.py --lang de            # nur deutsche Bilder (*-de.png)
    .venv\Scripts\python.exe make_screenshots.py --only banner frames # nur bestimmte Bilder
    # Namen: banner, steps, frames, rotate, main, 3d, editor, export, social
**Beispiel:**
    → == en …  docs\images\banner.png 2560x820 … docs\images\rotate.gif 840x520, 60 Bilder, ~1500 KB … == de …
**Wichtig:** nutzt nur das eingebaute Beispielbild (`remstudio/samples.py`) – nie fremde/urheberrechtlich geschützte Bilder; Einstellungen nur im Test-Profil `RemStudio3D_test`; im Export-Dialog steht der neutrale Ordner `C:\3D prints` (kein persönlicher Pfad).
**Feature-Icons:** `docs/images/icons/*.svg` sind eigene, einfache Linien-Icons (nicht die Segoe-Schrift der App, siehe ENTSCHEIDUNGEN).
**Social-Preview:** `docs/images/social-preview.png` (1280×640) muss der Nutzer selbst hochladen: GitHub → Repo → Settings → General → „Social preview“ → Edit → Upload.
**Vorschau der README vor dem Push:** GitHub-Markdown-API rendern lassen (`<GH> api markdown`) und lokal per `python -m http.server` ansehen (Vorschau-Dateien in `.preview/`, steht in `.git/info/exclude`).
**Typische Fehler:** leere 2D-Vorschau (F-031), kaputte 3D-Ansicht/Shader-Fehler (F-030), Absturz „access violation“ (F-029), grauer Rand/abgeschnittene Texte bei 125 % Skalierung (F-031).
**Im Code:** `make_screenshots.py` → `main()`, `render()` (freigestelltes 3D-Bild per Schwarz/Weiß-Trick), `card_background()`, `shadowed()`

## Installer testen (ohne Risiko)
**Wofür:** Installation/Deinstallation prüfen, ohne den PC des Nutzers zu verändern.
**Aufruf (Git-Bash, Testordner statt echtem Ziel):**
    ./RemStudio3D-Setup.exe //VERYSILENT //SUPPRESSMSGBOXES //NORESTART //LANG=en "//DIR=<TESTORDNER>\inst" '//TASKS='
    "<TESTORDNER>\inst\unins000.exe" //VERYSILENT //SUPPRESSMSGBOXES //NORESTART
**Prüfen:** EXE + `unins000.exe` vorhanden, Startmenü-Verknüpfung „RemStudio 3D.lnk“, Uninstall-Eintrag in `HKCU\…\Uninstall`; nach Deinstallation alles weg, Modelle bleiben.
**Achtung:** Nie den GUI-Installer per Skript auf dem Bildschirm des Nutzers mit echtem Ziel durchklicken/hart beenden (F-023).
**Installer-Optionen:** `/ALLUSERS` = für alle Benutzer installieren (Adminrechte); Standard: aktueller Benutzer.

## Release auf GitHub veröffentlichen
**Wofür:** neue Version zum Download anbieten.
**Voraussetzungen:** `<GH>` angemeldet (`<GH> auth status` → „Logged in … Remomniac“); falls nicht: `<GH> auth login --web` – der **Nutzer** gibt den Gerätecode im Browser ein.
**So geht's:**
1. Version in `remstudio/__init__.py` erhöhen (z. B. `1.0.0` → `1.0.1`).
2. `.venv\Scripts\python.exe tests\smoke_test.py` → alles grün.
3. `build.bat` (Programm vorher schließen) – automatisiert lieber `.venv\Scripts\python.exe build.py` (F-027). Danach EXE-Selbsttest (→ `ok`).
4. Portable-ZIP erstellen: Ordner „RemStudio 3D/“ mit `RemStudio3D.exe` + `RemStudio3D_files/` → `RemStudio3D-<version>-portable.zip` (wird per `.gitignore` ignoriert). PowerShell:
       $d = "$env:TEMP\rs_portable\RemStudio 3D"; New-Item -ItemType Directory -Force $d | Out-Null
       Copy-Item .\RemStudio3D.exe $d; Copy-Item .\RemStudio3D_files $d -Recurse
       Compress-Archive -Path $d -DestinationPath .\RemStudio3D-1.0.1-portable.zip -Force
   Release-Text: letzte Datei in `docs/release-notes/` kopieren → `vX.Y.Z.md`, Versionsnummern + Abschnitt „What's new“ anpassen.
5. Commit + Tag + Push + Release:
       git add -A && git commit -m "…"
       git tag -a v1.0.1 -m "RemStudio 3D v1.0.1" && git push && git push origin v1.0.1
       <GH> release create v1.0.1 RemStudio3D-Setup.exe RemStudio3D-1.0.1-portable.zip --repo Remomniac/RemStudio-3D --title "RemStudio 3D v1.0.1" --notes-file docs/release-notes/v1.0.1.md --latest
**Hinweise:** Release-Texte englisch; Hinweis auf SmartScreen beibehalten (F-025). Commit-Nachrichten enden mit `Co-Authored-By: Claude …`.
**Git-Einstellungen (nur dieses Repo):** `user.name=Remomniac`, `user.email=<ID>+Remomniac@users.noreply.github.com`, Credential-Helper = `gh auth git-credential`.

## GitHub-Beschreibung / Topics ändern
    <GH> repo edit Remomniac/RemStudio-3D --description "…" --add-topic <thema>
    <GH> release edit v1.0.0 --repo Remomniac/RemStudio-3D --notes-file notes.md
