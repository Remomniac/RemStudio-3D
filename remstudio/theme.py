"""Dunkles, modernes Erscheinungsbild (Pillen-Formen, schwebende Leisten) und Icons.

Icons stammen aus der Windows-Schrift „Segoe Fluent Icons“ (Windows 11) bzw.
„Segoe MDL2 Assets“ (Windows 10) – dadurch sind sie gestochen scharf in jeder Größe.
"""
from __future__ import annotations

import os

from PySide6.QtCore import Qt, QRectF, QSize
from PySide6.QtGui import QColor, QFont, QFontDatabase, QIcon, QImage, QPainter, QPalette, QPixmap, QPen

# ---------------------------------------------------------------- Farben
BG = "#0e0f11"          # Fensterhintergrund
CANVAS = "#121316"      # Vorschaufläche
SURFACE = "#1a1b1f"     # Seitenleiste
CARD = "#212328"        # Karten
CONTROL = "#2b2d33"     # Eingabefelder, Knöpfe
CONTROL_HOVER = "#353840"
CONTROL_PRESSED = "#3e414a"
ISLAND = "rgba(30, 31, 36, 0.94)"
BORDER = "rgba(255, 255, 255, 0.07)"
BORDER_HI = "rgba(255, 255, 255, 0.13)"
TEXT = "#f2f3f5"
TEXT_2 = "#a3a7af"
TEXT_3 = "#6c7079"
ACCENT = "#f97316"          # Orange
ACCENT_HOVER = "#fb8a3c"
ACCENT_PRESSED = "#ea580c"
GREEN = "#30d158"
ORANGE = "#ff9f0a"
RED = "#ff453a"
PURPLE = "#bf5af2"

# ---------------------------------------------------------------- Icons
ICON = {
    "undo": 0xE7A7, "redo": 0xE7A6, "open": 0xE8E5, "paste": 0xE77F, "save": 0xE74E, "export": 0xE896,
    "menu": 0xE700, "zoom_in": 0xE8A3, "zoom_out": 0xE71F, "fit": 0xE9A6, "pan": 0xE7C9, "move": 0xE7C2,
    "brush": 0xE771, "eraser": 0xE75C, "link": 0xE71B, "restore": 0xE81C, "crop": 0xE7A8, "sparkle": 0xF4A5,
    "image": 0xE91B, "eye": 0xE890, "warn": 0xE7BA, "check": 0xE73E, "error": 0xE783, "help": 0xE897,
    "cube": 0xF158, "layers": 0xE81E, "rect": 0xE7FB, "trash": 0xE74D, "chev_down": 0xE70D,
    "chev_right": 0xE76C, "keep": 0xE710, "remove": 0xE738, "wall": 0xEB9F, "mask": 0xE7B3,
}

_icon_font: str | None = None


def icon_font() -> str:
    global _icon_font
    if _icon_font is None:
        fams = set(QFontDatabase.families())
        _icon_font = next((f for f in ("Segoe Fluent Icons", "Segoe MDL2 Assets") if f in fams), "Segoe UI Symbol")
    return _icon_font


def glyph_pixmap(name: str, size: int, color: str, dpr: float = 2.0) -> QPixmap:
    px = QPixmap(int(size * dpr), int(size * dpr))
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    f = QFont(icon_font())
    f.setPixelSize(int(size * dpr * 0.82))
    p.setFont(f)
    p.setPen(QColor(color))
    p.drawText(QRectF(0, 0, size * dpr, size * dpr), Qt.AlignmentFlag.AlignCenter, chr(ICON[name]))
    p.end()
    px.setDevicePixelRatio(dpr)
    return px


def icon(name: str, color: str = TEXT, size: int = 18, checked_color: str | None = "#ffffff",
         disabled_color: str = TEXT_3) -> QIcon:
    ic = QIcon()
    ic.addPixmap(glyph_pixmap(name, size, color), QIcon.Mode.Normal, QIcon.State.Off)
    ic.addPixmap(glyph_pixmap(name, size, checked_color or color), QIcon.Mode.Normal, QIcon.State.On)
    ic.addPixmap(glyph_pixmap(name, size, disabled_color), QIcon.Mode.Disabled, QIcon.State.Off)
    ic.addPixmap(glyph_pixmap(name, size, disabled_color), QIcon.Mode.Disabled, QIcon.State.On)
    return ic


