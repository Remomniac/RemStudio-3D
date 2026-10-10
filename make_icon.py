"""Erzeugt das App-Symbol von RemStudio 3D: icon.ico (alle Windows-Größen) und icon.png.

Motiv: minimalistische Kamera auf orangem Feld, im Objektiv ein kräftiges „R“.
Aufruf:  python make_icon.py
"""
import struct

from PySide6.QtCore import Qt, QRectF, QPointF, QBuffer, QByteArray, QIODevice
from PySide6.QtGui import (QGuiApplication, QImage, QPainter, QColor, QPainterPath, QLinearGradient, QFont, QPen)

ORANGE_TOP = "#fb923c"
ORANGE_BOTTOM = "#ea580c"
DARK = "#18181c"


def render(size: int, with_r: bool = True) -> QImage:
    S = float(size)
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)

    # Hintergrund: abgerundetes Quadrat mit Orange-Verlauf
    m = S * 0.04
    tile = QRectF(m, m, S - 2 * m, S - 2 * m)
    g = QLinearGradient(tile.topLeft(), tile.bottomLeft())
    g.setColorAt(0, QColor(ORANGE_TOP))
    g.setColorAt(1, QColor(ORANGE_BOTTOM))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(g)
    r = tile.width() * 0.235
    p.drawRoundedRect(tile, r, r)
    if size >= 48:  # feiner Glanz an der Oberkante
        p.setPen(QPen(QColor(255, 255, 255, 70), max(1.0, S * 0.008)))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(tile.adjusted(S * 0.006, S * 0.006, -S * 0.006, -S * 0.006), r, r)

    # Kamera-Körper (weiß) mit Sucher-Höcker
    body = QPainterPath()
    body.addRoundedRect(QRectF(S * 0.17, S * 0.33, S * 0.66, S * 0.45), S * 0.10, S * 0.10)
    hump = QPainterPath()
    hump.addRoundedRect(QRectF(S * 0.28, S * 0.24, S * 0.20, S * 0.16), S * 0.05, S * 0.05)
    cam = body.united(hump)
    # Objektiv-Aussparung (das Orange scheint als Ring durch)
    cx, cy = S * 0.5, S * 0.565
    ring = QPainterPath()
    ring.addEllipse(QPointF(cx, cy), S * 0.185, S * 0.185)
    cam = cam.subtracted(ring)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#ffffff"))
    p.drawPath(cam)
    # Blitz-Punkt
    if size >= 32:
        p.setBrush(QColor(ORANGE_BOTTOM))
        p.drawEllipse(QPointF(S * 0.73, S * 0.42), S * 0.032, S * 0.032)
    # Objektiv innen (dunkel)
    p.setBrush(QColor(DARK))
    p.drawEllipse(QPointF(cx, cy), S * 0.148, S * 0.148)

    if with_r:
        # Kräftiges „R“ mittig im Objektiv
        f = QFont("Segoe UI Variable Display")
        f.setWeight(QFont.Weight.Black)
        f.setPixelSize(int(S * 0.23))
        path = QPainterPath()
        path.addText(0, 0, f, "R")
        br = path.boundingRect()
        path.translate(cx - br.center().x(), cy - br.center().y())
        p.setBrush(QColor("#ffffff"))
        p.drawPath(path)
    else:
        # sehr klein: nur ein Glanzpunkt statt Buchstabe
        p.setBrush(QColor(255, 255, 255, 150))
        p.drawEllipse(QPointF(cx - S * 0.05, cy - S * 0.05), S * 0.04, S * 0.04)
    p.end()
    return img


def png_bytes(img: QImage) -> bytes:
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, "PNG")
    return bytes(ba)


