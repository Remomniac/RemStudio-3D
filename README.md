<p align="center">
  <img src="icon.png" width="128" alt="RemStudio 3D Logo">
</p>

<h1 align="center">RemStudio 3D</h1>

<p align="center">
  Verwandelt Bilder und Zeichnungen in druckfertige 3D-Wandbilder mit Rahmen – als STL für den 3D-Drucker.
</p>

<p align="center">
  <a href="https://github.com/Remomniac/RemStudio-3D/releases/latest"><img alt="Release" src="https://img.shields.io/github/v/release/Remomniac/RemStudio-3D?color=f97316"></a>
  <a href="LICENSE"><img alt="Lizenz: MIT" src="https://img.shields.io/badge/Lizenz-MIT-f97316"></a>
  <img alt="Windows 10/11" src="https://img.shields.io/badge/Windows-10%20%7C%2011-1a1b1f">
</p>

---

## Funktionen

- **Hintergrund entfernen** direkt nach dem Laden: automatisch per KI (läuft lokal auf dem PC), alternativ per
  Rechteck ohne KI; Nachbessern mit „Behalten“-/„Entfernen“-Pinsel und halbtransparenter Vorschau des Originals
- **Motiv-Erkennung** für Strichzeichnungen, Comics, Logos, Silhouetten und Fotos (Skizze/Kanten)
- **Rahmen:** Rechteck, abgerundet, Kreis/Oval, Sechseck oder ohne Rahmen; Breite, Höhe, Rahmenbreite, Eckenradius
- **Motiv platzieren:** verschieben, skalieren (auch über den Rahmen hinaus), drehen, spiegeln, zuschneiden –
  in Echtzeit über die Grafikkarte
- **Druckbarkeit:** lose Teile werden automatisch mit kürzesten Stegen verbunden, Prüfung auf zu dünne Linien
  und zu enge Lücken
- **Nachbessern:** Pinsel, Radierer, Steg-Werkzeug, Rückgängig/Wiederholen
- **3D:** Motiv- und Rahmendicke, Rückplatte für zweifarbigen Druck (mit Angabe der Farbwechsel-Höhe),
  Aufhängung (Löcher oder Öse), drehbare 3D-Vorschau
- **Export:** STL (einzeln/kombiniert), automatisches Aufteilen großer Bilder auf Druckbett-Größe,
  zusätzlich SVG (Laser/Plotter) und PNG
- **Projekte** speichern und öffnen (`.remstudio`) inkl. aller Korrekturen
- Modernes dunkles Design, präzise Regler (0,01 mm; Umschalttaste = Feinjustierung)
- Englisch und Deutsch

## Installieren & Starten

| Datei (nach dem Bauen im Hauptordner) | Wofür |
|---|---|
| `RemStudio3D-Setup.exe` | **Installer** – installiert RemStudio 3D für den aktuellen Benutzer (ohne Administratorrechte), mit Startmenü- und Desktop-Verknüpfung sowie Deinstallation über die Windows-Einstellungen. |
| `RemStudio3D.exe` | Programm **direkt starten**, ohne Installation (benötigt den Ordner `RemStudio3D_files` daneben). |
| `start.bat` | Aus dem Quellcode starten – beim ersten Mal wird automatisch eine Python-Umgebung eingerichtet. |

**Sprache:** Englisch (Standard) oder Deutsch – umschaltbar oben rechts über **EN/DE** bzw. im Installer.

**Voraussetzungen:** Windows 10/11 (64 Bit). Zum Bauen bzw. Starten aus dem Quellcode: Python 3.10+;
für den Installer zusätzlich [Inno Setup 6.7+](https://jrsoftware.org/isinfo.php).

## Selbst bauen

`build.bat` doppelklicken (RemStudio 3D darf dabei nicht geöffnet sein). Das Skript `build.py`
1. baut das Programm mit PyInstaller (Zwischendateien im Temp-Ordner),
2. legt `RemStudio3D.exe` + `RemStudio3D_files` in den Hauptordner,
3. erzeugt mit Inno Setup den Installer `RemStudio3D-Setup.exe`.

Die fertigen Dateien sind per `.gitignore` vom Repository ausgeschlossen – für GitHub am besten als
**Release** hochladen (den Installer).

## Bedienung in Kürze

1. Bild per Drag & Drop, „Bild öffnen“ oder Strg+V laden.
2. Hintergrund entfernen (startet automatisch) → „Weiter“ – oder „Hintergrund behalten“.
3. Unter ① die Bildart wählen und mit den Reglern nachjustieren.
4. Unter ② Form und Größe des Rahmens festlegen.
5. Den Kasten „Prüfung“ beachten.
6. „3D-Datei exportieren“ → STL im Slicer (Bambu Studio, PrusaSlicer, Cura …) öffnen und drucken.

Ausführliche Hilfe im Programm mit **F1**.

## Projektaufbau

```
app.py                 Programmstart, Selbsttest für die EXE
remstudio/
  main_window.py       Hauptfenster, Einstellungen, Prüfung, Export-Dialog
  processing.py        Bildverarbeitung: Motiv → druckbare Maske, Stege, Analyse, Vorschau-Ebenen
  mesh.py              Maske → 3D-Netz (Extrusion), STL-Export
  export.py            Export (STL, Aufteilen, SVG, PNG), Materialschätzung
  bgremove.py          Hintergrund-Entfernung (KI-Modelle via ONNX Runtime, GrabCut)
  bg_editor.py         Editor zum Entfernen des Hintergrunds
  canvas.py            2D-Vorschau (OpenGL) mit Werkzeugen
  viewer3d.py          3D-Vorschau
  widgets.py, theme.py Bedienelemente und dunkles Design
  i18n.py              Sprachen (Englisch/Deutsch)
  samples.py           Beispielbild
installer/             Inno-Setup-Skript und Installer-Bilder
build.py, build.bat    Baut Programm und Installer
make_icon.py           erzeugt icon.ico / icon.png (und mit --installer die Installer-Bilder)
RemStudio3D.spec       PyInstaller-Bauanleitung
```

## Daten auf dem PC

- **KI-Modelle** für die Hintergrund-Entfernung werden beim ersten Gebrauch einmalig aus den Releases des
  Open-Source-Projekts [rembg](https://github.com/danielgatis/rembg) heruntergeladen und unter
  `%LOCALAPPDATA%\RemStudio\models` gespeichert. Danach läuft alles offline.
- **Einstellungen** liegen in der Windows-Registry unter `HKEY_CURRENT_USER\Software\RemStudio`.

## Verwendete Bibliotheken

PySide6 (Qt, LGPL-3.0), OpenCV (Apache-2.0), NumPy (BSD), pyqtgraph (MIT), PyOpenGL (BSD),
mapbox_earcut (ISC), ONNX Runtime (MIT); KI-Modelle aus dem rembg-Projekt (bitte deren Lizenzen beachten).

## Lizenz

RemStudio 3D ist Open Source unter der [MIT-Lizenz](LICENSE) – du darfst den Code frei verwenden, verändern und
weitergeben, solange der Copyright-Hinweis erhalten bleibt. Für die mitgelieferten Bibliotheken und die
KI-Modelle gelten deren eigene Lizenzen (siehe oben).
