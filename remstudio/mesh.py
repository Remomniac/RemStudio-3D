"""2D-Maske -> 3D-Netz (extrudierte Konturen) und STL-Export."""
from __future__ import annotations

import struct

import cv2
import mapbox_earcut as earcut
import numpy as np


class Mesh:
    def __init__(self, vertices: np.ndarray | None = None, faces: np.ndarray | None = None):
        self.vertices = vertices if vertices is not None else np.zeros((0, 3), np.float64)
        self.faces = faces if faces is not None else np.zeros((0, 3), np.int64)

    @staticmethod
    def concat(meshes: list["Mesh"]) -> "Mesh":
        vs, fs, off = [], [], 0
        for m in meshes:
            if len(m.faces) == 0:
                continue
            vs.append(m.vertices)
            fs.append(m.faces + off)
            off += len(m.vertices)
        if not vs:
            return Mesh()
        return Mesh(np.concatenate(vs), np.concatenate(fs))

    def translated(self, dx=0.0, dy=0.0, dz=0.0) -> "Mesh":
        return Mesh(self.vertices + np.array([dx, dy, dz]), self.faces.copy())

    @property
    def triangle_count(self) -> int:
        return len(self.faces)

    def volume_mm3(self) -> float:
        if len(self.faces) == 0:
            return 0.0
        v = self.vertices[self.faces]
        return float(abs(np.einsum("ij,ij->i", v[:, 0], np.cross(v[:, 1], v[:, 2])).sum()) / 6.0)

    def bounds(self):
        if len(self.vertices) == 0:
            return np.zeros(3), np.zeros(3)
        return self.vertices.min(0), self.vertices.max(0)

    def save_stl(self, path: str, name: str = "RemStudio"):
        v = self.vertices[self.faces].astype(np.float32)
        n = np.cross(v[:, 1] - v[:, 0], v[:, 2] - v[:, 0])
        ln = np.linalg.norm(n, axis=1, keepdims=True)
        ln[ln == 0] = 1
        n = (n / ln).astype(np.float32)
        rec = np.zeros(len(v), dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")])
        rec["n"] = n
        rec["v"] = v
        header = (name.encode("ascii", "replace")[:79]).ljust(80, b" ")
        with open(path, "wb") as f:
            f.write(header)
            f.write(struct.pack("<I", len(v)))
            f.write(rec.tobytes())


def _signed_area(pts: np.ndarray) -> float:
    x, y = pts[:, 0], pts[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(np.roll(x, -1), y))


def mask_polygons(mask: np.ndarray, ppm: float, simplify_px: float = 0.6, origin_h: int | None = None):
    """Konturen der Maske als Liste von (Außenring, [Löcher]) in mm.

    Koordinatensystem: x nach rechts, y nach oben (Bild wird nicht gespiegelt,
    wenn man von oben auf das Druckbett schaut)."""
    h = mask.shape[0] if origin_h is None else origin_h
    # Doppelte Auflösung: Außen- und Lochkonturen laufen sonst bei 1 Pixel
    # breiten Stegen durch dieselben Pixelmittelpunkte (entartete Polygone).
    K = 2
    m = (mask > 0).astype(np.uint8)
    m = cv2.resize(m, (m.shape[1] * K, m.shape[0] * K), interpolation=cv2.INTER_NEAREST)
    # 1 Pixel Rand, damit Konturen am Bildrand geschlossen sind
    m = cv2.copyMakeBorder(m, 1, 1, 1, 1, cv2.BORDER_CONSTANT, value=0)
    contours, hier = cv2.findContours(m, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    if hier is None:
        return []
    hier = hier[0]
    polys = []

    def conv(c, simplify=True):
        if simplify and simplify_px > 0 and len(c) > 8:
            c = cv2.approxPolyDP(c, simplify_px * K, True)
        elif not simplify:
            c = cv2.approxPolyDP(c, 0.01, True)  # nur kollineare Punkte entfernen
        pts = c.reshape(-1, 2).astype(np.float64) - 1.0
        out = np.empty_like(pts)
        out[:, 0] = (pts[:, 0] + 0.5) / K / ppm
        out[:, 1] = (h - (pts[:, 1] + 0.5) / K) / ppm
        # doppelte aufeinanderfolgende Punkte entfernen
        keep = np.ones(len(out), bool)
        keep[1:] = np.any(np.abs(np.diff(out, axis=0)) > 1e-9, axis=1)
        out = out[keep]
        if len(out) > 1 and np.allclose(out[0], out[-1]):
            out = out[:-1]
        return out

    for i, c in enumerate(contours):
        if hier[i][3] != -1:
            continue  # Loch – wird beim Elternteil verarbeitet
        hole_idx = []
        ch = hier[i][2]
        while ch != -1:
            hole_idx.append(ch)
            ch = hier[ch][0]

        def make(simplify, c=c, hole_idx=hole_idx):
            outer = conv(c, simplify)
            if len(outer) < 3 or abs(_signed_area(outer)) < 1e-6:
                return None
            holes = []
            for hi in hole_idx:
                hp = conv(contours[hi], simplify)
                if len(hp) >= 3 and abs(_signed_area(hp)) > 1e-6:
                    holes.append(hp)
            return outer, holes

        poly = make(True)
        if poly is not None:
            # Fallback ohne Vereinfachung, falls die Triangulierung scheitert
            polys.append((poly[0], poly[1], lambda make=make: make(False)))
    return polys


def extrude_polygons(polys, z0: float, z1: float) -> Mesh:
    meshes = []
    for item in polys:
        outer, holes = item[0], item[1]
        mesh = _extrude_one(outer, holes, z0, z1)
        if mesh is None and len(item) > 2:
            alt = item[2]()
            if alt is not None:
                mesh = _extrude_one(alt[0], alt[1], z0, z1)
                if mesh is None:
                    mesh = _extrude_one(alt[0], alt[1], z0, z1, strict=False)
        if mesh is None:
            mesh = _extrude_one(outer, holes, z0, z1, strict=False)
        meshes.append(mesh)
    return Mesh.concat(meshes)


def _extrude_one(outer: np.ndarray, holes: list, z0: float, z1: float, strict: bool = True):
    """Extrudiert ein Polygon mit Löchern. Bei ``strict`` wird None
    zurückgegeben, wenn die Triangulierung unvollständig ist."""
    # Orientierung: außen gegen den Uhrzeigersinn, Löcher im Uhrzeigersinn
    if _signed_area(outer) < 0:
        outer = outer[::-1]
    rings = [outer]
    for hp in holes:
        rings.append(hp[::-1] if _signed_area(hp) > 0 else hp)
    pts2 = np.concatenate(rings)
    ends = np.cumsum([len(r) for r in rings]).astype(np.uint32)
    tri = earcut.triangulate_float64(pts2, ends).reshape(-1, 3).astype(np.int64)
    n = len(pts2)
    if strict and len(tri) != n - 2 + 2 * len(holes):
        return None
    if len(tri):
        # Dreiecke nach oben ausrichten
        a, b, c = pts2[tri[:, 0]], pts2[tri[:, 1]], pts2[tri[:, 2]]
        cross = (b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (b[:, 1] - a[:, 1]) * (c[:, 0] - a[:, 0])
        flip = cross < 0
        tri[flip] = tri[flip][:, [0, 2, 1]]

    verts = np.empty((2 * n, 3))
    verts[:n, :2] = pts2
    verts[:n, 2] = z0
    verts[n:, :2] = pts2
    verts[n:, 2] = z1

    top = tri + n
    bottom = tri[:, [0, 2, 1]]
    walls = []
    start = 0
    for r in rings:
        k = len(r)
        i = np.arange(k) + start
        j = np.roll(i, -1)
        walls.append(np.stack([i, j, j + n], 1))
        walls.append(np.stack([i, j + n, i + n], 1))
        start += k
    faces = np.concatenate([top, bottom] + walls)
    return Mesh(verts, faces)


def mask_to_mesh(mask: np.ndarray, ppm: float, z0: float, z1: float, simplify_px: float = 0.6,
                 origin_h: int | None = None) -> Mesh:
    return extrude_polygons(mask_polygons(mask, ppm, simplify_px, origin_h), z0, z1)


def build_meshes(res, p, simplify_px: float = 0.6) -> dict:
    """Erzeugt die Teile: 'motiv' (Motiv + Rahmen) und optional 'rueckplatte'."""
    ppm = res.ppm
    base = p.backplate_mm if p.backplate else 0.0
    art_h = max(0.2, p.art_height_mm)
    parts = {}
    art = mask_to_mesh(res.mask, ppm, base, base + art_h, simplify_px)
    extra = []
    if p.frame_shape != "none" and p.frame_height_mm > art_h + 1e-6 and res.frame_mask.any():
        extra.append(mask_to_mesh(res.frame_mask, ppm, base + art_h, base + p.frame_height_mm, simplify_px))
    parts["motiv"] = Mesh.concat([art] + extra)
    if p.backplate:
        parts["rueckplatte"] = mask_to_mesh(res.outer_mask, ppm, 0.0, base, simplify_px)
    return parts
