"""2D-Vorschau mit Zoom, Verschieben und Zeichenwerkzeugen."""
from __future__ import annotations

import os

import numpy as np
from PySide6.QtCore import Qt, Signal, QPointF, QRectF
from PySide6.QtGui import (QImage, QPixmap, QPainter, QPen, QColor, QPainterPath, QBrush, QCursor, QTransform,
                           QSurfaceFormat, QPolygonF, QFont)
from PySide6.QtWidgets import (QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QGraphicsPathItem,
                               QGraphicsEllipseItem, QGraphicsItem)

# Grafikkarte (OpenGL) zum Zeichnen der Vorschau verwenden. Abschaltbar über die
# Einstellungen oder die Umgebungsvariable REMSTUDIO_NO_GL (z. B. bei Treiberproblemen).
USE_GL = not os.environ.get("REMSTUDIO_NO_GL")

TOOL_PAN = "pan"
TOOL_MOVE = "move"      # Motiv verschieben / skalieren
TOOL_BRUSH = "brush"    # Material hinzufügen
TOOL_ERASE = "erase"    # Material entfernen
TOOL_LINE = "line"      # gerade Linie / Steg
TOOL_RESTORE = "restore"  # Korrekturen entfernen
TOOL_CROP = "crop"        # Zuschnitt (nur in der Original-Ansicht)

EDIT_TOOLS = (TOOL_BRUSH, TOOL_ERASE, TOOL_LINE, TOOL_RESTORE)


def to_qimage(img: np.ndarray) -> QImage:
    """numpy (Grau, BGR oder BGRA) -> QImage (Kopie)."""
    img = np.ascontiguousarray(img)
    if img.ndim == 2:
        h, w = img.shape
        q = QImage(img.data, w, h, w, QImage.Format.Format_Grayscale8)
    elif img.shape[2] == 4:
        h, w, _ = img.shape
        # BGRA im Speicher entspricht ARGB32 auf Little-Endian-Systemen
        q = QImage(img.data, w, h, 4 * w, QImage.Format.Format_ARGB32)
    else:
        h, w, _ = img.shape
        q = QImage(img.data, w, h, 3 * w, QImage.Format.Format_BGR888)
    return q.copy()


