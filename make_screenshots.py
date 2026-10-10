"""Erzeugt die Bilder für die GitHub-Seite (README) in docs/images/.

Nutzt nur das eingebaute Beispielbild (keine fremden Bilder) und ein eigenes Test-Einstellungsprofil
(RemStudio3D_test) – die echten Einstellungen bleiben unberührt. Das Programmfenster erscheint kurz auf dem
Bildschirm (nicht anklicken, bis das Skript fertig ist).

Aufruf:  .venv\\Scripts\\python.exe make_screenshots.py [--lang en|de|all] [--only NAME ...]
         NAME: banner, steps, frames, rotate, main, 3d, editor, export, social
Die animierte 3D-Vorschau (rotate.gif) braucht Pillow:  .venv\\Scripts\\python.exe -m pip install pillow
"""
import argparse
import math
import os
import sys
import time

os.environ["REMSTUDIO_NO_GL"] = "1"  # 2D-Vorschau ohne OpenGL zeichnen, damit sie sich abfotografieren lässt
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"  # Bildschirm-Skalierung (z. B. 125 %) ignorieren -> Screenshots 1:1
os.environ["QT_FONT_DPI"] = "96"                 # … und Schriften passend dazu (sonst zu groß/abgeschnitten)

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "docs", "images")
sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402
from PySide6.QtCore import QPointF, QRectF, QSettings, Qt  # noqa: E402
from PySide6.QtGui import (QColor, QFont, QFontDatabase, QImage, QLinearGradient, QPainter, QPainterPath,  # noqa: E402
                           QPen, QRadialGradient)
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

ORANGE = "#f97316"
BG_TOP, BG_BOTTOM = "#1c1d22", "#0e0f11"

TEXTS = {
    "en": {
        "tagline": "Turn images and drawings into\nprint-ready 3D wall art.",
        "chips": ["Free & open source", "Windows 10 / 11", "STL for any 3D printer"],
        "steps": [("Load an image", "Drawing, comic, logo or photo"),
                  ("Get a printable motif", "Bridges & checks happen automatically"),
                  ("Export & print", "STL with frame – ready for your slicer")],
        "frames": ["Rectangle", "Rounded", "Circle / oval", "Hexagon", "No frame"],
    },
    "de": {
        "tagline": "Verwandle Bilder und Zeichnungen in\ndruckfertige 3D-Wandbilder.",
        "chips": ["Kostenlos & Open Source", "Windows 10 / 11", "STL für jeden 3D-Drucker"],
        "steps": [("Bild laden", "Zeichnung, Comic, Logo oder Foto"),
                  ("Druckbares Motiv", "Stege & Prüfung laufen automatisch"),
                  ("Exportieren & drucken", "STL mit Rahmen – fertig für den Slicer")],
        "frames": ["Rechteck", "Abgerundet", "Kreis / Oval", "Sechseck", "Ohne Rahmen"],
    },
}


# ------------------------------------------------------------------ Hilfsfunktionen für Bilder
def font(px: float, weight=QFont.Weight.Normal, display=True) -> QFont:
    fams = set(QFontDatabase.families())
    name = next((f for f in (("Segoe UI Variable Display" if display else "Segoe UI Variable Text"), "Segoe UI")
                 if f in fams), "Arial")
    f = QFont(name)
    f.setPixelSize(int(px))
    f.setWeight(weight)
    return f


def new_image(w, h, fill=Qt.GlobalColor.transparent) -> QImage:
    img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(fill)
    return img


def painter(img) -> QPainter:
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    return p


def rounded(rect: QRectF, r: float) -> QPainterPath:
    path = QPainterPath()
    path.addRoundedRect(rect, r, r)
    return path