# ---------------------------------------------------------------- Bild-Dateien für das Stylesheet
def _asset_dir() -> str:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    d = os.path.join(base, "RemStudio", "ui")
    os.makedirs(d, exist_ok=True)
    return d


def _make_assets() -> dict:
    d = _asset_dir()
    out = {}

    def save(name, pm: QPixmap):
        path = os.path.join(d, name)
        pm.toImage().save(path)
        out[name] = path.replace("\\", "/")

    # Pfeil für Auswahllisten
    save("chev.png", glyph_pixmap("chev_down", 12, TEXT_2, dpr=2.0))
    # Häkchen
    save("check.png", glyph_pixmap("check", 12, "#ffffff", dpr=2.0))
    return out


# ---------------------------------------------------------------- Stylesheet
def stylesheet(assets: dict) -> str:
    chev = assets.get("chev.png", "")
    check = assets.get("check.png", "")
    return f"""
* {{ font-family: "Segoe UI Variable Text", "Segoe UI"; font-size: 10pt; color: {TEXT}; }}
QMainWindow, QDialog {{ background: {BG}; }}
QWidget#rightPanel {{ background: {SURFACE}; border-left: 1px solid {BORDER}; }}
QWidget#canvasArea {{ background: {CANVAS}; }}
QToolTip {{ background: #2c2e34; color: {TEXT}; border: 1px solid {BORDER_HI}; border-radius: 8px; padding: 6px 8px; }}

/* ---------- Schwebende Leisten („Inseln“) ---------- */
QFrame#island {{ background: {ISLAND}; border: 1px solid {BORDER_HI}; border-radius: 22px; }}
QFrame#island QLabel {{ color: {TEXT_2}; background: transparent; }}
QFrame#segment {{ background: rgba(255,255,255,0.06); border-radius: 16px; }}
QFrame#segment QPushButton, QFrame#segment QToolButton {{
    background: transparent; border: none; border-radius: 13px; padding: 5px 14px; color: {TEXT_2}; font-weight: 600; }}
QFrame#segment QPushButton:hover, QFrame#segment QToolButton:hover {{ color: {TEXT}; background: rgba(255,255,255,0.06); }}
QFrame#segment QPushButton:checked, QFrame#segment QToolButton:checked {{
    background: #4a4d56; color: #ffffff; border-top: 1px solid rgba(255,255,255,0.18); }}
QFrame#segment QToolButton#tool:checked {{ background: {ACCENT}; border-top: 1px solid rgba(255,255,255,0.25); }}
QFrame#segment QToolButton:disabled, QFrame#segment QPushButton:disabled {{ color: {TEXT_3}; }}

/* Runde Symbol-Knöpfe */
QToolButton#round, QPushButton#round {{
    background: rgba(255,255,255,0.07); border: none; border-radius: 16px; min-width: 32px; min-height: 32px;
    max-width: 32px; max-height: 32px; padding: 0; }}
QToolButton#round:hover, QPushButton#round:hover {{ background: rgba(255,255,255,0.14); }}
QToolButton#round:pressed, QPushButton#round:pressed {{ background: rgba(255,255,255,0.20); }}
QToolButton#round:disabled, QPushButton#round:disabled {{ background: rgba(255,255,255,0.03); }}
QToolButton#round::menu-indicator {{ width: 0; image: none; }}
QLabel#statusline {{ color: {TEXT_3}; font-size: 9pt; background: transparent; padding: 0 4px; }}
QLabel#zoomLabel {{ color: {TEXT_2}; font-size: 9pt; min-width: 44px; qproperty-alignment: AlignCenter; }}

/* ---------- Knöpfe ---------- */
QPushButton {{
    background: {CONTROL}; border: none; border-top: 1px solid rgba(255,255,255,0.08); border-radius: 16px;
    padding: 7px 16px; color: {TEXT}; font-weight: 600; }}
QPushButton:hover {{ background: {CONTROL_HOVER}; }}
QPushButton:pressed {{ background: {CONTROL_PRESSED}; }}
QPushButton:disabled {{ background: #23252a; color: {TEXT_3}; }}
QPushButton::menu-indicator {{ width: 0; image: none; }}
QPushButton#primary {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #fb923c, stop:1 {ACCENT});
    border-top: 1px solid rgba(255,255,255,0.30); border-radius: 22px; padding: 12px 18px; font-size: 11pt;
    color: #ffffff; }}
QPushButton#primary:hover {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #fda766, stop:1 {ACCENT_HOVER}); }}
QPushButton#primary:pressed {{ background: {ACCENT_PRESSED}; }}
QPushButton#accent, QPushButton#primary2 {{ background: {ACCENT}; color: #ffffff; border-top: 1px solid rgba(255,255,255,0.28); }}
QPushButton#accent:hover, QPushButton#primary2:hover {{ background: {ACCENT_HOVER}; }}
QPushButton#accent:pressed, QPushButton#primary2:pressed {{ background: {ACCENT_PRESSED}; }}
QPushButton#ghost {{ background: transparent; border: 1px solid {BORDER_HI}; }}
QPushButton#ghost:hover {{ background: rgba(255,255,255,0.06); }}

/* ---------- Karten / Abschnitte ---------- */
QWidget#card {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 18px; }}
QToolButton#sectionHeader {{
    background: transparent; border: none; padding: 11px 12px; font-weight: 700; font-size: 10.5pt;
    color: {TEXT}; text-align: left; }}
QToolButton#sectionHeader:hover {{ color: #ffffff; }}
QWidget#subcard {{ background: rgba(255,255,255,0.035); border: 1px solid {BORDER}; border-radius: 14px; }}
QWidget#subcard QToolButton#sectionHeader {{ font-weight: 600; font-size: 10pt; color: {TEXT_2}; padding: 8px 10px; }}
QLabel#hint {{ color: {TEXT_3}; font-size: 9pt; }}
QLabel#paramLabel {{ color: {TEXT_2}; }}
QLabel#title {{ font-size: 13pt; font-weight: 700; color: {TEXT}; }}
QLabel#subtitle {{ font-size: 9pt; color: {TEXT_3}; }}
QFrame#checkCard {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 18px; }}
QFrame#checkCard QLabel {{ background: transparent; }}

/* ---------- Eingaben ---------- */
QDoubleSpinBox, QSpinBox, QLineEdit {{
    background: {CONTROL}; border: 1px solid transparent; border-radius: 10px; padding: 4px 8px; color: {TEXT};
    selection-background-color: {ACCENT}; }}
QDoubleSpinBox:focus, QSpinBox:focus, QLineEdit:focus {{ border: 1px solid {ACCENT}; }}
QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {{ subcontrol-origin: border; width: 0px; height: 0px;
    border: none; }}
QComboBox {{
    background: {CONTROL}; border: 1px solid transparent; border-radius: 12px; padding: 5px 30px 5px 12px;
    min-width: 150px; color: {TEXT}; }}
QComboBox:hover {{ background: {CONTROL_HOVER}; }}
QComboBox:focus {{ border: 1px solid {ACCENT}; }}
QComboBox::drop-down {{ border: none; width: 26px; subcontrol-origin: padding; subcontrol-position: center right; }}
QComboBox::down-arrow {{ image: url("{chev}"); width: 12px; height: 12px; }}
QComboBox QAbstractItemView {{
    background: #26282e; color: {TEXT}; border: 1px solid {BORDER_HI}; border-radius: 10px; padding: 4px;
    selection-background-color: {ACCENT}; selection-color: #ffffff; outline: none; }}

/* ---------- Schieberegler (iOS-Stil) ---------- */
QSlider {{ min-height: 22px; background: transparent; }}
QSlider::groove:horizontal {{ height: 4px; background: rgba(255,255,255,0.12); border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 2px; }}
QSlider::handle:horizontal {{
    background: #ffffff; width: 18px; height: 18px; margin: -7px 0; border-radius: 9px;
    border: 1px solid rgba(0,0,0,0.25); }}
QSlider::handle:horizontal:hover {{ background: #f0f4ff; }}
QSlider::sub-page:horizontal:disabled {{ background: #4a4d55; }}
QSlider::handle:horizontal:disabled {{ background: #8a8d94; }}

/* ---------- Kontrollkästchen ---------- */
QCheckBox {{ spacing: 8px; color: {TEXT}; background: transparent; }}
QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 6px; background: {CONTROL};
    border: 1px solid {BORDER_HI}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border: 1px solid {ACCENT}; image: url("{check}"); }}

/* ---------- Bildlauf ---------- */
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px 2px; }}
QScrollBar::handle:vertical {{ background: rgba(255,255,255,0.16); border-radius: 3px; min-height: 40px; }}
QScrollBar::handle:vertical:hover {{ background: rgba(255,255,255,0.28); }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px 4px; }}
QScrollBar::handle:horizontal {{ background: rgba(255,255,255,0.16); border-radius: 3px; min-width: 40px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* ---------- Menüs, Dialoge ---------- */
QMenu {{ background: #26282e; border: 1px solid {BORDER_HI}; border-radius: 12px; padding: 6px; }}
QMenu::item {{ padding: 7px 26px 7px 12px; border-radius: 8px; }}
QMenu::item:selected {{ background: {ACCENT}; color: #ffffff; }}
QMenu::separator {{ height: 1px; background: {BORDER_HI}; margin: 5px 8px; }}
QMessageBox, QProgressDialog {{ background: {SURFACE}; }}
QMessageBox QLabel {{ color: {TEXT}; }}
QDialog QGroupBox {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 14px; margin-top: 16px;
    padding: 12px 10px 10px 10px; font-weight: 600; }}
QDialog QGroupBox::title {{ subcontrol-origin: margin; left: 14px; padding: 0 4px; color: {TEXT_2}; }}
QProgressBar {{ background: {CONTROL}; border: none; border-radius: 6px; height: 12px; text-align: center; color: {TEXT}; }}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 6px; }}
QSplitter::handle {{ background: {BG}; }}

/* ---------- Ältere Leisten (z. B. im Hintergrund-Editor) ---------- */
QFrame#toolbar, QFrame#toolbar2 {{ background: {SURFACE}; border: none; border-bottom: 1px solid {BORDER}; }}
QFrame#toolbar QLabel, QFrame#toolbar2 QLabel {{ color: {TEXT_2}; }}
QFrame#toolbar QPushButton#segment, QFrame#toolbar2 QToolButton#tool {{
    background: {CONTROL}; border: none; border-radius: 15px; padding: 6px 14px; color: {TEXT_2}; font-weight: 600; }}
QFrame#toolbar QPushButton#segment:hover, QFrame#toolbar2 QToolButton#tool:hover {{ background: {CONTROL_HOVER}; color: {TEXT}; }}
QFrame#toolbar QPushButton#segment:checked, QFrame#toolbar2 QToolButton#tool:checked {{
    background: {ACCENT}; color: #ffffff; border-top: 1px solid rgba(255,255,255,0.25); }}
"""


