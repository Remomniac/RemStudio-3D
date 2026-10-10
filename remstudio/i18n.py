"""Sprachen: Englisch (Standard) und Deutsch.

Die Texte im Quellcode sind deutsch und dienen als Schlüssel. ``T(text, **werte)`` liefert die
Übersetzung der aktiven Sprache (mit ``str.format``-Platzhaltern). ``translate_tree(widget)``
übersetzt nachträglich alle festen Beschriftungen eines Fensters (Texte, Tooltips, Listen, Titel).
"""
from __future__ import annotations

import re

LANGUAGES = {"en": "English", "de": "Deutsch"}
DEFAULT_LANGUAGE = "en"
LANG = DEFAULT_LANGUAGE


def set_language(code: str):
    global LANG
    LANG = code if code in LANGUAGES else DEFAULT_LANGUAGE


def T(text: str, **kw) -> str:
    s = EN.get(text, text) if LANG == "en" else text
    return s.format(**kw) if kw else s


def num(v: float, d: int = 1) -> str:
    """Zahl mit passendem Dezimaltrennzeichen (1.25 / 1,25)."""
    s = f"{v:.{d}f}"
    return s if LANG == "en" else s.replace(".", ",")


_ws = re.compile(r"^(\s*)(.*?)(\s*)$", re.S)


def _tr(s: str) -> str:
    if not s or LANG != "en":
        return s
    if "\n\n" in s:
        return "\n\n".join(_tr(part) for part in s.split("\n\n"))
    m = _ws.match(s)
    lead, core, trail = m.group(1), m.group(2), m.group(3)
    hit = EN.get(core)
    return lead + hit + trail if hit is not None else s


def translate_tree(root):
    """Übersetzt alle festen Texte eines Fensters samt Unterelementen."""
    if LANG != "en":
        return
    from PySide6.QtWidgets import (QWidget, QLabel, QAbstractButton, QComboBox, QGroupBox, QLineEdit)
    widgets = [root] + root.findChildren(QWidget)
    for w in widgets:
        if w.toolTip():
            w.setToolTip(_tr(w.toolTip()))
        if isinstance(w, QLabel) and w.text():
            w.setText(_tr(w.text()))
        elif isinstance(w, QAbstractButton) and w.text():
            w.setText(_tr(w.text()))
        elif isinstance(w, QComboBox):
            for i in range(w.count()):
                w.setItemText(i, _tr(w.itemText(i)))
        elif isinstance(w, QGroupBox):
            w.setTitle(_tr(w.title()))
        elif isinstance(w, QLineEdit) and w.placeholderText():
            w.setPlaceholderText(_tr(w.placeholderText()))
        if w.isWindow() and w.windowTitle():
            w.setWindowTitle(_tr(w.windowTitle()))
        for a in w.actions():
            if a.text():
                a.setText(_tr(a.text()))
            if a.toolTip():
                a.setToolTip(_tr(a.toolTip()))