def card_background(p: QPainter, rect: QRectF, radius: float, glow_at=None, glow_r=0.0):
    """Dunkle Karte mit Verlauf und optionalem orangem Leuchten."""
    p.save()
    p.setClipPath(rounded(rect, radius))
    g = QLinearGradient(rect.topLeft(), rect.bottomLeft())
    g.setColorAt(0, QColor(BG_TOP))
    g.setColorAt(1, QColor(BG_BOTTOM))
    p.fillRect(rect, g)
    if glow_at is not None:
        rg = QRadialGradient(glow_at, glow_r)
        c = QColor(ORANGE)
        for stop, a in ((0, 70), (0.45, 22), (1, 0)):
            c.setAlpha(a)
            rg.setColorAt(stop, c)
        p.fillRect(rect, rg)
    p.restore()
    p.setPen(QPen(QColor(255, 255, 255, 22), 2))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(rounded(rect.adjusted(1, 1, -1, -1), radius))


def numpy_to_qimage(rgba: np.ndarray) -> QImage:
    """rgba: HxWx4 uint8 (nicht vormultipliziert)."""
    rgba = np.ascontiguousarray(rgba)
    h, w = rgba.shape[:2]
    return QImage(rgba.data, w, h, 4 * w, QImage.Format.Format_RGBA8888).copy()


