"""Zwischen-Editor zum Entfernen des Bildhintergrunds."""
from __future__ import annotations

import traceback

import cv2
import numpy as np
from PySide6.QtCore import Qt, QObject, Signal, QRunnable, QThreadPool, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QVBoxLayout, QWidget, QPushButton, QLabel, QFrame,
                               QButtonGroup, QToolButton, QScrollArea, QMessageBox, QProgressDialog, QCheckBox,
                               QApplication, QSlider)

from . import bgremove as bg
from .canvas import Canvas, TOOL_PAN, TOOL_BRUSH, TOOL_ERASE, TOOL_CROP
from .widgets import ParamSlider, Section, ChoiceBox, labeled, Slider
from .i18n import T, translate_tree

WORK_MAX = 1600  # Arbeitsauflösung im Editor


class _Sig(QObject):
    done = Signal(object)
    failed = Signal(str)
    progress = Signal(float)


class _Job(QRunnable):
    def __init__(self, fn, *args):
        super().__init__()
        self.fn, self.args = fn, args
        self.sig = _Sig()

    def run(self):
        try:
            res = self.fn(*self.args)
        except Exception:
            res, err = None, traceback.format_exc()
        else:
            err = None
        try:
            if err is None:
                self.sig.done.emit(res)
            else:
                self.sig.failed.emit(err)
        except RuntimeError:
            pass  # Fenster wurde inzwischen geschlossen


