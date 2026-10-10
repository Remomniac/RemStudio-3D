"""Schnelltest für RemStudio 3D – prüft die wichtigsten Funktionen ohne Bedienung.

Aufruf (im Projektordner):
    .venv\\Scripts\\python.exe tests\\smoke_test.py            # alle Tests
    .venv\\Scripts\\python.exe tests\\smoke_test.py --no-gui   # nur Kern (Bildverarbeitung + 3D-Netz)

Nutzt eigene Test-Einstellungen (Registry „RemStudio3D_test“) – die echten Einstellungen bleiben unberührt.
Läuft unsichtbar (Qt „offscreen“, ohne OpenGL). Exit-Code 0 = alles ok.
"""
import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("REMSTUDIO_NO_GL", "1")

import numpy as np  # noqa: E402

failures = []


def check(name, ok, info=""):
    print(f"{'✅' if ok else '❌'} {name}" + (f" – {info}" if info else ""))
    if not ok:
        failures.append(name)


def test_core():
    import cv2
    from remstudio import processing as P, mesh as M, samples
    gray = cv2.cvtColor(samples.demo_image(), cv2.COLOR_BGR2GRAY)
    for shape in ("rect", "rounded", "circle", "hexagon", "none"):
        for back in (False, True):
            hang = {"rect": "holes", "circle": "tab"}.get(shape, "none")
            p = P.Params(frame_shape=shape, backplate=back, hang=hang, frame_height_mm=5)
            r = P.process(gray, None, p, 6.0)
            parts = M.build_meshes(r, p)
            for name, m in parts.items():
                f = m.faces
                e = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
                key, rkey = e[:, 0] * 10 ** 7 + e[:, 1], e[:, 1] * 10 ** 7 + e[:, 0]
                closed = bool(np.isin(key, rkey).all()) and len(np.unique(key)) == len(key)
                check(f"3D-Netz geschlossen: {shape}, Rückplatte={back}, {name}", closed and m.volume_mm3() > 0,
                      f"{m.triangle_count} Dreiecke")
            if not back:
                check(f"Keine losen Teile: {shape}", r.loose_after == 0, f"{r.bridge_count} Stege")