# ---------------------------------------------------------------------------
# Deutsch -> Englisch
# ---------------------------------------------------------------------------
EN = {
    # --- allgemein / Hauptfenster
    "Bild → druckbares 3D-Wandbild": "Image → printable 3D wall art",
    "Bild hierher ziehen\noder rechts auf „Bild öffnen“ klicken – oder mit Strg+V einfügen":
        "Drop an image here\nor click “Open image” on the right – or paste with Ctrl+V",
    "Rückgängig (Strg+Z)": "Undo (Ctrl+Z)",
    "Wiederholen (Strg+Y)": "Redo (Ctrl+Y)",
    "Wand": "Wall",
    "So sieht das fertige Bild an der Wand aus": "How the finished piece looks on the wall",
    "Schwarz/Weiß": "Black/White",
    "Nur die druckbaren Flächen": "Only the printable areas",
    "Original": "Original",
    "Eingefügtes Bild (hier auch zuschneiden)": "Imported image (crop it here)",
    "Drehbare 3D-Vorschau des Druckmodells": "Rotatable 3D preview of the print model",
    "Problemstellen": "Problem areas",
    "Blau = automatisch ergänzte Stege · Orange = zu dünn · Lila = zu enge Lücke · Rot = loses Teil":
        "Blue = automatically added bridges · Orange = too thin · Purple = gap too narrow · Red = loose part",
    "Lässt das Originalbild halbtransparent durchscheinen – hilfreich beim Nachbessern":
        "Shows the original image semi-transparently – helpful for touch-ups",
    "Ansicht": "View",
    "Ansicht verschieben (H) – Mausrad zoomt. Tipp: Leertaste gedrückt halten":
        "Pan the view (H) – mouse wheel zooms. Tip: hold the space bar",
    "Motiv": "Motif",
    "Motiv im Rahmen verschieben (M) – Mausrad ändert die Größe":
        "Move the motif inside the frame (M) – mouse wheel changes its size",
    "Pinsel": "Brush",
    "Material hinzufügen (B) – z. B. Linien verbinden oder Stege malen":
        "Add material (B) – e.g. connect lines or paint bridges",
    "Radierer": "Eraser",
    "Material entfernen (E)": "Remove material (E)",
    "Steg": "Bridge",
    "Gerade Verbindung ziehen (L) – ideal um lose Teile anzubinden":
        "Draw a straight connection (L) – ideal for attaching loose parts",
    "Korrektur weg": "Undo touch-up",
    "Eigene Korrekturen an dieser Stelle entfernen (R)": "Remove your own touch-ups at this spot (R)",
    "Größe": "Size",
    "Durchmesser von Pinsel/Radierer/Steg. Tasten [ und ] oder Alt+Mausrad":
        "Diameter of brush/eraser/bridge. Keys [ and ] or Alt+mouse wheel",
    "Alle eigenen Korrekturen löschen": "Delete all your touch-ups",
    "Rechteck über den gewünschten Bildteil ziehen": "Drag a rectangle over the part of the image you want",
    "Leeren Rand entfernen": "Remove empty border",
    "Schneidet weiße (leere) Ränder automatisch ab": "Automatically cuts off white (empty) borders",
    "Ganzes Bild": "Whole image",
    "Zuschnitt aufheben": "Remove cropping",
    "Verkleinern": "Zoom out",
    "Vergrößern": "Zoom in",
    "Ganzes Bild anzeigen (Strg+0)": "Show the whole image (Ctrl+0)",
    "Projekt speichern/öffnen, Beispiel, Hilfe": "Save/open project, example, help",
    "Sprache / Language": "Language / Sprache",
    "Bild öffnen": "Open image",
    "Bild oder Zeichnung laden (Strg+O). Geht auch per Drag & Drop.":
        "Load an image or drawing (Ctrl+O). Drag & drop works too.",
    "Einfügen": "Paste",
    "Bild aus der Zwischenablage einfügen (Strg+V)": "Paste an image from the clipboard (Ctrl+V)",
    "Hintergrund entfernen": "Remove background",
    "Hintergrund bearbeiten": "Edit background",
    "Öffnet den Editor zum (automatischen) Entfernen des Bildhintergrunds (Strg+B)":
        "Opens the editor for (automatically) removing the image background (Ctrl+B)",
    "Zuschneiden": "Crop",
    "Bildausschnitt wählen (Ansicht „Original“)": "Choose the image section (“Original” view)",
    "Prüfung": "Check",
    "3D-Datei exportieren": "Export 3D file",
    "Druckfertige STL-Datei(en) speichern (Strg+E)": "Save print-ready STL file(s) (Ctrl+E)",

    # --- Abschnitt 1
    "①  Motiv erkennen": "①  Detect motif",
    "Wähle, was für ein Bild du hast – die Einstellungen werden passend vorbelegt":
        "Choose what kind of image you have – the settings are preset accordingly",
    "Bildart": "Image type",
    "Strichzeichnung / Comic (empfohlen)": "Line art / comic (recommended)",
    "Logo / Schrift / Silhouette": "Logo / lettering / silhouette",
    "Silhouette → nur Umriss": "Silhouette → outline only",
    "Foto → Skizze": "Photo → sketch",
    "Foto → Kanten": "Photo → edges",
    "Schwelle automatisch bestimmen": "Set threshold automatically",
    "Findet selbst die beste Grenze zwischen hell und dunkel": "Finds the best split between light and dark by itself",
    "Schwelle (hell ↔ dunkel)": "Threshold (light ↔ dark)",
    "Alles, was dunkler als dieser Wert ist, wird gedruckt. Höher = mehr Material, niedriger = weniger":
        "Everything darker than this value gets printed. Higher = more material, lower = less",
    "Detailgröße": "Detail size",
    "Kleiner = feinere Details, größer = gröbere, ruhigere Flächen": "Smaller = finer details, larger = coarser, calmer areas",
    "Empfindlichkeit": "Sensitivity",
    "Höher = weniger Linien (nur kräftige Kontraste), niedriger = mehr Linien":
        "Higher = fewer lines (strong contrasts only), lower = more lines",
    "Höher = mehr Kanten werden erkannt": "Higher = more edges are detected",
    "Strichbreite": "Stroke width",
    "Breite der erzeugten Linien": "Width of the generated lines",
    "Linien dicker / dünner": "Lines thicker / thinner",
    "Positiv macht alle Linien kräftiger (stabiler), negativ feiner":
        "Positive makes all lines bolder (sturdier), negative finer",
    "Kanten glätten": "Smooth edges",
    "Rundet ausgefranste, pixelige Kanten ab": "Rounds off frayed, pixelated edges",
    "Kleine Flecken entfernen": "Remove small specks",
    "Punkte und Krümel, die kleiner sind, werden gelöscht": "Dots and crumbs smaller than this are deleted",
    "Farben umkehren (helle Linien drucken)": "Invert colors (print light lines)",
    "Für Bilder mit hellen Linien auf dunklem Hintergrund": "For images with light lines on a dark background",
    "Flächen füllen (Silhouette)": "Fill areas (silhouette)",
    "Schließt alle Innenflächen – macht aus einer Umrisszeichnung eine volle Fläche":
        "Closes all inner areas – turns an outline drawing into a solid shape",
    "Nur Umriss drucken": "Print outline only",
    "Wandelt volle Flächen in Umrisslinien um (spart Material, wirkt filigraner)":
        "Turns solid areas into outlines (saves material, looks more delicate)",
    "Umriss-Breite": "Outline width",
    "Breite der Umrisslinie": "Width of the outline",
    "Feineinstellungen Bild": "Image fine-tuning",
    "Erkennungsart": "Detection method",
    "Schwellwert (Zeichnung)": "Threshold (drawing)",
    "Adaptiv (Foto)": "Adaptive (photo)",
    "Kanten": "Edges",
    "Wie aus dem Bild Linien gemacht werden": "How lines are created from the image",
    "Helligkeit": "Brightness",
    "Bild vor der Erkennung aufhellen": "Brighten the image before detection",
    "Kontrast": "Contrast",
    "Bild vor der Erkennung kontrastreicher": "Increase contrast before detection",
    "Rauschen entfernen": "Remove noise",
    "Weichzeichnen vor der Erkennung – gegen Bildrauschen und JPEG-Artefakte":
        "Blur before detection – against image noise and JPEG artifacts",
    "Winzige Löcher schließen": "Close tiny holes",
    "Löcher kleiner als dieser Wert werden gefüllt (sind sowieso nicht druckbar)":
        "Holes smaller than this are filled (they can't be printed anyway)",

    # --- Abschnitt 2
    "②  Rahmen && Größe": "②  Frame && size",
    "Form": "Shape",
    "Rechteck": "Rectangle",
    "Abgerundet": "Rounded",
    "Kreis / Oval": "Circle / oval",
    "Sechseck": "Hexagon",
    "Kein Rahmen": "No frame",
    "Form des Rahmens": "Shape of the frame",
    "Breite": "Width",
    "Gesamtbreite inkl. Rahmen": "Total width including frame",
    "Höhe": "Height",
    "Gesamthöhe inkl. Rahmen": "Total height including frame",
    "Seitenverhältnis sperren": "Lock aspect ratio",
    "Breite und Höhe ändern sich gemeinsam": "Width and height change together",
    "An Bild anpassen": "Fit to image",
    "Höhe so wählen, dass das Motiv genau in den Rahmen passt": "Choose the height so the motif fits the frame exactly",
    "Rahmenbreite": "Frame width",
    "Wie breit der Rahmen-Rand ist": "How wide the frame border is",
    "Eckenradius": "Corner radius",
    "Wie rund die Ecken sind": "How round the corners are",
    "Abstand Motiv ↔ Rahmen": "Gap motif ↔ frame",
    "Freiraum zwischen Rahmen und Motiv (das Motiv wird dort abgeschnitten)":
        "Space between frame and motif (the motif is cut off there)",

    # --- Abschnitt 3
    "③  Motiv platzieren": "③  Place motif",
    "Tipp: Mit dem Werkzeug „✥ Motiv“ kannst du das Motiv direkt in der Vorschau ziehen und mit dem Mausrad vergrößern.":
        "Tip: with the “Motif” tool you can drag the motif directly in the preview and resize it with the mouse wheel.",
    "1,00 = passt genau in den Rahmen. Größer = Motiv ragt über den Rahmen hinaus und wird abgeschnitten (wie im Beispielbild)":
        "1.00 = fits the frame exactly. Larger = the motif extends beyond the frame and is cut off (like in the example)",
    "Links ↔ Rechts": "Left ↔ right",
    "Motiv waagerecht verschieben": "Move the motif horizontally",
    "Oben ↔ Unten": "Up ↔ down",
    "Motiv senkrecht verschieben": "Move the motif vertically",
    "Drehen": "Rotate",
    "Motiv drehen": "Rotate the motif",
    "Spiegeln": "Mirror",
    "Motiv seitenverkehrt": "Mirror the motif",
    "Einpassen": "Fit",
    "Motiv vollständig im Rahmen zeigen": "Show the whole motif inside the frame",
    "Füllen": "Fill",
    "Motiv füllt den Rahmen komplett aus (Ränder werden abgeschnitten)":
        "The motif fills the whole frame (edges are cut off)",
    "Zentrieren": "Center",
    "Motiv in die Mitte setzen": "Put the motif in the center",

    # --- Abschnitt 4
    "④  Druckbarkeit": "④  Printability",
    "Dünnste Linie": "Thinnest line",
    "Linien dünner als das werden orange markiert. Faustregel: 2× Düsendurchmesser (0,4-mm-Düse → 0,8 mm)":
        "Lines thinner than this are marked orange. Rule of thumb: 2× nozzle diameter (0.4 mm nozzle → 0.8 mm)",
    "Engste Lücke": "Narrowest gap",
    "Lücken enger als das könnten beim Druck zulaufen (lila markiert)":
        "Gaps narrower than this may close up when printing (marked purple)",
    "Zu dünne Stellen automatisch verstärken": "Automatically thicken thin spots",
    "Verbreitert alle Linien, die dünner als die dünnste druckbare Linie sind":
        "Widens all lines that are thinner than the thinnest printable line",
    "Lose Teile": "Loose parts",
    "Automatisch verbinden": "Connect automatically",
    "Entfernen": "Remove",
    "Nur markieren": "Only mark",
    "Teile, die nirgends mit dem Rahmen verbunden sind (z. B. Augen, Buchstaben-Innenteile), würden herausfallen.":
        "Parts that aren't connected to the frame anywhere (e.g. eyes, inner parts of letters) would fall out.",
    "Stegbreite": "Bridge width",
    "Breite der automatisch ergänzten Verbindungsstege": "Width of the automatically added bridges",
    "Mit Rückplatte halten alle Teile von selbst – Stege sind nicht nötig.":
        "With a back plate all parts hold by themselves – no bridges needed.",

    # --- Abschnitt 5
    "⑤  3D-Druck": "⑤  3D print",
    "Dicke Motiv": "Motif thickness",
    "Höhe der Linien. 2–4 mm sind für Wandbilder ideal": "Height of the lines. 2–4 mm is ideal for wall art",
    "Dicke Rahmen": "Frame thickness",
    "Ist der Rahmen dicker als das Motiv, wirkt das Bild plastischer":
        "A frame thicker than the motif makes the piece look more three-dimensional",
    "Rückplatte (für zweifarbigen Druck)": "Back plate (for two-color printing)",
    "Eine geschlossene Platte hinter dem Motiv – in anderer Farbe gedruckt wirkt es wie im Beispielfoto. Lose Teile halten dann von selbst.":
        "A solid plate behind the motif – printed in another color it looks like the example photo. Loose parts then hold by themselves.",
    "Dicke Rückplatte": "Back plate thickness",
    "Dicke der Rückplatte": "Thickness of the back plate",
    "Aufhängung": "Hanging",
    "Keine (z. B. Klebestreifen)": "None (e.g. adhesive strips)",
    "Löcher oben im Rahmen": "Holes at the top of the frame",
    "Öse oben": "Loop at the top",
    "Wie das Bild an die Wand kommt": "How the piece is mounted on the wall",
    "Lochdurchmesser": "Hole diameter",
    "Für Nägel ca. 3 mm, für Schrauben 4–5 mm": "About 3 mm for nails, 4–5 mm for screws",
    "Drucker && Qualität": "Printer && quality",
    "Druckbett Breite": "Print bed width",
    "Druckbett Tiefe": "Print bed depth",
    "Größe deines Druckbetts": "Size of your print bed",
    "Export-Qualität": "Export quality",
    "Wie fein die Kanten im 3D-Modell aufgelöst werden": "How finely the edges are resolved in the 3D model",
    "Entwurf (schnell)": "Draft (fast)",
    "Normal (empfohlen)": "Normal (recommended)",
    "Fein (große Datei)": "Fine (large file)",

    # --- Abschnitt 6
    "⑥  Vorschau-Farben": "⑥  Preview colors",
    "Motiv / Rahmen": "Motif / frame",
    "Rückplatte": "Back plate",
    "Die Farben dienen nur der Vorschau – gedruckt wird in der Farbe deines Filaments.":
        "The colors are only for the preview – it prints in the color of your filament.",
    "Farbe wählen": "Choose color",

    # --- Menü
    "Bild öffnen …": "Open image …",
    "Bild einfügen": "Paste image",
    "Projekt speichern": "Save project",
    "Projekt speichern unter …": "Save project as …",
    "Projekt öffnen …": "Open project …",
    "Projekt öffnen": "Open project",
    "Exportieren …": "Export …",
    "Rückgängig": "Undo",
    "Wiederholen": "Redo",
    "Hintergrund entfernen …": "Remove background …",
    "Beispielbild laden": "Load example image",
    "Alle Einstellungen zurücksetzen": "Reset all settings",
    "Kurzanleitung": "Quick guide",
    "Hintergrund-Editor nach dem Laden öffnen": "Open background editor after loading",
    "Grafikkarte für die Vorschau verwenden": "Use graphics card for the preview",

    # --- Meldungen
    "Bilder": "Images",
    "Alle Dateien": "All files",
    "Bilder und Projekte": "Images and projects",
    "Projekt": "project",
    "Die Datei konnte nicht als Bild geöffnet werden.": "The file could not be opened as an image.",
    "In der Zwischenablage ist kein Bild.": "There is no image on the clipboard.",
    "Leerer Bildrand wurde automatisch abgeschnitten (änderbar in der Ansicht „Original“).":
        "Empty image border was cropped automatically (adjustable in the “Original” view).",
    "Bitte zuerst ein Bild laden.": "Please load an image first.",
    "Hintergrund entfernt. Rückgängig mit „↶ Rückgängig“.": "Background removed. Undo with “↶ Undo”.",
    "Kein leerer Rand gefunden.": "No empty border found.",
    "Fehler bei der Berechnung – Details in der Konsole.": "Calculation error – details in the console.",
    "Noch kein Bild geladen. Ziehe ein Bild in die Vorschau – oder lade über ☰ das Beispiel.":
        "No image loaded yet. Drag an image into the preview – or load the example via ☰.",
    "Rückplatte hält alle Teile zusammen": "The back plate holds all parts together",
    "Alles hängt zusammen": "Everything is connected",
    " ({n} Stege ergänzt – blau)": " ({n} bridges added – blue)",
    "{n} lose Teile würden herausfallen (rot) – „Lose Teile: Automatisch verbinden“ wählen oder mit „Steg“ anbinden":
        "{n} loose parts would fall out (red) – choose “Loose parts: Connect automatically” or attach them with “Bridge”",
    "{n} Stellen dünner als {w} mm (orange) – „Linien dicker“ oder „automatisch verstärken“":
        "{n} spots thinner than {w} mm (orange) – “Lines thicker” or “automatically thicken”",
    "Alle Linien mindestens {w} mm breit": "All lines at least {w} mm wide",
    "{n} sehr enge Lücken (lila) – könnten zulaufen": "{n} very narrow gaps (purple) – may close up",
    "Passt aufs Druckbett ({x}×{y} mm)": "Fits the print bed ({x}×{y} mm)",
    "Größer als dein Druckbett → wird beim Export in {c}×{r} Teile aufgeteilt":
        "Larger than your print bed → will be split into {c}×{r} parts on export",
    "ca. {g} g PLA ({m} m)": "approx. {g} g PLA ({m} m)",
    "Farbwechsel bei <b>{h} mm</b> Höhe (Rückplatte → Motiv)": "Color change at <b>{h} mm</b> height (back plate → motif)",
    "Vorschau: {p} Pixel/mm   ·   Export: {e} Pixel/mm   ·   Werkzeuge: H Ansicht · M Motiv · B Pinsel · E Radierer · L Steg · [ ] Pinselgröße · Strg+Z Rückgängig":
        "Preview: {p} pixels/mm   ·   Export: {e} pixels/mm   ·   Tools: H view · M motif · B brush · E eraser · L bridge · [ ] brush size · Ctrl+Z undo",
    "Es ist noch kein Bild geladen.": "No image has been loaded yet.",
    "{app}-Projekt": "{app} project",
    "Speichern fehlgeschlagen:\n{e}": "Saving failed:\n{e}",
    "Projekt gespeichert: {p}": "Project saved: {p}",
    "Projekt konnte nicht geöffnet werden:\n{e}": "The project could not be opened:\n{e}",
    "Projektdatei ist beschädigt.": "The project file is damaged.",
    "Das aktuelle Projekt hat ungespeicherte Änderungen.\nMöchtest du es vorher speichern?":
        "The current project has unsaved changes.\nDo you want to save it first?",
    "Berechne druckfertiges Modell …": "Calculating print-ready model …",
    "Export": "Export",
    "Berechne Motiv in voller Auflösung …": "Calculating motif at full resolution …",
    "Beim Export ist ein Fehler aufgetreten:\n\n": "An error occurred during export:\n\n",
    "Im Slicer flach auf das Druckbett legen (Vorderseite nach oben).":
        "Place it flat on the print bed in the slicer (front side up).",
    "Empfehlung: 0,2 mm Schichthöhe, 2–3 Wandlinien, 15–20 % Füllung.":
        "Recommended: 0.2 mm layer height, 2–3 walls, 15–20 % infill.",
    "<b>Einfarbiger Drucker:</b> „_komplett.stl“ laden und bei <b>{h} mm</b> einen Farbwechsel/Pause einfügen.":
        "<b>Single-color printer:</b> load “_komplett.stl” and add a color change/pause at <b>{h} mm</b>.",
    "<b>Mehrfarbdrucker (AMS/MMU):</b> „_motiv.stl“ und „_rueckplatte.stl“ gleichzeitig laden → „als ein Objekt mit mehreren Teilen“ bestätigen und Farben zuweisen.":
        "<b>Multi-color printer (AMS/MMU):</b> load “_motiv.stl” and “_rueckplatte.stl” together → confirm “as one object with multiple parts” and assign colors.",
    "Hinweis: In {n} Teilstück(en) gibt es Stücke, die erst beim Zusammenkleben Halt bekommen.":
        "Note: {n} tile(s) contain pieces that only hold once the tiles are glued together.",
    "Export fertig": "Export finished",
    "<b>{n} Datei(en) gespeichert:</b>": "<b>{n} file(s) saved:</b>",
    "<b>Tipps:</b>": "<b>Tips:</b>",
    "Ordner öffnen": "Open folder",
    "Die Änderung wird beim nächsten Start des Programms wirksam.\n\nTipp: Nur abschalten, wenn die Vorschau mit Grafikkarte Fehler zeigt.":
        "The change takes effect the next time the program starts.\n\nTip: only turn this off if the preview shows errors with the graphics card.",
    "Die Sprache wird nach einem Neustart übernommen. Jetzt neu starten?":
        "The language is applied after a restart. Restart now?",
    "Ein unerwarteter Fehler ist aufgetreten:\n\n": "An unexpected error occurred:\n\n",

    # --- Export-Dialog
    "Dateiname:": "File name:",
    "Ordner:": "Folder:",
    "Durchsuchen …": "Browse …",
    "Dateien": "Files",
    "Motiv und Rückplatte als getrennte Dateien (Mehrfarbdrucker / AMS)":
        "Motif and back plate as separate files (multi-color printer / AMS)",
    "Alles in einer Datei (einfarbiger Drucker mit Farbwechsel-Pause)":
        "Everything in one file (single-color printer with color-change pause)",
    "Es wird eine STL-Datei mit Motiv und Rahmen erstellt.": "One STL file with motif and frame will be created.",
    "Zusätzlich SVG (für Lasercutter / Plotter / CAD)": "Additionally SVG (for laser cutters / plotters / CAD)",
    "Zusätzlich PNG-Vorlage (schwarz/weiß)": "Additionally PNG template (black/white)",
    "Aufteilen (für große Bilder)": "Split (for large pieces)",
    "In mehrere Teile aufteilen": "Split into several parts",
    "Spalten:": "Columns:",
    "Zeilen:": "Rows:",
    "Entwurf": "Draft",
    "Normal": "Normal",
    "Fein": "Fine",
    "Größe: {w} × {h} mm · Qualität: {q}": "Size: {w} × {h} mm · Quality: {q}",
    "Achtung: {n} lose Teile!": "Warning: {n} loose parts!",
    "{n} sehr dünne Stellen.": "{n} very thin spots.",
    "Exportieren": "Export",
    "Jedes Teil: {w} × {h} mm – ": "Each part: {w} × {h} mm – ",
    "passt aufs Druckbett ✔": "fits the print bed ✔",
    "zu groß für dein Druckbett ✖": "too large for your print bed ✖",
    "Ordner wählen": "Choose folder",
    "Bitte einen Dateinamen eingeben.": "Please enter a file name.",
    "Der Ordner ist ungültig.": "The folder is invalid.",

    # --- Verarbeitung / Export (Hintergrund-Aufgaben)
    "Ohne Rahmen besteht das Motiv aus mehreren losen Teilen.": "Without a frame the motif consists of several loose parts.",
    "Größer als das Druckbett – beim Export in Teile aufteilen.": "Larger than the print bed – split into parts on export.",
    "Rahmen zu schmal für {d} mm Löcher (mind. {m} mm).": "Frame too narrow for {d} mm holes (at least {m} mm).",
    "Für die Aufhängeöse sollte der Rahmen mind. 4 mm breit sein.":
        "For the hanging loop the frame should be at least 4 mm wide.",
    "Erzeuge 3D-Modell {k}/{n} …": "Creating 3D model {k}/{n} …",
    "Schreibe SVG …": "Writing SVG …",
    "Schreibe PNG …": "Writing PNG …",
    "Fertig": "Done",

    # --- 3D-Ansicht
    "3D-Ansicht nicht verfügbar (OpenGL fehlt).\nDer Export funktioniert trotzdem.":
        "3D view not available (OpenGL missing).\nExport still works.",
    "3D-Ansicht konnte nicht gestartet werden.\nDer Export funktioniert trotzdem.":
        "The 3D view could not be started.\nExport still works.",
    "Linke Maustaste: drehen · Mausrad: zoomen · Mittlere Maustaste: verschieben":
        "Left mouse button: rotate · Mouse wheel: zoom · Middle mouse button: pan",
    "Vorne": "Front",
    "Schräg": "Angled",
    "Hinten": "Back",

    # --- Regler
    "Mausrad über der Zahl ändert den Wert": "Mouse wheel over the number changes the value",
    "Feinjustierung: Umschalttaste (Shift) beim Ziehen gedrückt halten · Zahl anklicken und eintippen · Mausrad über der Zahl (mit Strg in 10er-Schritten)":
        "Fine-tuning: hold Shift while dragging · click the number and type · mouse wheel over the number (with Ctrl in steps of 10)",

    # --- Hintergrund-Editor
    "Schritt 1 von 2: Hintergrund entfernen": "Step 1 of 2: Remove background",
    "↶ Rückgängig": "↶ Undo",
    "Letzten Schritt rückgängig machen (Strg+Z)": "Undo the last step (Ctrl+Z)",
    "↷ Wiederholen": "↷ Redo",
    "Bearbeiten": "Edit",
    "Ganzes Bild: entfernte Bereiche erscheinen durchsichtig (Karomuster), die Grenze türkis":
        "Whole image: removed areas appear transparent (checkerboard), the border turquoise",
    "Ergebnis": "Result",
    "So sieht das Bild ohne Hintergrund aus": "How the image looks without the background",
    "Unverändertes Bild": "Unchanged image",
    "Entfernter Hintergrund sichtbar:": "Removed background visible:",
    "Wie stark das Originalbild in den entfernten Bereichen durchscheint":
        "How strongly the original image shows through in the removed areas",
    "✋ Ansicht": "✋ View",
    "Ansicht verschieben – Mausrad zoomt": "Pan the view – mouse wheel zooms",
    "□ Rechteck": "□ Rectangle",
    "Rechteck um das Motiv ziehen – der Rest wird automatisch als Hintergrund erkannt (ohne KI)":
        "Drag a rectangle around the motif – the rest is detected as background automatically (no AI)",
    "🟢 Behalten": "🟢 Keep",
    "Über Bereiche malen, die zum Motiv gehören": "Paint over areas that belong to the motif",
    "🔴 Entfernen": "🔴 Remove",
    "Über Bereiche malen, die weg sollen": "Paint over areas that should go",
    "Pinselgröße": "Brush size",
    "Tasten [ und ] oder Alt+Mausrad": "Keys [ and ] or Alt+mouse wheel",
    "①  Automatisch entfernen": "①  Remove automatically",
    "Welche KI das Motiv erkennt. Probiere ein anderes, wenn das Ergebnis nicht passt.":
        "Which AI detects the motif. Try another one if the result doesn't fit.",
    "Erkennung": "Detection",
    "Comic / Zeichentrick / Anime": "Comic / cartoon / anime",
    "Fotos / echte Personen & Objekte": "Photos / real people & objects",
    "Schnell & klein (einfache Motive)": "Fast & small (simple motifs)",
    "🪄  Hintergrund automatisch entfernen": "🪄  Remove background automatically",
    "Eine KI erkennt das Hauptmotiv (Person, Figur, Tier, Objekt) und entfernt alles andere. Läuft komplett auf deinem PC.":
        "An AI detects the main motif (person, character, animal, object) and removes everything else. Runs entirely on your PC.",
    "Nicht zufrieden? Andere Erkennung wählen und nochmal klicken – oder ohne KI: Werkzeug „□ Rechteck“ wählen und ein Rechteck um das Motiv ziehen.":
        "Not happy? Choose another detection and click again – or without AI: pick the “□ Rectangle” tool and drag a rectangle around the motif.",
    "②  Nachbessern": "②  Touch up",
    "Mit 🟢 Behalten und 🔴 Entfernen über Stellen malen, die falsch erkannt wurden. Grob malen reicht, wenn du danach „Kanten anpassen“ drückst.":
        "Paint with 🟢 Keep and 🔴 Remove over spots that were detected wrongly. Rough strokes are enough if you press “Fit edges” afterwards.",
    "✨  Kanten an Pinselstriche anpassen": "✨  Fit edges to brush strokes",
    "Passt die Grenze zwischen Motiv und Hintergrund anhand deiner Pinselstriche an den Bildkanten an":
        "Fits the border between motif and background to the image edges based on your brush strokes",
    "Alles behalten": "Keep everything",
    "Nichts entfernen (von vorn beginnen)": "Remove nothing (start over)",
    "Auswahl umkehren": "Invert selection",
    "Motiv und Hintergrund tauschen": "Swap motif and background",
    "③  Rand && Feinschliff": "③  Edge && finishing",
    "Rand kleiner ↔ größer": "Edge smaller ↔ larger",
    "Verschiebt die Kante nach innen (−) oder außen (+), z. B. um Hintergrund-Reste am Rand zu entfernen":
        "Moves the edge inwards (−) or outwards (+), e.g. to remove leftover background at the edge",
    "Kante glätten": "Smooth edge",
    "Macht ausgefranste Kanten glatter": "Makes frayed edges smoother",
    "Löcher im Motiv füllen": "Fill holes in the motif",
    "Bereiche, die ganz vom Motiv umschlossen sind, bleiben erhalten": "Areas completely enclosed by the motif are kept",
    "Kleine Streuteile entfernen": "Remove small stray bits",
    "Behält nur das Hauptmotiv (und große Teile davon)": "Keeps only the main motif (and large parts of it)",
    "Umrisslinie um das Motiv": "Outline around the motif",
    "Zeichnet eine schwarze Linie um das Motiv – sinnvoll, wenn das Motiv am Rand hell ist und sonst im Hintergrund verschwinden würde":
        "Draws a black line around the motif – useful when the motif is light at the edge and would otherwise disappear",
    "④  Danach": "④  Afterwards",
    "Bild auf das Motiv zuschneiden": "Crop the image to the motif",
    "Entfernt leere Ränder, damit das Motiv den Rahmen besser ausfüllt":
        "Removes empty borders so the motif fills the frame better",
    "Nach dem Laden eines Bildes automatisch hier starten": "Start here automatically after loading an image",
    "Kann auch im Menü ☰ wieder eingeschaltet werden": "Can also be switched back on in the ☰ menu",
    "Hintergrund behalten": "Keep background",
    "Nichts entfernen und mit dem Originalbild weitermachen": "Remove nothing and continue with the original image",
    "Abbrechen": "Cancel",
    "Original verwenden": "Use original",
    "Hintergrund NICHT entfernen (auch eine frühere Entfernung aufheben)":
        "Do NOT remove the background (also undoes an earlier removal)",
    "Weiter  ›": "Continue  ›",
    "✔  Übernehmen": "✔  Apply",
    "Weiter": "Continue",
    "Übernehmen": "Apply",
    "Tipp: Klicke auf „🪄 Hintergrund automatisch entfernen“.": "Tip: click “🪄 Remove background automatically”.",
    "Klicke auf „Hintergrund automatisch entfernen“ (einmaliger Download des KI-Modells) – oder „Hintergrund behalten“.":
        "Click “Remove background automatically” (one-time download of the AI model) – or “Keep background”.",
    "Erkenne Motiv im Rechteck …": "Detecting motif in the rectangle …",
    "Fertig. Mit 🟢/🔴 nachbessern, falls nötig.": "Done. Touch up with 🟢/🔴 if needed.",
    "KI-Modell herunterladen": "Download AI model",
    "Für die automatische Erkennung wird einmalig das KI-Modell „{label}“ (ca. {mb} MB) aus dem Open-Source-Projekt rembg (GitHub) heruntergeladen.\n\nDanach funktioniert es auch ohne Internet. Jetzt herunterladen?":
        "For automatic detection the AI model “{label}” (approx. {mb} MB) is downloaded once from the open-source project rembg (GitHub).\n\nAfter that it also works offline. Download now?",
    "KI erkennt das Motiv … (einige Sekunden)": "AI is detecting the motif … (a few seconds)",
    "Fertig! Prüfe den Rand – mit 🟢 Behalten / 🔴 Entfernen nachbessern und dann „{btn}“. Fehlt etwas? Andere „Erkennung“ probieren.":
        "Done! Check the edge – touch up with 🟢 Keep / 🔴 Remove and then “{btn}”. Something missing? Try another “Detection”.",
    "Hinweis": "Note",
    "Male zuerst mit 🟢 Behalten oder 🔴 Entfernen über die Stellen, die angepasst werden sollen.":
        "First paint with 🟢 Keep or 🔴 Remove over the spots that should be adjusted.",
    "Passe Kanten an …": "Fitting edges …",
    "Kanten angepasst.": "Edges fitted.",
    "Lade KI-Modell herunter …": "Downloading AI model …",
    "Download": "Download",
    "Download fehlgeschlagen": "Download failed",
    "Das Modell konnte nicht geladen werden. Bitte Internetverbindung prüfen.\n\n":
        "The model could not be downloaded. Please check your internet connection.\n\n",
    "Fehler – siehe Meldung.": "Error – see message.",
    "Fehler": "Error",
    "Es wurde alles entfernt – bitte das Motiv mit 🟢 Behalten markieren.":
        "Everything was removed – please mark the motif with 🟢 Keep.",
}

