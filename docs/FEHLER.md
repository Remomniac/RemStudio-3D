# Fehler-Datenbank – RemStudio 3D

> Vor jeder Fehlersuche hier nach der Meldung suchen. IDs fortlaufend vergeben (nächste freie ID: **F-027**).
> Einträge F-001 … F-025 wurden am 2026-10-10 aus der Entwicklung nachgetragen (Zeiten ungefähr).

## F-001 – Automatische Schwelle (Otsu) = 0 → Motiv verschwindet komplett
**Status:** 🟢 gelöst
**Wann/Wo:** 2026-10-10 · `remstudio/processing.py` → `otsu_threshold()` · Windows 11 · vor v1.0.0
**Fehlermeldung:** keine – Ergebnis war nur der Rahmen, kein Motiv (Netz mit 48 Dreiecken).
**Nachstellen:** reines Schwarz/Weiß-Bild (nur Werte 0 und 255) laden, „Schwelle automatisch“ an.
**Ursache:** `cv2.threshold(..., THRESH_OTSU)` liefert bei zweiwertigen Bildern die Obergrenze der dunklen Klasse (= 0); Vergleich `warped < 0` trifft nie zu.
**Versuche:** 1. Mitte zwischen den Mittelwerten beider Klassen verwenden → ✅
**Lösung:** `otsu_threshold()` gibt `(mean(dunkel) + mean(hell)) / 2` zurück (Fallback 128).
**Vorbeugen:** Schwellwert-Code immer auch mit reinem S/W-Bild testen.

## F-002 – 3D-Netz nicht geschlossen bei Kreisrahmen mit Aufhängeöse
**Status:** 🟢 gelöst
**Wann/Wo:** 2026-10-10 · `remstudio/processing.py` → `apply_hanging()` (Öse)
**Fehlermeldung:** keine – eigener Test meldete `manifold=False` (22 Kanten ohne Gegenkante).
**Nachstellen:** Rahmenform Kreis + Aufhängung „Öse oben“, Export.
**Ursache:** Öse war nur über einen sehr dünnen Hals mit dem Kreisrahmen verbunden; Loch der Öse berührte fast den Außenrand → entartetes Polygon.
**Versuche:** 1. Steg der Öse bis tief in den Rahmen (`top + fw*0.8`) und nicht mehr mit Außenform schneiden → ✅
**Lösung:** siehe Versuch 1.
**Vorbeugen:** Anbauteile immer großzügig mit dem Rahmen überlappen lassen.

## F-003 – Triangulierung verliert ein Dreieck bei 1-Pixel-Stegen
**Status:** 🟢 gelöst
**Wann/Wo:** 2026-10-10 · `remstudio/mesh.py` → `mask_polygons()`, `_extrude_one()`
**Fehlermeldung:** keine – `top tris expected 2878 got 2877`, Netz nicht geschlossen.
**Ursache:** Außen- und Lochkontur laufen bei 1 px breitem Material durch dieselben Pixelmittelpunkte → earcut bekommt sich berührende Ringe.
**Versuche:** 1. Maske vor `findContours` 2× (nearest) hochskalieren (K=2) + Fallback ohne Vereinfachung, wenn die Dreieckszahl nicht stimmt → ✅
**Lösung:** K=2-Hochskalierung in `mask_polygons()`; `_extrude_one(strict=True)` gibt `None` bei unvollständiger Triangulierung, dann Fallback.
**Vorbeugen:** Netz-Test „jede gerichtete Kante hat genau eine Gegenkante“ (in `tests/smoke_test.py`).

## F-004 – Texte in Eingabefeldern/Häkchen unsichtbar (Windows-Dunkelmodus)
**Status:** 🟢 gelöst (später ohnehin dunkles Design)
**Wann/Wo:** 2026-10-10 · damals `app.py` → Stylesheet/Palette
**Fehlermeldung:** keine – weiße Schrift auf weißem Grund.
**Ursache:** Windows-Dunkelmodus setzt helle Textfarben; Palette wurde im Test nicht gesetzt.
**Lösung:** `styleHints().setColorScheme(...)` + vollständige eigene Palette + Farben im Stylesheet (heute `remstudio/theme.py` → `setup_app()`).
**Vorbeugen:** Farben nie dem System überlassen; Screenshot-Test auch mit Systemdunkelmodus.

