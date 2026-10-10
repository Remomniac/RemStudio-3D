# Entscheidungen – RemStudio 3D

> Vor neuen Lösungsansätzen hier nachsehen. Einträge vom 2026-10-10 wurden aus der Entwicklung nachgetragen.

## 2026-10-10 – Technik: Python + PySide6 (Qt) + OpenCV, Auslieferung per PyInstaller
**Gewählt:** Python 3.12, PySide6, OpenCV, NumPy, mapbox_earcut, pyqtgraph(OpenGL), ONNX Runtime – weil Bildverarbeitung damit robust und schnell umsetzbar ist; PyInstaller erzeugt eine EXE ohne Python-Installation.
**Alternativen:** .NET/WPF (nur Laufzeit vorhanden, Bildverarbeitung selbst schreiben – viel Aufwand).
**Hinweis:** PyInstaller **onedir** (schneller Start) statt onefile (würde ~300 MB bei jedem Start entpacken).

## 2026-10-10 – 3D-Netz aus Konturen extrudieren (statt Pixel-/Voxel-Netz)
**Gewählt:** Konturen (`findContours`, RETR_CCOMP) → earcut-Triangulierung → Seitenwände; Rahmen-Überhöhung als gestapelte Extrusion – glatte Kanten, wenige Dreiecke.
**VERWORFEN:** pro Pixel Quader – Millionen Dreiecke, Treppenkanten.

## 2026-10-10 – Stege für lose Teile: minimaler Spannbaum über Voronoi-Nachbarschaft
**Gewählt:** `distanceTransformWithLabels` + Kruskal (MST) – kürzeste Gesamtlänge, ein Durchlauf, schnell.
**VERWORFEN:** Teil für Teil an den Hauptteil hängen (viele Distanztransformationen, langsam).
**Hinweis:** Mit Rückplatte keine Stege nötig.

## 2026-10-10 – Hintergrund-Entfernung: rembg-ONNX-Modelle, bei Bedarf herunterladen
**Gewählt:** Modelle aus den rembg-GitHub-Releases, Download beim ersten Gebrauch nach `%LOCALAPPDATA%\RemStudio\models`; Standardmodell **isnet-anime** – weil es bei Comics die Schultern behielt.
**Alternativen:** isnet-general-use (schnitt beim Testbild die Schultern ab), u2netp (klein/schnell, gröber); GrabCut per Rechteck als Weg ohne KI.
**VERWORFEN:** Modelle in die EXE packen (+180 MB je Modell).

## 2026-10-10 – Vorschau: GPU-Ebenen + mm-Szeneneinheiten, keine schnelle Halbauflösung
**Gewählt:** Vorschau in zwei Ebenen (Wand/Rahmen + transparente Motiv-Ebene), OpenGL-Viewport; beim Verschieben/Skalieren/Drehen nur die Ebene transformieren (≈ 0,1–4 ms statt ≈ 200 ms), exakt gerechnet wird nach 220 ms Ruhe. Szene in **Millimetern** → Zoom bleibt bei Größenänderungen gleich.
**VERWORFEN:** abwechselnd schnelle Halbauflösung und volle Vorschau – Markierungen flackerten („springt hin und her“); automatisches Neu-Einpassen bei jeder Größenänderung (Bild sprang).
**Option:** GPU im Menü ☰ abschaltbar (`use_gpu`), Umgebungsvariable `REMSTUDIO_NO_GL`.

## 2026-10-10 – Design: dunkel, „Liquid Glass“-Formen, Akzent Orange
**Gewählt:** eigenes Stylesheet (`theme.py`), schwebende Inseln, Pillen-Knöpfe, iOS-Schalter (`Toggle`), Icons aus „Segoe Fluent Icons“; Akzent `#f97316` (vorher Blau, auf Nutzerwunsch Orange). 3D-Ansicht mit hellem Hintergrund (Nutzerwunsch).

## 2026-10-10 – Regler: Mausrad nur über der Zahl, Feinjustierung mit Shift, 2 Nachkommastellen
**Gewählt:** Schieber ignorieren das Rad (Seitenleiste scrollt), Zahl reagiert; Shift-Ziehen = 10× feiner; mm/mm²/° mit 0,01-Schritten (Nutzerwunsch).