def test_gui():
    from PySide6.QtWidgets import QApplication, QDialog
    from PySide6.QtCore import QSettings
    import app as appmod
    from remstudio import i18n, main_window as mw, bg_editor as be, bgremove as bg
    test_settings = QSettings("RemStudio", "RemStudio3D_test")
    test_settings.clear()
    test_settings.setValue("bg_auto_open", "false")
    mw.QSettings = lambda *a: QSettings("RemStudio", "RemStudio3D_test")
    i18n.set_language("en")
    qapp = QApplication.instance() or QApplication(sys.argv)
    appmod.setup_app(qapp)
    errors = []
    sys.excepthook = lambda t, v, tb: errors.append(f"{t.__name__}: {v}")
    from PySide6.QtWidgets import QMessageBox
    QMessageBox.critical = staticmethod(lambda *a, **k: errors.append(str(a[2])[:300]))
    QMessageBox.warning = staticmethod(lambda *a, **k: errors.append(str(a[2])[:300]))
    QMessageBox.information = staticmethod(lambda *a, **k: None)
    win = mw.MainWindow()
    win.resize(1400, 860)
    win.show()

    def pump(s):
        t = time.time()
        while time.time() - t < s:
            qapp.processEvents()
            time.sleep(0.01)

    def idle(timeout=30):
        pump(0.3)
        t = time.time()
        while (win.busy or win.pending or win.full_timer.isActive()) and time.time() - t < timeout:
            pump(0.05)
        pump(0.2)

    win._dirty = False
    win.load_demo()
    idle()
    check("Vorschau berechnet", win.last_full is not None)
    # Pinselstrich + Rückgängig/Wiederholen
    sc, pad = win.shown["scale"], win.shown["pad"]
    win.on_stroke([((pad + 300 + i * 5) * sc, (pad + 300) * sc) for i in range(40)], mw.TOOL_BRUSH)
    idle()
    painted = int((win.edits > 0).sum())
    win.undo(); idle()
    after_undo = int((win.edits > 0).sum())
    win.redo(); idle()
    check("Pinsel + Rückgängig + Wiederholen", painted > 0 and after_undo == 0 and int((win.edits > 0).sum()) == painted)
    # Motiv per Grafikkarten-Vorschau verschieben (ohne Neuberechnung)
    t = time.perf_counter()
    for _ in range(30):
        win.on_motif_drag(0.5, 0.2)
    ms = (time.perf_counter() - t) / 30 * 1000
    check("Motiv verschieben schnell", ms < 50, f"{ms:.1f} ms pro Bewegung")
    idle()
    # Projekt speichern / laden
    tmp = tempfile.mkdtemp(prefix="remstudio_test_")
    win.project_path = os.path.join(tmp, "test.remstudio")
    ok = win.save_project()
    win._dirty = False
    win.load_project(win.project_path)
    idle()
    check("Projekt speichern/laden", ok and int((win.edits > 0).sum()) == painted)
    # Export (Dialog automatisch bestätigen)
    def auto_exec(dlg):
        dlg.ed_folder.setText(os.path.join(tmp, "export"))
        dlg.cb_svg.setChecked(True)
        return QDialog.DialogCode.Accepted
    mw.ExportDialog.exec = auto_exec
    done = []
    win._export_done = lambda out, p, folder: done.append(out)
    win.export_dialog()
    t = time.time()
    while not done and time.time() - t < 120 and not errors:
        pump(0.1)
    files = done[0][0] if done else []
    check("Export STL + SVG", any(f.endswith(".stl") for f in files) and any(f.endswith(".svg") for f in files),
          f"{len(files)} Dateien")
    # Hintergrund-Editor (nur wenn ein KI-Modell vorhanden ist)
    name = next((n for n in ("u2netp", bg.DEFAULT_MODEL) if bg.model_available(n)), None)
    if name:
        test_settings.setValue("bg_model", name)
        dlg = be.BackgroundEditor(win, win.orig_bgr, None, 0, test_settings, onboarding=False)
        dlg.show(); pump(0.3)
        dlg.run_ai()
        t = time.time()
        while not dlg.isEnabled() and time.time() - t < 60:
            pump(0.05)
        check("KI-Hintergrund-Erkennung läuft", dlg.hidx >= 1, f"Modell {name}")
        dlg.close()
    else:
        print("⏭️  KI-Test übersprungen (kein Modell heruntergeladen)")
    # Übersetzung: in Englisch darf kein deutscher Text übrig sein
    import re
    from PySide6.QtWidgets import QWidget, QLabel, QAbstractButton, QComboBox
    german = re.compile(r"[äöüÄÖÜß]|\b(und|nicht|wird|Bild|Rahmen|Motiv|Hintergrund|Ansicht|Pinsel|Prüfung)\b")
    left = set()
    for w in [win] + win.findChildren(QWidget):
        texts = [w.toolTip()]
        if isinstance(w, (QLabel, QAbstractButton)):
            texts.append(w.text())
        if isinstance(w, QComboBox):
            texts += [w.itemText(i) for i in range(w.count())]
        for txt in texts:
            for part in (txt or "").split("\n\n"):
                if german.search(part):
                    left.add(part[:60])
    check("Englische Oberfläche vollständig übersetzt", not left, "; ".join(sorted(left))[:300])
    check("Keine Fehlermeldungen", not errors, "; ".join(errors)[:300])
    win._dirty = False
    test_settings.clear()


if __name__ == "__main__":
    test_core()
    if "--no-gui" not in sys.argv:
        test_gui()
    print(f"\n{'✅ Alle Tests bestanden' if not failures else f'❌ {len(failures)} Test(s) fehlgeschlagen'}")
    sys.exit(1 if failures else 0)