HELP_EN = """<h3>How it works – in 5 steps</h3>
<ol>
<li><b>Load an image</b> – drag &amp; drop, “Open image” or Ctrl+V. Clear line drawings, comics, logos and
silhouettes work best. The background editor starts right away: the AI removes the background, you check it and
click “Continue” (or “Keep background”).</li>
<li><b>Choose the image type</b> (①) and fine-tune with <i>Threshold</i>, <i>Lines thicker/thinner</i> and
<i>Remove small specks</i> until the wall view looks good.</li>
<li><b>Set frame &amp; size</b> (②). With the “Motif” tool you can drag the motif and resize it with the mouse
wheel – if it extends beyond the frame it is cut off (as usual for wall art).</li>
<li><b>Watch the check panel</b> at the top right: loose parts are attached to the frame with small bridges (blue)
automatically. Orange spots are too thin. Use Brush, Eraser and Bridge to touch up by hand.</li>
<li><b>Export</b> – open the STL file in your slicer (Bambu Studio, PrusaSlicer, Cura …) and print.</li>
</ol>
<h3>Tips</h3>
<ul>
<li>Two colors like in the example photo: enable “Back plate”. Loose parts then hold too.</li>
<li>For a 0.4 mm nozzle, lines should be at least 0.8 mm wide.</li>
<li>Hold the space bar = pan the view, mouse wheel = zoom, [ and ] = brush size.</li>
<li>Sliders: hold Shift while dragging for fine-tuning, or click the number and type the value.</li>
<li>“↶” / “↷” at the top left (or Ctrl+Z / Ctrl+Y). Ctrl+S saves the project including all touch-ups and the
background removal.</li>
</ul>"""