## 2026-10-10 – Hintergrund-Schritt direkt nach dem Laden
**Gewählt:** Nach „Bild öffnen“/Einfügen startet der Editor („Schritt 1 von 2“), KI läuft automatisch; „Weiter“ / „Hintergrund behalten“; abschaltbar (`bg_auto_open`). Nicht bei Projekt/Beispielbild.

## 2026-10-10 – Name „RemStudio 3D“, Projektdateien `.remstudio`
**Gewählt:** Umbenennung überall (Code, Paket `remstudio/`, EXE, Registry, Datenordner). Alte Einstellungen/Modelle einmalig verschoben – **kein** Kompatibilitätscode mit dem alten Namen im Programm. Einzige Ausnahme: alte Projektdateien `.rahmen` lassen sich weiter öffnen.

## 2026-10-10 – Sprachen: deutsche Quelltexte als Schlüssel, Englisch Standard
**Gewählt:** `i18n.py` mit `EN`-Wörterbuch; feste Texte per `translate_tree()` nach dem Aufbau eines Fensters, dynamische per `T()` mit Platzhaltern; Sprachwechsel mit Neustart; Locale + Qt-Übersetzung (`qtbase_de`) passend.
**Alternativen:** Qt Linguist (.ts/.qm) – mehr Werkzeug-Aufwand, kein Vorteil bei 2 Sprachen.

## 2026-10-10 – Installer: Inno Setup 6.7, dunkel, pro Benutzer
**Gewählt:** Inno Setup (`WizardStyle=modern dark`, eigene Bilder), Installation ohne Adminrechte nach `{autopf}` (= `%LOCALAPPDATA%\Programs`), Sprache en/de (Englisch vorausgewählt, setzt die App-Sprache), Deinstallation fragt nach Löschen von Modellen/Einstellungen.
**VERWORFEN:** Dialog „Für mich / für alle Benutzer“ (`PrivilegesRequiredOverridesAllowed=dialog`) – unnötig technisch; jetzt nur per `/ALLUSERS`.
**VERWORFEN:** eigener Installer mit PySide6 – mehr Aufwand/Risiko, Deinstallation selbst bauen.

## 2026-10-10 – Build-Ausgabe im Hauptordner
**Gewählt:** `build.py` legt nur `RemStudio3D.exe` (+ `RemStudio3D_files/`) und `RemStudio3D-Setup.exe` in den Projektordner; Zwischendateien in `%TEMP%\RemStudio3D-build`.
**VERWORFEN:** `dist/` und `build/` im Projekt (Nutzer fand das verwirrend).

## 2026-10-10 – GitHub: öffentlich, MIT, noreply-Adresse
**Gewählt:** Repo `Remomniac/RemStudio-3D`, MIT-Lizenz (Nutzer: „soll Open Source sein“), Commits mit GitHub-noreply-E-Mail (echte Adresse bleibt privat), Login über GitHub CLI (`gh`, Gerätecode im Browser durch den Nutzer). Binärdateien nur als Release-Assets, nie im Repo. README englisch (Haupt) + `README.de.md`.

## 2026-10-10 – Code-Signierung gegen SmartScreen (F-025)
**Empfohlen:** **SignPath Foundation** – kostenlos für Open-Source-Projekte (OSI-Lizenz ✔); Voraussetzungen: automatischer Build (GitHub Actions) mit SignPath-Anbindung, „Code Signing Policy“ auf der Projektseite; Herausgeber erscheint als „SignPath Foundation“. Antrag stellt der Nutzer.
**Alternativen:** OV-Zertifikat einer Zertifizierungsstelle (jährliche Kosten, Warnung verschwindet erst mit Reputation).
**VERWORFEN:** Microsoft Artifact Signing (Trusted Signing) als Privatperson – laut Microsoft-Doku nur für Einzelpersonen in USA/Kanada; selbstsigniertes Zertifikat – hilft nicht gegen SmartScreen.

## 2026-10-10 – Doku: öffentlich → Platzhalter
**Gewählt:** Doku-Dateien enthalten keine persönlichen Pfade/E-Mails/Windows-Benutzernamen (Repo ist öffentlich); Befehle mit relativen Pfaden oder `%LOCALAPPDATA%`.