def setup_app(app):
    """Dunkles Erscheinungsbild für die ganze Anwendung."""
    try:
        app.styleHints().setColorScheme(Qt.ColorScheme.Dark)
    except Exception:
        pass
    app.setStyle("Fusion")
    pal = QPalette()
    roles = {
        QPalette.ColorRole.Window: SURFACE, QPalette.ColorRole.WindowText: TEXT,
        QPalette.ColorRole.Base: CONTROL, QPalette.ColorRole.AlternateBase: CARD,
        QPalette.ColorRole.Text: TEXT, QPalette.ColorRole.Button: CONTROL,
        QPalette.ColorRole.ButtonText: TEXT, QPalette.ColorRole.Highlight: ACCENT,
        QPalette.ColorRole.HighlightedText: "#ffffff", QPalette.ColorRole.ToolTipBase: "#2c2e34",
        QPalette.ColorRole.ToolTipText: TEXT, QPalette.ColorRole.PlaceholderText: TEXT_3,
        QPalette.ColorRole.Light: "#3a3d45", QPalette.ColorRole.Mid: "#2b2d33", QPalette.ColorRole.Dark: "#141518",
        QPalette.ColorRole.Shadow: "#000000", QPalette.ColorRole.BrightText: "#ffffff",
        QPalette.ColorRole.Link: ACCENT,
    }
    for role, col in roles.items():
        pal.setColor(role, QColor(col))
    if hasattr(QPalette.ColorRole, "Accent"):
        pal.setColor(QPalette.ColorRole.Accent, QColor(ACCENT))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.WindowText, QPalette.ColorRole.ButtonText):
        pal.setColor(QPalette.ColorGroup.Disabled, role, QColor(TEXT_3))
    app.setPalette(pal)
    app.setStyleSheet(stylesheet(_make_assets()))