## F-005 – Zahlenfeld (QDoubleSpinBox) zeigt keine Zahl
**Status:** 🟢 gelöst
**Wann/Wo:** 2026-10-10 · Stylesheet + `ButtonSymbols.NoButtons`
**Fehlermeldung:** keine – `lineEdit().geometry()` = `QRect(0, 3, 1, 22)` (Breite 1 px).
**Ursache:** Qt-Fehler: mit Stylesheet + NoButtons belegen die (unsichtbaren) Pfeil-Knöpfe den ganzen Platz.
**Versuche:** 1. `::up-button {width:0}` → ❌ 2. zusätzlich `subcontrol-origin: border; height: 0` → ✅
**Lösung:** `QAbstractSpinBox::up-button, ::down-button { subcontrol-origin: border; width: 0px; height: 0px; border: none; }` (in `theme.py`).

## F-006 – 3D-Kamera beim ersten Öffnen im Modell
**Status:** 🟢 gelöst · `remstudio/viewer3d.py` → `set_meshes()`
**Ursache:** Kamera wurde nur bei großer Größenänderung neu gesetzt; Startwert `_size=200` passte zufällig.
**Lösung:** `_size = None` am Anfang → erste Anzeige setzt die Kamera immer.

## F-007 – 3D-Vorschau zu dunkel (helle Rückplatte fast schwarz)
**Status:** 🟢 gelöst · `remstudio/viewer3d.py`
**Ursache:** pyqtgraph-Shader „shaded“ dunkelt stark ab.
**Lösung:** eigene Beleuchtung pro Dreieck `_shade()` (Umgebungslicht + 2 Lichter), `shader=None` mit `faceColors`.

## F-008 – Smoke-Test bricht ohne Ausgabe ab
**Status:** 🟢 gelöst (nur Test)
**Fehlermeldung:** keine sichtbar – eigener `sys.excepthook` schluckte `UnicodeEncodeError` (✔-Zeichen in cp1252-Konsole).
**Lösung:** Tests mit `PYTHONIOENCODING=utf-8` starten.

## F-009 – Löschbefehl mit Variable im Pfad blockiert
**Status:** 🟢 umgangen (Werkzeug)
**Fehlermeldung:**
    Permission for this command was denied by a built-in Claude Code safety check … Dangerous rm operation detected
**Ursache:** `rm -rf "$S/…"` – Ziel nicht statisch auflösbar → Sicherheitsprüfung verweigert (ganzer Befehl wird nicht ausgeführt).
**Lösung:** Löschen nur mit festen, vollständigen Pfaden (PowerShell `Remove-Item -LiteralPath "…"`), keine Variablen.

## F-010 – Striche/Schlieren beim Bewegen des Pinsel-Cursors über den grauen Bereich
**Status:** 🟢 gelöst (vom Nutzer gemeldet, Screenshot)
**Wann/Wo:** 2026-10-10 · `remstudio/canvas.py` → `Canvas.__init__()`
**Ursache:** QGraphicsView zeichnet nur Teilbereiche neu; der dünne, kantengeglättete Kreis-Cursor ragt über sein boundingRect → Reste an den 4 Extrempunkten.
**Lösung:** `setViewportUpdateMode(FullViewportUpdate)` (heute ohnehin mit OpenGL-Viewport).
**Vorbeugen:** Offscreen-Tests zeigen das nicht (zeichnen immer komplett) – nur am echten Bildschirm prüfbar.

