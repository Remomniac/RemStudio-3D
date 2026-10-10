"""Hauptfenster von RemStudio 3D."""
from __future__ import annotations

import base64
import json
import math
import os
import sys
import traceback

import cv2
import numpy as np
from PySide6.QtCore import Qt, QTimer, QObject, Signal, QRunnable, QThreadPool, QSettings, QUrl
from PySide6.QtGui import QAction, QKeySequence, QImage, QDesktopServices, QShortcut, QTransform
from PySide6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QSplitter, QScrollArea, QLabel,
                               QPushButton, QFileDialog, QMessageBox, QStackedWidget, QButtonGroup, QCheckBox,
                               QSlider, QDialog, QDialogButtonBox, QLineEdit, QSpinBox, QGridLayout, QProgressDialog,
                               QApplication, QToolButton, QFrame, QSizePolicy, QGroupBox, QMenu)

from . import processing as proc
from . import mesh as meshmod
from . import export as exp
from . import bgremove as bgr
from .canvas import (Canvas, TOOL_PAN, TOOL_MOVE, TOOL_BRUSH, TOOL_ERASE, TOOL_LINE, TOOL_RESTORE, TOOL_CROP,
                     EDIT_TOOLS)
from .viewer3d import Viewer3D
from .widgets import (Slider, ParamSlider, Section, ColorButton, ChoiceBox, labeled, checkbox, Toggle, CompactSlider,
                      CanvasArea, island, segment, round_button, vsep)
from . import theme
from .i18n import T, num, translate_tree, help_text, LANGUAGES
from . import i18n
from .samples import demo_image

APP_NAME = "RemStudio 3D"
from . import __version__ as APP_VERSION  # noqa: E402
PROJECT_EXT = ".remstudio"
LEGACY_PROJECT_EXT = ".rahmen"  # ältere Projektdateien weiterhin öffnen
IMAGE_PATTERN = "*.png *.jpg *.jpeg *.bmp *.gif *.tif *.tiff *.webp"


def image_filter() -> str:
    return f"{T('Bilder')} ({IMAGE_PATTERN});;{T('Alle Dateien')} (*)"

VIEW_WALL, VIEW_MASK, VIEW_ORIG, VIEW_3D = "wall", "mask", "orig", "3d"

# Diese Werte verändern nur Lage/Größe des Motivs -> Vorschau kann sofort per Grafikkarte folgen
MOTIF_KEYS = ("motif_scale", "motif_dx", "motif_dy", "motif_rotation", "mirror")

PRESETS = [
    ("Strichzeichnung / Comic (empfohlen)", "line"),
    ("Logo / Schrift / Silhouette", "logo"),
    ("Silhouette → nur Umriss", "outline"),
    ("Foto → Skizze", "photo"),
    ("Foto → Kanten", "edges"),
]

PRESET_VALUES = {
    "line": dict(mode=proc.MODE_THRESHOLD, auto_threshold=True, blur_mm=0.0, smooth_mm=0.3, min_speck_mm2=2.0,
                 min_hole_mm2=0.5, line_adjust_mm=0.0, outline_only=False, fill_shapes=False),
    "logo": dict(mode=proc.MODE_THRESHOLD, auto_threshold=True, blur_mm=0.0, smooth_mm=0.4, min_speck_mm2=4.0,
                 min_hole_mm2=1.0, line_adjust_mm=0.0, outline_only=False, fill_shapes=False),
    "outline": dict(mode=proc.MODE_THRESHOLD, auto_threshold=True, blur_mm=0.0, smooth_mm=0.5, min_speck_mm2=6.0,
                    min_hole_mm2=2.0, line_adjust_mm=0.0, outline_only=True, outline_width_mm=2.0,
                    fill_shapes=True),
    "photo": dict(mode=proc.MODE_ADAPTIVE, adaptive_block_mm=8.0, adaptive_c=10, blur_mm=0.5, smooth_mm=0.4,
                  min_speck_mm2=4.0, min_hole_mm2=1.0, line_adjust_mm=0.2, outline_only=False, fill_shapes=False),
    "edges": dict(mode=proc.MODE_EDGES, edge_sensitivity=50, edge_width_mm=1.2, blur_mm=0.3, smooth_mm=0.3,
                  min_speck_mm2=4.0, min_hole_mm2=1.0, line_adjust_mm=0.0, outline_only=False, fill_shapes=False),
}

QUALITY = [("Entwurf (schnell)", 6.0), ("Normal (empfohlen)", 10.0), ("Fein (große Datei)", 16.0)]

# Werte, die sich das Programm zwischen den Sitzungen merkt
PERSISTENT_KEYS = ["bed_x_mm", "bed_y_mm", "quality_ppm", "min_line_mm", "min_gap_mm", "color_art", "color_back",
                   "color_wall", "art_height_mm", "frame_height_mm", "bridge_width_mm", "backplate_mm"]


# ---------------------------------------------------------------------------
# Hintergrund-Arbeiter
# ---------------------------------------------------------------------------

class _Signals(QObject):
    done = Signal(int, object)
    failed = Signal(int, str)
    progress = Signal(str, float)


class Task(QRunnable):
    def __init__(self, gen: int, fn, *args):
        super().__init__()
        self.gen, self.fn, self.args = gen, fn, args
        self.signals = _Signals()
        self.setAutoDelete(True)

    def run(self):
        try:
            out = self.fn(*self.args)
            self.signals.done.emit(self.gen, out)
        except Exception:
            self.signals.failed.emit(self.gen, traceback.format_exc())


def run_preview_job(job: dict) -> dict:
    p: proc.Params = job["params"]
    ppm = job["ppm"]
    res = proc.process(job["gray"], job["edits"], p, ppm, analyse=True)
    view = job["view"]
    out = {"res": res, "params": p, "ppm": ppm, "view": view}
    if view in (VIEW_WALL, VIEW_MASK):
        out.update(proc.render_layers(res, p, job["problems"], "mask" if view == VIEW_MASK else "wall"))
    if job["overlay"] > 0 and job["color"] is not None and view in (VIEW_WALL, VIEW_MASK):
        out["overlay"] = proc.warp_color(job["color"], p, ppm)
    if job["want3d"]:
        parts = meshmod.build_meshes(res, p, simplify_px=0.8)
        out["meshes"] = [(parts["motiv"], p.color_art)]
        if "rueckplatte" in parts:
            out["meshes"].append((parts["rueckplatte"], p.color_back))
    out["material"] = exp.estimate_material(res, p)
    return out


