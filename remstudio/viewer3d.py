"""Drehbare 3D-Vorschau (pyqtgraph / OpenGL)."""
from __future__ import annotations

import numpy as np
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QPushButton
from PySide6.QtCore import Qt

try:
    import pyqtgraph.opengl as gl
    from pyqtgraph import Vector
    HAVE_GL = True
except Exception:  # pragma: no cover
    HAVE_GL = False


def _rgb(hexcol: str, a: float = 1.0):
    h = hexcol.lstrip("#")
    return (int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255, a)


def _shade(verts, faces, hexcol):
    """Einfache Beleuchtung pro Dreieck (Umgebungslicht + zwei Lichtquellen)."""
    base = np.array(_rgb(hexcol)[:3], np.float32)
    v = verts[faces]
    n = np.cross(v[:, 1] - v[:, 0], v[:, 2] - v[:, 0])
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    ln[ln == 0] = 1
    n /= ln
    l1 = np.array([0.35, -0.55, 0.75], np.float32)
    l1 /= np.linalg.norm(l1)
    l2 = np.array([-0.6, 0.4, 0.3], np.float32)
    l2 /= np.linalg.norm(l2)
    d = 0.62 * np.clip(n @ l1, 0, 1) + 0.25 * np.clip(n @ l2, 0, 1)
    c = base[None, :] * (0.38 + d[:, None]) + 0.10 * d[:, None]  # leichter Glanz, damit auch Schwarz plastisch wirkt
    out = np.ones((len(faces), 4), np.float32)
    out[:, :3] = np.clip(c, 0, 1)
    return out


class Viewer3D(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.items = []
        self._size = None
        self.view = None
        if not HAVE_GL:
            lab = QLabel("3D-Ansicht nicht verfügbar (OpenGL fehlt).\nDer Export funktioniert trotzdem.")
            lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(lab)
            return
        try:
            self.view = gl.GLViewWidget()
        except Exception:
            lab = QLabel("3D-Ansicht konnte nicht gestartet werden.\nDer Export funktioniert trotzdem.")
            lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(lab)
            return
        self.view.setBackgroundColor((233, 234, 237))
        lay.addWidget(self.view, 1)
        bar = QHBoxLayout()
        bar.setContentsMargins(16, 8, 16, 14)
        hint = QLabel("Linke Maustaste: drehen · Mausrad: zoomen · Mittlere Maustaste: verschieben")
        hint.setObjectName("hint")
        bar.addWidget(hint, 1)
        for text, el, az in (("Vorne", 90, -90), ("Schräg", 35, -110), ("Hinten", -90, -90)):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, el=el, az=az: self.set_angle(el, az))
            bar.addWidget(b)
        lay.addLayout(bar)
        self.grid = gl.GLGridItem()
        self.grid.setColor((0, 0, 0, 38))
        self.view.addItem(self.grid)

    def set_angle(self, elevation, azimuth):
        if self.view is None:
            return
        self.view.setCameraPosition(distance=(self._size or 200.0) * 1.7, elevation=elevation, azimuth=azimuth)

    def set_meshes(self, parts: list, size_mm: float, reset_camera: bool = False):
        """parts: Liste von (Mesh, Farbe-hex)."""
        if self.view is None:
            return
        for it in self.items:
            self.view.removeItem(it)
        self.items = []
        allv = [m.vertices for m, _ in parts if len(m.faces)]
        if not allv:
            return
        v = np.concatenate(allv)
        lo, hi = v.min(0), v.max(0)
        center = (lo + hi) / 2
        for mesh, color in parts:
            if len(mesh.faces) == 0:
                continue
            verts = (mesh.vertices - center).astype(np.float32)
            faces = mesh.faces.astype(np.int32)
            md = gl.MeshData(vertexes=verts, faces=faces, faceColors=_shade(verts, faces, color))
            item = gl.GLMeshItem(meshdata=md, smooth=False, shader=None, glOptions="opaque",
                                 computeNormals=False)
            self.view.addItem(item)
            self.items.append(item)
        new_size = float(max(hi[0] - lo[0], hi[1] - lo[1], 1.0))
        g = max(10, int(round(new_size / 10.0)))
        self.grid.setSize(new_size * 1.4, new_size * 1.4)
        self.grid.setSpacing(g, g)
        self.grid.resetTransform()
        self.grid.translate(0, 0, -(center[2] - lo[2]) - 0.05)
        if reset_camera or self._size is None or abs(new_size - self._size) > self._size * 0.25:
            self._size = new_size
            self.view.opts["center"] = Vector(0, 0, 0)
            self.set_angle(35, -110)