def qimage_to_numpy(img: QImage) -> np.ndarray:
    """HxWx4 RGBA-Kopie (das konvertierte Bild muss bis zum Kopieren am Leben bleiben)."""
    conv = img.convertToFormat(QImage.Format.Format_RGBA8888)
    a = np.frombuffer(conv.constBits(), np.uint8, conv.sizeInBytes())
    return a.reshape(conv.height(), conv.bytesPerLine() // 4, 4)[:, :conv.width()].copy()


def crop_alpha(img: QImage, pad: int = 0) -> QImage:
    a = qimage_to_numpy(img)[:, :, 3]
    ys, xs = np.nonzero(a > 4)
    if not len(xs):
        return img
    x0, x1 = max(0, xs.min() - pad), min(img.width(), xs.max() + 1 + pad)
    y0, y1 = max(0, ys.min() - pad), min(img.height(), ys.max() + 1 + pad)
    return img.copy(int(x0), int(y0), int(x1 - x0), int(y1 - y0))


def draw_fitted(p: QPainter, img: QImage, rect: QRectF):
    s = min(rect.width() / img.width(), rect.height() / img.height())
    w, h = img.width() * s, img.height() * s
    p.drawImage(QRectF(rect.center().x() - w / 2, rect.center().y() - h / 2, w, h), img)


def shadowed(img: QImage, radius: float, shadow: int = 40) -> QImage:
    """Bild mit runden Ecken und weichem Schatten (transparenter Rand)."""
    w, h = img.width() + 2 * shadow, img.height() + 2 * shadow
    out = new_image(w, h)
    p = painter(out)
    p.setPen(Qt.PenStyle.NoPen)
    steps = shadow
    for i in range(steps):
        a = int(70 * (1 - i / steps) ** 2.2 / steps * 6)
        p.setBrush(QColor(0, 0, 0, max(0, min(255, a))))
        g = i
        p.drawPath(rounded(QRectF(shadow - g, shadow - g + shadow * 0.25, img.width() + 2 * g, img.height() + 2 * g),
                           radius + g))
    p.setClipPath(rounded(QRectF(shadow, shadow, img.width(), img.height()), radius))
    p.drawImage(shadow, shadow, img)
    p.setClipping(False)
    p.setPen(QPen(QColor(255, 255, 255, 30), 1.5))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(rounded(QRectF(shadow + 0.75, shadow + 0.75, img.width() - 1.5, img.height() - 1.5), radius))
    p.end()
    return out


def save(img: QImage, name: str):
    path = os.path.join(OUT, name)
    img.save(path)
    print("  ", os.path.relpath(path, ROOT), f"{img.width()}x{img.height()}")


# ------------------------------------------------------------------ Hauptprogramm
def main() -> int:
    ap = argparse.ArgumentParser(description="Bilder für die GitHub-Seite erzeugen")
    ap.add_argument("--lang", default="all", choices=("en", "de", "all"))
    ap.add_argument("--only", nargs="*", help="nur diese Bilder")
    args = ap.parse_args()
    want = lambda n: not args.only or n in args.only  # noqa: E731

    import app as appmod
    from remstudio import i18n, main_window as mw, processing as proc, mesh as meshmod, viewer3d
    from remstudio.samples import demo_image

    test_settings = QSettings("RemStudio", "RemStudio3D_test")
    test_settings.clear()
    test_settings.setValue("bg_auto_open", "false")
    mw.QSettings = lambda *a: QSettings("RemStudio", "RemStudio3D_test")
    # zwei 3D-Ansichten (Programm + Renderer) brauchen gemeinsame OpenGL-Kontexte, sonst Shader-Fehler
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    qapp = QApplication.instance() or QApplication(sys.argv)
    appmod.setup_app(qapp)
    QMessageBox.information = staticmethod(lambda *a, **k: None)
    os.makedirs(OUT, exist_ok=True)

    def pump(s):
        t = time.time()
        while time.time() - t < s:
            qapp.processEvents()
            time.sleep(0.01)

    # ---------------- 3D-Renderer (eigenes Fenster, ohne Gitter) – liefert freigestellte Bilder
    rv = viewer3d.Viewer3D()
    rv.resize(640, 420)
    rv.move(40, 40)
    rv.show()
    rv.grid.setVisible(False)
    pump(0.5)

    def build_parts(p: proc.Params, gray, edits, ppm=6.0):
        res = proc.process(gray, edits, p, ppm)
        parts = meshmod.build_meshes(res, p, simplify_px=0.6)
        out = [(parts["motiv"], p.color_art)]
        if "rueckplatte" in parts:
            out.append((parts["rueckplatte"], p.color_back))
        return out, max(p.width_mm, p.height_mm)

    def render_array(w, h, bg):
        rv.view.setBackgroundColor(bg)
        arr = rv.view.renderToArray((w, h))          # (h, w, 4) BGRA, oben = oben
        return arr[:, :, [2, 1, 0, 3]].astype(np.float32)

    def render(parts, size_mm, w, h, elev=32, azim=-112, dist=1.55, ss=2) -> QImage:
        """Freigestelltes 3D-Bild (Alpha aus Schwarz-/Weiß-Hintergrund), mit Supersampling geglättet."""
        rv.set_meshes(parts, size_mm, reset_camera=True)
        rv.grid.setVisible(False)
        rv.view.setCameraPosition(distance=size_mm * dist, elevation=elev, azimuth=azim)
        b = render_array(w * ss, h * ss, (0, 0, 0))
        wh = render_array(w * ss, h * ss, (255, 255, 255))
        alpha = np.clip(1.0 - (wh[:, :, :3] - b[:, :, :3]).mean(2) / 255.0, 0, 1)
        rgb = np.where(alpha[..., None] > 0.004, b[:, :, :3] / np.maximum(alpha[..., None], 0.004), 0)
        rgba = np.dstack([np.clip(rgb, 0, 255), alpha * 255]).astype(np.uint8)
        img = numpy_to_qimage(rgba)
        return img.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)

    def styled(p: proc.Params, shape=None) -> proc.Params:
        q = p.copy()
        if shape:
            q.frame_shape = shape
        q.backplate = True
        q.color_art = ORANGE
        q.color_back = "#f4f4f5"
        return q

    langs = ["en", "de"] if args.lang == "all" else [args.lang]
    for lang in langs:
        i18n.set_language(lang)
        tx = TEXTS[lang]
        sfx = "" if lang == "en" else "-de"
        print(f"== {lang}")

        win = mw.MainWindow()
        win.resize(1440, 900)
        win.move(20, 20)
        win.show()

        def idle(timeout=60):
            pump(0.3)
            t = time.time()
            while (win.busy or win.pending or win.full_timer.isActive()) and time.time() - t < timeout:
                pump(0.05)
            pump(0.4)

        win._dirty = False
        win.load_demo()
        idle()
        gray, edits = win.src_gray, win._cropped_edits()
        base = win.params.copy()
        hero_parts, hero_size = build_parts(styled(base), gray, edits)

        # ---------------- Banner
        if want("banner") or want("social"):
            model = crop_alpha(render(hero_parts, hero_size, 1500, 1100, elev=30, azim=-118, dist=1.35))
        if want("banner"):
            W, H = 2560, 820
            img = new_image(W, H)
            p = painter(img)
            card_background(p, QRectF(0, 0, W, H), 48, glow_at=QPointF(W * 0.74, H * 0.5), glow_r=W * 0.38)
            # Modell rechts neben den Pillen (deutsche Texte sind länger)
            p.setFont(font(34, QFont.Weight.DemiBold, display=False))
            chips_end = 150 + sum(p.fontMetrics().horizontalAdvance(c) + 64 + 22 for c in tx["chips"])
            left = max(W * 0.50, chips_end + 40)
            draw_fitted(p, model, QRectF(left, 50, W - 70 - left, H - 100))
            logo = QImage(os.path.join(ROOT, "icon.png"))
            p.drawImage(QRectF(150, 150, 150, 150), logo)
            p.setPen(QColor("#ffffff"))
            p.setFont(font(124, QFont.Weight.Bold))
            p.drawText(QRectF(340, 140, 1100, 170), Qt.AlignmentFlag.AlignVCenter, "RemStudio 3D")
            p.setPen(QColor("#c9ccd2"))
            p.setFont(font(54))
            p.drawText(QRectF(150, 340, 1250, 160), Qt.AlignmentFlag.AlignLeft, tx["tagline"])
            x = 150
            p.setFont(font(34, QFont.Weight.DemiBold, display=False))
            for i, chip in enumerate(tx["chips"]):
                tw = p.fontMetrics().horizontalAdvance(chip) + 64
                r = QRectF(x, 560, tw, 72)
                if i == 0:
                    p.setPen(Qt.PenStyle.NoPen)
                    p.setBrush(QColor(ORANGE))
                    p.drawRoundedRect(r, 36, 36)
                    p.setPen(QColor("#ffffff"))
                else:
                    p.setPen(QPen(QColor(255, 255, 255, 50), 2))
                    p.setBrush(QColor(255, 255, 255, 14))
                    p.drawRoundedRect(r, 36, 36)
                    p.setPen(QColor("#e6e7ea"))
                p.drawText(r, Qt.AlignmentFlag.AlignCenter, chip)
                x += tw + 22
            p.end()
            save(img, f"banner{sfx}.png")

        # ---------------- Social-Preview (GitHub: Settings → Social preview, 1280×640) – nur englisch
        if want("social") and lang == "en":
            W, H = 1280, 640
            img = new_image(W, H, QColor(BG_BOTTOM))
            p = painter(img)
            card_background(p, QRectF(0, 0, W, H), 0, glow_at=QPointF(W * 0.72, H * 0.52), glow_r=W * 0.42)
            draw_fitted(p, model, QRectF(W * 0.47, 40, W * 0.5, H - 80))
            p.drawImage(QRectF(70, 150, 96, 96), QImage(os.path.join(ROOT, "icon.png")))
            p.setPen(QColor("#ffffff"))
            p.setFont(font(68, QFont.Weight.Bold))
            p.drawText(QRectF(70, 260, 700, 100), Qt.AlignmentFlag.AlignVCenter, "RemStudio 3D")
            p.setPen(QColor("#c9ccd2"))
            p.setFont(font(31))
            p.drawText(QRectF(72, 370, 620, 120), Qt.AlignmentFlag.AlignLeft, TEXTS["en"]["tagline"])
            p.end()
            save(img, "social-preview.png")

        # ---------------- So funktioniert's: Original → druckbares Motiv → 3D
        if want("steps"):
            win.set_view(mw.VIEW_WALL)
            idle()
            win.canvas.fit() if hasattr(win.canvas, "fit") else None
            idle()
            wall = win.canvas.viewport().grab().toImage()
            # Vorschaufläche (einfarbig) wegschneiden
            arr = qimage_to_numpy(wall)[:, :, :3].astype(int)
            diff = np.abs(arr - arr[2, 2]).sum(2) > 24
            ys, xs = np.nonzero(diff)
            wall = wall.copy(int(xs.min()), int(ys.min()), int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1))
            src = demo_image()[:, :, ::-1].copy()
            orig = QImage(src.data, src.shape[1], src.shape[0], 3 * src.shape[1], QImage.Format.Format_RGB888).copy()
            model3 = crop_alpha(render(hero_parts, hero_size, 1100, 900, elev=36, azim=-112, dist=1.4))

            W, H = 2560, 980
            img = new_image(W, H)
            p = painter(img)
            card_background(p, QRectF(0, 0, W, H), 48, glow_at=QPointF(W * 0.84, H * 0.45), glow_r=W * 0.3)
            cw, gap, top = 700, 150, 90
            x0 = (W - 3 * cw - 2 * gap) / 2
            for i, ((title, sub), pic) in enumerate(zip(tx["steps"], (orig, wall, model3))):
                x = x0 + i * (cw + gap)
                box = QRectF(x, top, cw, 620)
                if i < 2:
                    p.save()
                    p.setClipPath(rounded(box, 28))
                    p.fillRect(box, QColor("#ffffff") if i == 0 else QColor("#121316"))
                    p.restore()
                    draw_fitted(p, pic, box.adjusted(30, 30, -30, -30))
                    p.setPen(QPen(QColor(255, 255, 255, 30), 2))
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.drawPath(rounded(box, 28))
                else:
                    draw_fitted(p, pic, box.adjusted(0, -20, -10, 20))
                # Nummer + Text
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(ORANGE))
                p.drawEllipse(QRectF(x, top + 670, 76, 76))
                p.setPen(QColor("#ffffff"))
                p.setFont(font(42, QFont.Weight.Bold))
                p.drawText(QRectF(x, top + 670, 76, 76), Qt.AlignmentFlag.AlignCenter, str(i + 1))
                p.setFont(font(50, QFont.Weight.DemiBold))
                p.drawText(QRectF(x + 100, top + 662, cw - 100, 90), Qt.AlignmentFlag.AlignVCenter, title)
                p.setPen(QColor("#a3a7af"))
                p.setFont(font(34, display=False))
                p.drawText(QRectF(x + 100, top + 750, cw - 80, 60), Qt.AlignmentFlag.AlignLeft, sub)
                if i < 2:  # Pfeil
                    ax, ay = x + cw + gap / 2, top + 310
                    p.setPen(QPen(QColor(ORANGE), 9, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                                  Qt.PenJoinStyle.RoundJoin))
                    p.drawLine(QPointF(ax - 40, ay), QPointF(ax + 40, ay))
                    p.drawLine(QPointF(ax + 12, ay - 28), QPointF(ax + 40, ay))
                    p.drawLine(QPointF(ax + 12, ay + 28), QPointF(ax + 40, ay))
            p.end()
            save(img, f"steps{sfx}.png")

        # ---------------- Rahmenformen
        if want("frames"):
            shapes = [proc.FRAME_RECT, proc.FRAME_ROUNDED, proc.FRAME_CIRCLE, proc.FRAME_HEXAGON, proc.FRAME_NONE]
            renders = []
            for s in shapes:
                q = styled(base, s)
                if s in (proc.FRAME_CIRCLE, proc.FRAME_HEXAGON):
                    q.height_mm = q.width_mm
                parts, size = build_parts(q, gray, edits)
                renders.append(crop_alpha(render(parts, size, 760, 760, elev=58, azim=-98, dist=1.55)))
            W, H = 2560, 640
            img = new_image(W, H)
            p = painter(img)
            card_background(p, QRectF(0, 0, W, H), 48, glow_at=QPointF(W / 2, H * 0.4), glow_r=W * 0.45)
            cw = (W - 120) / 5
            for i, (r, label) in enumerate(zip(renders, tx["frames"])):
                x = 60 + i * cw
                draw_fitted(p, r, QRectF(x + 30, 50, cw - 60, 440))
                p.setPen(QColor("#e6e7ea"))
                p.setFont(font(40, QFont.Weight.DemiBold))
                p.drawText(QRectF(x, 515, cw, 70), Qt.AlignmentFlag.AlignCenter, label)
            p.end()
            save(img, f"frames{sfx}.png")

        # ---------------- Drehende 3D-Vorschau (GIF, sprachunabhängig)
        if want("rotate") and lang == "en":
            from PIL import Image
            frames = []
            n = 60
            W, H = 840, 520
            rv.set_meshes(hero_parts, hero_size, reset_camera=True)
            rv.grid.setVisible(False)
            for k in range(n):
                t = 2 * math.pi * k / n
                rv.view.setCameraPosition(distance=hero_size * 1.95, elevation=36 + 8 * math.cos(t),
                                          azimuth=-100 + 32 * math.sin(t))
                a = render_array(W * 2, H * 2, (22, 23, 26))[:, :, :3].astype(np.uint8)
                im = Image.fromarray(a, "RGB").resize((W, H), Image.LANCZOS)
                frames.append(im)
            pal = frames[0].quantize(colors=255, method=Image.Quantize.MEDIANCUT)
            q = [f.quantize(palette=pal, dither=Image.Dither.NONE) for f in frames]
            path = os.path.join(OUT, "rotate.gif")
            q[0].save(path, save_all=True, append_images=q[1:], duration=55, loop=0, optimize=True)
            print("  ", os.path.relpath(path, ROOT), f"{W}x{H}, {n} Bilder, {os.path.getsize(path) // 1024} KB")

        # ---------------- Screenshots des Programms
        def win_shot(name, widget=None):
            save(shadowed((widget or win).grab().toImage(), 14, 36), f"{name}{sfx}.png")

        if want("main"):
            win.set_view(mw.VIEW_WALL)
            idle()
            win.canvas.fit()
            win.canvas.zoom(0.86)  # etwas Luft zu den schwebenden Leisten
            pump(0.5)
            win_shot("main")
        if want("3d"):
            win.params = styled(base, proc.FRAME_ROUNDED)
            win.sync_controls()
            win.update_visibility()
            win.set_view(mw.VIEW_3D)
            win.request()
            idle()
            pump(1.0)
            win_shot("3d")
            win.params = base.copy()
            win.sync_controls()
        if want("editor"):
            from remstudio.bg_editor import BackgroundEditor
            from remstudio import bgremove as bg
            dlg = BackgroundEditor(win, win.orig_bgr, None, 0.0, win.settings, onboarding=False)
            dlg.resize(1280, 800)
            dlg.show()
            pump(1.0)
            if bg.model_available(dlg.model.value()):  # KI-Erkennung zeigen (nur wenn das Modell schon da ist)
                dlg.run_ai()
                pump(15.0)
            win_shot("editor", dlg)
            dlg.reject()
        if want("export"):
            dlg = mw.ExportDialog(win, win.params.copy(), r"C:\3D prints", "landscape", win.last_full)
            dlg.show()
            pump(0.8)
            win_shot("export", dlg)
            dlg.reject()

        win._dirty = False
        win.close()
        win.deleteLater()
        pump(0.3)

    rv.close()
    test_settings.clear()
    return 0


if __name__ == "__main__":
    sys.exit(main())