# ---------------------------------------------------------------------------
# Hauptfenster
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1440, 900)
        self.setAcceptDrops(True)
        self.settings = QSettings("RemStudio", "RemStudio3D")

        self.params = proc.Params()
        self._load_persistent()
        self.orig_bgr: np.ndarray | None = None   # Bild wie geladen
        self.bg_mask: np.ndarray | None = None    # Hintergrund-Maske (255 = behalten) oder None
        self.bg_version = 0
        self._bg_counter = 0
        self._bg_key = None
        self.full_bgr: np.ndarray | None = None   # ganzes Bild (ggf. ohne Hintergrund)
        self.full_gray: np.ndarray | None = None
        self.src_bgr: np.ndarray | None = None    # zugeschnittener Ausschnitt (wird verarbeitet)
        self.src_gray: np.ndarray | None = None
        self._crop_key = None
        self.edits: np.ndarray | None = None      # Korrekturen in Koordinaten des ganzen Bildes
        self.edits_version = 0
        self.image_name = "remstudio"
        self.project_path: str | None = None

        self.shown: dict | None = None        # zuletzt angezeigtes Ergebnis
        self.last_full: dict | None = None    # zuletzt vollständig berechnetes Ergebnis
        self.view = VIEW_WALL
        self.gen = 0
        self.busy = False
        self.pending: dict | None = None
        self.pool = QThreadPool.globalInstance()
        self._live = set()  # laufende Aufgaben (verhindert vorzeitiges Aufräumen der Signale)
        self._prev_view = VIEW_WALL
        self._loading = False
        self.history: list = []
        self.hidx = -1
        self._dirty = False
        self._notice = ""

        self.controls: dict = {}
        self.dyn: dict = {}  # Widgets, die je nach Einstellung ein-/ausgeblendet werden

        self._build_ui()
        self._build_actions()

        self.full_timer = QTimer(self, singleShot=True, interval=40)
        self.full_timer.timeout.connect(self.request)
        self.commit_timer = QTimer(self, singleShot=True, interval=700)
        self.commit_timer.timeout.connect(self.commit)

        self.sync_controls()
        self.update_visibility()
        self.update_checks()
        translate_tree(self)

    # ======================================================================
    # Aufbau der Oberfläche
    # ======================================================================
    def _build_ui(self):
        central = QWidget()
        hl = QHBoxLayout(central)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(0)
        self.setCentralWidget(central)

        # ---------------- links: Vorschau mit schwebenden Leisten
        self.area = CanvasArea()
        self.stack = QStackedWidget(self.area)
        self.canvas = Canvas()
        self.canvas.placeholder = T("Bild hierher ziehen\noder rechts auf „Bild öffnen“ klicken – "
                                    "oder mit Strg+V einfügen")
        self.canvas.strokeFinished.connect(self.on_stroke)
        self.canvas.motifDragged.connect(self.on_motif_drag)
        self.canvas.motifDragFinished.connect(lambda: self.full_timer.start(0))
        self.canvas.motifScaled.connect(self.on_motif_scale)
        self.canvas.brushSizeStep.connect(self._brush_step)
        self.canvas.fileDropped.connect(self.open_path)
        self.canvas.cropSelected.connect(self.on_crop_selected)
        self.stack.addWidget(self.canvas)
        self.viewer = Viewer3D()
        self.stack.addWidget(self.viewer)
        self.area.content = self.stack

        # Obere Insel: Rückgängig/Wiederholen, Ansichten, Optionen
        top = island(self.area)
        tl = top.layout()
        self.btn_undo = round_button("undo", "Rückgängig (Strg+Z)", self.undo)
        self.btn_redo = round_button("redo", "Wiederholen (Strg+Y)", self.redo)
        tl.addWidget(self.btn_undo)
        tl.addWidget(self.btn_redo)
        tl.addWidget(vsep())
        seg = segment()
        self.view_group = QButtonGroup(self)
        for text, ic, key, tip in (("Wand", "wall", VIEW_WALL, "So sieht das fertige Bild an der Wand aus"),
                                   ("Schwarz/Weiß", "mask", VIEW_MASK, "Nur die druckbaren Flächen"),
                                   ("Original", "image", VIEW_ORIG, "Eingefügtes Bild (hier auch zuschneiden)"),
                                   ("3D", "cube", VIEW_3D, "Drehbare 3D-Vorschau des Druckmodells")):
            b = QPushButton(text)
            b.setIcon(theme.icon(ic, theme.TEXT_2, 16))
            b.setCheckable(True)
            b.setToolTip(tip)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setProperty("viewkey", key)
            self.view_group.addButton(b)
            seg.layout().addWidget(b)
            if key == VIEW_WALL:
                b.setChecked(True)
        self.view_group.buttonClicked.connect(lambda b: self.set_view(b.property("viewkey")))
        tl.addWidget(seg)
        tl.addWidget(vsep())
        self.cb_problems = Toggle("Problemstellen")
        self.cb_problems.setChecked(True)
        self.cb_problems.setToolTip("Blau = automatisch ergänzte Stege · Orange = zu dünn · Lila = zu enge Lücke · "
                                    "Rot = loses Teil")
        self.cb_problems.toggled.connect(lambda _: self.request())
        tl.addWidget(self.cb_problems)
        tl.addSpacing(6)
        lab = QLabel("Original")
        lab.setToolTip("Lässt das Originalbild halbtransparent durchscheinen – hilfreich beim Nachbessern")
        tl.addWidget(lab)
        self.sl_overlay = Slider(Qt.Orientation.Horizontal)
        self.sl_overlay.setRange(0, 90)
        self.sl_overlay.setFixedWidth(90)
        self.sl_overlay.setToolTip(lab.toolTip())
        self.sl_overlay.valueChanged.connect(self._overlay_changed)
        tl.addWidget(self.sl_overlay)
        self.area.top = top

        # Untere Insel: Werkzeuge
        self.toolbar2 = island(self.area)
        bl = self.toolbar2.layout()
        tseg = segment()
        self.tool_group = QButtonGroup(self)
        self.tool_buttons = {}
        for text, ic, key, tip in (
                ("Ansicht", "pan", TOOL_PAN, "Ansicht verschieben (H) – Mausrad zoomt. Tipp: Leertaste gedrückt halten"),
                ("Motiv", "move", TOOL_MOVE, "Motiv im Rahmen verschieben (M) – Mausrad ändert die Größe"),
                ("Pinsel", "brush", TOOL_BRUSH, "Material hinzufügen (B) – z. B. Linien verbinden oder Stege malen"),
                ("Radierer", "eraser", TOOL_ERASE, "Material entfernen (E)"),
                ("Steg", "link", TOOL_LINE, "Gerade Verbindung ziehen (L) – ideal um lose Teile anzubinden"),
                ("Korrektur weg", "restore", TOOL_RESTORE, "Eigene Korrekturen an dieser Stelle entfernen (R)")):
            b = QToolButton()
            b.setObjectName("tool")
            b.setText(text)
            b.setIcon(theme.icon(ic, theme.TEXT_2, 16))
            b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            b.setCheckable(True)
            b.setToolTip(tip)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            self.tool_group.addButton(b)
            self.tool_buttons[key] = b
            b.clicked.connect(lambda _=False, k=key: self.set_tool(k))
            tseg.layout().addWidget(b)
        self.tool_buttons[TOOL_PAN].setChecked(True)
        bl.addWidget(tseg)
        bl.addWidget(vsep())
        self.brush_slider = CompactSlider("Größe", 0.4, 30, 0.1, 1, "mm",
                                          "Durchmesser von Pinsel/Radierer/Steg. Tasten [ und ] oder Alt+Mausrad")
        self.brush_slider.setValue(2.0)
        self.brush_slider.valueChanged.connect(self._brush_changed)
        bl.addWidget(self.brush_slider)
        self.btn_clear_edits = round_button("trash", "Alle eigenen Korrekturen löschen", self.clear_edits)
        bl.addWidget(self.btn_clear_edits)
        self.area.bottom = self.toolbar2

        # Untere Insel in der Original-Ansicht: Zuschneiden
        self.toolbar3 = island(self.area)
        cl = self.toolbar3.layout()
        ic = QLabel()
        ic.setPixmap(theme.glyph_pixmap("crop", 16, theme.TEXT_2))
        cl.addWidget(ic)
        cl.addWidget(QLabel("Rechteck über den gewünschten Bildteil ziehen"))
        b = QPushButton("Leeren Rand entfernen")
        b.setToolTip("Schneidet weiße (leere) Ränder automatisch ab")
        b.clicked.connect(self.auto_crop)
        cl.addWidget(b)
        b = QPushButton("Ganzes Bild")
        b.setToolTip("Zuschnitt aufheben")
        b.clicked.connect(lambda: self.set_crop(None))
        cl.addWidget(b)
        self.toolbar3.setVisible(False)
        self.area.bottom_alt = self.toolbar3

        # Zoom-Insel
        zoom = island(self.area)
        zl = zoom.layout()
        zl.addWidget(round_button("zoom_out", "Verkleinern", lambda: self.canvas.zoom(1 / 1.25)))
        self.zoom_label = QLabel("100 %")
        self.zoom_label.setObjectName("zoomLabel")
        zl.addWidget(self.zoom_label)
        zl.addWidget(round_button("zoom_in", "Vergrößern", lambda: self.canvas.zoom(1.25)))
        zl.addWidget(round_button("fit", "Ganzes Bild anzeigen (Strg+0)", lambda: self.canvas.fit()))
        self.canvas.zoomChanged.connect(lambda z: self.zoom_label.setText(f"{z:.0f} %"))
        self.area.zoom = zoom

        self.status = QLabel("", self.area)
        self.status.setObjectName("statusline")
        self.area.status = self.status
        hl.addWidget(self.area, 1)

        # ---------------- rechts: Einstellungen
        right = QWidget()
        right.setObjectName("rightPanel")
        right.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        right.setFixedWidth(410)
        rv = QVBoxLayout(right)
        rv.setContentsMargins(14, 14, 14, 14)
        rv.setSpacing(10)

        head = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(QApplication.windowIcon().pixmap(30, 30))
        head.addWidget(logo)
        tbox = QVBoxLayout()
        tbox.setSpacing(0)
        t = QLabel(APP_NAME)
        t.setObjectName("title")
        tbox.addWidget(t)
        st = QLabel("Bild → druckbares 3D-Wandbild")
        st.setObjectName("subtitle")
        tbox.addWidget(st)
        head.addLayout(tbox, 1)
        self.btn_lang = QToolButton()
        self.btn_lang.setObjectName("round")
        self.btn_lang.setText(i18n.LANG.upper())
        self.btn_lang.setToolTip("Sprache / Language")
        self.btn_lang.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_lang.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.btn_lang.setStyleSheet("font-weight: 700; font-size: 9pt;")
        head.addWidget(self.btn_lang)
        self.btn_more = round_button("menu", "Projekt speichern/öffnen, Beispiel, Hilfe", None)
        head.addWidget(self.btn_more)
        rv.addLayout(head)

        row = QHBoxLayout()
        row.setSpacing(8)
        b = QPushButton("  Bild öffnen")
        b.setObjectName("accent")
        b.setIcon(theme.icon("open", "#ffffff", 16))
        b.setToolTip("Bild oder Zeichnung laden (Strg+O). Geht auch per Drag & Drop.")
        b.clicked.connect(self.open_dialog)
        row.addWidget(b, 1)
        b = QPushButton("  Einfügen")
        b.setIcon(theme.icon("paste", theme.TEXT, 16))
        b.setToolTip("Bild aus der Zwischenablage einfügen (Strg+V)")
        b.clicked.connect(self.paste)
        row.addWidget(b)
        rv.addLayout(row)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.btn_bg = QPushButton("  Hintergrund entfernen")
        self.btn_bg.setIcon(theme.icon("sparkle", "#c58cff", 16))
        self.btn_bg.setToolTip("Öffnet den Editor zum (automatischen) Entfernen des Bildhintergrunds (Strg+B)")
        self.btn_bg.clicked.connect(self.open_bg_editor)
        row.addWidget(self.btn_bg, 1)
        b = QPushButton("  Zuschneiden")
        b.setIcon(theme.icon("crop", theme.TEXT, 16))
        b.setToolTip("Bildausschnitt wählen (Ansicht „Original“)")
        b.clicked.connect(lambda: self.set_view(VIEW_ORIG))
        row.addWidget(b)
        rv.addLayout(row)

        self.check_box = QFrame()
        self.check_box.setObjectName("checkCard")
        cb = QVBoxLayout(self.check_box)
        cb.setContentsMargins(14, 10, 14, 12)
        cb.setSpacing(4)
        ct = QLabel("Prüfung")
        ct.setStyleSheet(f"font-weight: 700; color: {theme.TEXT};")
        cb.addWidget(ct)
        self.check_label = QLabel()
        self.check_label.setWordWrap(True)
        self.check_label.setTextFormat(Qt.TextFormat.RichText)
        self.check_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        # Feste Höhe: längere Meldungen scrollen im Kasten, statt die Regler zu verschieben
        cscroll = QScrollArea()
        cscroll.setWidgetResizable(True)
        cscroll.setFrameShape(QFrame.Shape.NoFrame)
        cscroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        cscroll.setWidget(self.check_label)
        cb.addWidget(cscroll, 1)
        self.check_box.setFixedHeight(196)
        rv.addWidget(self.check_box)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        panel = QWidget()
        self.panel_layout = QVBoxLayout(panel)
        self.panel_layout.setContentsMargins(0, 0, 6, 0)
        self.panel_layout.setSpacing(10)
        scroll.setWidget(panel)
        rv.addWidget(scroll, 1)
        self._build_sections()
        self.panel_layout.addStretch(1)

        self.btn_export = QPushButton("  3D-Datei exportieren")
        self.btn_export.setObjectName("primary")
        self.btn_export.setIcon(theme.icon("export", "#ffffff", 18))
        self.btn_export.setToolTip("Druckfertige STL-Datei(en) speichern (Strg+E)")
        self.btn_export.clicked.connect(self.export_dialog)
        rv.addWidget(self.btn_export)
        hl.addWidget(right)

    # ----------------------------------------------------------------------
    def _slider(self, key, label, mn, mx, step, dec, unit, tip):
        # Längen und Winkel feiner einstellbar (z. B. 0,61 mm statt 0,6 mm)
        if unit in ("mm", "mm²", "°"):
            dec = 2 if dec >= 1 else 1
            step = 10.0 ** -dec
        w = ParamSlider(label, mn, mx, step, dec, unit, tip)
        w.valueChanged.connect(lambda v, k=key: self.set_param(k, v))
        self.controls[key] = w
        return w

    def _check(self, key, text, tip):
        w = checkbox(text, tip)
        w.toggled.connect(lambda v, k=key: self.set_param(k, bool(v)))
        self.controls[key] = w
        return w

    def _choice(self, key, items, tip=""):
        w = ChoiceBox(items)
        if tip:
            w.setToolTip(tip)
        w.currentIndexChanged.connect(lambda _i, k=key, w=w: self.set_param(k, w.value()))
        self.controls[key] = w
        return w

    def _build_sections(self):
        L = self.panel_layout

        # ---------------- 1) Motiv
        s = Section("①  Motiv erkennen")
        self.preset = ChoiceBox(PRESETS)
        self.preset.setToolTip("Wähle, was für ein Bild du hast – die Einstellungen werden passend vorbelegt")
        self.preset.currentIndexChanged.connect(self.apply_preset)
        s.add(labeled("Bildart", self.preset))
        self.dyn["threshold_box"] = w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._check("auto_threshold", "Schwelle automatisch bestimmen",
                                  "Findet selbst die beste Grenze zwischen hell und dunkel"))
        lay.addWidget(self._slider("threshold", "Schwelle (hell ↔ dunkel)", 1, 254, 1, 0, "",
                                   "Alles, was dunkler als dieser Wert ist, wird gedruckt. "
                                   "Höher = mehr Material, niedriger = weniger"))
        s.add(w)
        self.dyn["adaptive_box"] = w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._slider("adaptive_block_mm", "Detailgröße", 2, 40, 0.5, 1, "mm",
                                   "Kleiner = feinere Details, größer = gröbere, ruhigere Flächen"))
        lay.addWidget(self._slider("adaptive_c", "Empfindlichkeit", -10, 40, 1, 0, "",
                                   "Höher = weniger Linien (nur kräftige Kontraste), niedriger = mehr Linien"))
        s.add(w)
        self.dyn["edges_box"] = w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._slider("edge_sensitivity", "Empfindlichkeit", 0, 100, 1, 0, "",
                                   "Höher = mehr Kanten werden erkannt"))
        lay.addWidget(self._slider("edge_width_mm", "Strichbreite", 0.4, 5, 0.1, 1, "mm",
                                   "Breite der erzeugten Linien"))
        s.add(w)
        s.add(self._slider("line_adjust_mm", "Linien dicker / dünner", -3, 3, 0.1, 1, "mm",
                           "Positiv macht alle Linien kräftiger (stabiler), negativ feiner"))
        s.add(self._slider("smooth_mm", "Kanten glätten", 0, 3, 0.1, 1, "mm",
                           "Rundet ausgefranste, pixelige Kanten ab"))
        s.add(self._slider("min_speck_mm2", "Kleine Flecken entfernen", 0, 100, 0.5, 1, "mm²",
                           "Punkte und Krümel, die kleiner sind, werden gelöscht"))
        s.add(self._check("invert", "Farben umkehren (helle Linien drucken)",
                          "Für Bilder mit hellen Linien auf dunklem Hintergrund"))
        s.add(self._check("fill_shapes", "Flächen füllen (Silhouette)",
                          "Schließt alle Innenflächen – macht aus einer Umrisszeichnung eine volle Fläche"))
        s.add(self._check("outline_only", "Nur Umriss drucken",
                          "Wandelt volle Flächen in Umrisslinien um (spart Material, wirkt filigraner)"))
        self.dyn["outline_w"] = s.add(self._slider("outline_width_mm", "Umriss-Breite", 0.6, 10, 0.1, 1, "mm",
                                                   "Breite der Umrisslinie"))
        adv = Section("Feineinstellungen Bild", expanded=False)
        adv.add(labeled("Erkennungsart", self._choice("mode", [("Schwellwert (Zeichnung)", proc.MODE_THRESHOLD),
                                                              ("Adaptiv (Foto)", proc.MODE_ADAPTIVE),
                                                              ("Kanten", proc.MODE_EDGES)]),
                        "Wie aus dem Bild Linien gemacht werden"))
        adv.add(self._slider("brightness", "Helligkeit", -100, 100, 1, 0, "", "Bild vor der Erkennung aufhellen"))
        adv.add(self._slider("contrast", "Kontrast", -100, 100, 1, 0, "", "Bild vor der Erkennung kontrastreicher"))
        adv.add(self._slider("blur_mm", "Rauschen entfernen", 0, 3, 0.1, 1, "mm",
                             "Weichzeichnen vor der Erkennung – gegen Bildrauschen und JPEG-Artefakte"))
        adv.add(self._slider("min_hole_mm2", "Winzige Löcher schließen", 0, 20, 0.1, 1, "mm²",
                             "Löcher kleiner als dieser Wert werden gefüllt (sind sowieso nicht druckbar)"))
        s.add(adv)
        L.addWidget(s)

        # ---------------- 2) Rahmen
        s = Section("②  Rahmen && Größe")
        s.add(labeled("Form", self._choice("frame_shape", [("Rechteck", proc.FRAME_RECT),
                                                          ("Abgerundet", proc.FRAME_ROUNDED),
                                                          ("Kreis / Oval", proc.FRAME_CIRCLE),
                                                          ("Sechseck", proc.FRAME_HEXAGON),
                                                          ("Kein Rahmen", proc.FRAME_NONE)]),
                      "Form des Rahmens"))
        s.add(self._slider("width_mm", "Breite", 30, 1000, 1, 0, "mm", "Gesamtbreite inkl. Rahmen"))
        s.add(self._slider("height_mm", "Höhe", 30, 1000, 1, 0, "mm", "Gesamthöhe inkl. Rahmen"))
        row = QHBoxLayout()
        self.cb_lock = QCheckBox("Seitenverhältnis sperren")
        self.cb_lock.setToolTip("Breite und Höhe ändern sich gemeinsam")
        row.addWidget(self.cb_lock)
        b = QPushButton("An Bild anpassen")
        b.setToolTip("Höhe so wählen, dass das Motiv genau in den Rahmen passt")
        b.clicked.connect(self.fit_frame_to_image)
        row.addWidget(b)
        s.add(row)
        self.dyn["frame_box"] = w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._slider("frame_width_mm", "Rahmenbreite", 2, 60, 0.5, 1, "mm",
                                   "Wie breit der Rahmen-Rand ist"))
        self.dyn["corner"] = self._slider("corner_radius_mm", "Eckenradius", 0, 150, 0.5, 1, "mm",
                                          "Wie rund die Ecken sind")
        lay.addWidget(self.dyn["corner"])
        lay.addWidget(self._slider("inner_margin_mm", "Abstand Motiv ↔ Rahmen", 0, 40, 0.5, 1, "mm",
                                   "Freiraum zwischen Rahmen und Motiv (das Motiv wird dort abgeschnitten)"))
        s.add(w)
        L.addWidget(s)

        # ---------------- 3) Motiv-Position
        s = Section("③  Motiv platzieren", expanded=False)
        s.hint("Tipp: Mit dem Werkzeug „✥ Motiv“ kannst du das Motiv direkt in der Vorschau ziehen "
               "und mit dem Mausrad vergrößern.")
        s.add(self._slider("motif_scale", "Größe", 0.1, 5, 0.01, 2, "×",
                           "1,00 = passt genau in den Rahmen. Größer = Motiv ragt über den Rahmen hinaus "
                           "und wird abgeschnitten (wie im Beispielbild)"))
        s.add(self._slider("motif_dx", "Links ↔ Rechts", -500, 500, 0.5, 1, "mm", "Motiv waagerecht verschieben"))
        s.add(self._slider("motif_dy", "Oben ↔ Unten", -500, 500, 0.5, 1, "mm", "Motiv senkrecht verschieben"))
        s.add(self._slider("motif_rotation", "Drehen", -180, 180, 0.5, 1, "°", "Motiv drehen"))
        row = QHBoxLayout()
        row.addWidget(self._check("mirror", "Spiegeln", "Motiv seitenverkehrt"))
        for text, tip, fn in (("Einpassen", "Motiv vollständig im Rahmen zeigen", self.motif_fit),
                              ("Füllen", "Motiv füllt den Rahmen komplett aus (Ränder werden abgeschnitten)",
                               self.motif_fill),
                              ("Zentrieren", "Motiv in die Mitte setzen", self.motif_center)):
            b = QPushButton(text)
            b.setToolTip(tip)
            b.clicked.connect(fn)
            row.addWidget(b)
        s.add(row)
        L.addWidget(s)

        # ---------------- 4) Druckbarkeit
        s = Section("④  Druckbarkeit")
        s.add(self._slider("min_line_mm", "Dünnste Linie", 0.3, 3, 0.05, 2, "mm",
                           "Linien dünner als das werden orange markiert. Faustregel: 2× Düsendurchmesser "
                           "(0,4-mm-Düse → 0,8 mm)"))
        s.add(self._slider("min_gap_mm", "Engste Lücke", 0.2, 3, 0.05, 2, "mm",
                           "Lücken enger als das könnten beim Druck zulaufen (lila markiert)"))
        s.add(self._check("fix_thin", "Zu dünne Stellen automatisch verstärken",
                          "Verbreitert alle Linien, die dünner als die dünnste druckbare Linie sind"))
        self.dyn["islands_box"] = w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(labeled("Lose Teile", self._choice("islands", [("Automatisch verbinden", proc.ISLANDS_BRIDGE),
                                                                    ("Entfernen", proc.ISLANDS_REMOVE),
                                                                    ("Nur markieren", proc.ISLANDS_KEEP)]),
                              "Teile, die nirgends mit dem Rahmen verbunden sind (z. B. Augen, "
                              "Buchstaben-Innenteile), würden herausfallen."))
        self.dyn["bridge_w"] = self._slider("bridge_width_mm", "Stegbreite", 0.6, 6, 0.1, 1, "mm",
                                            "Breite der automatisch ergänzten Verbindungsstege")
        lay.addWidget(self.dyn["bridge_w"])
        s.add(w)
        self.dyn["islands_hint"] = s.hint("Mit Rückplatte halten alle Teile von selbst – Stege sind nicht nötig.")
        L.addWidget(s)

        # ---------------- 5) 3D
        s = Section("⑤  3D-Druck")
        s.add(self._slider("art_height_mm", "Dicke Motiv", 0.6, 20, 0.1, 1, "mm",
                           "Höhe der Linien. 2–4 mm sind für Wandbilder ideal"))
        self.dyn["frame_h"] = s.add(self._slider("frame_height_mm", "Dicke Rahmen", 0.6, 30, 0.1, 1, "mm",
                                                 "Ist der Rahmen dicker als das Motiv, wirkt das Bild "
                                                 "plastischer"))
        s.add(self._check("backplate", "Rückplatte (für zweifarbigen Druck)",
                          "Eine geschlossene Platte hinter dem Motiv – in anderer Farbe gedruckt wirkt es "
                          "wie im Beispielfoto. Lose Teile halten dann von selbst."))
        self.dyn["back_h"] = s.add(self._slider("backplate_mm", "Dicke Rückplatte", 0.4, 10, 0.1, 1, "mm",
                                                "Dicke der Rückplatte"))
        s.add(labeled("Aufhängung", self._choice("hang", [("Keine (z. B. Klebestreifen)", proc.HANG_NONE),
                                                         ("Löcher oben im Rahmen", proc.HANG_HOLES),
                                                         ("Öse oben", proc.HANG_TAB)]),
                      "Wie das Bild an die Wand kommt"))
        self.dyn["hang_d"] = s.add(self._slider("hang_hole_mm", "Lochdurchmesser", 2, 10, 0.5, 1, "mm",
                                                "Für Nägel ca. 3 mm, für Schrauben 4–5 mm"))
        adv = Section("Drucker && Qualität", expanded=False)
        adv.add(self._slider("bed_x_mm", "Druckbett Breite", 100, 600, 1, 0, "mm", "Größe deines Druckbetts"))
        adv.add(self._slider("bed_y_mm", "Druckbett Tiefe", 100, 600, 1, 0, "mm", "Größe deines Druckbetts"))
        adv.add(labeled("Export-Qualität", self._choice("quality_ppm", QUALITY),
                        "Wie fein die Kanten im 3D-Modell aufgelöst werden"))
        s.add(adv)
        L.addWidget(s)

        # ---------------- 6) Farben
        s = Section("⑥  Vorschau-Farben", expanded=False)
        self.color_buttons = {}
        for key, text in (("color_art", "Motiv / Rahmen"), ("color_back", "Rückplatte"), ("color_wall", "Wand")):
            cbtn = ColorButton(getattr(self.params, key))
            cbtn.colorChanged.connect(lambda c, k=key: self.set_param(k, c))
            self.color_buttons[key] = cbtn
            s.add(labeled(text, cbtn))
        s.hint("Die Farben dienen nur der Vorschau – gedruckt wird in der Farbe deines Filaments.")
        L.addWidget(s)

    def _build_actions(self):
        def act(text, seq, fn):
            a = QAction(T(text), self)
            if seq:
                a.setShortcut(QKeySequence(seq))
            a.triggered.connect(fn)
            self.addAction(a)
            return a

        self.a_open = act("Bild öffnen …", "Ctrl+O", self.open_dialog)
        self.a_paste = act("Bild einfügen", "Ctrl+V", self.paste)
        self.a_save = act("Projekt speichern", "Ctrl+S", self.save_project)
        self.a_save_as = act("Projekt speichern unter …", "Ctrl+Shift+S", lambda: self.save_project(True))
        self.a_load = act("Projekt öffnen …", "Ctrl+Shift+O", self.load_project_dialog)
        self.a_export = act("Exportieren …", "Ctrl+E", self.export_dialog)
        self.a_undo = act("Rückgängig", "Ctrl+Z", self.undo)
        self.a_redo = act("Wiederholen", "Ctrl+Y", self.redo)
        act("", "Ctrl+Shift+Z", self.redo)
        act("", "Ctrl+0", lambda: self.canvas.fit())
        self.a_bg = act("Hintergrund entfernen …", "Ctrl+B", self.open_bg_editor)
        self.a_demo = act("Beispielbild laden", None, self.load_demo)
        self.a_reset = act("Alle Einstellungen zurücksetzen", None, self.reset_settings)
        self.a_help = act("Kurzanleitung", "F1", self.show_help)
        self.a_bgauto = QAction("Hintergrund-Editor nach dem Laden öffnen", self)
        self.a_bgauto.setCheckable(True)
        self.a_bgauto.setChecked(self.settings.value("bg_auto_open", "true") not in ("false", False))
        self.a_bgauto.toggled.connect(lambda on: self.settings.setValue("bg_auto_open", "true" if on else "false"))
        self.a_gpu = QAction("Grafikkarte für die Vorschau verwenden", self)
        self.a_gpu.setCheckable(True)
        self.a_gpu.setChecked(self.settings.value("use_gpu", "true") not in ("false", False))
        self.a_gpu.toggled.connect(self._toggle_gpu)
        for key, tool in (("H", TOOL_PAN), ("M", TOOL_MOVE), ("B", TOOL_BRUSH), ("E", TOOL_ERASE),
                          ("L", TOOL_LINE), ("R", TOOL_RESTORE)):
            sc = QShortcut(QKeySequence(key), self)
            sc.activated.connect(lambda t=tool: self.set_tool(t))
        QShortcut(QKeySequence("["), self).activated.connect(lambda: self._brush_step(-1))
        QShortcut(QKeySequence("]"), self).activated.connect(lambda: self._brush_step(1))

        lang_menu = QMenu("Sprache / Language", self)
        self.lang_actions = {}
        for code, label in LANGUAGES.items():
            a = QAction(label, self)
            a.setCheckable(True)
            a.setChecked(code == i18n.LANG)
            a.triggered.connect(lambda _=False, c=code: self._set_language(c))
            lang_menu.addAction(a)
            self.lang_actions[code] = a
        self.btn_lang.setMenu(lang_menu)

        menu = QMenu(self)
        for a in (self.a_load, self.a_save, self.a_save_as, None, self.a_undo, self.a_redo, None, self.a_bg,
                  self.a_demo,
                  self.a_reset, None, self.a_bgauto, self.a_gpu, self.a_help):
            if a is None:
                menu.addSeparator()
            else:
                menu.addAction(a)
        menu.addSeparator()
        menu.addMenu(lang_menu)
        self.btn_more.setMenu(menu)
        self.btn_more.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)

    # ======================================================================
    # Parameter
    # ======================================================================
    def set_param(self, key, value):
        if self._loading:
            return
        default = getattr(proc.Params(), key)
        if isinstance(default, bool):
            value = bool(value)
        elif isinstance(default, int):
            value = int(round(value))
        elif isinstance(default, float):
            value = float(value)
        old = getattr(self.params, key)
        if old == value:
            return
        if key in ("width_mm", "height_mm") and self.cb_lock.isChecked() and old > 0:
            other = "height_mm" if key == "width_mm" else "width_mm"
            setattr(self.params, other, round(getattr(self.params, other) * value / old, 1))
            self._set_control(other, getattr(self.params, other))
        setattr(self.params, key, value)
        if key == "threshold":
            self.params.auto_threshold = False
            self._set_control("auto_threshold", False)
        if key == "mode":
            self.preset.setValue({proc.MODE_ADAPTIVE: "photo", proc.MODE_EDGES: "edges"}.get(value, "line"))
        self.update_visibility()
        self.changed(motif_only=key in MOTIF_KEYS)

    def _set_control(self, key, value):
        w = self.controls.get(key)
        if w is None:
            return
        self._loading = True
        try:
            if isinstance(w, ParamSlider):
                w.setValue(value)
            elif isinstance(w, QCheckBox):
                w.setChecked(bool(value))
            elif isinstance(w, ChoiceBox):
                w.setValue(value)
        finally:
            self._loading = False

    def sync_controls(self):
        for key in self.controls:
            self._set_control(key, getattr(self.params, key))
        for key, b in self.color_buttons.items():
            b.setColor(getattr(self.params, key))

    def update_visibility(self):
        p = self.params
        self.dyn["threshold_box"].setVisible(p.mode == proc.MODE_THRESHOLD)
        self.dyn["adaptive_box"].setVisible(p.mode == proc.MODE_ADAPTIVE)
        self.dyn["edges_box"].setVisible(p.mode == proc.MODE_EDGES)
        self.dyn["outline_w"].setVisible(p.outline_only)
        has_frame = p.frame_shape != proc.FRAME_NONE
        self.dyn["frame_box"].setVisible(has_frame)
        self.dyn["corner"].setVisible(p.frame_shape == proc.FRAME_ROUNDED)
        self.dyn["frame_h"].setVisible(has_frame)
        self.dyn["back_h"].setVisible(p.backplate)
        self.dyn["islands_box"].setVisible(not p.backplate)
        self.dyn["islands_hint"].setVisible(p.backplate)
        self.dyn["bridge_w"].setVisible(p.islands == proc.ISLANDS_BRIDGE)
        self.dyn["hang_d"].setVisible(p.hang != proc.HANG_NONE and has_frame)

    def changed(self, commit: bool = True, motif_only: bool = False):
        self._dirty = True
        if self.src_gray is not None:
            if motif_only and self._apply_proxy():
                # Grafikkarte zeigt die neue Lage sofort; exakt gerechnet wird, sobald Ruhe ist
                self.full_timer.start(220)
            else:
                self.full_timer.start(40)
        if commit:
            self.commit_timer.start()
        self._update_title()
        self._update_undo_buttons()

    def apply_preset(self, *_):
        key = self.preset.value()
        vals = PRESET_VALUES.get(key, {})
        for k, v in vals.items():
            setattr(self.params, k, v)
        self.sync_controls()
        self.update_visibility()
        self.changed()

    # ======================================================================
    # Bild laden
    # ======================================================================
    def open_dialog(self):
        d = self.settings.value("last_dir", os.path.expanduser("~"))
        path, _ = QFileDialog.getOpenFileName(self, T("Bild öffnen"), d,
                                              f"{T('Bilder und Projekte')} ({IMAGE_PATTERN} *{PROJECT_EXT} "
                                              f"*{LEGACY_PROJECT_EXT});;{image_filter()}")
        if path:
            self.open_path(path)

    def open_path(self, path: str):
        if not path:
            return
        if path.lower().endswith((PROJECT_EXT, LEGACY_PROJECT_EXT)):
            self.load_project(path)
            return
        img = read_image(path)
        if img is None:
            QMessageBox.warning(self, APP_NAME, T("Die Datei konnte nicht als Bild geöffnet werden."))
            return
        self.settings.setValue("last_dir", os.path.dirname(path))
        if self.set_source(img, os.path.splitext(os.path.basename(path))[0]):
            self._start_bg_step()

    def paste(self):
        cb = QApplication.clipboard()
        md = cb.mimeData()
        if md.hasImage():
            qimg = cb.image()
            if not qimg.isNull():
                if self.set_source(qimage_to_bgr(qimg), "eingefuegt"):
                    self._start_bg_step()
                return
        if md.hasUrls() and md.urls():
            self.open_path(md.urls()[0].toLocalFile())
            return
        if md.hasText() and os.path.isfile(md.text().strip().strip('"')):
            self.open_path(md.text().strip().strip('"'))
            return
        QMessageBox.information(self, APP_NAME, T("In der Zwischenablage ist kein Bild."))

    def load_demo(self):
        self.set_source(demo_image(), "beispiel")

    def set_source(self, bgr: np.ndarray, name: str, keep_params: bool = False, edits=None, bg_mask=None) -> bool:
        if not self._confirm_discard():
            return False
        h, w = bgr.shape[:2]
        limit = 3000
        if max(h, w) > limit:
            f = limit / max(h, w)
            bgr = cv2.resize(bgr, (int(w * f), int(h * f)), interpolation=cv2.INTER_AREA)
        self.orig_bgr = bgr
        self.bg_mask = bg_mask if (bg_mask is not None and bg_mask.shape == bgr.shape[:2]) else None
        self._bg_counter += 1
        self.bg_version = self._bg_counter
        if not keep_params:
            self.params.bg_outline_px = 0.0
        self._bg_key = None
        self._recompose()
        self.edits = edits if edits is not None else np.zeros(self.full_gray.shape, np.uint8)
        self.edits_version += 1
        self.image_name = name
        self.project_path = None
        msg = ""
        if not keep_params:
            self.params.motif_scale, self.params.motif_dx, self.params.motif_dy = 1.0, 0.0, 0.0
            self.params.motif_rotation, self.params.mirror = 0.0, False
            # Helle Linien auf dunklem Grund automatisch erkennen
            self.params.invert = float(self.full_gray.mean()) < 100
            self.params.crop = proc.content_bbox(self.full_gray, self.params.invert)
            if self.params.crop:
                msg = "  " + T("Leerer Bildrand wurde automatisch abgeschnitten (änderbar in der Ansicht „Original“).")
        self._crop_key = "x"
        self._apply_crop()
        if not keep_params:
            self.fit_frame_to_image(schedule=False)
            self.sync_controls()
        self.history, self.hidx = [], -1
        self.commit()
        self._dirty = False
        self.canvas._fit_pending = True
        self.request()
        self._update_title()
        self._notice = msg
        self._update_bg_button()
        self._update_undo_buttons()
        if self.view == VIEW_ORIG:
            self.set_view(VIEW_ORIG)
        return True

    # ----------------------------------------------------------------- Hintergrund
    def _recompose(self) -> bool:
        """Setzt full_bgr/full_gray aus Originalbild + Hintergrund-Maske zusammen."""
        if self.orig_bgr is None:
            return False
        key = (self.bg_version, round(float(self.params.bg_outline_px), 2))
        if key == self._bg_key and self.full_bgr is not None:
            return False
        self._bg_key = key
        if self.bg_mask is not None:
            self.full_bgr = bgr.composite(self.orig_bgr, self.bg_mask, self.params.bg_outline_px)
        else:
            self.full_bgr = self.orig_bgr
        self.full_gray = cv2.cvtColor(self.full_bgr, cv2.COLOR_BGR2GRAY)
        self._crop_key = "x"
        return True

    def _update_bg_button(self):
        self.btn_bg.setText("  " + T("Hintergrund bearbeiten" if self.bg_mask is not None else "Hintergrund entfernen"))

    def _start_bg_step(self):
        """Nach dem Laden eines Bildes direkt den Hintergrund-Schritt zeigen (abschaltbar)."""
        if self.settings.value("bg_auto_open", "true") in ("false", False):
            return
        QTimer.singleShot(150, lambda: self.open_bg_editor(onboarding=True))

    def open_bg_editor(self, onboarding: bool = False):
        if self.orig_bgr is None:
            QMessageBox.information(self, APP_NAME, T("Bitte zuerst ein Bild laden."))
            return
        from .bg_editor import BackgroundEditor
        if self.commit_timer.isActive():
            self.commit()
        dlg = BackgroundEditor(self, self.orig_bgr, self.bg_mask, self.params.bg_outline_px, self.settings,
                               onboarding=onboarding)
        accepted = dlg.exec() == QDialog.DialogCode.Accepted
        self.a_bgauto.setChecked(self.settings.value("bg_auto_open", "true") not in ("false", False))
        if not accepted:
            return
        if dlg.result_mask is None and self.bg_mask is None:
            return
        self._bg_counter += 1
        self.bg_version = self._bg_counter
        self.bg_mask = dlg.result_mask
        self.params.bg_outline_px = float(dlg.outline_px) if self.bg_mask is not None else 0.0
        self._recompose()
        if self.bg_mask is not None:
            self.params.invert = False  # Hintergrund ist jetzt weiß
            if dlg.crop_to_subject:
                self.params.crop = bgr.mask_bbox(self.bg_mask)
            self.params.motif_dx = self.params.motif_dy = 0.0
            self._notice = "  " + T("Hintergrund entfernt. Rückgängig mit „↶ Rückgängig“.")
        self._apply_crop()
        self.sync_controls()
        self.update_visibility()
        self._update_bg_button()
        self._dirty = True
        self.commit()
        self.request()
        self._update_title()

    # ----------------------------------------------------------------- Zuschnitt
    def _valid_crop(self, c):
        if not c or self.full_gray is None:
            return None
        h, w = self.full_gray.shape
        x0, y0, x1, y1 = (int(round(v)) for v in c)
        x0, x1 = max(0, min(x0, w - 1)), max(1, min(x1, w))
        y0, y1 = max(0, min(y0, h - 1)), max(1, min(y1, h))
        if x1 - x0 < 4 or y1 - y0 < 4:
            return None
        return [x0, y0, x1, y1]

    def _apply_crop(self):
        """Erzeugt den zu verarbeitenden Bildausschnitt aus params.crop."""
        self._recompose()
        if self.full_gray is None:
            return
        c = self._valid_crop(self.params.crop)
        self.params.crop = c
        key = tuple(c) if c else None
        if key == self._crop_key and self.src_gray is not None:
            return
        self._crop_key = key
        if c:
            x0, y0, x1, y1 = c
            self.src_bgr = np.ascontiguousarray(self.full_bgr[y0:y1, x0:x1])
            self.src_gray = np.ascontiguousarray(self.full_gray[y0:y1, x0:x1])
        else:
            self.src_bgr, self.src_gray = self.full_bgr, self.full_gray

    def _crop_offset(self):
        c = self.params.crop
        return (c[0], c[1]) if c else (0, 0)

    def _cropped_edits(self) -> np.ndarray:
        c = self.params.crop
        if not c:
            return self.edits.copy()
        return self.edits[c[1]:c[3], c[0]:c[2]].copy()

    def set_crop(self, c):
        if self.full_gray is None:
            return
        self.params.crop = self._valid_crop(c)
        self._apply_crop()
        self.params.motif_dx = self.params.motif_dy = 0.0
        self.fit_frame_to_image(schedule=False)
        self.sync_controls()
        self._show_crop_rect()
        self.changed()

    def auto_crop(self):
        if self.full_gray is None:
            return
        c = proc.content_bbox(self.full_gray, self.params.invert)
        if c is None:
            self.status.setText("  " + T("Kein leerer Rand gefunden."))
        self.set_crop(c)

    def on_crop_selected(self, x0, y0, x1, y1):
        if x0 < 0:
            self._show_crop_rect()
            return
        self.set_crop([x0, y0, x1, y1])

    def _show_crop_rect(self):
        if self.view != VIEW_ORIG or self.full_gray is None:
            self.canvas.set_crop_rect(None)
            return
        from PySide6.QtCore import QRectF
        c = self.params.crop
        if c:
            self.canvas.set_crop_rect(QRectF(c[0], c[1], c[2] - c[0], c[3] - c[1]))
        else:
            self.canvas.set_crop_rect(None)

    def fit_frame_to_image(self, schedule: bool = True):
        if self.src_gray is None:
            return
        p = self.params
        h, w = self.src_gray.shape
        a = math.radians(p.motif_rotation)
        bw = abs(w * math.cos(a)) + abs(h * math.sin(a))
        bh = abs(w * math.sin(a)) + abs(h * math.cos(a))
        fw = (p.frame_width_mm + p.inner_margin_mm) if p.frame_shape != proc.FRAME_NONE else 0.0
        inner_w = max(10.0, p.width_mm - 2 * fw)
        inner_h = inner_w * bh / bw
        new_h = round(inner_h + 2 * fw, 0)
        if new_h > 1000:
            f = 1000 / new_h
            p.width_mm = round(p.width_mm * f)
            new_h = 1000
        p.height_mm = max(30.0, new_h)
        self._set_control("width_mm", p.width_mm)
        self._set_control("height_mm", p.height_mm)
        if schedule:
            self.changed()

    # ----------------------------------------------------------------- Motiv
    def motif_fit(self):
        self.params.motif_scale, self.params.motif_dx, self.params.motif_dy = 1.0, 0.0, 0.0
        self.sync_controls()
        self.changed(motif_only=True)

    def motif_center(self):
        self.params.motif_dx, self.params.motif_dy = 0.0, 0.0
        self.sync_controls()
        self.changed(motif_only=True)

    def motif_fill(self):
        if self.src_gray is None:
            return
        p = self.params
        h, w = self.src_gray.shape
        inset = (p.frame_width_mm if p.frame_shape != proc.FRAME_NONE else 0.0) + p.inner_margin_mm
        aw, ah = p.width_mm - 2 * inset, p.height_mm - 2 * inset
        if aw <= 0 or ah <= 0:
            return
        fit = min(aw / w, ah / h)
        fill = max(aw / w, ah / h)
        p.motif_scale = round(fill / fit, 2)
        p.motif_dx = p.motif_dy = 0.0
        self.sync_controls()
        self.changed(motif_only=True)

    def on_motif_drag(self, dx, dy):
        if not self.shown:
            return
        ppm = self.shown["scene_ppm"]
        self.params.motif_dx = round(self.params.motif_dx + dx / ppm, 2)
        self.params.motif_dy = round(self.params.motif_dy + dy / ppm, 2)
        self._set_control("motif_dx", self.params.motif_dx)
        self._set_control("motif_dy", self.params.motif_dy)
        self.changed(motif_only=True)

    def on_motif_scale(self, f):
        self.params.motif_scale = round(max(0.1, min(5.0, self.params.motif_scale * f)), 3)
        self._set_control("motif_scale", self.params.motif_scale)
        self.changed(motif_only=True)

    # ======================================================================
    # Zeichenwerkzeuge
    # ======================================================================
    def set_tool(self, tool: str):
        if self.view in (VIEW_ORIG, VIEW_3D):
            self.set_view(VIEW_WALL)
        self.tool_buttons[tool].setChecked(True)
        self.canvas.set_tool(tool)
        self._brush_changed(self.brush_slider.value())

    def _brush_changed(self, mm):
        ppm = self.shown["scene_ppm"] if self.shown else 1.0
        self.canvas.set_brush_radius(mm * ppm / 2)

    def _brush_step(self, d):
        v = self.brush_slider.value()
        v = v * (1.2 if d > 0 else 1 / 1.2)
        self.brush_slider.setValue(round(max(0.4, min(30, v)), 1), emit=True)

    def on_stroke(self, pts, tool):
        self.canvas.clear_stroke()
        if self.src_gray is None or not self.shown or self.edits is None:
            return
        shown = self.shown
        # Wird das Motiv gerade per Grafikkarte verschoben gezeigt, gilt bereits die neue Lage
        p = self.params if self._proxy_ok(shown["params"]) else shown["params"]
        ppm_out = shown["ppm"]
        sc = shown["scale"]
        pad = shown["pad"]
        sh, sw = self.src_gray.shape
        Minv = proc.output_to_source(p, ppm_out, sw, sh)
        M = proc.motif_transform(p, ppm_out, sw, sh, *_top_w_hbody(p, ppm_out))
        s_scale = math.hypot(M[0, 0], M[1, 0])
        src_pts = []
        for x, y in pts:
            ox, oy = x / sc - pad, y / sc - pad
            sx = Minv[0, 0] * ox + Minv[0, 1] * oy + Minv[0, 2]
            sy = Minv[1, 0] * ox + Minv[1, 1] * oy + Minv[1, 2]
            src_pts.append((sx, sy))
        ox0, oy0 = self._crop_offset()
        src_pts = [(sx + ox0, sy + oy0) for sx, sy in src_pts]
        r_src = self.brush_slider.value() / 2 * ppm_out / s_scale
        value = {TOOL_BRUSH: 1, TOOL_LINE: 1, TOOL_ERASE: 2, TOOL_RESTORE: 0}[tool]
        thick = max(1, int(round(2 * r_src)))
        arr = np.round(np.array(src_pts) * 16).astype(np.int32)
        if len(arr) == 1 or (len(arr) == 2 and np.all(arr[0] == arr[1])):
            cv2.circle(self.edits, tuple(int(v) for v in arr[0]), int(round(r_src * 16)), value, -1, cv2.LINE_8, 4)
        else:
            cv2.polylines(self.edits, [arr.reshape(-1, 1, 2)], False, value, thick, cv2.LINE_8, 4)
            for q in (arr[0], arr[-1]):
                cv2.circle(self.edits, tuple(int(v) for v in q), int(round(r_src * 16)), value, -1, cv2.LINE_8, 4)
        self.edits_version += 1
        self._dirty = True
        self.commit()
        self.request()

    def clear_edits(self):
        if self.edits is None or not self.edits.any():
            return
        self.edits[:] = 0
        self.edits_version += 1
        self.commit()
        self.request()

    # ======================================================================
    # Rückgängig / Wiederholen
    # ======================================================================
    def _snapshot(self):
        d = self.params.to_dict()
        prev = self.history[self.hidx] if 0 <= self.hidx < len(self.history) else None
        if prev is not None and prev[1] == self.edits_version:
            eb = prev[2]
        else:
            eb = None
            if self.edits is not None:
                ok, buf = cv2.imencode(".png", self.edits)
                eb = buf.tobytes() if ok else None
        if prev is not None and prev[3] == self.bg_version:
            bb = prev[4]
        elif self.bg_mask is not None:
            ok, buf = cv2.imencode(".png", self.bg_mask)
            bb = buf.tobytes() if ok else None
        else:
            bb = None
        return (d, self.edits_version, eb, self.bg_version, bb)

    def commit(self):
        self.commit_timer.stop()
        snap = self._snapshot()
        if 0 <= self.hidx < len(self.history):
            cur = self.history[self.hidx]
            if cur[0] == snap[0] and cur[1] == snap[1] and cur[3] == snap[3]:
                self._update_undo_buttons()
                return
        self.history = self.history[:self.hidx + 1]
        self.history.append(snap)
        if len(self.history) > 60:
            self.history = self.history[-60:]
        self.hidx = len(self.history) - 1
        self._update_undo_buttons()

    def _update_undo_buttons(self):
        if not hasattr(self, "btn_undo"):
            return
        pending = self.commit_timer.isActive() if hasattr(self, "commit_timer") else False
        self.btn_undo.setEnabled(self.hidx > 0 or pending)
        self.btn_redo.setEnabled(self.hidx < len(self.history) - 1 and not pending)

    def _restore(self, snap):
        d, ver, eb, bv, bb = snap
        self.params = proc.Params.from_dict(d)
        if eb is not None:
            self.edits = cv2.imdecode(np.frombuffer(eb, np.uint8), cv2.IMREAD_UNCHANGED)
        self.edits_version = ver
        if bv != self.bg_version:
            self.bg_mask = cv2.imdecode(np.frombuffer(bb, np.uint8), cv2.IMREAD_UNCHANGED) if bb else None
            self.bg_version = bv
        self._update_bg_button()
        self._update_undo_buttons()
        self._apply_crop()
        self._show_crop_rect()
        self.sync_controls()
        self.update_visibility()
        self.changed(commit=False)
        self.request()

    def undo(self):
        if self.commit_timer.isActive():
            self.commit()
        if self.hidx > 0:
            self.hidx -= 1
            self._restore(self.history[self.hidx])

    def redo(self):
        if self.hidx < len(self.history) - 1:
            self.hidx += 1
            self._restore(self.history[self.hidx])

    # ======================================================================
    # Berechnung
    # ======================================================================
    def preview_ppm(self) -> float:
        p = self.params
        target = 1150.0
        return max(1.5, min(p.quality_ppm, target / max(p.width_mm, p.height_mm)))

    def schedule(self):
        if self.src_gray is not None:
            self.full_timer.start(40)

    def request(self, fast: bool = False):
        """Berechnet die Vorschau im Hintergrund (immer nur der neueste Auftrag)."""
        if self.src_gray is None:
            return
        self.full_timer.stop()
        job = dict(params=self.params.copy(), ppm=self.preview_ppm(), gray=self.src_gray,
                   edits=self._cropped_edits(), view=self.view,
                   problems=self.cb_problems.isChecked(), overlay=self.sl_overlay.value(),
                   color=self.src_bgr, want3d=self.view == VIEW_3D)
        if self.busy:
            self.pending = job
            return
        self._start(job)

    # ------------------------------------------------------------------ Grafikkarten-Vorschau
    def _proxy_ok(self, shown_params) -> bool:
        """True, wenn sich seit der angezeigten Vorschau nur Lage/Größe des Motivs geändert hat."""
        a, b = shown_params.to_dict(), self.params.to_dict()
        for k in MOTIF_KEYS:
            a.pop(k, None)
            b.pop(k, None)
        return a == b

    def _art_delta(self, ps, pc, ppm, pad) -> QTransform:
        sh, sw = self.src_gray.shape
        m0 = np.vstack([proc.motif_transform(ps, ppm, sw, sh, *_top_w_hbody(ps, ppm)), [0, 0, 1]])
        m1 = np.vstack([proc.motif_transform(pc, ppm, sw, sh, *_top_w_hbody(pc, ppm)), [0, 0, 1]])
        d = m1 @ np.linalg.inv(m0)
        t = np.array([[1, 0, pad], [0, 1, pad], [0, 0, 1.0]]) @ d @ np.array([[1, 0, -pad], [0, 1, -pad], [0, 0, 1.0]])
        return QTransform(t[0, 0], t[1, 0], t[0, 1], t[1, 1], t[0, 2], t[1, 2])

    def _apply_proxy(self) -> bool:
        """Verschiebt/skaliert/dreht die angezeigte Motiv-Ebene auf die aktuellen Werte (ohne Rechnen)."""
        sh = self.shown
        if not sh or "art" not in sh or self.view not in (VIEW_WALL, VIEW_MASK) or self.src_gray is None:
            return False
        if not self._proxy_ok(sh["params"]):
            self.canvas.set_art_transform(None)
            return False
        self.canvas.set_art_transform(self._art_delta(sh["params"], self.params, sh["ppm"], sh["pad"]))
        return True

    def _start(self, job):
        self.busy = True
        self.gen += 1
        t = Task(self.gen, run_preview_job, job)
        sig = t.signals
        self._live.add(sig)
        sig.done.connect(lambda g, out, job=job, sig=sig: (self._live.discard(sig), self._done(g, out, job)))
        sig.failed.connect(lambda g, tb, sig=sig: (self._live.discard(sig), self._failed(g, tb)))
        self.pool.start(t)

    def _done(self, gen, out, job):
        self.busy = False
        if gen == self.gen:
            self._show(out, job)
        if self.pending is not None:
            nxt, self.pending = self.pending, None
            self._start(nxt)

    def _failed(self, gen, tb):
        self.busy = False
        print(tb)
        self.status.setText(T("Fehler bei der Berechnung – Details in der Konsole."))
        if self.pending is not None:
            nxt, self.pending = self.pending, None
            self._start(nxt)

    def _show(self, out, job):
        # Szene-Einheiten = Millimeter: Größenänderungen verändern den Zoom nicht
        out["scale"] = 1.0 / out["ppm"]
        out["scene_ppm"] = 1.0
        self.last_full = out
        if self.view in (VIEW_WALL, VIEW_MASK) and out.get("view") != self.view:
            self.request()  # Ansicht wurde inzwischen gewechselt
            return
        self.shown = out
        if self.view == VIEW_ORIG:
            self.canvas.set_image(self.full_bgr)
            self.canvas.set_overlay(None)
            self._show_crop_rect()
        elif self.view in (VIEW_WALL, VIEW_MASK) and "base" in out:
            self.canvas.set_layers(out["base"], out["art"], out["scale"], out["polys"])
            self.canvas.set_overlay(out.get("overlay"), (out["pad"], out["pad"]), self.sl_overlay.value() / 100.0)
            self._apply_proxy()
        if self.view == VIEW_3D and "meshes" in out:
            p = out["params"]
            self.viewer.set_meshes(out["meshes"], max(p.width_mm, p.height_mm))
        self._brush_changed(self.brush_slider.value())
        res = out["res"]
        if self.params.auto_threshold and res.threshold_used >= 0:
            self._set_control("threshold", res.threshold_used)
        self.update_checks()

    def _overlay_changed(self, v):
        if self.shown and self.shown.get("overlay") is not None and v > 0:
            self.canvas.overlay.setOpacity(v / 100.0)
            self.canvas.overlay.setVisible(True)
        else:
            self.request()

    def set_view(self, view: str):
        self._prev_view, self.view = self.view, view
        for b in self.view_group.buttons():
            if b.property("viewkey") == view:
                b.setChecked(True)
        self.stack.setCurrentIndex(1 if view == VIEW_3D else 0)
        self.toolbar2.setVisible(view in (VIEW_WALL, VIEW_MASK))
        self.toolbar3.setVisible(view == VIEW_ORIG)
        self.area.zoom.setVisible(view != VIEW_3D)
        self.status.setVisible(view != VIEW_3D)  # im 3D-Modus steht unten die Bedienhilfe
        self.area.relayout()
        self.canvas.edit_enabled = view in (VIEW_WALL, VIEW_MASK)
        if view == VIEW_ORIG:
            self.canvas.set_tool(TOOL_CROP)
        elif self.canvas.tool == TOOL_CROP:
            checked = [k for k, b in self.tool_buttons.items() if b.isChecked()]
            self.canvas.set_tool(checked[0] if checked else TOOL_PAN)
        if view == VIEW_ORIG and self.full_bgr is not None:
            self.canvas.set_overlay(None)
            self.canvas.set_image(self.full_bgr, fit=True)
            self.canvas._fit_pending = True
            self._show_crop_rect()
            return
        self.canvas.set_crop_rect(None)
        if view in (VIEW_WALL, VIEW_MASK) and self._prev_view == VIEW_ORIG:
            self.canvas._fit_pending = True
        self.request()

    # ======================================================================
    # Prüfung / Status
    # ======================================================================
    def update_checks(self):
        if self.src_gray is None or not self.last_full:
            self.check_label.setText(f"<span style='color:{theme.TEXT_2}'>" + T(
                "Noch kein Bild geladen. Ziehe ein Bild in die Vorschau – oder lade über ☰ das Beispiel.") + "</span>")
            self.status.setText("")
            return
        res: proc.Result = self.last_full["res"]
        p: proc.Params = self.last_full["params"]
        ok, warn, bad = theme.GREEN, theme.ORANGE, theme.RED
        rows = []

        def row(color, sym, text):
            rows.append(f"<tr><td style='color:{color};font-weight:bold;padding-right:6px'>{sym}</td>"
                        f"<td>{text}</td></tr>")

        if p.backplate:
            row(ok, "✔", T("Rückplatte hält alle Teile zusammen"))
        elif res.loose_after == 0:
            extra = T(" ({n} Stege ergänzt – blau)", n=res.bridge_count) if res.bridge_count else ""
            row(ok, "✔", T("Alles hängt zusammen") + extra)
        else:
            row(bad, "✖", T("{n} lose Teile würden herausfallen (rot) – „Lose Teile: Automatisch verbinden“ wählen "
                            "oder mit „Steg“ anbinden", n=res.loose_after))
        if res.thin_count:
            row(warn, "⚠", T("{n} Stellen dünner als {w} mm (orange) – „Linien dicker“ oder „automatisch verstärken“",
                             n=res.thin_count, w=de(p.min_line_mm, 2)))
        else:
            row(ok, "✔", T("Alle Linien mindestens {w} mm breit", w=de(p.min_line_mm, 2)))
        if res.narrow_count:
            row(warn, "⚠", T("{n} sehr enge Lücken (lila) – könnten zulaufen", n=res.narrow_count))
        cols, rows_n = exp.tile_grid(p)
        if cols * rows_n == 1:
            row(ok, "✔", T("Passt aufs Druckbett ({x}×{y} mm)", x=f"{p.bed_x_mm:.0f}", y=f"{p.bed_y_mm:.0f}"))
        else:
            row(warn, "⚠", T("Größer als dein Druckbett → wird beim Export in {c}×{r} Teile aufgeteilt",
                             c=cols, r=rows_n))
        bed_warning = T("Größer als das Druckbett – beim Export in Teile aufteilen.")
        for w in res.warnings:
            if w != bed_warning:
                row(warn, "⚠", w)
        grams, meters = self.last_full["material"]
        total_h = (p.backplate_mm if p.backplate else 0) + max(p.art_height_mm, p.frame_height_mm
                                                                if p.frame_shape != proc.FRAME_NONE else 0)
        info = (f"<div style='color:{theme.TEXT_2};margin-top:6px'>{p.width_mm:.0f} × {p.height_mm:.0f} × "
                f"{de(total_h, 1)} mm · " + T("ca. {g} g PLA ({m} m)", g=f"{grams:.0f}", m=de(meters, 1)))
        if p.backplate:
            info += "<br>" + T("Farbwechsel bei <b>{h} mm</b> Höhe (Rückplatte → Motiv)", h=de(p.backplate_mm, 2))
        info += "</div>"
        self.check_label.setText("<table cellspacing='0' cellpadding='1'>" + "".join(rows) + "</table>" + info)
        if self._notice:
            self.status.setText(self._notice)
            self._notice = ""
            return
        self.status.setText("  " + T("Vorschau: {p} Pixel/mm   ·   Export: {e} Pixel/mm   ·   Werkzeuge: H Ansicht · "
                                     "M Motiv · B Pinsel · E Radierer · L Steg · [ ] Pinselgröße · Strg+Z Rückgängig",
                                     p=de(self.last_full['ppm'], 1), e=f"{p.quality_ppm:.0f}"))

    def _update_title(self):
        name = os.path.basename(self.project_path) if self.project_path else self.image_name
        self.setWindowTitle(f"{name}{' •' if self._dirty else ''} – {APP_NAME}")

    # ======================================================================
    # Projekt
    # ======================================================================
    def save_project(self, save_as: bool = False) -> bool:
        if self.src_bgr is None:
            QMessageBox.information(self, APP_NAME, T("Es ist noch kein Bild geladen."))
            return False
        path = self.project_path
        if save_as or not path:
            d = self.settings.value("last_dir", os.path.expanduser("~"))
            path, _ = QFileDialog.getSaveFileName(self, T("Projekt speichern"),
                                                  os.path.join(d, self.image_name + PROJECT_EXT),
                                                  f"{T('{app}-Projekt', app=APP_NAME)} (*{PROJECT_EXT})")
            if not path:
                return False
            if not path.lower().endswith(PROJECT_EXT):
                path += PROJECT_EXT
        ok1, img = cv2.imencode(".png", self.orig_bgr)
        ok2, ed = cv2.imencode(".png", self.edits)
        data = {"app": APP_NAME, "version": 1, "name": self.image_name, "params": self.params.to_dict(),
                "image": base64.b64encode(img.tobytes()).decode("ascii"),
                "edits": base64.b64encode(ed.tobytes()).decode("ascii")}
        if self.bg_mask is not None:
            ok3, bm = cv2.imencode(".png", self.bg_mask)
            data["bgmask"] = base64.b64encode(bm.tobytes()).decode("ascii")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except OSError as e:
            QMessageBox.critical(self, APP_NAME, T("Speichern fehlgeschlagen:\n{e}", e=e))
            return False
        self.project_path = path
        self.settings.setValue("last_dir", os.path.dirname(path))
        self._dirty = False
        self._update_title()
        self.status.setText("  " + T("Projekt gespeichert: {p}", p=path))
        return True

    def load_project_dialog(self):
        d = self.settings.value("last_dir", os.path.expanduser("~"))
        path, _ = QFileDialog.getOpenFileName(self, T("Projekt öffnen"), d,
                                              f"{T('{app}-Projekt', app=APP_NAME)} (*{PROJECT_EXT} *{LEGACY_PROJECT_EXT})")
        if path:
            self.load_project(path)

    def load_project(self, path: str):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            img = cv2.imdecode(np.frombuffer(base64.b64decode(data["image"]), np.uint8), cv2.IMREAD_COLOR)
            ed = cv2.imdecode(np.frombuffer(base64.b64decode(data["edits"]), np.uint8), cv2.IMREAD_UNCHANGED)
            params = proc.Params.from_dict(data.get("params", {}))
            bm = None
            if data.get("bgmask"):
                bm = cv2.imdecode(np.frombuffer(base64.b64decode(data["bgmask"]), np.uint8), cv2.IMREAD_UNCHANGED)
        except Exception as e:
            QMessageBox.critical(self, APP_NAME, T("Projekt konnte nicht geöffnet werden:\n{e}", e=e))
            return
        if img is None:
            QMessageBox.critical(self, APP_NAME, T("Projektdatei ist beschädigt."))
            return
        if not self._confirm_discard():
            return
        self._dirty = False
        self.params = params
        if ed is None or ed.shape != img.shape[:2]:
            ed = None
        self.set_source(img, data.get("name", "projekt"), keep_params=True, edits=ed, bg_mask=bm)
        self.project_path = path
        self.sync_controls()
        self.update_visibility()
        self._update_title()

    def _confirm_discard(self) -> bool:
        if not self._dirty or self.src_gray is None:
            return True
        r = QMessageBox.question(self, APP_NAME, T("Das aktuelle Projekt hat ungespeicherte Änderungen.\n"
                                                   "Möchtest du es vorher speichern?"),
                                 QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard |
                                 QMessageBox.StandardButton.Cancel)
        if r == QMessageBox.StandardButton.Cancel:
            return False
        if r == QMessageBox.StandardButton.Save:
            return self.save_project()
        return True

    def reset_settings(self):
        keep = {k: getattr(self.params, k) for k in PERSISTENT_KEYS}
        w, h = self.params.width_mm, self.params.height_mm
        self.params = proc.Params(**keep)
        self.params.width_mm, self.params.height_mm = w, h
        self.preset.setValue("line")
        self.sync_controls()
        self.update_visibility()
        self.changed()

    # ======================================================================
    # Export
    # ======================================================================
    def export_dialog(self):
        if self.src_gray is None:
            QMessageBox.information(self, APP_NAME, T("Bitte zuerst ein Bild laden."))
            return
        if self.commit_timer.isActive():
            self.commit()
        p = self.params.copy()
        dlg = ExportDialog(self, p, self.settings.value("export_dir", self.settings.value("last_dir",
                                                                                        os.path.expanduser("~"))),
                           self.image_name, self.last_full)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        opts = dlg.options()
        folder, base = opts["folder"], opts["name"]
        self.settings.setValue("export_dir", folder)

        prog = QProgressDialog(T("Berechne druckfertiges Modell …"), "", 0, 100, self)
        prog.setCancelButton(None)
        prog.setWindowTitle(T("Export"))
        prog.setWindowModality(Qt.WindowModality.WindowModal)
        prog.setMinimumDuration(0)
        prog.setValue(1)

        gray, edits = self.src_gray, self._cropped_edits()

        task_sig = _Signals()

        def work():
            task_sig.progress.emit(T("Berechne Motiv in voller Auflösung …"), 0.02)
            # sehr große Bilder: Auflösung begrenzen (max. ca. 40 Mio. Pixel), damit der Speicher reicht
            ppm = min(p.quality_ppm, math.sqrt(40e6 / max(1.0, p.width_mm * p.height_mm)))
            res = proc.process(gray, edits, p, ppm, analyse=False)
            files = exp.export_all(res, p, folder, base, opts,
                                   progress=lambda t, f: task_sig.progress.emit(t, f))
            loose_tiles = 0
            if opts.get("split") and not p.backplate and opts["cols"] * opts["rows"] > 1:
                h, w = res.mask.shape
                xs = np.linspace(0, w, opts["cols"] + 1).round().astype(int)
                ys = np.linspace(0, h, opts["rows"] + 1).round().astype(int)
                for r in range(opts["rows"]):
                    for c in range(opts["cols"]):
                        if proc.count_blobs(res.mask[ys[r]:ys[r + 1], xs[c]:xs[c + 1]] > 0) > 1:
                            loose_tiles += 1
            return files, loose_tiles

        t = Task(0, work)
        self._live.add(t.signals)
        self._live.add(task_sig)

        def on_prog(text, frac):
            prog.setLabelText(text)
            prog.setValue(int(frac * 100))

        task_sig.progress.connect(on_prog)
        def cleanup():
            prog.close()
            self._live.discard(t.signals)
            self._live.discard(task_sig)

        t.signals.done.connect(lambda _g, out: (cleanup(), self._export_done(out, p, folder)))
        t.signals.failed.connect(lambda _g, tb: (cleanup(), QMessageBox.critical(
            self, APP_NAME, T("Beim Export ist ein Fehler aufgetreten:\n\n") + tb[-1500:])))
        self.pool.start(t)

    def _export_done(self, out, p, folder):
        files, loose_tiles = out
        names = "".join(f"<li>{os.path.basename(f)}</li>" for f in files)
        tips = [T("Im Slicer flach auf das Druckbett legen (Vorderseite nach oben)."),
                T("Empfehlung: 0,2 mm Schichthöhe, 2–3 Wandlinien, 15–20 % Füllung.")]
        if p.backplate:
            tips.insert(0, T("<b>Einfarbiger Drucker:</b> „_komplett.stl“ laden und bei <b>{h} mm</b> einen "
                             "Farbwechsel/Pause einfügen.", h=de(p.backplate_mm, 2)))
            tips.insert(1, T("<b>Mehrfarbdrucker (AMS/MMU):</b> „_motiv.stl“ und „_rueckplatte.stl“ gleichzeitig "
                             "laden → „als ein Objekt mit mehreren Teilen“ bestätigen und Farben zuweisen."))
        if loose_tiles:
            tips.append(T("Hinweis: In {n} Teilstück(en) gibt es Stücke, die erst beim Zusammenkleben "
                          "Halt bekommen.", n=loose_tiles))
        msg = QMessageBox(self)
        msg.setWindowTitle(T("Export fertig"))
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setText(T("<b>{n} Datei(en) gespeichert:</b>", n=len(files)) + f"<ul>{names}</ul>"
                    + T("<b>Tipps:</b>") + "<ul>" + "".join(f"<li>{t}</li>" for t in tips) + "</ul>")
        open_btn = msg.addButton(T("Ordner öffnen"), QMessageBox.ButtonRole.ActionRole)
        msg.addButton("OK", QMessageBox.ButtonRole.AcceptRole)
        msg.exec()
        if msg.clickedButton() == open_btn:
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    # ======================================================================
    # Hilfe, Einstellungen, Fenster
    # ======================================================================
    def show_help(self):
        QMessageBox.information(self, T("Kurzanleitung"), help_text())

    def _set_language(self, code: str):
        for c, a in self.lang_actions.items():
            a.setChecked(c == i18n.LANG)
        if code == i18n.LANG:
            return
        self.settings.setValue("language", code)
        key = "Die Sprache wird nach einem Neustart übernommen. Jetzt neu starten?"
        text = i18n.EN.get(key, key) if code == "en" else key  # schon in der neuen Sprache fragen
        r = QMessageBox.question(self, APP_NAME, text)
        if r != QMessageBox.StandardButton.Yes:
            return
        if not self._confirm_discard():
            return
        self._dirty = False
        from PySide6.QtCore import QProcess
        if getattr(sys, "frozen", False):
            QProcess.startDetached(sys.executable, [])
        else:
            QProcess.startDetached(sys.executable, [os.path.abspath(sys.argv[0])])
        self.close()

    def _toggle_gpu(self, on: bool):
        self.settings.setValue("use_gpu", "true" if on else "false")
        QMessageBox.information(self, APP_NAME, T("Die Änderung wird beim nächsten Start des Programms wirksam.\n\n"
                                                  "Tipp: Nur abschalten, wenn die Vorschau mit Grafikkarte Fehler "
                                                  "zeigt."))

    def _load_persistent(self):
        raw = self.settings.value("persistent", "")
        if raw:
            try:
                d = json.loads(raw)
                for k in PERSISTENT_KEYS:
                    if k in d:
                        setattr(self.params, k, type(getattr(self.params, k))(d[k]))
            except Exception:
                pass

    def closeEvent(self, e):
        if not self._confirm_discard():
            e.ignore()
            return
        self.settings.setValue("persistent", json.dumps({k: getattr(self.params, k) for k in PERSISTENT_KEYS}))
        e.accept()

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        urls = e.mimeData().urls()
        if urls:
            self.open_path(urls[0].toLocalFile())