## F-011 – Tests verändern die echten Programmeinstellungen
**Status:** 🟢 gelöst
**Ursache:** Tests nutzten `QSettings("RemStudio","RemStudio3D")`: z. B. KI-Modell blieb auf „general-use“ hängen, Export-Ordner zeigte in Temp.
**Lösung:** In Tests `mw.QSettings` auf Profil `RemStudio3D_test` umbiegen (so in `tests/smoke_test.py`); echte Einstellungen nie löschen.

## F-012 – EXE-Build bricht ab, `dist` beschädigt, wenn RemStudio läuft
**Status:** 🟢 gelöst
**Fehlermeldung:**
    PermissionError: [WinError 5] Zugriff verweigert: '…\dist\RemStudio3D\_internal\cv2\cv2.pyd'
    … danach beim Start der alten EXE:
    ImportError: OpenCV loader: missing configuration file: ['config.py']. Check OpenCV installation.
**Ursache:** PyInstaller löscht den Zielordner; laufendes Programm sperrt Dateien → Abbruch mittendrin.
**Lösung:** `build.py` → `is_running()` bricht vorher mit Hinweis ab; Build-Zwischendateien liegen im Temp-Ordner.
**Vorbeugen:** Vor dem Bauen fragen, ob das Programm geschlossen werden darf.

## F-013 – Untere Werkzeugleiste klebt oben links
**Status:** 🟢 gelöst · `remstudio/widgets.py` → `CanvasArea.relayout()`
**Ursache:** `isVisible()` ist vor dem Anzeigen des Fensters immer `False` → Leiste wurde nicht positioniert.
**Lösung:** `not w.isHidden()` statt `isVisible()`, zusätzlich `relayout()` in `showEvent()`.

## F-014 – Gewählte Segment-Knöpfe haben graue statt weiße Schrift
**Status:** 🟢 gelöst · `remstudio/theme.py`
**Ursache:** Regel `QFrame#segment:disabled QToolButton {color: …}` – Qt wertet Pseudo-Zustände an Vorfahren nicht aus → Regel galt immer.
**Lösung:** `QFrame#segment QToolButton:disabled` (Pseudo-Zustand nur am Ziel-Element).
**Vorbeugen:** In Qt-Stylesheets `:disabled/:hover/:checked` nur am letzten Selektor-Teil verwenden.

## F-015 – Screenshots der GPU-Vorschau weiß/schwarz
**Status:** 🟡 Workaround (nur Tests)
**Ursache:** `QWidget.grab()` bzw. `QOpenGLWidget.grabFramebuffer()` erfassen den QGraphicsView-Inhalt im OpenGL-Viewport nicht.
**Lösung:** Szene direkt rendern: `canvas.scene().render(QPainter(img), img.rect(), sichtbarer_Bereich)`; 3D-Ansicht: `viewer.view.grabFramebuffer()` funktioniert.

## F-016 – Bildschirmfoto erfasste fremde Fenster des Nutzers
**Status:** 🟢 vermieden (Regel)
**Ursache:** `grabWindow(0, x, y, …)` fotografiert den Bildschirmbereich – war das Fenster verdeckt, kam fremder Inhalt mit.
**Lösung:** Bilder gelöscht; nur noch eigene Fenster/Szenen rendern bzw. `PrintWindow` auf das eigene Fenster.

## F-017 – Mausrad über Schieberegler scrollt die Seitenleiste nicht
**Status:** 🟢 gelöst · `remstudio/widgets.py` → `Slider.wheelEvent()`
**Ursache:** `e.ignore()` reicht nicht zuverlässig weiter (künstliche Events werden nicht an Eltern gereicht).
**Lösung:** Rad-Event explizit an das Viewport der umgebenden `QAbstractScrollArea` senden.

## F-018 – Patch-Skripte per Bash-Heredoc zerstören `\n` in Strings
**Status:** 🟢 umgangen (Werkzeug)
**Fehlermeldung:**
    SyntaxError: unterminated string literal (detected at line 1554)
**Ursache:** In Heredocs wurden `\n`-Escapes zu echten Zeilenumbrüchen.
**Lösung:** Patch-Skripte mit dem Write-Werkzeug als Datei schreiben und dann ausführen; danach `py_compile`.

