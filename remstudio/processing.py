"""Bildverarbeitung: Motiv -> druckbare 2D-Maske (Material = 255).

Alle Längenangaben in den Parametern sind in Millimetern, damit die
Vorschau (niedrige Auflösung) und der Export (hohe Auflösung) exakt das
gleiche Ergebnis liefern. ``process`` rechnet sie anhand von ``ppm``
(Pixel pro Millimeter) in Pixel um.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict, fields

import cv2
import numpy as np

from .i18n import T

# ---------------------------------------------------------------------------
# Parameter
# ---------------------------------------------------------------------------

MODE_THRESHOLD = "threshold"   # Strichzeichnung / Comic / Logo
MODE_ADAPTIVE = "adaptive"     # Foto -> Skizze
MODE_EDGES = "edges"           # Kantenerkennung

FRAME_RECT = "rect"
FRAME_ROUNDED = "rounded"
FRAME_CIRCLE = "circle"        # Kreis bzw. Oval (bei ungleicher Breite/Höhe)
FRAME_HEXAGON = "hexagon"
FRAME_NONE = "none"

ISLANDS_BRIDGE = "bridge"
ISLANDS_REMOVE = "remove"
ISLANDS_KEEP = "keep"

HANG_NONE = "none"
HANG_HOLES = "holes"           # zwei Bohrungen in den oberen Ecken
HANG_TAB = "tab"               # Aufhängeöse oben mittig


@dataclass
class Params:
    # --- Motiv / Bild -----------------------------------------------------
    mode: str = MODE_THRESHOLD
    threshold: int = 128
    auto_threshold: bool = True
    invert: bool = False            # helle Linien auf dunklem Grund
    brightness: int = 0             # -100..100
    contrast: int = 0               # -100..100
    blur_mm: float = 0.0            # Rauschen entfernen (vor Schwellwert)
    adaptive_block_mm: float = 6.0  # Foto-Modus: Detailgröße
    adaptive_c: int = 8             # Foto-Modus: Empfindlichkeit
    edge_sensitivity: int = 50      # Kanten-Modus 0..100
    edge_width_mm: float = 1.2      # Kanten-Modus: Strichbreite
    outline_only: bool = False      # Flächen in Umrisse umwandeln
    outline_width_mm: float = 1.5
    fill_shapes: bool = False       # Silhouette: Löcher füllen
    line_adjust_mm: float = 0.0     # + dicker / - dünner
    smooth_mm: float = 0.3          # Kanten glätten
    min_speck_mm2: float = 2.0      # kleine Flecken entfernen
    min_hole_mm2: float = 0.5       # winzige Löcher schließen

    # --- Zuschnitt des Quellbilds: None oder [x0, y0, x1, y1] in Pixeln -----
    crop: object = None
    bg_outline_px: float = 0.0      # Umrisslinie nach Hintergrund-Entfernung (Pixel des Originalbilds)

    # --- Platzierung des Motivs -----------------------------------------
    motif_scale: float = 1.0        # 1.0 = in Innenfläche einpassen
    motif_dx: float = 0.0           # Verschiebung in mm
    motif_dy: float = 0.0
    motif_rotation: float = 0.0     # Grad
    mirror: bool = False

    # --- Rahmen -----------------------------------------------------------
    frame_shape: str = FRAME_RECT
    width_mm: float = 200.0
    height_mm: float = 200.0
    frame_width_mm: float = 8.0
    corner_radius_mm: float = 12.0
    inner_margin_mm: float = 0.0    # Abstand Motiv <-> Rahmen

    # --- Druck --------------------------------------------------------------
    min_line_mm: float = 0.8        # dünnste druckbare Linie
    min_gap_mm: float = 0.6         # engste druckbare Lücke
    fix_thin: bool = False          # dünne Stellen automatisch verstärken
    islands: str = ISLANDS_BRIDGE
    bridge_width_mm: float = 1.6
    hang: str = HANG_NONE
    hang_hole_mm: float = 4.0

    # --- 3D ---------------------------------------------------------------
    art_height_mm: float = 3.0
    frame_height_mm: float = 4.0
    backplate: bool = False
    backplate_mm: float = 1.2
    quality_ppm: float = 10.0       # Export-Auflösung (Pixel pro mm)
    bed_x_mm: float = 256.0
    bed_y_mm: float = 256.0

    # --- Darstellung --------------------------------------------------------
    color_art: str = "#1b1b1b"
    color_back: str = "#d9d9d9"
    color_wall: str = "#f1eeea"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Params":
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in names})

    def copy(self) -> "Params":
        return Params.from_dict(self.to_dict())


@dataclass
class Result:
    ppm: float
    mask: np.ndarray                # finale Maske (Motiv + Rahmen), uint8 0/255
    frame_mask: np.ndarray          # nur Rahmen (für erhöhten Rahmen)
    outer_mask: np.ndarray          # Außenform (für Rückplatte)
    islands: np.ndarray             # lose Teile (bool) – bevor sie behandelt wurden
    bridges: np.ndarray             # automatisch erzeugte Stege (bool)
    thin: np.ndarray                # zu dünne Stellen (bool)
    narrow: np.ndarray              # zu enge Lücken (bool)
    island_count: int = 0
    bridge_count: int = 0
    thin_count: int = 0
    narrow_count: int = 0
    loose_after: int = 0            # noch lose Teile in der finalen Maske
    threshold_used: int = -1
    art_free: np.ndarray | None = None    # Motiv vor dem Beschneiden (für flüssiges Verschieben)
    inner_mask: np.ndarray | None = None  # Innenfläche des Rahmens
    warnings: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def disk(radius_px: float) -> np.ndarray:
    r = max(1, int(round(radius_px)))
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))


def dilate(mask: np.ndarray, radius_px: float) -> np.ndarray:
    if radius_px < 0.5:
        return mask
    return cv2.dilate(mask, disk(radius_px))


def erode(mask: np.ndarray, radius_px: float) -> np.ndarray:
    if radius_px < 0.5:
        return mask
    return cv2.erode(mask, disk(radius_px))


def count_blobs(boolmask: np.ndarray) -> int:
    if not boolmask.any():
        return 0
    n, _ = cv2.connectedComponents(boolmask.astype(np.uint8), connectivity=8)
    return n - 1


def remove_small(mask: np.ndarray, min_area_px: float) -> np.ndarray:
    """Entfernt zusammenhängende Flächen kleiner als min_area_px."""
    if min_area_px < 1:
        return mask
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if n <= 1:
        return mask
    keep = stats[:, cv2.CC_STAT_AREA] >= min_area_px
    keep[0] = False
    return np.where(keep[labels], 255, 0).astype(np.uint8)


def fill_small_holes(mask: np.ndarray, max_area_px: float) -> np.ndarray:
    if max_area_px < 1:
        return mask
    inv = cv2.bitwise_not(mask)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(inv, connectivity=4)
    h, w = mask.shape
    small = stats[:, cv2.CC_STAT_AREA] < max_area_px
    # Flächen, die den Bildrand berühren, sind keine Löcher
    border = np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))
    small[border] = False
    small[0] = False  # Label 0 = Material selbst
    out = mask.copy()
    out[small[labels]] = 255
    return out


def fill_all_holes(mask: np.ndarray) -> np.ndarray:
    h, w = mask.shape
    padded = cv2.copyMakeBorder(mask, 1, 1, 1, 1, cv2.BORDER_CONSTANT, value=0)
    ff = padded.copy()
    ffmask = np.zeros((h + 4, w + 4), np.uint8)
    cv2.floodFill(ff, ffmask, (0, 0), 255)
    holes = cv2.bitwise_not(ff)[1:-1, 1:-1]
    return cv2.bitwise_or(mask, holes)


def fix_diagonals(mask: np.ndarray) -> np.ndarray:
    """Pixel, die sich nur über Eck berühren, verbinden (sonst nicht-mannigfaltige
    3D-Geometrie und instabile Druckstellen)."""
    m = mask > 0
    a = m[:-1, :-1]
    b = m[:-1, 1:]
    c = m[1:, :-1]
    d = m[1:, 1:]
    diag1 = a & d & ~b & ~c
    diag2 = b & c & ~a & ~d
    if diag1.any() or diag2.any():
        out = m.copy()
        out[:-1, 1:] |= diag1      # b setzen
        out[:-1, :-1] |= diag2     # a setzen
        return np.where(out, 255, 0).astype(np.uint8)
    return mask


def hex_to_bgr(h: str) -> tuple:
    h = h.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (b, g, r)


# ---------------------------------------------------------------------------
# Geometrie des Rahmens
# ---------------------------------------------------------------------------

def shape_mask(shape: str, w: int, h: int, inset_px: float, radius_px: float) -> np.ndarray:
    """Gefüllte Form (255) mit Abstand ``inset_px`` zum Bildrand."""
    m = np.zeros((h, w), np.uint8)
    x0, y0 = inset_px, inset_px
    x1, y1 = w - 1 - inset_px, h - 1 - inset_px
    if x1 <= x0 or y1 <= y0:
        return m
    sh = 4  # Sub-Pixel-Genauigkeit für cv2-Zeichenfunktionen
    S = 1 << sh

    def P(x, y):
        return (int(round(x * S)), int(round(y * S)))

    if shape in (FRAME_RECT, FRAME_NONE):
        cv2.rectangle(m, (int(round(x0)), int(round(y0))), (int(round(x1)), int(round(y1))), 255, -1)
    elif shape == FRAME_ROUNDED:
        r = max(0.0, min(radius_px, (x1 - x0) / 2, (y1 - y0) / 2))
        if r < 1:
            cv2.rectangle(m, (int(round(x0)), int(round(y0))), (int(round(x1)), int(round(y1))), 255, -1)
        else:
            cv2.rectangle(m, (int(round(x0 + r)), int(round(y0))), (int(round(x1 - r)), int(round(y1))), 255, -1)
            cv2.rectangle(m, (int(round(x0)), int(round(y0 + r))), (int(round(x1)), int(round(y1 - r))), 255, -1)
            for cx, cy in ((x0 + r, y0 + r), (x1 - r, y0 + r), (x0 + r, y1 - r), (x1 - r, y1 - r)):
                cv2.circle(m, P(cx, cy), int(round(r * S)), 255, -1, cv2.LINE_8, sh)
    elif shape == FRAME_CIRCLE:
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        axes = (int(round((x1 - x0) / 2 * S)), int(round((y1 - y0) / 2 * S)))
        cv2.ellipse(m, P(cx, cy), axes, 0, 0, 360, 255, -1, cv2.LINE_8, sh)
    elif shape == FRAME_HEXAGON:
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        rx, ry = (x1 - x0) / 2, (y1 - y0) / 2
        pts = []
        for i in range(6):
            a = math.radians(60 * i)
            pts.append(P(cx + rx * math.cos(a), cy + ry * math.sin(a)))
        cv2.fillPoly(m, [np.array(pts, np.int32)], 255, cv2.LINE_8, sh)
    return m


def frame_geometry(p: Params, ppm: float):
    """Gibt (Bildgröße w,h, äußere Form, innere Form, Rahmenring) zurück.

    Bei der Aufhängeöse wird oben zusätzlicher Platz eingeplant.
    """
    tab_extra_mm = 0.0
    if p.hang == HANG_TAB and p.frame_shape != FRAME_NONE:
        tab_extra_mm = p.hang_hole_mm + 6.0
    w = max(8, int(round(p.width_mm * ppm)))
    h_body = max(8, int(round(p.height_mm * ppm)))
    top = int(round(tab_extra_mm * ppm))
    h = h_body + top

    outer = np.zeros((h, w), np.uint8)
    outer[top:] = shape_mask(p.frame_shape, w, h_body, 0, p.corner_radius_mm * ppm)
    if p.frame_shape == FRAME_NONE:
        inner = outer.copy()
        ring = np.zeros_like(outer)
    else:
        fw = p.frame_width_mm * ppm
        inner_r = max(0.0, p.corner_radius_mm - p.frame_width_mm) * ppm
        inner = np.zeros_like(outer)
        inner[top:] = shape_mask(p.frame_shape, w, h_body, fw, inner_r)
        ring = cv2.subtract(outer, inner)
    return w, h, top, outer, inner, ring


# ---------------------------------------------------------------------------
# Motiv in den Rahmen platzieren
# ---------------------------------------------------------------------------

def motif_transform(p: Params, ppm: float, src_w: int, src_h: int, top: int, w: int, h_body: int) -> np.ndarray:
    """Affine 2x3-Matrix: Quellbild-Pixel -> Ausgabe-Pixel."""
    inset = (p.frame_width_mm if p.frame_shape != FRAME_NONE else 0.0) + p.inner_margin_mm
    avail_w = max(1.0, w - 2 * inset * ppm)
    avail_h = max(1.0, h_body - 2 * inset * ppm)
    fit = min(avail_w / src_w, avail_h / src_h)
    s = fit * p.motif_scale
    cx = w / 2 + p.motif_dx * ppm
    cy = top + h_body / 2 + p.motif_dy * ppm
    a = math.radians(-p.motif_rotation)
    ca, sa = math.cos(a) * s, math.sin(a) * s
    mx = -1.0 if p.mirror else 1.0
    # M = T(cx,cy) * R * S * Mirror * T(-src_w/2, -src_h/2)
    m00, m01 = ca * mx, -sa
    m10, m11 = sa * mx, ca
    tx = cx - (m00 * src_w / 2 + m01 * src_h / 2)
    ty = cy - (m10 * src_w / 2 + m11 * src_h / 2)
    return np.array([[m00, m01, tx], [m10, m11, ty]], np.float64)


def output_to_source(p: Params, ppm: float, src_w: int, src_h: int) -> np.ndarray:
    w, h, top, *_ = _sizes(p, ppm)
    M = motif_transform(p, ppm, src_w, src_h, top, w, h - top)
    return cv2.invertAffineTransform(M)


def _sizes(p: Params, ppm: float):
    tab_extra_mm = p.hang_hole_mm + 6.0 if (p.hang == HANG_TAB and p.frame_shape != FRAME_NONE) else 0.0
    w = max(8, int(round(p.width_mm * ppm)))
    h_body = max(8, int(round(p.height_mm * ppm)))
    top = int(round(tab_extra_mm * ppm))
    return w, h_body + top, top


# ---------------------------------------------------------------------------
# Brücken (Stege) für lose Teile
# ---------------------------------------------------------------------------

def compute_bridges(mask: np.ndarray, main_seed: np.ndarray | None, width_px: float):
    """Verbindet alle losen Teile mit möglichst kurzen Stegen (minimaler
    Spannbaum über die Voronoi-Nachbarschaft der Teile).

    Gibt (Stegmaske, Anzahl Stege) zurück.
    """
    n, comp = cv2.connectedComponents(mask, connectivity=8)
    if n <= 2:
        return np.zeros(mask.shape, bool), 0

    # Abstand jedes Hintergrund-Pixels zum nächsten Material-Pixel + dessen Index
    src = np.where(mask > 0, 0, 255).astype(np.uint8)
    dist, lab = cv2.distanceTransformWithLabels(src, cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL)
    ys, xs = np.nonzero(mask)
    max_label = int(lab.max()) + 1
    lab_y = np.zeros(max_label, np.int32)
    lab_x = np.zeros(max_label, np.int32)
    own = lab[ys, xs]
    lab_y[own] = ys
    lab_x[own] = xs
    lab_comp = np.zeros(max_label, np.int32)
    lab_comp[own] = comp[ys, xs]
    near_comp = lab_comp[lab]

    cand = []
    for axis in (0, 1):
        if axis == 0:
            ca, cb = near_comp[:, :-1], near_comp[:, 1:]
            da, db = dist[:, :-1], dist[:, 1:]
            la, lb = lab[:, :-1], lab[:, 1:]
        else:
            ca, cb = near_comp[:-1, :], near_comp[1:, :]
            da, db = dist[:-1, :], dist[1:, :]
            la, lb = lab[:-1, :], lab[1:, :]
        sel = (ca != cb) & (ca > 0) & (cb > 0)
        if sel.any():
            cand.append(np.stack([ca[sel], cb[sel], (da[sel] + db[sel]), la[sel], lb[sel]], 1))
    if not cand:
        return np.zeros(mask.shape, bool), 0
    c = np.concatenate(cand).astype(np.float64)
    a = np.minimum(c[:, 0], c[:, 1]).astype(np.int64)
    b = np.maximum(c[:, 0], c[:, 1]).astype(np.int64)
    key = a * n + b
    order = np.lexsort((c[:, 2], key))
    key_s = key[order]
    first = np.ones(len(order), bool)
    first[1:] = key_s[1:] != key_s[:-1]
    best = order[first]

    edges = sorted(((c[i, 2], int(c[i, 0]), int(c[i, 1]), int(c[i, 3]), int(c[i, 4])) for i in best))

    # Hauptteil (Rahmen) bevorzugen: Teile, die den Seed berühren, sind schon "verbunden"
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    if main_seed is not None and main_seed.any():
        seed_comps = np.unique(comp[main_seed & (mask > 0)])
        seed_comps = seed_comps[seed_comps > 0]
        for sc in seed_comps[1:]:
            parent[find(int(sc))] = find(int(seed_comps[0]))

    bridges = np.zeros(mask.shape, np.uint8)
    thick = max(1, int(round(width_px)))
    count = 0
    for cost, ca_, cb_, la_, lb_ in edges:
        ra, rb = find(ca_), find(cb_)
        if ra == rb:
            continue
        parent[ra] = rb
        p1 = (int(lab_x[la_]), int(lab_y[la_]))
        p2 = (int(lab_x[lb_]), int(lab_y[lb_]))
        cv2.line(bridges, p1, p2, 255, thick, cv2.LINE_8)
        count += 1
    return bridges > 0, count


def find_islands(mask: np.ndarray, main_seed: np.ndarray | None) -> np.ndarray:
    """Bool-Maske aller Teile, die nicht mit dem Hauptteil verbunden sind."""
    n, comp, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if n <= 1:
        return np.zeros(mask.shape, bool)
    if main_seed is not None and main_seed.any():
        main = np.unique(comp[main_seed & (mask > 0)])
        main = main[main > 0]
    else:
        main = np.array([1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))])
    is_main = np.zeros(n, bool)
    is_main[main] = True
    is_main[0] = True
    return ~is_main[comp]


# ---------------------------------------------------------------------------
# Hauptfunktion
# ---------------------------------------------------------------------------

def prepare_gray(img_gray: np.ndarray, p: Params) -> np.ndarray:
    g = img_gray.astype(np.float32)
    if p.contrast or p.brightness:
        c = 1.0 + p.contrast / 100.0 * (1.5 if p.contrast > 0 else 1.0)
        g = (g - 128.0) * max(0.0, c) + 128.0 + p.brightness * 1.28
    return np.clip(g, 0, 255).astype(np.uint8)


def otsu_threshold(img_gray: np.ndarray) -> int:
    t, _ = cv2.threshold(img_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    # Otsu liefert die Obergrenze der dunklen Klasse (bei reinem S/W also 0).
    # Mitte zwischen den Klassenmittelwerten ist robuster.
    dark = img_gray[img_gray <= t]
    light = img_gray[img_gray > t]
    if dark.size and light.size:
        return int(round((float(dark.mean()) + float(light.mean())) / 2))
    return int(t) if t > 0 else 128


def process(src_gray: np.ndarray, edits: np.ndarray | None, p: Params, ppm: float,
            analyse: bool = True) -> Result:
    """Kompletter Ablauf. ``src_gray`` = Quellbild (Graustufen, uint8),
    ``edits`` = Bearbeitungsebene in Quell-Koordinaten (0 nichts, 1 Material, 2 radiert)."""
    warnings: list[str] = []
    threshold_used = -1
    w, h, top, outer, inner, ring = frame_geometry(p, ppm)
    h_body = h - top

    # Interessante Fläche: Innenfläche abzgl. Rand
    content_area = inner
    if p.inner_margin_mm > 0 and p.frame_shape != FRAME_NONE:
        content_area = erode(inner, p.inner_margin_mm * ppm)

    # ---- 1) Graustufenbild vorbereiten und in Ausgaberaum transformieren
    sh, sw = src_gray.shape
    g = prepare_gray(src_gray, p)
    if p.invert:
        g = 255 - g
    M = motif_transform(p, ppm, sw, sh, top, w, h_body)
    scale = math.hypot(M[0, 0], M[1, 0])
    if scale < 0.7:
        # Starke Verkleinerung: vorher sauber herunterrechnen (sonst Treppen/Aliasing)
        f = scale / 0.7
        nw, nh = max(2, int(round(sw * f))), max(2, int(round(sh * f)))
        g = cv2.resize(g, (nw, nh), interpolation=cv2.INTER_AREA)
        if edits is not None and edits.any():
            e1 = cv2.resize(np.where(edits == 1, 255, 0).astype(np.uint8), (nw, nh), interpolation=cv2.INTER_AREA)
            e2 = cv2.resize(np.where(edits == 2, 255, 0).astype(np.uint8), (nw, nh), interpolation=cv2.INTER_AREA)
            edits = np.zeros((nh, nw), np.uint8)
            edits[e1 >= 100] = 1
            edits[e2 >= 100] = 2
        fx, fy = nw / sw, nh / sh
        M = M.copy()
        M[:, 0] /= fx
        M[:, 1] /= fy
        sw, sh = nw, nh
        scale = math.hypot(M[0, 0], M[1, 0])
    interp = cv2.INTER_CUBIC if scale > 1 else cv2.INTER_LINEAR
    warped = cv2.warpAffine(g, M, (w, h), flags=interp, borderMode=cv2.BORDER_CONSTANT, borderValue=255)
    inside_img = cv2.warpAffine(np.full((sh, sw), 255, np.uint8), M, (w, h), flags=cv2.INTER_NEAREST,
                                borderMode=cv2.BORDER_CONSTANT, borderValue=0)

    if p.blur_mm > 0:
        k = p.blur_mm * ppm
        warped = cv2.GaussianBlur(warped, (0, 0), max(0.3, k / 2))

    # ---- 2) In Schwarz/Weiß umwandeln (Material = dunkel)
    if p.mode == MODE_ADAPTIVE:
        block = int(p.adaptive_block_mm * ppm) | 1
        block = max(3, block)
        art = cv2.adaptiveThreshold(warped, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV,
                                    block, p.adaptive_c)
    elif p.mode == MODE_EDGES:
        sigma = max(0.5, 0.6 * ppm)
        bl = cv2.GaussianBlur(warped, (0, 0), sigma)
        hi = int(np.interp(p.edge_sensitivity, [0, 100], [220, 25]))
        art = cv2.Canny(bl, hi * 0.5, hi)
        art = dilate(art, p.edge_width_mm * ppm / 2)
    else:
        t = p.threshold
        if p.auto_threshold:
            t = otsu_threshold(g)
        threshold_used = t
        art = np.where(warped < t, 255, 0).astype(np.uint8)
    art[inside_img == 0] = 0

    # ---- 3) Formen bearbeiten
    if p.fill_shapes:
        art = fill_all_holes(art)
    if p.outline_only:
        ow = p.outline_width_mm * ppm
        art = cv2.subtract(art, erode(art, ow))
    if p.line_adjust_mm > 0:
        art = dilate(art, p.line_adjust_mm * ppm / 2)
    elif p.line_adjust_mm < 0:
        art = erode(art, -p.line_adjust_mm * ppm / 2)
    if p.smooth_mm > 0:
        s = p.smooth_mm * ppm
        art = cv2.GaussianBlur(art, (0, 0), max(0.5, s))
        art = np.where(art >= 128, 255, 0).astype(np.uint8)
    art = remove_small(art, p.min_speck_mm2 * ppm * ppm)
    art = fill_small_holes(art, p.min_hole_mm2 * ppm * ppm)

    # ---- 4) Manuelle Bearbeitungen (Pinsel/Radierer) anwenden
    if edits is not None and edits.any():
        add = cv2.warpAffine(np.where(edits == 1, 255, 0).astype(np.uint8), M, (w, h),
                             flags=cv2.INTER_LINEAR, borderValue=0)
        rem = cv2.warpAffine(np.where(edits == 2, 255, 0).astype(np.uint8), M, (w, h),
                             flags=cv2.INTER_LINEAR, borderValue=0)
        art[add >= 128] = 255
        art[rem >= 128] = 0

    # ---- 5) Auf Innenfläche beschneiden und mit Rahmen kombinieren
    art_free = art
    art = cv2.bitwise_and(art, content_area)
    combined = cv2.bitwise_or(art, ring)
    combined = fix_diagonals(combined)

    seed = ring > 0 if p.frame_shape != FRAME_NONE else None
    need_connect = not p.backplate

    # ---- 6) Lose Teile (Inseln)
    islands = find_islands(combined, seed)
    island_count = count_blobs(islands)
    bridges = np.zeros(combined.shape, bool)
    bridge_count = 0
    if island_count and need_connect:
        if p.islands == ISLANDS_BRIDGE:
            bridges, bridge_count = compute_bridges(combined, seed, p.bridge_width_mm * ppm)
            bridges &= (outer > 0)
            combined[bridges] = 255
        elif p.islands == ISLANDS_REMOVE:
            combined[islands] = 0

    # ---- 7) Dünne Stellen verstärken
    if p.fix_thin:
        r = p.min_line_mm * ppm / 2
        opened = cv2.morphologyEx(combined, cv2.MORPH_OPEN, disk(r))
        thin_now = cv2.subtract(combined, opened)
        thin_now = remove_small(thin_now, 2)
        if thin_now.any():
            grow = dilate(thin_now, r)
            combined = cv2.bitwise_or(combined, cv2.bitwise_and(grow, outer))

    # ---- 8) Aufhängung
    if p.frame_shape != FRAME_NONE and p.hang != HANG_NONE:
        combined, ring, outer = apply_hanging(p, ppm, combined, ring, outer, top, w, h_body, warnings)

    combined = fix_diagonals(combined)

    # ---- 9) Analyse
    thin = np.zeros(combined.shape, bool)
    narrow = np.zeros(combined.shape, bool)
    thin_count = narrow_count = 0
    if analyse:
        r = p.min_line_mm * ppm / 2
        if r >= 0.75:
            opened = cv2.morphologyEx(combined, cv2.MORPH_OPEN, disk(r))
            t = cv2.subtract(combined, opened)
            # Spitzen (z. B. Baumwipfel) sind harmlos -> nur größere dünne Bereiche melden
            t = remove_small(t, max(2, 2.0 * (p.min_line_mm * ppm) ** 2))
            thin = t > 0
            thin_count = count_blobs(thin)
        rg = p.min_gap_mm * ppm / 2
        if rg >= 0.75:
            closed = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, disk(rg))
            nn = cv2.bitwise_and(cv2.subtract(closed, combined), outer)
            # spitze Winkel an Verbindungsstellen sind harmlos -> nur größere Bereiche melden
            nn = remove_small(nn, max(2, 2.0 * (p.min_gap_mm * ppm) ** 2))
            narrow = nn > 0
            narrow_count = count_blobs(narrow)

    loose_after = count_blobs(find_islands(combined, ring > 0 if p.frame_shape != FRAME_NONE else None))

    if p.frame_shape == FRAME_NONE and loose_after and need_connect:
        warnings.append(T("Ohne Rahmen besteht das Motiv aus mehreren losen Teilen."))
    bed_ok_a = p.width_mm <= p.bed_x_mm and p.height_mm <= p.bed_y_mm
    bed_ok_b = p.width_mm <= p.bed_y_mm and p.height_mm <= p.bed_x_mm
    if not (bed_ok_a or bed_ok_b):
        warnings.append(T("Größer als das Druckbett – beim Export in Teile aufteilen."))

    return Result(ppm=ppm, mask=combined, frame_mask=ring, outer_mask=outer, islands=islands,
                  bridges=bridges, thin=thin, narrow=narrow, island_count=island_count,
                  bridge_count=bridge_count, thin_count=thin_count, narrow_count=narrow_count,
                  loose_after=loose_after if need_connect else 0, warnings=warnings,
                  threshold_used=threshold_used, art_free=art_free, inner_mask=content_area)


def apply_hanging(p, ppm, combined, ring, outer, top, w, h_body, warnings):
    d = p.hang_hole_mm * ppm
    fw = p.frame_width_mm * ppm
    holes = np.zeros_like(combined)
    if p.hang == HANG_HOLES:
        if p.frame_width_mm < p.hang_hole_mm + 2.0:
            warnings.append(T("Rahmen zu schmal für {d} mm Löcher (mind. {m} mm).",
                              d=f"{p.hang_hole_mm:.0f}", m=f"{p.hang_hole_mm + 2:.0f}"))
        # Position: in der Mitte des Rahmenstegs, oben links/rechts
        if p.frame_shape == FRAME_CIRCLE:
            cx = w / 2
            cy = top + fw / 2
            pts = [(cx, cy)]
        else:
            off = fw / 2
            if p.frame_shape == FRAME_ROUNDED:
                off = max(off, p.corner_radius_mm * ppm * 0.293 + fw / 2 * 0.707)
            pts = [(off, top + off), (w - 1 - off, top + off)]
            if p.frame_shape == FRAME_HEXAGON:
                pts = [(w / 2, top + fw * 0.6)]
        for cx, cy in pts:
            cv2.circle(holes, (int(round(cx * 16)), int(round(cy * 16))), int(round(d / 2 * 16)), 255, -1,
                       cv2.LINE_8, 4)
        combined = cv2.subtract(combined, holes)
        ring = cv2.subtract(ring, holes)
        outer = cv2.subtract(outer, holes)
    elif p.hang == HANG_TAB:
        if p.frame_width_mm < 4:
            warnings.append(T("Für die Aufhängeöse sollte der Rahmen mind. 4 mm breit sein."))
        tab = np.zeros_like(combined)
        cx = w / 2
        rr = d / 2 + 3.0 * ppm
        cy = top - (d / 2 + 0.5 * ppm) + rr * 0.15
        cv2.circle(tab, (int(round(cx * 16)), int(round(cy * 16))), int(round(rr * 16)), 255, -1, cv2.LINE_8, 4)
        # Steg reicht bis tief in den Rahmen, damit die Öse fest verbunden ist
        cv2.rectangle(tab, (int(round(cx - rr)), int(round(cy))), (int(round(cx + rr)), int(round(top + fw * 0.8))),
                      255, -1)
        cv2.circle(holes, (int(round(cx * 16)), int(round(cy * 16))), int(round(d / 2 * 16)), 255, -1,
                   cv2.LINE_8, 4)
        tab = cv2.subtract(tab, holes)
        combined = cv2.bitwise_or(combined, tab)
        ring = cv2.bitwise_or(ring, tab)
        outer = cv2.bitwise_or(outer, tab)
    return combined, ring, outer


# ---------------------------------------------------------------------------
# Darstellung
# ---------------------------------------------------------------------------

def render_wall(res: Result, p: Params, show_problems: bool, view: str = "wall") -> np.ndarray:
    """Erzeugt ein BGR-Vorschaubild. view: 'wall' (wie an der Wand), 'mask' (S/W)."""
    m = res.mask
    h, w = m.shape
    pad = int(max(w, h) * 0.06)
    wall = np.array(hex_to_bgr(p.color_wall), np.uint8)
    art_c = np.array(hex_to_bgr(p.color_art), np.float32)
    back_c = np.array(hex_to_bgr(p.color_back), np.float32)

    if view == "mask":
        img = np.full((h, w, 3), 255, np.uint8)
        img[res.outer_mask == 0] = (225, 225, 225)
        img[m > 0] = 0
        canvas = cv2.copyMakeBorder(img, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=(225, 225, 225))
    else:
        canvas = np.empty((h + 2 * pad, w + 2 * pad, 3), np.float32)
        canvas[:] = wall
        # leichte Wandstruktur / Verlauf
        yy = np.linspace(-1, 1, canvas.shape[0], dtype=np.float32)[:, None]
        xx = np.linspace(-1, 1, canvas.shape[1], dtype=np.float32)[None, :]
        vign = 1.0 - 0.06 * (xx * xx + yy * yy)
        canvas *= vign[..., None]
        body = m.copy()
        if p.backplate:
            body = cv2.bitwise_or(body, res.outer_mask)
        big = np.zeros(canvas.shape[:2], np.uint8)
        big[pad:pad + h, pad:pad + w] = body
        # Schatten
        sigma = max(1.5, max(w, h) / 220)
        off = int(round(sigma * 1.2))
        shadow = cv2.GaussianBlur(big, (0, 0), sigma).astype(np.float32) / 255.0
        shadow = np.roll(np.roll(shadow, off, 0), off, 1)
        canvas *= (1.0 - 0.45 * shadow)[..., None]
        region = canvas[pad:pad + h, pad:pad + w]
        if p.backplate:
            ob = res.outer_mask > 0
            region[ob] = back_c
        sel = m > 0
        # leichte Kantenaufhellung für Plastizität
        edge = cv2.morphologyEx(m, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)) > 0
        region[sel] = art_c
        hl = np.clip(art_c + 40, 0, 255)
        e2 = edge & sel
        region[e2] = region[e2] * 0.5 + hl * 0.5
        canvas = np.clip(canvas, 0, 255).astype(np.uint8)

    if show_problems:
        region = canvas[pad:pad + h, pad:pad + w]
        overlay_problem(region, res, p)
    return canvas


_wall_cache: dict = {}


def _wall(H: int, W: int, color: str) -> np.ndarray:
    """Wandfläche mit leichter Vignette (zwischengespeichert)."""
    key = (H, W, color)
    img = _wall_cache.get(key)
    if img is None:
        if len(_wall_cache) > 6:
            _wall_cache.clear()
        wall = np.array(hex_to_bgr(color), np.float32)
        yy = np.linspace(-1, 1, H, dtype=np.float32)[:, None]
        xx = np.linspace(-1, 1, W, dtype=np.float32)[None, :]
        vign = 1.0 - 0.06 * (xx * xx + yy * yy)
        img = np.clip(wall[None, None, :] * vign[..., None], 0, 255).astype(np.uint8)
        _wall_cache[key] = img
    return img


def _shadow(mask_big: np.ndarray, sigma: float, off: int) -> np.ndarray:
    sh = cv2.GaussianBlur(mask_big, (0, 0), sigma)
    if off:
        sh = cv2.warpAffine(sh, np.float32([[1, 0, off], [0, 1, off]]), (sh.shape[1], sh.shape[0]))
    return sh


def render_layers(res: Result, p: Params, show_problems: bool, view: str = "wall") -> dict:
    """Vorschau in zwei Ebenen, damit die Grafikkarte das Motiv frei verschieben kann:

    base – BGR: Wand, Rückplatte, Rahmen (+ Schatten)
    art  – BGRA (transparent): Motiv mit eigenem Schatten und Problem-Markierungen;
           außerhalb der Innenfläche liegt das unbeschnittene Motiv (wird in der Anzeige weggeschnitten)
    polys – Umriss der Innenfläche (Bildpixel) zum Beschneiden
    """
    m = res.mask > 0
    h, w = m.shape
    pad = int(max(w, h) * 0.06)
    H, W = h + 2 * pad, w + 2 * pad
    inner = res.inner_mask > 0 if res.inner_mask is not None else np.ones_like(m)
    free = res.art_free > 0 if res.art_free is not None else m
    art_m = np.where(inner, m, free)
    frame_m = m & ~inner
    outer = res.outer_mask > 0
    art_c = np.array(hex_to_bgr(p.color_art), np.uint8)
    hl = np.clip(art_c.astype(np.int16) + 40, 0, 255).astype(np.uint8)
    k3 = np.ones((3, 3), np.uint8)
    sl = (slice(pad, pad + h), slice(pad, pad + w))
    art = np.zeros((H, W, 4), np.uint8)
    a = art[sl]

    if view == "mask":
        base = np.empty((H, W, 3), np.uint8)
        base[:] = (22, 19, 18)
        reg = base[sl]
        reg[outer] = 255
        reg[frame_m] = 0
        a[art_m] = (0, 0, 0, 255)
    else:
        base = _wall(H, W, p.color_wall).copy()
        sigma = max(1.5, max(w, h) / 220)
        off = int(round(sigma * 1.2))
        body = frame_m | outer if p.backplate else frame_m
        big = np.zeros((H, W), np.uint8)
        big[sl][body] = 255
        f = 255 - (_shadow(big, sigma, off).astype(np.uint16) * 115 // 255)
        base = (base.astype(np.uint16) * f[..., None] // 255).astype(np.uint8)
        reg = base[sl]
        if p.backplate:
            reg[outer] = hex_to_bgr(p.color_back)
        reg[frame_m] = art_c
        e = (cv2.morphologyEx(frame_m.astype(np.uint8), cv2.MORPH_GRADIENT, k3) > 0) & frame_m
        reg[e] = (reg[e].astype(np.uint16) + hl) // 2
        # Motiv-Ebene: eigener Schatten + Farbe
        big[:] = 0
        big[sl][art_m] = 255
        art[..., 3] = (_shadow(big, sigma, off).astype(np.uint16) * 115 // 255).astype(np.uint8)
        a[art_m] = (*art_c, 255)
        e = (cv2.morphologyEx(art_m.astype(np.uint8), cv2.MORPH_GRADIENT, k3) > 0) & art_m
        a[e, :3] = ((a[e, :3].astype(np.uint16) + hl) // 2).astype(np.uint8)

    if show_problems:
        def tint(mask, color, alpha=0.8, grow=0):
            if mask is None or not mask.any():
                return
            mm = mask
            if grow:
                mm = cv2.dilate(mask.astype(np.uint8), disk(grow)) > 0
            col = np.array(color, np.float32)
            a[mm, :3] = (a[mm, :3] * (1 - alpha) + col * alpha).astype(np.uint8)
            a[mm, 3] = 255
        g = max(1, int(res.ppm * 0.4))
        if not p.backplate:
            if p.islands == ISLANDS_KEEP:
                tint(res.islands, (58, 69, 255), 0.9)
            tint(res.bridges, (255, 132, 10), 0.95)
        tint(res.thin, (10, 159, 255), 0.9, g)
        tint(res.narrow, (242, 90, 191), 0.85, g)

    cs, _ = cv2.findContours(inner.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    polys = [cv2.approxPolyDP(c, 0.6, True).reshape(-1, 2).astype(np.float64) + pad for c in cs if len(c) >= 3]
    return {"base": base, "art": art, "pad": pad, "polys": polys}


def overlay_problem(region: np.ndarray, res: Result, p: Params):
    def tint(mask, color, alpha=0.75, grow=0):
        if not mask.any():
            return
        mm = mask
        if grow:
            mm = cv2.dilate(mask.astype(np.uint8), disk(grow)) > 0
        region[mm] = (region[mm] * (1 - alpha) + np.array(color) * alpha).astype(np.uint8)

    g = max(1, int(res.ppm * 0.4))
    if not p.backplate:
        if p.islands == ISLANDS_KEEP:
            tint(res.islands, (40, 40, 230), 0.85)          # rot
        tint(res.bridges, (230, 140, 20), 0.9)               # blau
    tint(res.thin, (0, 150, 255), 0.85, g)                   # orange
    tint(res.narrow, (200, 60, 200), 0.75, g)                # lila


def content_bbox(gray: np.ndarray, invert: bool = False):
    """Rechteck um das eigentliche Motiv (ohne leere Ränder) oder None."""
    h, w = gray.shape
    t = otsu_threshold(gray)
    ink = (gray > t) if invert else (gray < t)
    ink = remove_small(np.where(ink, 255, 0).astype(np.uint8), max(4, h * w * 0.00002))
    pts = cv2.findNonZero(ink)
    if pts is None:
        return None
    x, y, bw, bh = cv2.boundingRect(pts)
    m = int(round(max(w, h) * 0.02))
    x0, y0 = max(0, x - m), max(0, y - m)
    x1, y1 = min(w, x + bw + m), min(h, y + bh + m)
    if (x1 - x0) > 0.94 * w and (y1 - y0) > 0.94 * h:
        return None
    if (x1 - x0) < 8 or (y1 - y0) < 8:
        return None
    return [int(x0), int(y0), int(x1), int(y1)]


def warp_color(src_bgr: np.ndarray, p: Params, ppm: float) -> np.ndarray:
    """Farbiges Originalbild im Ausgaberaum (zum Durchscheinen-Lassen)."""
    w, h, top = _sizes(p, ppm)
    sh, sw = src_bgr.shape[:2]
    M = motif_transform(p, ppm, sw, sh, top, w, h - top)
    scale = math.hypot(M[0, 0], M[1, 0])
    img = src_bgr
    if scale < 0.7:
        f = scale / 0.7
        nw, nh = max(2, int(round(sw * f))), max(2, int(round(sh * f)))
        img = cv2.resize(src_bgr, (nw, nh), interpolation=cv2.INTER_AREA)
        M = M.copy()
        M[:, 0] /= nw / sw
        M[:, 1] /= nh / sh
    return cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT,
                          borderValue=(255, 255, 255))