def _top_w_hbody(p, ppm):
    w, h, top = proc._sizes(p, ppm)
    return top, w, h - top


# ---------------------------------------------------------------------------
# Export-Dialog
# ---------------------------------------------------------------------------

class ExportDialog(QDialog):
    def __init__(self, parent, p: proc.Params, folder: str, name: str, last_full):
        super().__init__(parent)
        self.setWindowTitle("3D-Datei exportieren")
        self.setMinimumWidth(520)
        self.p = p
        lay = QVBoxLayout(self)

        g = QGridLayout()
        g.addWidget(QLabel("Dateiname:"), 0, 0)
        self.ed_name = QLineEdit(_safe_name(name))
        g.addWidget(self.ed_name, 0, 1, 1, 2)
        g.addWidget(QLabel("Ordner:"), 1, 0)
        self.ed_folder = QLineEdit(folder)
        g.addWidget(self.ed_folder, 1, 1)
        b = QPushButton("Durchsuchen …")
        b.clicked.connect(self._browse)
        g.addWidget(b, 1, 2)
        lay.addLayout(g)

        box = QGroupBox("Dateien")
        bl = QVBoxLayout(box)
        self.cb_separate = QCheckBox("Motiv und Rückplatte als getrennte Dateien (Mehrfarbdrucker / AMS)")
        self.cb_combined = QCheckBox("Alles in einer Datei (einfarbiger Drucker mit Farbwechsel-Pause)")
        self.cb_separate.setChecked(True)
        self.cb_combined.setChecked(True)
        if p.backplate:
            bl.addWidget(self.cb_separate)
            bl.addWidget(self.cb_combined)
        else:
            lab = QLabel("Es wird eine STL-Datei mit Motiv und Rahmen erstellt.")
            bl.addWidget(lab)
        self.cb_svg = QCheckBox("Zusätzlich SVG (für Lasercutter / Plotter / CAD)")
        self.cb_png = QCheckBox("Zusätzlich PNG-Vorlage (schwarz/weiß)")
        bl.addWidget(self.cb_svg)
        bl.addWidget(self.cb_png)
        lay.addWidget(box)

        box = QGroupBox("Aufteilen (für große Bilder)")
        bl = QGridLayout(box)
        cols, rows = exp.tile_grid(p)
        self.cb_split = QCheckBox("In mehrere Teile aufteilen")
        self.cb_split.setChecked(cols * rows > 1)
        bl.addWidget(self.cb_split, 0, 0, 1, 4)
        bl.addWidget(QLabel("Spalten:"), 1, 0)
        self.sp_cols = QSpinBox()
        self.sp_cols.setRange(1, 10)
        self.sp_cols.setValue(cols)
        bl.addWidget(self.sp_cols, 1, 1)
        bl.addWidget(QLabel("Zeilen:"), 1, 2)
        self.sp_rows = QSpinBox()
        self.sp_rows.setRange(1, 10)
        self.sp_rows.setValue(rows)
        bl.addWidget(self.sp_rows, 1, 3)
        self.lab_tile = QLabel()
        self.lab_tile.setObjectName("hint")
        bl.addWidget(self.lab_tile, 2, 0, 1, 4)
        for w in (self.sp_cols, self.sp_rows):
            w.valueChanged.connect(self._upd)
        self.cb_split.toggled.connect(self._upd)
        lay.addWidget(box)

        info = QLabel()
        info.setWordWrap(True)
        info.setObjectName("hint")
        q = {6.0: T("Entwurf"), 10.0: T("Normal"), 16.0: T("Fein")}.get(p.quality_ppm, f"{p.quality_ppm:.0f} px/mm")
        txt = T("Größe: {w} × {h} mm · Qualität: {q}", w=f"{p.width_mm:.0f}", h=f"{p.height_mm:.0f}", q=q)
        if last_full:
            res = last_full["res"]
            if not p.backplate and res.loose_after:
                txt += f"<br><span style='color:{theme.RED}'>" + T("Achtung: {n} lose Teile!", n=res.loose_after) + "</span>"
            if res.thin_count:
                txt += f"<br><span style='color:{theme.ORANGE}'>" + T("{n} sehr dünne Stellen.", n=res.thin_count) + "</span>"
        info.setText(txt)
        lay.addWidget(info)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Ok).setText("Exportieren")
        bb.button(QDialogButtonBox.StandardButton.Cancel).setText("Abbrechen")
        bb.accepted.connect(self._accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        translate_tree(self)
        self._upd()

    def _upd(self):
        on = self.cb_split.isChecked()
        self.sp_cols.setEnabled(on)
        self.sp_rows.setEnabled(on)
        c, r = (self.sp_cols.value(), self.sp_rows.value()) if on else (1, 1)
        tw, th = self.p.width_mm / c, self.p.height_mm / r
        fits = (tw <= self.p.bed_x_mm and th <= self.p.bed_y_mm) or (tw <= self.p.bed_y_mm and th <= self.p.bed_x_mm)
        self.lab_tile.setText(T("Jedes Teil: {w} × {h} mm – ", w=f"{tw:.0f}", h=f"{th:.0f}") +
                              (T("passt aufs Druckbett ✔") if fits else f"<span style='color:{theme.RED}'>"
                               + T("zu groß für dein Druckbett ✖") + "</span>"))

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, T("Ordner wählen"), self.ed_folder.text())
        if d:
            self.ed_folder.setText(d)

    def _accept(self):
        if not self.ed_name.text().strip():
            QMessageBox.warning(self, APP_NAME, T("Bitte einen Dateinamen eingeben."))
            return
        if not os.path.isdir(self.ed_folder.text()):
            try:
                os.makedirs(self.ed_folder.text(), exist_ok=True)
            except OSError:
                QMessageBox.warning(self, APP_NAME, T("Der Ordner ist ungültig."))
                return
        self.accept()

    def options(self) -> dict:
        return dict(folder=self.ed_folder.text(), name=_safe_name(self.ed_name.text()),
                    separate=self.cb_separate.isChecked(), combined=self.cb_combined.isChecked(),
                    split=self.cb_split.isChecked(), cols=self.sp_cols.value(), rows=self.sp_rows.value(),
                    svg=self.cb_svg.isChecked(), png=self.cb_png.isChecked())


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def de(v: float, d: int = 1) -> str:
    """Zahl mit dem Dezimaltrennzeichen der eingestellten Sprache."""
    return num(v, d)