## F-019 – Absturz im Test-Skript beim Bild-Auslesen (Exit 139)
**Status:** 🟢 gelöst (nur Test) · Ursache: `np.array(qimage.constBits())` auf temporärem QImage. Lösung: QImage in Variable halten, `bytes(img.constBits())`.

## F-020 – „Signal source has been deleted“ beim Schließen des Editors während die KI rechnet
**Status:** 🟢 gelöst · `remstudio/bg_editor.py` → `_Job.run()`
**Fehlermeldung:**
    RuntimeError: Signal source has been deleted
**Lösung:** Emittieren der Signale in `try/except RuntimeError` (Fenster schon zu → Ergebnis verwerfen).

## F-021 – `build.py` bricht mit UnicodeDecodeError ab
**Status:** 🟢 gelöst · `build.py` → `is_running()`
**Fehlermeldung:**
    UnicodeDecodeError: 'charmap' codec can't decode byte 0x81 in position 74: character maps to <undefined>
**Ursache:** `tasklist`-Ausgabe in OEM-Codepage mit Umlauten, `text=True` dekodiert mit cp1252.
**Lösung:** Bytes lesen, `decode("ascii", "replace")`.

## F-022 – Installer-Testskript: `wmic` fehlt unter Windows 11
**Status:** 🟡 Workaround (nur Test)
**Fehlermeldung:**
    FileNotFoundError: [WinError 2] Das System kann die angegebene Datei nicht finden
**Lösung:** Fenster per `EnumWindows` über den Titel finden („Select Setup Language“, „Setup - RemStudio 3D“).

## F-023 – Installer mitten in der Installation beendet
**Status:** 🟢 bereinigt (Regel)
**Wann/Wo:** 2026-10-10 · Test des Installers (GUI) auf dem Bildschirm des Nutzers
**Ursache:** Das Testskript scheiterte (F-022); der Installer blieb offen, der Nutzer klickte sich durch; das Fenster wurde dann per `Stop-Process` hart beendet → halbe Installation (`unins000.dat` 0 Byte) in `%LOCALAPPDATA%\Programs\RemStudio 3D`.
**Lösung:** Unvollständigen Ordner gelöscht (keine Verknüpfungen/Registry-Einträge vorhanden). Installer-Tests nur noch still: `/VERYSILENT /DIR=<Testordner>` + stilles Deinstallieren; GUI-Bilder nur mit Test-`/DIR` und sofortigem Abbruch.
**Vorbeugen:** Vor dem Beenden fremder/benutzersichtbarer Prozesse prüfen, was sie gerade tun.

## F-024 – Ordner-Umbenennung: „Datei wird von einem anderen Prozess verwendet“
**Status:** 🟢 gelöst
**Fehlermeldung:**
    Rename-Item : Der Prozess kann nicht auf die Datei zugreifen, da sie bereits von einem anderen Prozess verwendet wird.
**Ursache:** Die eigene Shell hatte den Projektordner als Arbeitsverzeichnis.
**Lösung:** Shell zuerst in den Elternordner wechseln (`cd ..`), dann umbenennen.

## F-025 – SmartScreen: „Der Computer wurde durch Windows geschützt“
**Status:** 🟡 Workaround
**Wann/Wo:** 2026-10-10 · `RemStudio3D-Setup.exe` v1.0.0 beim ersten Start auf fremden PCs (vom Nutzer gemeldet, Screenshot)
**Fehlermeldung:**
    Der Computer wurde durch Windows geschützt
    Von Microsoft Defender SmartScreen wurde der Start einer unbekannten App verhindert. …
    App: RemStudio3D-Setup.exe · Herausgeber: Unbekannter Herausgeber