def write_ico(path: str, sizes=(16, 20, 24, 32, 40, 48, 64, 96, 128, 256)):
    """ICO mit eigenem Bild je Größe (scharf auch in Taskleiste und Explorer)."""
    blobs = [png_bytes(render(s, with_r=s >= 32)) for s in sizes]
    header = struct.pack("<HHH", 0, 1, len(sizes))
    offset = 6 + 16 * len(sizes)
    entries, data = b"", b""
    for s, blob in zip(sizes, blobs):
        entries += struct.pack("<BBBBHHII", s % 256, s % 256, 0, 0, 1, 32, len(blob), offset + len(data))
        data += blob
    with open(path, "wb") as f:
        f.write(header + entries + data)


if __name__ == "__main__":
    app = QGuiApplication([])
    write_ico("icon.ico")
    render(512).save("icon.png")
    print("icon.ico und icon.png erstellt")


# ---------------------------------------------------------------------------
# Bilder für den Installer (Inno Setup, dunkles Design)
# ---------------------------------------------------------------------------

def render_wizard_large(scale: float) -> QImage:
    """Seitenbild für Willkommens-/Fertig-Seite (Basis 164×314)."""
    from PySide6.QtGui import QRadialGradient
    W, H = int(round(164 * scale)), int(round(314 * scale))
    img = QImage(W, H, QImage.Format.Format_RGB32)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    g = QLinearGradient(0, 0, 0, H)
    g.setColorAt(0, QColor("#1c1d22"))
    g.setColorAt(1, QColor("#0e0f11"))
    p.fillRect(0, 0, W, H, g)
    glow = QRadialGradient(QPointF(W * 0.5, H * 0.36), W * 0.85)
    glow.setColorAt(0, QColor(249, 115, 22, 120))
    glow.setColorAt(1, QColor(249, 115, 22, 0))
    p.fillRect(0, 0, W, H, glow)
    logo = render(int(W * 0.56))
    p.drawImage(int((W - logo.width()) / 2), int(H * 0.36 - logo.height() / 2), logo)
    f = QFont("Segoe UI Variable Display")
    f.setWeight(QFont.Weight.Bold)
    f.setPixelSize(int(19 * scale))
    p.setFont(f)
    p.setPen(QColor("#f2f3f5"))
    p.drawText(QRectF(0, H * 0.58, W, 30 * scale), Qt.AlignmentFlag.AlignCenter, "RemStudio 3D")
    f.setWeight(QFont.Weight.Normal)
    f.setPixelSize(int(10.5 * scale))
    p.setFont(f)
    p.setPen(QColor("#a3a7af"))
    p.drawText(QRectF(10 * scale, H * 0.58 + 28 * scale, W - 20 * scale, 40 * scale),
               Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
               "Image → 3D wall art")
    p.setPen(QPen(QColor(249, 115, 22, 200), max(1.0, 2 * scale)))
    p.drawLine(QPointF(W * 0.38, H * 0.58 + 66 * scale), QPointF(W * 0.62, H * 0.58 + 66 * scale))
    p.end()
    return img


def render_wizard_small(scale: float) -> QImage:
    """Kleines Logo oben rechts auf den Assistenten-Seiten (Basis 55×55)."""
    S = int(round(55 * scale))
    img = QImage(S, S, QImage.Format.Format_RGB32)
    img.fill(QColor("#16171a"))  # = WizardBackColor des Installers
    p = QPainter(img)
    p.drawImage(0, 0, render(S))
    p.end()
    return img


def write_installer_images(folder: str = "installer"):
    import os
    os.makedirs(folder, exist_ok=True)
    for pct, sc in ((100, 1.0), (125, 1.25), (150, 1.5), (175, 1.75), (200, 2.0), (250, 2.5)):
        render_wizard_large(sc).save(os.path.join(folder, f"wizard_{pct}.bmp"))
        render_wizard_small(sc).save(os.path.join(folder, f"wizard_small_{pct}.bmp"))


if __name__ == "__main__" and "--installer" in __import__("sys").argv:
    write_installer_images()
    print("Installer-Bilder erstellt")