def _safe_name(s: str) -> str:
    bad = '<>:"/\\|?*'
    s = "".join("_" if ch in bad else ch for ch in s.strip())
    return s or "remstudio"


def read_image(path: str):
    try:
        data = np.fromfile(path, np.uint8)
    except OSError:
        return None
    img = cv2.imdecode(data, cv2.IMREAD_UNCHANGED)
    if img is None:
        # z. B. GIF/WebP, das OpenCV nicht kann -> über Qt versuchen
        q = QImage(path)
        if q.isNull():
            return None
        return qimage_to_bgr(q)
    return normalize_image(img)


def normalize_image(img: np.ndarray) -> np.ndarray:
    if img.dtype != np.uint8:
        img = cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    if img.ndim == 2:
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    if img.shape[2] == 4:
        # Transparenz -> weißer Hintergrund
        a = img[:, :, 3:4].astype(np.float32) / 255.0
        rgb = img[:, :, :3].astype(np.float32)
        return (rgb * a + 255 * (1 - a)).astype(np.uint8)
    return img[:, :, :3].copy()


def qimage_to_bgr(q: QImage) -> np.ndarray:
    q = q.convertToFormat(QImage.Format.Format_RGBA8888)
    w, h = q.width(), q.height()
    ptr = q.constBits()
    arr = np.frombuffer(ptr, np.uint8, count=q.bytesPerLine() * h).reshape(h, q.bytesPerLine() // 4, 4)[:, :w]
    rgba = arr.copy()
    bgra = rgba[:, :, [2, 1, 0, 3]]
    return normalize_image(bgra)


HELP_TEXT = """<h3>So geht's in 5 Schritten</h3>
<ol>
<li><b>Bild laden</b> – per Drag &amp; Drop, „Bild öffnen“ oder Strg+V. Am besten eignen sich klare
Strichzeichnungen, Comics, Logos oder Silhouetten. Stört der Hintergrund, klicke auf
<b>„🪄 Hintergrund entfernen“</b> – die KI stellt das Motiv automatisch frei.</li>
<li><b>Bildart wählen</b> (①) und mit <i>Schwelle</i>, <i>Linien dicker/dünner</i> und
<i>Kleine Flecken entfernen</i> nachjustieren, bis die Wandansicht gut aussieht.</li>
<li><b>Rahmen &amp; Größe</b> (②) festlegen. Mit „✥ Motiv“ kannst du das Motiv ziehen und mit dem Mausrad
vergrößern – ragt es über den Rahmen, wird es abgeschnitten (wie bei Wandbildern üblich).</li>
<li><b>Prüfung</b> oben rechts beachten: Lose Teile werden automatisch mit kleinen Stegen (blau) an den Rahmen
gebunden. Orange Stellen sind zu dünn. Mit 🖌 Pinsel, ⌫ Radierer und ╱ Steg kannst du von Hand nachbessern.</li>
<li><b>Exportieren</b> – die STL-Datei im Slicer (Bambu Studio, PrusaSlicer, Cura …) öffnen und drucken.</li>
</ol>
<h3>Tipps</h3>
<ul>
<li>Zweifarbig wie im Beispielfoto: „Rückplatte“ aktivieren. Dann halten auch lose Teile.</li>
<li>Für eine 0,4-mm-Düse sollten Linien mindestens 0,8 mm breit sein.</li>
<li>Leertaste gedrückt halten = Ansicht verschieben, Mausrad = zoomen, [ und ] = Pinselgröße.</li>
<li>„↶ Rückgängig“ / „↷ Wiederholen“ oben links (oder Strg+Z / Strg+Y). Strg+S speichert das Projekt
inkl. Korrekturen und Hintergrund-Entfernung.</li>
</ul>"""