**Ursache:** Installer/EXE sind nicht digital signiert und (noch) ohne Reputation.
**Versuche:** 1. Recherche Signier-Möglichkeiten → Ergebnis in ENTSCHEIDUNGEN.md (2026-10-10 „Code-Signierung“).
**Lösung (vorläufig):** Hinweis in README/Release: „Weitere Informationen → Trotzdem ausführen“.
**Dauerhaft:** Code-Signierung (Empfehlung: SignPath Foundation, kostenlos für Open Source – Antrag durch den Nutzer).

## F-026 – Kreisrahmen: 3D-Netz nicht geschlossen (Beispielbild, 6 px/mm)
**Status:** 🟢 gelöst – veröffentlicht in v1.0.1 (v1.0.0 enthält den Fehler noch)
**Wann/Wo:** 2026-10-10 · `remstudio/processing.py` → `process()` Schritt 8; `remstudio/mesh.py` → `mask_polygons()`
**Fehlermeldung:** keine – `tests/smoke_test.py`:
    ❌ 3D-Netz geschlossen: circle, Rückplatte=False, motiv – 91400 Dreiecke
    ❌ 3D-Netz geschlossen: circle, Rückplatte=True, motiv – 74300 Dreiecke
**Nachstellen:** Beispielbild laden, Rahmenform „Kreis / Oval“ (mit/ohne Öse), Vorschau-Auflösung 6 px/mm.
**Ursache:** Zwei winzige, benachbarte Löcher (0,0 und 0,1 mm²) entstanden **nach** dem Schritt „Winzige Löcher schließen“
(durch Stege/Rahmen/Aufhängung). Jedes Loch allein triangulierte, zusammen fehlte ein Dreieck (auch ohne Vereinfachung).
**Versuche:**
1. Diagonal-Muster gesucht → ❌ keine vorhanden
2. Löcher einzeln trianguliert → Ursache gefunden (Kombination der zwei Mini-Löcher)
3. Mini-Löcher am Ende nochmals schließen + Löcher < 0,05 mm² im Netz ignorieren → ✅
**Lösung:** `process()`: vor dem letzten `fix_diagonals()` `fill_small_holes(combined, max(p.min_hole_mm2, 0.2)·ppm²)`;
`mask_polygons()`: Löcher mit Fläche ≤ 0,05 mm² weglassen. Ergebnis zusätzlich kleiner (≈ 30 000 statt 91 000 Dreiecke).
**Getestet:** Smoke-Test grün; alle 5 Formen × Rückplatte an/aus bei 10 und 16 px/mm geschlossen.
**Vorbeugen:** `tests/smoke_test.py` vor jedem Release laufen lassen.

## F-027 – `cmd /c "build.bat"` aus dem PowerShell-Tool: „Befehl nicht gefunden“
**Status:** 🟡 Workaround
**Wann/Wo:** 2026-10-10 · `build.bat` · Windows 11, Aufruf durch Claude über das PowerShell-Werkzeug · v1.0.1-Build
**Fehlermeldung:**
    cmd : Der Befehl "build.bat" ist entweder falsch geschrieben oder
    konnte nicht gefunden werden.
**Nachstellen:** Im PowerShell-Werkzeug von Claude `cmd /c "build.bat < NUL"` im Projektordner ausführen.
**Ursache:** unklar, Vermutung: `cmd` startet dort nicht im Projektordner (bzw. Pfad mit Leerzeichen „RemStudio Projekt“). Doppelklick auf `build.bat` ist nicht betroffen.
**Versuche:**
1. `cmd /c "build.bat < NUL"` → ❌ Meldung oben
2. Direkt `.venv/Scripts/python.exe build.py` (Bash-Werkzeug, Projektordner) → ✅ Build fertig
**Lösung:** Bei automatisiertem Bauen `build.py` direkt aufrufen (PyInstaller ist in `.venv` installiert). `build.bat` enthält ohnehin `pause` und ist für Doppelklick gedacht.
**Vorbeugen:** siehe ANLEITUNG „Bauen“ / „Release“.

