"""Wiederverwendbare, einfach bedienbare Bedienelemente."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QSize, QRectF, QPointF, QVariantAnimation, QEasingCurve
from PySide6.QtGui import QColor, QPainter, QWheelEvent
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QLabel, QSlider, QDoubleSpinBox,
                               QToolButton, QFrame, QSizePolicy, QPushButton, QColorDialog, QComboBox,
                               QCheckBox, QGraphicsDropShadowEffect, QAbstractScrollArea,
                               QApplication)


class Slider(QSlider):
    """Schieberegler, der das Mausrad ignoriert – das Rad scrollt stattdessen die Seitenleiste.
    (Werte per Mausrad nur über dem Zahlenfeld ändern.)"""

    # Feinjustierung: mit gedrückter Umschalttaste (Shift) bewegt sich der Regler 10× langsamer
    _fine = None

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and e.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            self._fine = (e.position().x(), self.value())
            self.setSliderDown(True)
            e.accept()
            return
        self._fine = None
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._fine is not None:
            x0, v0 = self._fine
            span = max(1.0, self.width() - 18.0)
            dv = (e.position().x() - x0) / span * (self.maximum() - self.minimum()) * 0.1
            self.setValue(int(round(v0 + dv)))
            e.accept()
            return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        if self._fine is not None:
            self._fine = None
            self.setSliderDown(False)
            e.accept()
            return
        super().mouseReleaseEvent(e)

    def wheelEvent(self, e):
        # an die umgebende Bildlauf-Fläche (z. B. Seitenleiste) weitergeben
        w = self.parentWidget()
        while w is not None and not isinstance(w, QAbstractScrollArea):
            w = w.parentWidget()
        if w is None:
            e.ignore()
            return
        vp = w.viewport()
        pos = QPointF(vp.mapFromGlobal(e.globalPosition().toPoint()))
        fwd = QWheelEvent(pos, e.globalPosition(), e.pixelDelta(), e.angleDelta(), e.buttons(), e.modifiers(),
                          e.phase(), e.inverted())
        QApplication.sendEvent(vp, fwd)
        e.accept()


class WheelValueLabel(QLabel):
    """Zahl neben einem Regler: Mausrad darüber ändert den Wert."""

    def __init__(self, slider: QSlider, parent=None):
        super().__init__(parent)
        self._slider = slider
        self.setCursor(Qt.CursorShape.SizeVerCursor)
        self.setToolTip("Mausrad über der Zahl ändert den Wert")

    def wheelEvent(self, e):
        steps = e.angleDelta().y() / 120.0
        if steps:
            self._slider.setValue(self._slider.value() + int(round(steps)) * self._slider.singleStep())
        e.accept()


class ParamSlider(QWidget):
    """Beschriftung + Schieberegler + Zahlenfeld (+ Einheit) in einer Zeile."""
    valueChanged = Signal(float)

    def __init__(self, label: str, minimum: float, maximum: float, step: float = 1.0,
                 decimals: int = 0, unit: str = "", tooltip: str = "", parent=None):
        super().__init__(parent)
        self._scale = 10 ** decimals
        self._block = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 2, 0, 2)
        lay.setSpacing(1)
        top = QHBoxLayout()
        top.setSpacing(4)
        self.label = QLabel(label)
        self.label.setObjectName("paramLabel")
        top.addWidget(self.label, 1)
        self.spin = QDoubleSpinBox()
        self.spin.setDecimals(decimals)
        self.spin.setRange(minimum, maximum)
        self.spin.setSingleStep(step)
        self.spin.setSuffix(f" {unit}" if unit else "")
        self.spin.setKeyboardTracking(False)
        self.spin.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.spin.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.spin.setFixedWidth(82)
        top.addWidget(self.spin)
        lay.addLayout(top)
        self.slider = Slider(Qt.Orientation.Horizontal)
        self.slider.setRange(int(round(minimum * self._scale)), int(round(maximum * self._scale)))
        self.slider.setSingleStep(max(1, int(round(step * self._scale))))
        self.slider.setPageStep(max(1, int(round(step * self._scale * 5))))
        lay.addWidget(self.slider)
        tip = (tooltip + "\n\n" if tooltip else "") + (
            "Feinjustierung: Umschalttaste (Shift) beim Ziehen gedrückt halten · Zahl anklicken und eintippen · "
            "Mausrad über der Zahl (mit Strg in 10er-Schritten)")
        for w in (self, self.label, self.spin, self.slider):
            w.setToolTip(tip)
        self.slider.valueChanged.connect(self._from_slider)
        self.spin.valueChanged.connect(self._from_spin)

    def _from_slider(self, v: int):
        if self._block:
            return
        self._block = True
        self.spin.setValue(v / self._scale)
        self._block = False
        self.valueChanged.emit(self.value())

    def _from_spin(self, v: float):
        if self._block:
            return
        self._block = True
        self.slider.setValue(int(round(v * self._scale)))
        self._block = False
        self.valueChanged.emit(self.value())

    def value(self) -> float:
        return float(self.spin.value())

    def setValue(self, v: float, emit: bool = False):
        self._block = True
        self.spin.setValue(v)
        self.slider.setValue(int(round(v * self._scale)))
        self._block = False
        if emit:
            self.valueChanged.emit(self.value())

    def setRange(self, minimum: float, maximum: float):
        self._block = True
        self.spin.setRange(minimum, maximum)
        self.slider.setRange(int(round(minimum * self._scale)), int(round(maximum * self._scale)))
        self._block = False


class Section(QWidget):
    """Auf- und zuklappbare Karte mit Überschrift (verschachtelt = hellere Unterkarte)."""

    def __init__(self, title: str, expanded: bool = True, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 2, 4, 2)
        lay.setSpacing(0)
        self.header = QToolButton()
        self.header.setObjectName("sectionHeader")
        self.header.setText("  " + title)
        self.header.setCheckable(True)
        self.header.setChecked(expanded)
        self.header.setCursor(Qt.CursorShape.PointingHandCursor)
        self.header.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.header.setIconSize(QSize(14, 14))
        self.header.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.header.toggled.connect(self._toggle)
        lay.addWidget(self.header)
        self.body = QWidget()
        self.body.setObjectName("sectionBody")
        self.content = QVBoxLayout(self.body)
        self.content.setContentsMargins(12, 0, 12, 12)
        self.content.setSpacing(8)
        lay.addWidget(self.body)
        self.body.setVisible(expanded)
        self._update_icon()

    def _update_icon(self):
        from . import theme
        self.header.setIcon(theme.icon("chev_down" if self.header.isChecked() else "chev_right",
                                       theme.TEXT_2, 14, checked_color=theme.TEXT_2))

    def _toggle(self, on: bool):
        self.body.setVisible(on)
        self._update_icon()

    def make_sub(self):
        self.setObjectName("subcard")
        self.content.setContentsMargins(10, 0, 10, 10)
        self.style().unpolish(self)
        self.style().polish(self)

    def add(self, w):
        if isinstance(w, Section):
            w.make_sub()
        if isinstance(w, QWidget):
            self.content.addWidget(w)
        else:
            self.content.addLayout(w)
        return w

    def hint(self, text: str) -> QLabel:
        lab = QLabel(text)
        lab.setWordWrap(True)
        lab.setObjectName("hint")
        self.content.addWidget(lab)
        return lab


class Toggle(QCheckBox):
    """Schalter im iOS-Stil (verhält sich wie eine QCheckBox)."""

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._t = 0.0
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(140)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._step)
        self.toggled.connect(self._animate)

    def _step(self, v):
        self._t = float(v)
        self.update()

    def _animate(self, on):
        self._anim.stop()
        self._anim.setStartValue(self._t)
        self._anim.setEndValue(1.0 if on else 0.0)
        self._anim.start()

    def setChecked(self, on):  # ohne Animation, wenn per Programm gesetzt und Signale blockiert
        super().setChecked(on)
        if self.signalsBlocked():
            self._t = 1.0 if on else 0.0
            self.update()

    def showEvent(self, e):
        self._t = 1.0 if self.isChecked() else 0.0
        super().showEvent(e)

    def sizeHint(self):
        fm = self.fontMetrics()
        tw = fm.horizontalAdvance(self.text()) + 14 if self.text() else 0
        return QSize(tw + 42, max(26, fm.height() + 6))

    def minimumSizeHint(self):
        return QSize(42, 26)

    def hitButton(self, pos):
        return self.rect().contains(pos)

    def paintEvent(self, e):
        from . import theme
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect()
        tw, th = 40, 24
        x = r.right() - tw if self.text() else r.left()
        y = r.center().y() - th / 2 + 1
        off = QColor(255, 255, 255, 40)
        on = QColor(theme.ACCENT)
        t = self._t
        col = QColor(int(off.red() + (on.red() - off.red()) * t), int(off.green() + (on.green() - off.green()) * t),
                     int(off.blue() + (on.blue() - off.blue()) * t), int(off.alpha() + (255 - off.alpha()) * t))
        if not self.isEnabled():
            col.setAlpha(70)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(col)
        p.drawRoundedRect(QRectF(x, y, tw, th), th / 2, th / 2)
        k = th - 4
        kx = x + 2 + (tw - k - 4) * t
        p.setBrush(QColor(0, 0, 0, 60))
        p.drawEllipse(QRectF(kx, y + 3, k, k))
        p.setBrush(QColor("#ffffff") if self.isEnabled() else QColor("#9a9da4"))
        p.drawEllipse(QRectF(kx, y + 2, k, k))
        if self.text():
            p.setPen(QColor(theme.TEXT if self.isEnabled() else theme.TEXT_3))
            p.setFont(self.font())
            tr = r.adjusted(0, 0, -(tw + 10), 0)
            p.drawText(tr, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                       self.fontMetrics().elidedText(self.text(), Qt.TextElideMode.ElideRight, tr.width()))
        p.end()


class ColorButton(QPushButton):
    colorChanged = Signal(str)

    def __init__(self, color: str = "#000000", parent=None):
        super().__init__(parent)
        self._color = color
        self.setFixedSize(QSize(46, 24))
        self.clicked.connect(self._pick)
        self._update()

    def _update(self):
        self.setStyleSheet(f"QPushButton {{ background: {self._color}; border: 2px solid rgba(255,255,255,0.18); "
                           f"border-radius: 12px; padding: 0; }}")

    def color(self) -> str:
        return self._color

    def setColor(self, c: str):
        self._color = c
        self._update()

    def _pick(self):
        from .i18n import T
        c = QColorDialog.getColor(QColor(self._color), self, T("Farbe wählen"))
        if c.isValid():
            self._color = c.name()
            self._update()
            self.colorChanged.emit(self._color)


def labeled(label: str, widget: QWidget, tooltip: str = "") -> QWidget:
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lab = QLabel(label)
    lab.setObjectName("paramLabel")
    lay.addWidget(lab, 1)
    lay.addWidget(widget)
    if tooltip:
        lab.setToolTip(tooltip)
        widget.setToolTip(tooltip)
    return w


class ChoiceBox(QComboBox):
    """ComboBox mit (Anzeige-Text, Wert)-Paaren."""

    def __init__(self, items, parent=None):
        super().__init__(parent)
        for text, value in items:
            self.addItem(text, value)

    def value(self):
        return self.currentData()

    def setValue(self, v):
        i = self.findData(v)
        if i >= 0:
            self.blockSignals(True)
            self.setCurrentIndex(i)
            self.blockSignals(False)


def checkbox(text: str, tooltip: str = "") -> QCheckBox:
    c = Toggle(text)
    if tooltip:
        c.setToolTip(tooltip)
    return c


# ---------------------------------------------------------------------------
# Bausteine für die schwebenden Leisten
# ---------------------------------------------------------------------------

def island(parent=None) -> QFrame:
    """Abgerundete, schwebende Leiste (Pillenform)."""
    f = QFrame(parent)
    f.setObjectName("island")
    f.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    lay = QHBoxLayout(f)
    lay.setContentsMargins(7, 6, 10, 6)
    lay.setSpacing(6)
    eff = QGraphicsDropShadowEffect(f)
    eff.setBlurRadius(28)
    eff.setOffset(0, 6)
    eff.setColor(QColor(0, 0, 0, 120))
    f.setGraphicsEffect(eff)
    return f


def segment() -> QFrame:
    """Segment-Steuerung: Knöpfe in einer gemeinsamen Pille."""
    f = QFrame()
    f.setObjectName("segment")
    f.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    lay = QHBoxLayout(f)
    lay.setContentsMargins(3, 3, 3, 3)
    lay.setSpacing(2)
    return f


def round_button(icon_name: str, tooltip: str, slot=None) -> QToolButton:
    from . import theme
    b = QToolButton()
    b.setObjectName("round")
    b.setIcon(theme.icon(icon_name, theme.TEXT, 16))
    b.setIconSize(QSize(16, 16))
    b.setToolTip(tooltip)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    if slot is not None:
        b.clicked.connect(slot)
    return b


def vsep() -> QFrame:
    f = QFrame()
    f.setFixedSize(1, 22)
    f.setStyleSheet("background: rgba(255,255,255,0.12); border: none;")
    return f


class CompactSlider(QWidget):
    """Kleiner Regler für Leisten: Beschriftung + Schieber + Wert (gleiche API wie ParamSlider)."""
    valueChanged = Signal(float)

    def __init__(self, label: str, minimum: float, maximum: float, step: float = 1.0, decimals: int = 0,
                 unit: str = "", tooltip: str = "", parent=None):
        super().__init__(parent)
        self._scale = 10 ** decimals
        self._dec = decimals
        self._unit = unit
        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 0, 0, 0)
        lay.setSpacing(8)
        lab = QLabel(label)
        lay.addWidget(lab)
        self.slider = Slider(Qt.Orientation.Horizontal)
        self.slider.setRange(int(round(minimum * self._scale)), int(round(maximum * self._scale)))
        self.slider.setSingleStep(max(1, int(round(step * self._scale))))
        self.slider.setFixedWidth(120)
        lay.addWidget(self.slider)
        self.val = WheelValueLabel(self.slider)
        self.val.setFixedWidth(52)
        lay.addWidget(self.val)
        if tooltip:
            for w in (self, lab, self.slider):
                w.setToolTip(tooltip)
        self.slider.valueChanged.connect(self._changed)
        self._changed(self.slider.value(), emit=False)

    def _changed(self, v, emit=True):
        from .i18n import num
        self.val.setText(f"{num(v / self._scale, self._dec)} {self._unit}")
        if emit:
            self.valueChanged.emit(self.value())

    def value(self) -> float:
        return self.slider.value() / self._scale

    def setValue(self, v: float, emit: bool = False):
        self.slider.blockSignals(True)
        self.slider.setValue(int(round(v * self._scale)))
        self.slider.blockSignals(False)
        self._changed(self.slider.value(), emit=emit)


class CanvasArea(QWidget):
    """Vorschau-Fläche, über der die Leisten schweben und sich selbst anordnen."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("canvasArea")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.content = None
        self.top = None
        self.bottom = None
        self.bottom_alt = None
        self.zoom = None
        self.status = None

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.relayout()

    def showEvent(self, e):
        super().showEvent(e)
        self.relayout()

    def relayout(self):
        W, H = self.width(), self.height()
        if self.content is not None:
            self.content.setGeometry(0, 0, W, H)
        m = 14
        if self.top is not None:
            self.top.adjustSize()
            self.top.move(max(m, (W - self.top.width()) // 2), m)
            self.top.raise_()
        bottom_top = H
        for b in (self.bottom, self.bottom_alt):
            if b is not None and not b.isHidden():
                b.adjustSize()
                x = max(m, (W - b.width()) // 2)
                b.move(x, H - b.height() - m)
                b.raise_()
                bottom_top = min(bottom_top, b.y())
        if self.zoom is not None:
            self.zoom.adjustSize()
            zx, zy = W - self.zoom.width() - m, H - self.zoom.height() - m
            for b in (self.bottom, self.bottom_alt):
                if b is not None and not b.isHidden() and b.geometry().right() + 10 > zx:
                    zy = b.y() - self.zoom.height() - 10  # zu schmal: über die Werkzeugleiste
            self.zoom.move(zx, zy)
            self.zoom.raise_()
        if self.status is not None:
            # Statuszeile links über der unteren Leiste
            self.status.setFixedWidth(max(80, W - 2 * m - (self.zoom.width() + 20 if self.zoom else 0)))
            self.status.adjustSize()
            y = (bottom_top if bottom_top < H else H) - self.status.height() - 8
            self.status.move(m + 6, y)
            self.status.raise_()