HELP_DE = """<h3>So geht's in 5 Schritten</h3>
<ol>
<li><b>Bild laden</b> – per Drag &amp; Drop, „Bild öffnen“ oder Strg+V. Am besten eignen sich klare
Strichzeichnungen, Comics, Logos oder Silhouetten. Der Hintergrund-Editor startet sofort: Die KI entfernt den
Hintergrund, du prüfst und klickst „Weiter“ (oder „Hintergrund behalten“).</li>
<li><b>Bildart wählen</b> (①) und mit <i>Schwelle</i>, <i>Linien dicker/dünner</i> und
<i>Kleine Flecken entfernen</i> nachjustieren, bis die Wandansicht gut aussieht.</li>
<li><b>Rahmen &amp; Größe</b> (②) festlegen. Mit dem Werkzeug „Motiv“ kannst du das Motiv ziehen und mit dem
Mausrad vergrößern – ragt es über den Rahmen, wird es abgeschnitten (wie bei Wandbildern üblich).</li>
<li><b>Prüfung</b> oben rechts beachten: Lose Teile werden automatisch mit kleinen Stegen (blau) an den Rahmen
gebunden. Orange Stellen sind zu dünn. Mit Pinsel, Radierer und Steg kannst du von Hand nachbessern.</li>
<li><b>Exportieren</b> – die STL-Datei im Slicer (Bambu Studio, PrusaSlicer, Cura …) öffnen und drucken.</li>
</ol>
<h3>Tipps</h3>
<ul>
<li>Zweifarbig wie im Beispielfoto: „Rückplatte“ aktivieren. Dann halten auch lose Teile.</li>
<li>Für eine 0,4-mm-Düse sollten Linien mindestens 0,8 mm breit sein.</li>
<li>Leertaste gedrückt halten = Ansicht verschieben, Mausrad = zoomen, [ und ] = Pinselgröße.</li>
<li>Regler: Umschalttaste (Shift) beim Ziehen = Feinjustierung, oder die Zahl anklicken und eintippen.</li>
<li>„↶“ / „↷“ oben links (oder Strg+Z / Strg+Y). Strg+S speichert das Projekt inkl. Korrekturen und
Hintergrund-Entfernung.</li>
</ul>"""


def help_text() -> str:
    return HELP_EN if LANG == "en" else HELP_DE