class Canvas(QGraphicsView):
    # Liste von Punkten (Szene-Koordinaten), Werkzeug, Pinselradius in Szene-Pixeln
    strokeFinished = Signal(list, str)
    motifDragged = Signal(float, float)      # Verschiebung in Szene-Pixeln
    motifDragFinished = Signal()
    motifScaled = Signal(float)              # Faktor
    brushSizeStep = Signal(int)
    fileDropped = Signal(str)
    clicked = Signal()
    cropSelected = Signal(float, float, float, float)  # x0, y0, x1, y1 in Bildpixeln
    zoomChanged = Signal(float)

    def __init__(self, parent=None, background: str = "#121316"):
        super().__init__(parent)
        self.gl = False
        if USE_GL:
            try:
                from PySide6.QtOpenGLWidgets import QOpenGLWidget
                vp = QOpenGLWidget()
                fmt = QSurfaceFormat()
                fmt.setSamples(4)
                vp.setFormat(fmt)
                self.setViewport(vp)
                self.gl = True
            except Exception:
                self.gl = False
        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        self.setScene(QGraphicsScene(self))
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        # Komplett neu zeichnen: verhindert Schlieren/Striche, wenn der Pinsel-Cursor
        # über den grauen Bereich außerhalb des Bildes bewegt wird
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setCacheMode(QGraphicsView.CacheModeFlag.CacheNone)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setBackgroundBrush(QBrush(QColor(background)))
        self.setAcceptDrops(True)
        self.setMouseTracking(True)
        self.pix = QGraphicsPixmapItem()
        self.pix.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        self.scene().addItem(self.pix)
        # Motiv-Ebene: wird auf die Innenfläche des Rahmens beschnitten und kann von der
        # Grafikkarte verschoben/skaliert/gedreht werden, ohne neu zu rechnen
        self.clip = QGraphicsPathItem()
        self.clip.setPen(QPen(Qt.PenStyle.NoPen))
        self.clip.setFlag(QGraphicsItem.GraphicsItemFlag.ItemClipsChildrenToShape, True)
        self.clip.setZValue(1)
        self.scene().addItem(self.clip)
        self.art = QGraphicsPixmapItem(self.clip)
        self.art.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        self.overlay = QGraphicsPixmapItem(self.clip)
        self.overlay.setZValue(1)
        self.overlay.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        self.clip.setVisible(False)
        self._layer_scale = 1.0
        self._art_delta = QTransform()
        self._ov_off = (0.0, 0.0)
        self.stroke_item = QGraphicsPathItem()
        self.stroke_item.setZValue(5)
        self.scene().addItem(self.stroke_item)
        self.cursor_item = QGraphicsEllipseItem()
        self.cursor_item.setZValue(6)
        self.cursor_item.setPen(QPen(QColor(255, 255, 255, 220), 0))
        self.cursor_item.setVisible(False)
        self.scene().addItem(self.cursor_item)
        self.cursor_item2 = QGraphicsEllipseItem()
        self.cursor_item2.setZValue(6)
        self.cursor_item2.setPen(QPen(QColor(0, 0, 0, 200), 0, Qt.PenStyle.DashLine))
        self.cursor_item2.setVisible(False)
        self.scene().addItem(self.cursor_item2)

        self.tool = TOOL_PAN
        self.brush_px = 10.0          # Radius in Szene-Pixeln
        self.edit_enabled = True
        self._stroke: list[QPointF] = []
        self._drawing = False
        self._panning = False
        self._pan_last = None
        self._move_last = None
        self._has_image = False
        self._fit_pending = True
        self._space = False
        self.placeholder = ""
        self.crop_dim = QGraphicsPathItem()
        self.crop_dim.setZValue(3)
        self.crop_dim.setBrush(QBrush(QColor(0, 0, 0, 140)))
        self.crop_dim.setPen(QPen(Qt.PenStyle.NoPen))
        self.crop_dim.setVisible(False)
        self.scene().addItem(self.crop_dim)
        self.crop_border = QGraphicsPathItem()
        self.crop_border.setZValue(4)
        pen = QPen(QColor(255, 255, 255), 0, Qt.PenStyle.DashLine)
        pen.setCosmetic(True)
        pen.setWidth(2)
        self.crop_border.setPen(pen)
        self.crop_border.setVisible(False)
        self.scene().addItem(self.crop_border)
        self._crop_start = None

    # ---------------------------------------------------------------- Bild
    def set_image(self, img: np.ndarray | None, fit: bool = False, scale: float = 1.0):
        """Zeigt ``img``; ``scale`` > 1 für schnelle Vorschauen mit geringerer Auflösung,
        damit die Szene-Koordinaten gleich bleiben."""
        if img is None:
            self.pix.setPixmap(QPixmap())
            self._has_image = False
            self.scene().setSceneRect(QRectF(0, 0, 10, 10))
            self.viewport().update()
            return
        self.clip.setVisible(False)
        self._set_base(img, scale, fit)

    def _set_base(self, img, scale, fit):
        was_visible = self._has_image and self._content_visible()
        self.pix.setPixmap(QPixmap.fromImage(to_qimage(img)))
        self.pix.setScale(scale)
        r = self.pix.sceneBoundingRect()
        m = max(r.width(), r.height()) * 1.5
        self.scene().setSceneRect(r.adjusted(-m, -m, m, m))
        self._has_image = True
        # Ansicht nur dann neu einpassen, wenn nötig – sonst springt das Bild beim Einstellen
        if fit or self._fit_pending or (was_visible and not self._content_visible()):
            self.fit()
            self._fit_pending = False

    def _content_visible(self) -> bool:
        vis = self.mapToScene(self.viewport().rect()).boundingRect()
        return vis.contains(self.pix.sceneBoundingRect().adjusted(2, 2, -2, -2))

    def set_layers(self, base: np.ndarray, art: np.ndarray, scale: float, polys, fit: bool = False):
        """Zwei-Ebenen-Vorschau: ``base`` (BGR) und ``art`` (BGRA), beschnitten auf ``polys``
        (Liste von Punkt-Arrays in Bildpixeln)."""
        self._layer_scale = scale
        self._set_base(base, scale, fit)
        path = QPainterPath()
        for poly in polys:
            path.addPolygon(QPolygonF([QPointF(float(x) * scale, float(y) * scale) for x, y in poly]))
            path.closeSubpath()
        self.clip.setPath(path)
        self.art.setPixmap(QPixmap.fromImage(to_qimage(art)))
        self._apply_layer_transform()
        self.clip.setVisible(True)

    def set_art_transform(self, delta: QTransform | None):
        """Verschiebt/skaliert/dreht die Motiv-Ebene (Angabe in Bildpixeln) – sofort, per Grafikkarte."""
        self._art_delta = delta if delta is not None else QTransform()
        self._apply_layer_transform()

    def _apply_layer_transform(self):
        s = self._layer_scale
        t = self._art_delta * QTransform.fromScale(s, s)
        self.art.setTransform(t)
        self.overlay.setTransform(QTransform.fromTranslate(self._ov_off[0], self._ov_off[1]) * t)

    def set_overlay(self, img: np.ndarray | None, offset=(0, 0), opacity: float = 0.0, scale: float = 1.0):
        if img is None or opacity <= 0:
            self.overlay.setVisible(False)
            return
        self.overlay.setPixmap(QPixmap.fromImage(to_qimage(img)))
        self._ov_off = (float(offset[0]), float(offset[1]))
        self._apply_layer_transform()
        self.overlay.setOpacity(opacity)
        self.overlay.setVisible(True)

    def _clamp(self, p: QPointF) -> QPointF:
        r = self.pix.sceneBoundingRect()
        return QPointF(min(max(p.x(), r.left()), r.right()), min(max(p.y(), r.top()), r.bottom()))

    def set_crop_rect(self, rect: QRectF | None):
        """Zeigt den Zuschnitt: außerhalb abgedunkelt, Rand gestrichelt."""
        if rect is None:
            self.crop_dim.setVisible(False)
            self.crop_border.setVisible(False)
            return
        full = QPainterPath()
        full.addRect(self.pix.sceneBoundingRect())
        inner = QPainterPath()
        inner.addRect(rect)
        self.crop_dim.setPath(full.subtracted(inner))
        self.crop_border.setPath(inner)
        self.crop_dim.setVisible(True)
        self.crop_border.setVisible(True)

    def fit(self):
        if not self._has_image:
            return
        self.resetTransform()
        f = self._fit_factor()
        if not f:
            return
        self.setTransform(QTransform.fromScale(f, f))
        self.centerOn(self.pix.sceneBoundingRect().center())
        self.zoomChanged.emit(100.0)

    def zoom(self, factor: float):
        cur = self.transform().m11()
        new = max(0.02, min(400.0, cur * factor))
        factor = new / cur
        self.scale(factor, factor)
        self._update_cursor(self.mapFromGlobal(QCursor.pos()))
        self.zoomChanged.emit(self.zoom_percent())

    def zoom_percent(self) -> float:
        """Zoom relativ zum eingepassten Bild (100 % = ganzes Bild sichtbar)."""
        f = self._fit_factor()
        return 100.0 * self.transform().m11() / f if f else 100.0

    def _fit_factor(self) -> float:
        r = self.pix.sceneBoundingRect()
        vr = self.viewport().rect()
        if r.width() <= 0 or vr.width() < 20 or vr.height() < 20:
            return 0.0
        # Rand für die schwebenden Leisten lassen
        mx, my = 36, 64
        return max(1e-3, min((vr.width() - 2 * mx) / r.width(), (vr.height() - 2 * my) / r.height()))

    def zoom_100(self):
        self.resetTransform()

    # ---------------------------------------------------------------- Werkzeuge
    def set_tool(self, tool: str):
        self.tool = tool
        self._update_cursor_shape()
        self._update_cursor(self.mapFromGlobal(QCursor.pos()))

    def set_brush_radius(self, px: float):
        self.brush_px = max(0.5, px)
        self._update_cursor(self.mapFromGlobal(QCursor.pos()))

    def _update_cursor_shape(self):
        if self._space or self.tool == TOOL_PAN:
            self.viewport().setCursor(Qt.CursorShape.OpenHandCursor)
        elif self.tool == TOOL_CROP:
            self.viewport().setCursor(Qt.CursorShape.CrossCursor)
        elif self.tool == TOOL_MOVE:
            self.viewport().setCursor(Qt.CursorShape.SizeAllCursor)
        elif self.tool in EDIT_TOOLS and self.edit_enabled:
            self.viewport().setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.viewport().setCursor(Qt.CursorShape.ArrowCursor)

    def _editing(self) -> bool:
        return self.tool in EDIT_TOOLS and self.edit_enabled and self._has_image and not self._space

    def _update_cursor(self, view_pos):
        show = self._editing() and self.viewport().rect().contains(view_pos)
        self.cursor_item.setVisible(show)
        self.cursor_item2.setVisible(show)
        if show:
            p = self.mapToScene(view_pos)
            r = self.brush_px
            self.cursor_item.setRect(QRectF(p.x() - r, p.y() - r, 2 * r, 2 * r))
            self.cursor_item2.setRect(QRectF(p.x() - r, p.y() - r, 2 * r, 2 * r))

    def _stroke_color(self) -> QColor:
        return {TOOL_BRUSH: QColor(40, 200, 90, 170), TOOL_LINE: QColor(40, 200, 90, 170),
                TOOL_ERASE: QColor(230, 60, 60, 170), TOOL_RESTORE: QColor(80, 160, 255, 150)}.get(
            self.tool, QColor(255, 255, 0, 150))

    def _update_stroke_item(self):
        path = QPainterPath()
        pts = self._stroke
        if pts:
            path.moveTo(pts[0])
            if len(pts) == 1:
                path.lineTo(pts[0] + QPointF(0.01, 0))
            for p in pts[1:]:
                path.lineTo(p)
        pen = QPen(self._stroke_color(), 2 * self.brush_px, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                   Qt.PenJoinStyle.RoundJoin)
        self.stroke_item.setPen(pen)
        self.stroke_item.setPath(path)

    def clear_stroke(self):
        self._stroke = []
        self.stroke_item.setPath(QPainterPath())

    # ---------------------------------------------------------------- Events
    def wheelEvent(self, e):
        steps = e.angleDelta().y() / 120.0
        if steps == 0:
            return
        if self.tool == TOOL_MOVE and not (e.modifiers() & Qt.KeyboardModifier.ControlModifier) and self._has_image:
            self.motifScaled.emit(1.05 ** steps)
            return
        if self.tool in EDIT_TOOLS and (e.modifiers() & Qt.KeyboardModifier.AltModifier):
            self.brushSizeStep.emit(1 if steps > 0 else -1)
            return
        self.zoom(1.2 ** steps)

    def mousePressEvent(self, e):
        self.clicked.emit()
        if e.button() == Qt.MouseButton.MiddleButton or (e.button() == Qt.MouseButton.LeftButton and
                                                         (self.tool == TOOL_PAN or self._space)):
            self._panning = True
            self._pan_last = e.position()
            self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
            return
        if e.button() == Qt.MouseButton.LeftButton and self._has_image:
            p = self.mapToScene(e.position().toPoint())
            if self.tool == TOOL_MOVE:
                self._move_last = p
                return
            if self.tool == TOOL_CROP:
                self._crop_start = self._clamp(p)
                self.set_crop_rect(QRectF(self._crop_start, self._crop_start))
                return
            if self._editing():
                self._drawing = True
                self._stroke = [p, p] if self.tool == TOOL_LINE else [p]
                self._update_stroke_item()
                return
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._panning and self._pan_last is not None:
            d = e.position() - self._pan_last
            self._pan_last = e.position()
            self.horizontalScrollBar().setValue(int(self.horizontalScrollBar().value() - d.x()))
            self.verticalScrollBar().setValue(int(self.verticalScrollBar().value() - d.y()))
            return
        p = self.mapToScene(e.position().toPoint())
        if self._crop_start is not None:
            self.set_crop_rect(QRectF(self._crop_start, self._clamp(p)).normalized())
            return
        if self._move_last is not None:
            d = p - self._move_last
            self._move_last = p
            self.motifDragged.emit(d.x(), d.y())
            return
        if self._drawing:
            if self.tool == TOOL_LINE:
                self._stroke[-1] = p
            else:
                last = self._stroke[-1]
                if (p - last).manhattanLength() >= max(0.5, self.brush_px * 0.25):
                    self._stroke.append(p)
            self._update_stroke_item()
        self._update_cursor(e.position().toPoint())
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        if self._panning:
            self._panning = False
            self._pan_last = None
            self._update_cursor_shape()
            return
        if self._move_last is not None:
            self._move_last = None
            self.motifDragFinished.emit()
            return
        if self._crop_start is not None:
            r = QRectF(self._crop_start, self._clamp(self.mapToScene(e.position().toPoint()))).normalized()
            self._crop_start = None
            if r.width() >= 8 and r.height() >= 8:
                self.cropSelected.emit(r.left(), r.top(), r.right(), r.bottom())
            else:
                self.cropSelected.emit(-1, -1, -1, -1)  # nur geklickt -> unverändert lassen
            return
        if self._drawing:
            self._drawing = False
            pts = [(q.x(), q.y()) for q in self._stroke]
            self.strokeFinished.emit(pts, self.tool)
            return
        super().mouseReleaseEvent(e)

    def leaveEvent(self, e):
        self.cursor_item.setVisible(False)
        self.cursor_item2.setVisible(False)
        super().leaveEvent(e)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Space and not e.isAutoRepeat():
            self._space = True
            self._update_cursor_shape()
            return
        super().keyPressEvent(e)

    def keyReleaseEvent(self, e):
        if e.key() == Qt.Key.Key_Space and not e.isAutoRepeat():
            self._space = False
            self._update_cursor_shape()
            return
        super().keyReleaseEvent(e)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self._fit_pending:
            self.fit()

    # Drag & Drop
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls() or e.mimeData().hasImage():
            e.acceptProposedAction()

    def dragMoveEvent(self, e):
        e.acceptProposedAction()

    def dropEvent(self, e):
        urls = e.mimeData().urls()
        if urls:
            self.fileDropped.emit(urls[0].toLocalFile())
            e.acceptProposedAction()

    def drawForeground(self, painter, rect):
        if self._has_image or not self.placeholder:
            return
        from . import theme
        painter.save()
        painter.resetTransform()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        vr = QRectF(self.viewport().rect()).adjusted(60, 90, -60, -90)
        pen = QPen(QColor(255, 255, 255, 46), 2, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(QColor(255, 255, 255, 6))
        painter.drawRoundedRect(vr, 28, 28)
        c = vr.center()
        painter.setPen(Qt.PenStyle.NoPen)
        glow = QColor(theme.ACCENT)
        glow.setAlpha(40)
        painter.setBrush(glow)
        painter.drawEllipse(QPointF(c.x(), c.y() - 52), 38, 38)
        f = painter.font()
        f.setFamily(theme.icon_font())
        f.setPixelSize(34)
        painter.setFont(f)
        painter.setPen(QColor(theme.ACCENT))
        painter.drawText(QRectF(c.x() - 40, c.y() - 92, 80, 80), Qt.AlignmentFlag.AlignCenter,
                         chr(theme.ICON["image"]))
        lines = self.placeholder.split("\n", 1)
        f = QFont("Segoe UI Variable Display")
        f.setPixelSize(22)
        f.setWeight(QFont.Weight.DemiBold)
        painter.setFont(f)
        painter.setPen(QColor(theme.TEXT))
        painter.drawText(QRectF(vr.left(), c.y() + 2, vr.width(), 34), Qt.AlignmentFlag.AlignCenter, lines[0])
        if len(lines) > 1:
            f.setPixelSize(14)
            f.setWeight(QFont.Weight.Normal)
            painter.setFont(f)
            painter.setPen(QColor(theme.TEXT_2))
            painter.drawText(QRectF(vr.left() + 20, c.y() + 40, vr.width() - 40, 60),
                             Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
                             lines[1])
        painter.restore()