class BackgroundEditor(QDialog):
    """Ergebnis nach ``exec()``: ``result_mask`` (volle Auflösung, 255 = behalten), ``outline_px``,
    ``crop_to_subject`` oder ``result_mask is None`` = Hintergrund nicht entfernen."""

    VIEW_RESULT, VIEW_MARK, VIEW_ORIG = "result", "mark", "orig"

    def __init__(self, parent, bgr: np.ndarray, mask: np.ndarray | None, outline_px: float, settings,
                 onboarding: bool = False):
        super().__init__(parent)
        self.onboarding = onboarding
        self.setWindowTitle("Schritt 1 von 2: Hintergrund entfernen" if onboarding else "Hintergrund entfernen")
        self.resize(1320, 860)
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
        self.settings = settings
        self.full = bgr
        H, W = bgr.shape[:2]
        self.f = min(1.0, WORK_MAX / max(H, W))
        self.img = cv2.resize(bgr, (int(round(W * self.f)), int(round(H * self.f))),
                              interpolation=cv2.INTER_AREA) if self.f < 1 else bgr.copy()
        h, w = self.img.shape[:2]
        if mask is not None:
            m = cv2.resize(mask, (w, h), interpolation=cv2.INTER_AREA) if self.f < 1 else mask.copy()
            self.base = np.where(m >= 128, 255, 0).astype(np.uint8)
        else:
            self.base = np.full((h, w), 255, np.uint8)
        self.keep_hint = np.zeros((h, w), np.uint8)
        self.remove_hint = np.zeros((h, w), np.uint8)
        self.history = [self.base.copy()]
        self.hidx = 0
        self.view = self.VIEW_MARK if mask is not None else self.VIEW_ORIG
        self.pool = QThreadPool.globalInstance()
        self._live = set()
        self.result_mask = None
        self.outline_px = outline_px
        self.crop_to_subject = True
        self._first_paint = True

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---------------- links: Bild + Werkzeuge
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(0)
        bar = QFrame()
        bar.setObjectName("toolbar")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(8, 6, 8, 6)
        bl.setSpacing(4)
        self.btn_undo = QPushButton("↶ Rückgängig")
        self.btn_undo.setToolTip("Letzten Schritt rückgängig machen (Strg+Z)")
        self.btn_undo.clicked.connect(self.undo)
        bl.addWidget(self.btn_undo)
        self.btn_redo = QPushButton("↷ Wiederholen")
        self.btn_redo.setToolTip("Wiederholen (Strg+Y)")
        self.btn_redo.clicked.connect(self.redo)
        bl.addWidget(self.btn_redo)
        bl.addSpacing(14)
        self.view_group = QButtonGroup(self)
        for text, key, tip in (("Bearbeiten", self.VIEW_MARK, "Ganzes Bild: entfernte Bereiche erscheinen "
                                                               "durchsichtig (Karomuster), die Grenze türkis"),
                               ("Ergebnis", self.VIEW_RESULT, "So sieht das Bild ohne Hintergrund aus"),
                               ("Original", self.VIEW_ORIG, "Unverändertes Bild")):
            b = QPushButton(text)
            b.setObjectName("segment")
            b.setCheckable(True)
            b.setToolTip(tip)
            b.setProperty("k", key)
            b.setChecked(key == self.view)
            self.view_group.addButton(b)
            bl.addWidget(b)
        self.view_group.buttonClicked.connect(lambda b: self.set_view(b.property("k")))
        bl.addSpacing(14)
        lab = QLabel("Entfernter Hintergrund sichtbar:")
        lab.setToolTip("Wie stark das Originalbild in den entfernten Bereichen durchscheint")
        bl.addWidget(lab)
        self.sl_vis = Slider(Qt.Orientation.Horizontal)
        self.sl_vis.setRange(0, 100)
        self.sl_vis.setFixedWidth(130)
        self.sl_vis.setToolTip(lab.toolTip())
        try:
            self.sl_vis.setValue(int(self.settings.value("bg_visibility", 45)))
        except (TypeError, ValueError):
            self.sl_vis.setValue(45)
        self.lab_vis = QLabel(f"{self.sl_vis.value()} %")
        self.lab_vis.setFixedWidth(40)
        self.sl_vis.valueChanged.connect(self._vis_changed)
        bl.addWidget(self.sl_vis)
        bl.addWidget(self.lab_vis)
        bl.addStretch(1)
        b = QPushButton("Einpassen")
        b.clicked.connect(lambda: self.canvas.fit())
        bl.addWidget(b)
        lv.addWidget(bar)

        bar2 = QFrame()
        bar2.setObjectName("toolbar2")
        b2 = QHBoxLayout(bar2)
        b2.setContentsMargins(8, 4, 8, 4)
        b2.setSpacing(4)
        self.tool_group = QButtonGroup(self)
        self.tool_buttons = {}
        for text, key, tip in (("✋ Ansicht", TOOL_PAN, "Ansicht verschieben – Mausrad zoomt"),
                               ("□ Rechteck", TOOL_CROP, "Rechteck um das Motiv ziehen – der Rest wird "
                                                         "automatisch als Hintergrund erkannt (ohne KI)"),
                               ("🟢 Behalten", TOOL_BRUSH, "Über Bereiche malen, die zum Motiv gehören"),
                               ("🔴 Entfernen", TOOL_ERASE, "Über Bereiche malen, die weg sollen")):
            tb = QToolButton()
            tb.setObjectName("tool")
            tb.setText(text)
            tb.setCheckable(True)
            tb.setToolTip(tip)
            tb.clicked.connect(lambda _=False, k=key: self.set_tool(k))
            self.tool_group.addButton(tb)
            self.tool_buttons[key] = tb
            b2.addWidget(tb)
        b2.addSpacing(10)
        self.brush = ParamSlider("Pinselgröße", 2, 200, 1, 0, "px", "Tasten [ und ] oder Alt+Mausrad")
        self.brush.setValue(max(8, round(max(w, h) / 60)))
        self.brush.setFixedWidth(220)
        self.brush.valueChanged.connect(lambda v: self.canvas.set_brush_radius(v / 2))
        b2.addWidget(self.brush)
        b2.addStretch(1)
        lv.addWidget(bar2)

        self.canvas = Canvas()
        self.canvas.strokeFinished.connect(self.on_stroke)
        self.canvas.cropSelected.connect(self.on_rect)
        self.canvas.brushSizeStep.connect(self._brush_step)
        lv.addWidget(self.canvas, 1)
        self.status = QLabel("")
        self.status.setObjectName("statusline")
        lv.addWidget(self.status)
        root.addWidget(left, 1)

        # ---------------- rechts: Optionen
        right = QWidget()
        right.setObjectName("rightPanel")
        right.setFixedWidth(380)
        rv = QVBoxLayout(right)
        rv.setContentsMargins(10, 10, 10, 10)
        rv.setSpacing(8)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        panel = QWidget()
        pl = QVBoxLayout(panel)
        pl.setContentsMargins(0, 0, 4, 0)
        pl.setSpacing(8)
        scroll.setWidget(panel)
        rv.addWidget(scroll, 1)

        s = Section("①  Automatisch entfernen")
        self.model = ChoiceBox([(v[0], k) for k, v in bg.MODELS.items()])
        self.model.setValue(self.settings.value("bg_model", bg.DEFAULT_MODEL))
        self.model.setToolTip("Welche KI das Motiv erkennt. Probiere ein anderes, wenn das Ergebnis nicht passt.")
        s.add(labeled("Erkennung", self.model))
        self.btn_ai = QPushButton("🪄  Hintergrund automatisch entfernen")
        self.btn_ai.setObjectName("primary2")
        self.btn_ai.clicked.connect(self.run_ai)
        s.add(self.btn_ai)
        s.hint("Eine KI erkennt das Hauptmotiv (Person, Figur, Tier, Objekt) und entfernt alles andere. "
               "Läuft komplett auf deinem PC.")
        s.hint("Nicht zufrieden? Andere Erkennung wählen und nochmal klicken – oder ohne KI: Werkzeug „□ Rechteck“ wählen und ein Rechteck um das Motiv ziehen.")
        pl.addWidget(s)

        s = Section("②  Nachbessern")
        s.hint("Mit 🟢 Behalten und 🔴 Entfernen über Stellen malen, die falsch erkannt wurden. "
               "Grob malen reicht, wenn du danach „Kanten anpassen“ drückst.")
        b = QPushButton("✨  Kanten an Pinselstriche anpassen")
        b.setToolTip("Passt die Grenze zwischen Motiv und Hintergrund anhand deiner Pinselstriche an den "
                     "Bildkanten an")
        b.clicked.connect(self.run_refine)
        s.add(b)
        row = QHBoxLayout()
        b = QPushButton("Alles behalten")
        b.setToolTip("Nichts entfernen (von vorn beginnen)")
        b.clicked.connect(lambda: self._set_base(np.full_like(self.base, 255)))
        row.addWidget(b)
        b = QPushButton("Auswahl umkehren")
        b.setToolTip("Motiv und Hintergrund tauschen")
        b.clicked.connect(lambda: self._set_base(255 - self.base))
        row.addWidget(b)
        s.add(row)
        pl.addWidget(s)

        s = Section("③  Rand && Feinschliff")
        self.sl_grow = ParamSlider("Rand kleiner ↔ größer", -20, 20, 1, 0, "px",
                                   "Verschiebt die Kante nach innen (−) oder außen (+), z. B. um Hintergrund-"
                                   "Reste am Rand zu entfernen")
        self.sl_smooth = ParamSlider("Kante glätten", 0, 10, 0.5, 1, "px", "Macht ausgefranste Kanten glatter")
        self.cb_fill = QCheckBox("Löcher im Motiv füllen")
        self.cb_fill.setToolTip("Bereiche, die ganz vom Motiv umschlossen sind, bleiben erhalten")
        self.cb_fill.setChecked(True)
        self.cb_largest = QCheckBox("Kleine Streuteile entfernen")
        self.cb_largest.setToolTip("Behält nur das Hauptmotiv (und große Teile davon)")
        self.cb_largest.setChecked(True)
        self.sl_outline = ParamSlider("Umrisslinie um das Motiv", 0, 30, 0.5, 1, "px",
                                      "Zeichnet eine schwarze Linie um das Motiv – sinnvoll, wenn das Motiv "
                                      "am Rand hell ist und sonst im Hintergrund verschwinden würde")
        self.sl_outline.setValue(outline_px)
        for wdg in (self.sl_grow, self.sl_smooth, self.cb_fill, self.cb_largest, self.sl_outline):
            s.add(wdg)
            sig = wdg.valueChanged if isinstance(wdg, ParamSlider) else wdg.toggled
            sig.connect(lambda *_: self.redraw())
        pl.addWidget(s)

        s = Section("④  Danach")
        self.cb_crop = QCheckBox("Bild auf das Motiv zuschneiden")
        self.cb_crop.setToolTip("Entfernt leere Ränder, damit das Motiv den Rahmen besser ausfüllt")
        self.cb_crop.setChecked(True)
        s.add(self.cb_crop)
        pl.addWidget(s)
        pl.addStretch(1)

        self.cb_auto = QCheckBox("Nach dem Laden eines Bildes automatisch hier starten")
        self.cb_auto.setToolTip("Kann auch im Menü ☰ wieder eingeschaltet werden")
        self.cb_auto.setChecked(self.settings.value("bg_auto_open", "true") not in ("false", False))
        self.cb_auto.toggled.connect(lambda on: self.settings.setValue("bg_auto_open", "true" if on else "false"))
        rv.addWidget(self.cb_auto)
        row = QHBoxLayout()
        if onboarding:
            b = QPushButton("Hintergrund behalten")
            b.setToolTip("Nichts entfernen und mit dem Originalbild weitermachen")
            b.clicked.connect(self.keep_background)
            row.addWidget(b)
        else:
            b = QPushButton("Abbrechen")
            b.clicked.connect(self.reject)
            row.addWidget(b)
            b = QPushButton("Original verwenden")
            b.setToolTip("Hintergrund NICHT entfernen (auch eine frühere Entfernung aufheben)")
            b.clicked.connect(self.use_original)
            row.addWidget(b)
        rv.addLayout(row)
        b = QPushButton("Weiter  ›" if onboarding else "✔  Übernehmen")
        b.setObjectName("primary")
        b.clicked.connect(self.apply)
        rv.addWidget(b)
        root.addWidget(right)

        QShortcut(QKeySequence("Ctrl+Z"), self).activated.connect(self.undo)
        QShortcut(QKeySequence("Ctrl+Y"), self).activated.connect(self.redo)
        QShortcut(QKeySequence("Ctrl+Shift+Z"), self).activated.connect(self.redo)
        QShortcut(QKeySequence("["), self).activated.connect(lambda: self._brush_step(-1))
        QShortcut(QKeySequence("]"), self).activated.connect(lambda: self._brush_step(1))

        translate_tree(self)
        self.set_tool(TOOL_BRUSH if mask is not None else TOOL_PAN)
        self.canvas.set_brush_radius(self.brush.value() / 2)
        self._update_undo()
        self.redraw()
        if mask is None:
            self.status.setText("  " + T("Tipp: Klicke auf „🪄 Hintergrund automatisch entfernen“."))
        if onboarding and mask is None:
            if bg.model_available(self.model.value()):
                # direkt loslegen: KI entfernt den Hintergrund, danach nur noch prüfen und „Weiter“
                QTimer.singleShot(250, self.run_ai)
            else:
                self.status.setText("  " + T("Klicke auf „Hintergrund automatisch entfernen“ (einmaliger Download "
                                             "des KI-Modells) – oder „Hintergrund behalten“."))

    # ------------------------------------------------------------------ Maske
    def final_mask(self, scale: float = 1.0, base=None) -> np.ndarray:
        b = self.base if base is None else base
        return bg.refine(b, self.sl_grow.value() * scale, self.sl_smooth.value() * scale,
                         self.cb_fill.isChecked(), self.cb_largest.isChecked())

    def _vis_changed(self, v):
        self.lab_vis.setText(f"{v} %")
        self.settings.setValue("bg_visibility", v)
        if self.view != self.VIEW_MARK:
            self.set_view(self.VIEW_MARK)
        else:
            self.redraw()

    def _checker(self):
        """Karomuster = übliches Zeichen für „durchsichtig“."""
        if getattr(self, "_checker_img", None) is None:
            h, w = self.img.shape[:2]
            s = max(8, int(round(max(h, w) / 80)))
            yy, xx = np.mgrid[0:h, 0:w]
            c = (((yy // s) + (xx // s)) % 2).astype(np.float32)
            g = 238 - 34 * c
            self._checker_img = np.repeat(g[..., None], 3, axis=2)
        return self._checker_img

    def redraw(self):
        if self.view == self.VIEW_ORIG:
            img = self.img
        else:
            m = self.final_mask()
            if self.view == self.VIEW_RESULT:
                img = bg.composite(self.img, m, self.sl_outline.value() * self.f)
            else:
                # Bearbeiten: behaltene Bereiche voll, entfernte halbtransparent über Karomuster
                a = self.sl_vis.value() / 100.0
                faded = (self.img.astype(np.float32) * a + self._checker() * (1 - a)).astype(np.uint8)
                keep = m >= 128
                img = np.where(keep[..., None], self.img, faded)
                edge = cv2.morphologyEx(m, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)) > 0
                img[edge] = (255, 230, 0)
        self.canvas.set_image(img, fit=self._first_paint)
        self._first_paint = False

    def _set_base(self, m: np.ndarray, push: bool = True):
        self.base = m.astype(np.uint8)
        if push:
            self.history = self.history[:self.hidx + 1] + [self.base.copy()]
            if len(self.history) > 40:
                self.history = self.history[-40:]
            self.hidx = len(self.history) - 1
        self._update_undo()
        if self.view == self.VIEW_ORIG:
            self.set_view(self.VIEW_MARK)
        else:
            self.redraw()

    def undo(self):
        if self.hidx > 0:
            self.hidx -= 1
            self._set_base(self.history[self.hidx].copy(), push=False)

    def redo(self):
        if self.hidx < len(self.history) - 1:
            self.hidx += 1
            self._set_base(self.history[self.hidx].copy(), push=False)

    def _update_undo(self):
        self.btn_undo.setEnabled(self.hidx > 0)
        self.btn_redo.setEnabled(self.hidx < len(self.history) - 1)

    # ------------------------------------------------------------------ Ansicht/Werkzeuge
    def set_view(self, v):
        self.view = v
        for b in self.view_group.buttons():
            b.setChecked(b.property("k") == v)
        self.redraw()

    def set_tool(self, t):
        self.tool_buttons[t].setChecked(True)
        self.canvas.set_tool(t)
        if t != TOOL_CROP:
            self.canvas.set_crop_rect(None)
        if t in (TOOL_BRUSH, TOOL_ERASE) and self.view == self.VIEW_ORIG:
            self.set_view(self.VIEW_MARK)

    def _brush_step(self, d):
        v = self.brush.value() * (1.25 if d > 0 else 0.8)
        self.brush.setValue(round(max(2, min(200, v))), emit=True)

    def on_stroke(self, pts, tool):
        self.canvas.clear_stroke()
        val = 255 if tool == TOOL_BRUSH else 0
        hint = self.keep_hint if tool == TOOL_BRUSH else self.remove_hint
        other = self.remove_hint if tool == TOOL_BRUSH else self.keep_hint
        r = self.brush.value() / 2
        arr = np.round(np.array(pts) * 16).astype(np.int32).reshape(-1, 1, 2)
        m = self.base.copy()
        for target, v in ((m, val), (hint, 255), (other, 0)):
            if len(arr) == 1:
                cv2.circle(target, tuple(int(x) for x in arr[0, 0]), int(round(r * 16)), v, -1, cv2.LINE_8, 4)
            else:
                cv2.polylines(target, [arr], False, v, max(1, int(round(2 * r))), cv2.LINE_8, 4)
        self._set_base(m)

    def on_rect(self, x0, y0, x1, y1):
        if x0 < 0:
            return
        self.keep_hint[:] = 0
        self.remove_hint[:] = 0
        self._busy(T("Erkenne Motiv im Rechteck …"))
        self._run(bg.grabcut, self.img, (x0, y0, x1, y1), None, None, None,
                  on_done=lambda m: (self.canvas.set_crop_rect(None), self.set_tool(TOOL_BRUSH),
                                     self._set_base(m),
                                     self.status.setText("  " + T("Fertig. Mit 🟢/🔴 nachbessern, falls nötig."))))

    # ------------------------------------------------------------------ KI / Verfeinern
    def run_ai(self):
        name = self.model.value()
        self.settings.setValue("bg_model", name)
        if not bg.model_available(name):
            label, _s, _m, _sd, mb = bg.MODELS[name]
            r = QMessageBox.question(
                self, T("KI-Modell herunterladen"),
                T("Für die automatische Erkennung wird einmalig das KI-Modell „{label}“ (ca. {mb} MB) aus dem "
                  "Open-Source-Projekt rembg (GitHub) heruntergeladen.\n\nDanach funktioniert es auch ohne Internet. "
                  "Jetzt herunterladen?", label=T(label), mb=mb))
            if r != QMessageBox.StandardButton.Yes:
                return
            self._download(name, then=self.run_ai)
            return
        self._busy(T("KI erkennt das Motiv … (einige Sekunden)"))
        self.keep_hint[:] = 0
        self.remove_hint[:] = 0
        self._run(bg.ai_mask, self.img, name,
                  on_done=lambda m: (self._set_base(np.where(m >= 128, 255, 0).astype(np.uint8)),
                                     self.set_tool(TOOL_BRUSH), self.set_view(self.VIEW_MARK),
                                     self.status.setText("  " + T(
                                         "Fertig! Prüfe den Rand – mit 🟢 Behalten / 🔴 Entfernen nachbessern und "
                                         "dann „{btn}“. Fehlt etwas? Andere „Erkennung“ probieren.",
                                         btn=T("Weiter" if self.onboarding else "Übernehmen")))))

    def run_refine(self):
        if not self.keep_hint.any() and not self.remove_hint.any():
            QMessageBox.information(self, T("Hinweis"), T("Male zuerst mit 🟢 Behalten oder 🔴 Entfernen über die "
                                                          "Stellen, die angepasst werden sollen."))
            return
        self._busy(T("Passe Kanten an …"))
        self._run(bg.grabcut, self.img, None, self.base, self.keep_hint > 0, self.remove_hint > 0,
                  on_done=lambda m: (self._set_base(m), self.status.setText("  " + T("Kanten angepasst."))))

    def _download(self, name, then):
        prog = QProgressDialog(T("Lade KI-Modell herunter …"), T("Abbrechen"), 0, 100, self)
        prog.setWindowTitle(T("Download"))
        prog.setWindowModality(Qt.WindowModality.WindowModal)
        prog.setMinimumDuration(0)
        prog.setValue(0)
        state = {"cancel": False}
        prog.canceled.connect(lambda: state.update(cancel=True))
        job = _Job(bg.download_model, name, lambda f: job.sig.progress.emit(f), lambda: state["cancel"])
        self._live.add(job.sig)
        job.sig.progress.connect(lambda f: prog.setValue(int(f * 100)))

        def ok(_):
            self._live.discard(job.sig)
            prog.close()
            then()

        def fail(tb):
            self._live.discard(job.sig)
            prog.close()
            if not state["cancel"]:
                QMessageBox.warning(self, T("Download fehlgeschlagen"),
                                    T("Das Modell konnte nicht geladen werden. Bitte Internetverbindung prüfen.\n\n")
                                    + tb.strip().splitlines()[-1])

        job.sig.done.connect(ok)
        job.sig.failed.connect(fail)
        self.pool.start(job)

    def _busy(self, text):
        self.status.setText("  " + text)
        self.setEnabled(False)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

    def _idle(self):
        QApplication.restoreOverrideCursor()
        self.setEnabled(True)

    def _run(self, fn, *args, on_done):
        job = _Job(fn, *args)
        self._live.add(job.sig)

        def ok(res):
            self._live.discard(job.sig)
            self._idle()
            on_done(res)

        def fail(tb):
            self._live.discard(job.sig)
            self._idle()
            self.status.setText("  " + T("Fehler – siehe Meldung."))
            QMessageBox.warning(self, T("Fehler"), tb[-1500:])

        job.sig.done.connect(ok)
        job.sig.failed.connect(fail)
        self.pool.start(job)

    # ------------------------------------------------------------------ Abschluss
    def apply(self):
        H, W = self.full.shape[:2]
        if self.f < 1:
            up = cv2.resize(self.base, (W, H), interpolation=cv2.INTER_LINEAR)
            base = np.where(up >= 128, 255, 0).astype(np.uint8)
        else:
            base = self.base
        m = self.final_mask(scale=1 / self.f, base=base)
        if (m > 0).all():
            self.result_mask = None  # nichts entfernt
        elif not (m > 0).any():
            QMessageBox.warning(self, T("Hinweis"), T("Es wurde alles entfernt – bitte das Motiv mit 🟢 Behalten "
                                                 "markieren."))
            return
        else:
            self.result_mask = m
        self.outline_px = self.sl_outline.value()
        self.crop_to_subject = self.cb_crop.isChecked()
        self.accept()

    def keep_background(self):
        """Einstieg: Hintergrund nicht entfernen, einfach weiter."""
        self.result_mask = None
        self.outline_px = 0.0
        self.crop_to_subject = False
        self.reject()

    def use_original(self):
        self.result_mask = None
        self.outline_px = 0.0
        self.crop_to_subject = False
        self.accept()