## F-029 – make_screenshots: „Windows fatal exception: access violation“ bei numpy + QImage
**Status:** 🟢 gelöst
**Wann/Wo:** 2026-10-10 · `make_screenshots.py` → `main()` (Bild „steps“), `crop_alpha()` · Windows 11 · PySide6 6.12
**Fehlermeldung:**
    Windows fatal exception: access violation
    Current thread … File "…make_screenshots.py", line 316 in main
**Nachstellen:** `np.frombuffer(img.convertToFormat(...).constBits(), …)` – das konvertierte QImage ist ein Zwischenobjekt und wird sofort freigegeben.
**Ursache:** numpy liest Speicher eines bereits gelöschten QImage.
**Versuche:** 1. Zwischenobjekt in Variable halten + sofort `.copy()` → ✅
**Lösung:** Hilfsfunktion `qimage_to_numpy()` (hält das konvertierte Bild, kopiert die Daten).
**Vorbeugen:** QImage→numpy immer über `qimage_to_numpy()`.

## F-030 – Zweite 3D-Ansicht: „GLError … glGetAttribLocation … ungültiger Wert“
**Status:** 🟢 gelöst
**Wann/Wo:** 2026-10-10 · `make_screenshots.py` (eigener `Viewer3D` + 3D-Ansicht im Hauptfenster) · pyqtgraph 0.14
**Fehlermeldung:**
    OpenGL.error.GLError: GLError(
    	err = 1281,
    	description = b'ung\xfcltiger Wert',
    	baseOperation = glGetAttribLocation,
    	cArguments = (9, b'a_position\x00'), …
    Error while drawing item <pyqtgraph.opengl.items.GLMeshItem.GLMeshItem …>.
**Nachstellen:** zwei `GLViewWidget` in einem Programm, ohne gemeinsame OpenGL-Kontexte → die zweite Ansicht bleibt leer.
**Ursache:** pyqtgraph teilt Shader-Programme zwischen Ansichten; ohne „shared contexts“ gehören sie nur zum ersten Kontext.
**Versuche:** 1. `QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)` vor dem Erzeugen der QApplication → ✅
**Lösung:** siehe Versuch 1 (in `make_screenshots.py`). Die App selbst hat nur eine 3D-Ansicht – nicht betroffen.
**Vorbeugen:** Sobald irgendwo eine zweite 3D-Ansicht entsteht, das Attribut auch in `app.py` setzen.

## F-031 – Screenshots: leere 2D-Vorschau, grauer Rand, abgeschnittene Texte
**Status:** 🟢 gelöst
**Wann/Wo:** 2026-10-10 · `make_screenshots.py` → `win.grab()` · Windows 11 mit 125 % Anzeige-Skalierung
**Fehlermeldung:** keine – Bildfehler: (a) 2D-Vorschau schwarz/leer, (b) Screenshot 1872×1197 statt 1512×972 mit grauem Bereich, (c) nach Abschalten der Skalierung Texte abgeschnitten („Line art / comic (recon“).
**Ursache:** (a) `QWidget.grab()` erfasst den OpenGL-Viewport der 2D-Vorschau nicht; (b) Fenster auf einem Bildschirm mit 125 % – grab-Bild und Zeichnung passen nicht zusammen; (c) ohne High-DPI-Skalierung rechnet Qt Schriften weiter mit 120 dpi.
**Versuche:**
1. `REMSTUDIO_NO_GL=1` (2D-Vorschau ohne OpenGL, sieht gleich aus) → ✅ (a)
2. `QT_ENABLE_HIGHDPI_SCALING=0` → ✅ (b), aber ❌ (c)
3. zusätzlich `QT_FONT_DPI=96` → ✅ (c)
**Lösung:** alle drei Umgebungsvariablen am Anfang von `make_screenshots.py`.
**Vorbeugen:** Screenshots nur über `make_screenshots.py` erzeugen.

> F-028 (Installer aus langem Ordnerpfad) steht im lokalen Branch `signpath` – gehört zur zurückgestellten SignPath-Vorbereitung.
