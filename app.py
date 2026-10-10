"""RemStudio 3D – Bilder in druckbare 3D-Wandbilder mit Rahmen verwandeln."""
import os
import sys
import traceback

from PySide6.QtCore import Qt, QSettings, QLocale, QTranslator, QLibraryInfo
from PySide6.QtGui import QIcon, QSurfaceFormat
from PySide6.QtWidgets import QApplication, QMessageBox

from remstudio import canvas as canvas_mod
from remstudio import theme
from remstudio import i18n
from remstudio.main_window import MainWindow, APP_NAME


def excepthook(etype, value, tb):
    text = "".join(traceback.format_exception(etype, value, tb))
    print(text, file=sys.stderr)
    try:
        from remstudio.i18n import T
        QMessageBox.critical(None, APP_NAME, T("Ein unerwarteter Fehler ist aufgetreten:\n\n") + text[-2000:])
    except Exception:
        pass


def setup_app(app: QApplication):
    """Dunkles, modernes Erscheinungsbild + App-Symbol."""
    theme.setup_app(app)
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    icon = os.path.join(base, "icon.ico")
    if os.path.exists(icon):
        app.setWindowIcon(QIcon(icon))


def main():
    sys.excepthook = excepthook
    fmt = QSurfaceFormat()
    fmt.setDepthBufferSize(24)
    fmt.setSamples(4)
    QSurfaceFormat.setDefaultFormat(fmt)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    settings = QSettings("RemStudio", "RemStudio3D")
    # Sprache (Standard: Englisch) – samt Zahlenformat und Qt-Standardknöpfen
    i18n.set_language(str(settings.value("language", i18n.DEFAULT_LANGUAGE)))
    if i18n.LANG == "de":
        QLocale.setDefault(QLocale(QLocale.Language.German, QLocale.Country.Germany))
        tr = QTranslator(app)
        if tr.load("qtbase_de", QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
            app.installTranslator(tr)
    else:
        QLocale.setDefault(QLocale(QLocale.Language.English, QLocale.Country.UnitedStates))
    # Grafikkarte für die Vorschau (in den Einstellungen abschaltbar)
    if settings.value("use_gpu", "true") in ("false", False):
        canvas_mod.USE_GL = False
    setup_app(app)
    win = MainWindow()
    win.show()
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        win.open_path(sys.argv[1])
    if os.environ.get("REMSTUDIO_SELFTEST"):
        _selftest(app, win, os.environ["REMSTUDIO_SELFTEST"])
    sys.exit(app.exec())


def _selftest(app, win, out_path):
    """Interner Test für die fertig gebaute EXE: Beispiel laden, 3D, Export, Ergebnis in Datei."""
    from PySide6.QtCore import QTimer
    from remstudio import processing as proc, export as exp

    def run():
        try:
            win.load_demo()
            win.set_view("3d")
            QTimer.singleShot(4000, finish)
        except Exception:
            done(traceback.format_exc())

    def finish():
        try:
            res = proc.process(win.src_gray, win._cropped_edits(), win.params, 4.0)
            files = exp.export_all(res, win.params, os.path.dirname(out_path), "selftest", {"svg": True})
            from remstudio import bgremove as bg
            ai = "kein Modell"
            if bg.model_available(bg.DEFAULT_MODEL):
                m = bg.ai_mask(win.orig_bgr, bg.DEFAULT_MODEL)
                ai = f"ai_fg={100 * (m >= 128).mean():.0f}%"
            done(f"ok shown={win.shown is not None} items3d={len(win.viewer.items)} files={len(files)} {ai}")
        except Exception:
            done(traceback.format_exc())

    def done(text):
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text)
        win._dirty = False
        app.quit()

    QTimer.singleShot(500, run)


if __name__ == "__main__":
    main()
