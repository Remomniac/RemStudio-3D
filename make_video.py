"""Renders the RemStudio 3D launch video (English, 1920×1080, H.264) from the real app code.

All visuals come from the built-in sample image and the real processing pipeline (bridges, 3D meshes),
plus the README screenshots in docs/images/ (run make_screenshots.py first).

Usage:   .venv\\Scripts\\python.exe make_video.py                     # full video -> RemStudio3D-launch.mp4
         .venv\\Scripts\\python.exe make_video.py --preview 2 7.5 12  # single frames as PNG (for checking)
         .venv\\Scripts\\python.exe make_video.py --ss 1 --fps 24     # faster draft
Needs:   .venv\\Scripts\\python.exe -m pip install imageio-ffmpeg     (ships its own ffmpeg)
A small helper window appears briefly while rendering (needed for OpenGL) – don't close it.
"""
import argparse
import math
import os
import subprocess
import sys
import time
from types import SimpleNamespace

os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
os.environ["QT_FONT_DPI"] = "96"

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

import cv2  # noqa: E402
import numpy as np  # noqa: E402
from PySide6.QtCore import QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import (QColor, QFont, QFontDatabase, QFontMetricsF, QImage, QPainter, QPainterPath,  # noqa: E402
                           QPen)
from PySide6.QtWidgets import QApplication  # noqa: E402

W, H = 1920, 1080
BG = QColor("#0c0d10")
INK = QColor("#ececf0")
ORANGE = QColor("#f97316")
TEXT2 = QColor("#9a9ea6")
LEFT = 120                       # left text column
VIS = QRectF(700, 40, 1180, 1000)  # visual area (right)

# ------------------------------------------------------------------ timeline (seconds)
S1, S2, S3, S4, S5, S6, END, TOTAL = 0.0, 5.0, 10.0, 15.5, 21.5, 28.5, 34.0, 39.0
CHAPTERS = [(S1, S2), (S2, S3), (S3, S4), (S4, S5), (S5, S6), (S6, END)]


# ------------------------------------------------------------------ easing
def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def seg(t, a, b):
    return clamp((t - a) / (b - a)) if b > a else float(t >= b)


def out_cubic(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def in_cubic(x):
    x = clamp(x)
    return x ** 3


def in_out_cubic(x):
    x = clamp(x)
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def out_back(x, s=1.5):
    x = clamp(x)
    return 1 + (s + 1) * (x - 1) ** 3 + s * (x - 1) ** 2


def lerp(a, b, x):
    return a + (b - a) * x


# ------------------------------------------------------------------ fonts
_fams = None


def font(px, weight=QFont.Weight.Normal, kind="display", spacing=0.0):
    global _fams
    if _fams is None:
        _fams = set(QFontDatabase.families())
    names = {"display": ("Segoe UI Variable Display", "Segoe UI"),
             "text": ("Segoe UI Variable Text", "Segoe UI"),
             "mono": ("Cascadia Mono", "Cascadia Code", "Consolas")}[kind]
    f = QFont(next((n for n in names if n in _fams), "Arial"))
    f.setPixelSize(int(px))
    f.setWeight(weight)
    if spacing:
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
    return f


F_EYEBROW = None


def init_fonts():
    global F_EYEBROW, F_HEAD, F_SUB, F_MONO, F_LIST
    F_EYEBROW = font(20, QFont.Weight.DemiBold, "mono", 3)
    F_HEAD = font(74, QFont.Weight.DemiBold, "display", -1.2)
    F_SUB = font(29, QFont.Weight.Normal, "text")
    F_MONO = font(21, QFont.Weight.Normal, "mono", 1.5)
    F_LIST = font(38, QFont.Weight.DemiBold, "display", -0.5)


def with_alpha(c: QColor, a: float) -> QColor:
    c = QColor(c)
    c.setAlphaF(clamp(a) * c.alphaF())
    return c


# ------------------------------------------------------------------ images
def np_to_qimage(rgba: np.ndarray, premultiplied=False) -> QImage:
    rgba = np.ascontiguousarray(rgba)
    fmt = QImage.Format.Format_RGBA8888_Premultiplied if premultiplied else QImage.Format.Format_RGBA8888
    return QImage(rgba.data, rgba.shape[1], rgba.shape[0], 4 * rgba.shape[1], fmt).copy()


def mask_image(mask: np.ndarray, color: QColor) -> QImage:
    a = mask.astype(np.uint8) * 255
    rgba = np.zeros(mask.shape + (4,), np.uint8)
    rgba[..., 0], rgba[..., 1], rgba[..., 2], rgba[..., 3] = color.red(), color.green(), color.blue(), a
    return np_to_qimage(rgba)


def fit_rect(w, h, box: QRectF) -> QRectF:
    s = min(box.width() / w, box.height() / h)
    return QRectF(box.center().x() - w * s / 2, box.center().y() - h * s / 2, w * s, h * s)


def scaled_rect(r: QRectF, s: float, origin: QPointF | None = None) -> QRectF:
    o = origin or r.center()
    return QRectF(o.x() + (r.x() - o.x()) * s, o.y() + (r.y() - o.y()) * s, r.width() * s, r.height() * s)


# ------------------------------------------------------------------ 3D renderer
class Renderer3D:
    """Offscreen-ish pyqtgraph renderer that returns premultiplied QImages with alpha."""

    def __init__(self, ss=2, fov=26):
        import pyqtgraph.opengl as gl
        from pyqtgraph import Vector
        self.gl, self.Vector, self.ss = gl, Vector, ss
        self.view = gl.GLViewWidget()
        self.view.setWindowTitle("RemStudio 3D – rendering video …")
        self.view.resize(320, 180)
        self.view.move(10, 10)
        self.view.show()
        self.view.opts["fov"] = fov
        self.items = []
        self.key = None

    def set_parts(self, key, parts, zscale=1.0, zclip=None):
        """parts: list of SimpleNamespace(v, f, c). Rebuilds items only when key changes."""
        gl = self.gl
        if key != self.key or zclip is not None:
            for it in self.items:
                self.view.removeItem(it)
            self.items = []
            for prt in parts:
                v = prt.v if zclip is None else np.concatenate([prt.v[:, :2], np.minimum(prt.v[:, 2:], zclip)], 1)
                md = gl.MeshData(vertexes=v, faces=prt.f, faceColors=prt.c)
                it = gl.GLMeshItem(meshdata=md, smooth=False, shader=None, glOptions="opaque", computeNormals=False)
                self.view.addItem(it)
                self.items.append(it)
            self.key = key if zclip is None else None
        for it in self.items:
            it.resetTransform()
            it.scale(1, 1, max(zscale, 0.001))

    def render(self, w, h, elev, azim, dist, center=(0, 0, 0)) -> QImage:
        ss = self.ss
        self.view.opts["center"] = self.Vector(*center)
        self.view.setCameraPosition(distance=dist, elevation=elev, azimuth=azim)
        res = []
        for bg in ((0, 0, 0), (255, 255, 255)):
            self.view.setBackgroundColor(bg)
            arr = self.view.renderToArray((w * ss, h * ss))           # (h, w, 4) BGRA
            res.append(arr[:, :, [2, 1, 0]].astype(np.float32))
        b, wh = res
        alpha = np.clip(1.0 - (wh - b).mean(2) / 255.0, 0, 1)
        if ss > 1:  # box-filter downsample (premultiplied → correct edges)
            b = b.reshape(h, ss, w, ss, 3).mean((1, 3))
            alpha = alpha.reshape(h, ss, w, ss).mean((1, 3))
        rgba = np.dstack([np.minimum(b, alpha[..., None] * 255), alpha * 255]).astype(np.uint8)
        return np_to_qimage(rgba, premultiplied=True)


# ------------------------------------------------------------------ the drawing (vector version of samples.py)
def demo_strokes():
    """Strokes of the sample image in its 1200×1200 pixel space: (kind, points, width, t0, t1)."""
    out = []
    m1 = [(0, 900), (260, 520), (400, 700), (600, 380), (900, 860), (1200, 640)]
    out.append(("line", m1, 16, 0.15, 1.35))
    hill = [(x, 980 + 40 * math.sin(x / 140.0)) for x in range(0, 1201, 20)]
    out.append(("line", hill, 14, 0.45, 1.45))
    c, r = (850, 330), 120
    circ = [(c[0] + r * math.cos(math.radians(a - 90)), c[1] + r * math.sin(math.radians(a - 90)))
            for a in range(0, 361, 6)]
    out.append(("line", circ, 14, 0.9, 1.7))
    for i in range(12):
        a = math.radians(i * 30 + 15)
        p1 = (c[0] + 155 * math.cos(a), c[1] + 155 * math.sin(a))
        p2 = (c[0] + 215 * math.cos(a), c[1] + 215 * math.sin(a))
        k = (i * 5) % 12  # scattered order looks more hand-made than a sweep
        out.append(("line", [p1, p2], 14, 1.3 + k * 0.045, 1.55 + k * 0.045))
    snow = [(530, 480), (600, 380), (670, 490), (630, 470), (600, 500), (565, 465)]
    out.append(("fill", snow, 0, 1.55, 1.85))
    for j, (x, y, s) in enumerate(((180, 1080, 1.0), (300, 1100, 0.8), (1000, 1070, 1.1))):
        tri = [(x, y - 260 * s), (x - 80 * s, y - 40 * s), (x + 80 * s, y - 40 * s)]
        trunk = [(x - 14 * s, y - 40 * s), (x + 14 * s, y - 40 * s), (x + 14 * s, y), (x - 14 * s, y)]
        out.append(("tree", (tri, trunk, (x, y)), 0, 1.75 + j * 0.12, 2.25 + j * 0.12))
    for j, (x, y, s) in enumerate(((300, 250, 1.0), (390, 200, 0.8), (450, 300, 0.7))):
        for dx in (-30 * s, 30 * s):
            arc = [(x + dx + 30 * s * math.cos(math.radians(a)), y + 18 * s * math.sin(math.radians(a)))
                   for a in range(200, 341, 10)]
            out.append(("line", arc, 9, 2.0 + j * 0.1 + (0.06 if dx > 0 else 0), 2.3 + j * 0.1 + (0.06 if dx > 0 else 0)))
    return out


def partial_polyline(pts, frac):
    if frac <= 0:
        return []
    seglens = [math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    total, goal, acc = sum(seglens), sum(seglens) * frac, 0.0
    out = [pts[0]]
    for i, L in enumerate(seglens):
        if acc + L >= goal:
            u = (goal - acc) / L if L else 1
            out.append((lerp(pts[i][0], pts[i + 1][0], u), lerp(pts[i][1], pts[i + 1][1], u)))
            return out
        out.append(pts[i + 1])
        acc += L
    return out


# ------------------------------------------------------------------ main
def main() -> int:
    ap = argparse.ArgumentParser(description="Render the RemStudio 3D launch video")
    ap.add_argument("--preview", nargs="*", type=float, help="only render these times (s) as PNG")
    ap.add_argument("--ss", type=int, default=2, help="3D supersampling (1 = fast draft)")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--crf", type=int, default=18)
    ap.add_argument("--out", default=os.path.join(ROOT, "RemStudio3D-launch.mp4"))
    args = ap.parse_args()

    app = QApplication.instance() or QApplication(sys.argv)
    init_fonts()
    from remstudio import processing as proc, mesh as meshmod
    from remstudio.viewer3d import _shade
    from remstudio.samples import demo_image

    t_start = time.time()
    # ---------------- real data from the pipeline
    demo = demo_image()
    gray = cv2.cvtColor(demo, cv2.COLOR_BGR2GRAY)
    zeros = np.zeros(gray.shape, np.uint8)
    base = proc.Params()
    PPM = 6.0
    res = proc.process(gray, zeros, base, PPM, analyse=True)
    n_islands, n_bridges = res.island_count, res.bridge_count
    frame_m = res.frame_mask > 0
    bridges_m = res.bridges
    art_m = (res.mask > 0) & ~frame_m & ~bridges_m
    islands_m = res.islands & art_m
    mh, mw = art_m.shape

    def parts_for(p: proc.Params, with_plate: bool, art_color="#f97316", plate_color="#f4f4f5"):
        p = p.copy()
        p.backplate = with_plate
        r = proc.process(gray, zeros, p, PPM)
        ms = meshmod.build_meshes(r, p, simplify_px=0.5)
        lst = [(ms["motiv"], art_color)] + ([(ms["rueckplatte"], plate_color)] if "rueckplatte" in ms else [])
        allv = np.concatenate([m.vertices for m, _ in lst])
        lo, hi = allv.min(0), allv.max(0)
        ctr = np.array([(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2]], np.float32)
        out = []
        for m, col in lst:
            v = (m.vertices - ctr).astype(np.float32)
            f = m.faces.astype(np.int32)
            out.append(SimpleNamespace(v=v, f=f, c=_shade(v, f, col)))
        return out, float(hi[2] - lo[2])

    shapes = [(proc.FRAME_RECT, "Rectangle"), (proc.FRAME_ROUNDED, "Rounded"), (proc.FRAME_CIRCLE, "Circle & oval"),
              (proc.FRAME_HEXAGON, "Hexagon"), (proc.FRAME_NONE, "No frame")]
    shape_parts = {}
    for s, _ in shapes:
        q = base.copy()
        q.frame_shape = s
        shape_parts[s] = parts_for(q, False)[0]
    plate_parts, z_top = parts_for(base, True)
    plate_z = base.backplate_mm
    LAYER = 0.2
    n_layers = int(round(z_top / LAYER))
    print(f"data ready ({time.time() - t_start:.1f}s): islands={n_islands} bridges={n_bridges} "
          f"height={z_top:.2f}mm layers={n_layers}")

    r3d = Renderer3D(ss=args.ss)
    RW, RH = int(VIS.width()), int(VIS.height())
    DIST = 640.0

    def render3d(key, parts, elev, azim, zscale=1.0, zclip=None, dist=DIST):
        r3d.set_parts(key, parts, zscale, zclip)
        return r3d.render(RW, RH, elev, azim, dist, center=(0, 0, 0))

    # Where does the flat model sit on screen (top view)? -> 2D scenes use exactly this rectangle
    top = render3d("rect", shape_parts[proc.FRAME_RECT], 89.9, -90, zscale=0.01)
    top_rgba = top.convertToFormat(QImage.Format.Format_RGBA8888)  # keep alive while numpy reads it (F-029)
    a = np.frombuffer(top_rgba.constBits(), np.uint8).reshape(RH, RW, 4)[..., 3].copy()
    ys, xs = np.nonzero(a > 40)
    MR = QRectF(VIS.x() + xs.min(), VIS.y() + ys.min(), xs.max() - xs.min() + 1, ys.max() - ys.min() + 1)

    # 2D layers (mask space -> MR)
    img_art = mask_image(art_m, INK)
    img_frame = mask_image(frame_m, INK)
    img_bridges = mask_image(bridges_m, ORANGE)
    img_islands = mask_image(islands_m, ORANGE)
    n_cc, _lab, _st, cents = cv2.connectedComponentsWithStats(bridges_m.astype(np.uint8))
    bridge_pts = sorted([tuple(c) for c in cents[1:]], key=lambda c: (c[0] + c[1] * 0.3))
    # map sample-image coordinates onto the motif inside the frame
    ys_i, xs_i = np.nonzero(gray < 128)
    ys_a, xs_a = np.nonzero(art_m | islands_m)
    sx = (xs_a.max() - xs_a.min()) / (xs_i.max() - xs_i.min())
    sy = (ys_a.max() - ys_a.min()) / (ys_i.max() - ys_i.min())
    k_mask = MR.width() / mw

    def demo_to_screen(x, y):
        mx = xs_a.min() + (x - xs_i.min()) * sx
        my = ys_a.min() + (y - ys_i.min()) * sy
        return QPointF(MR.x() + mx * k_mask, MR.y() + my * k_mask)

    def mask_to_screen(x, y):
        return QPointF(MR.x() + x * k_mask, MR.y() + y * k_mask)

    strokes = demo_strokes()
    stroke_scale = sx * k_mask

    shots = {n: QImage(os.path.join(ROOT, "docs", "images", n)) for n in ("editor.png", "main.png")}
    logo = QImage(os.path.join(ROOT, "icon.png"))
    for n, im in shots.items():
        if im.isNull():
            print(f"!! docs/images/{n} missing – run make_screenshots.py first")
            return 1

    # ------------------------------------------------------------------ drawing helpers
    def text_block(p, t, t_in, t_out, eyebrow, lines, sub=None, top=372):
        e_eb = out_cubic(seg(t, t_in, t_in + 0.5)) * (1 - in_cubic(seg(t, t_out - 0.45, t_out - 0.1)))
        p.setFont(F_EYEBROW)
        p.setPen(with_alpha(ORANGE, e_eb))
        p.drawText(QPointF(LEFT + (1 - e_eb) * -16, top), eyebrow)
        fm = QFontMetricsF(F_HEAD)
        lh = 84
        p.setFont(F_HEAD)
        k = 0
        y0 = top + 30
        for li, line in enumerate(lines):
            ly = y0 + li * lh
            p.save()
            p.setClipRect(QRectF(LEFT - 10, ly - 4, 660, lh + 24))  # room for descenders
            x = LEFT
            for w in line.split(" "):
                d_in = t_in + 0.1 + k * 0.055
                d_out = t_out - 0.5 + k * 0.03
                e_i = out_cubic(seg(t, d_in, d_in + 0.6))
                e_o = in_cubic(seg(t, d_out, d_out + 0.35))
                p.setPen(with_alpha(QColor("#ffffff"), e_i * (1 - e_o)))
                p.drawText(QPointF(x, ly + fm.ascent() + (1 - e_i) * lh * 1.15 - e_o * lh * 1.15), w)
                x += fm.horizontalAdvance(w + " ")
                k += 1
            p.restore()
        sub_y = y0 + len(lines) * lh + 26
        if sub:
            e_s = out_cubic(seg(t, t_in + 0.35, t_in + 0.95)) * (1 - in_cubic(seg(t, t_out - 0.4, t_out - 0.1)))
            p.setFont(F_SUB)
            p.setPen(with_alpha(TEXT2, e_s))
            p.drawText(QRectF(LEFT, sub_y + (1 - e_s) * 14, 540, 140),
                       Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap, sub)
        return sub_y

    def progress_bar(p, t):
        vis = 1 - seg(t, END - 0.2, END + 0.3)
        vis *= seg(t, 0.3, 0.9)
        if vis <= 0:
            return
        x, y, wseg, gap = LEFT, 996, 74, 8
        p.setPen(Qt.PenStyle.NoPen)
        for i, (a, b) in enumerate(CHAPTERS):
            r = QRectF(x + i * (wseg + gap), y, wseg, 3)
            p.setBrush(with_alpha(QColor("#ffffff"), 0.14 * vis))
            p.drawRoundedRect(r, 1.5, 1.5)
            f = seg(t, a, b)
            if f > 0:
                p.setBrush(with_alpha(ORANGE if f < 1 else QColor("#ffffff"), (1.0 if f < 1 else 0.45) * vis))
                p.drawRoundedRect(QRectF(r.x(), r.y(), r.width() * f, 3), 1.5, 1.5)
        p.setFont(F_MONO)
        idx = next((i for i, (a, b) in enumerate(CHAPTERS) if a <= t < b), len(CHAPTERS) - 1)
        p.setPen(with_alpha(TEXT2, 0.8 * vis))
        p.drawText(QPointF(x + 6 * (wseg + gap) + 10, y + 7), f"{idx + 1:02d}/06")

    def draw_layer(p, img, alpha=1.0, rect=None):
        if alpha <= 0:
            return
        p.setOpacity(clamp(alpha))
        p.drawImage(rect or MR, img)
        p.setOpacity(1.0)

    def ring(p, c: QPointF, r, alpha, width=2.0):
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(with_alpha(ORANGE, alpha), width))
        p.drawEllipse(c, r, r)

    def draw_shot(p, img, t_in, t, scale=1.0, focus=None, alpha=1.0, lift=60):
        e = out_cubic(seg(t, t_in, t_in + 0.8))
        if e <= 0 or alpha <= 0:
            return None
        r = fit_rect(img.width(), img.height(), VIS.adjusted(10, 60, -10, -60))
        r = r.translated(0, (1 - e) * lift)
        if scale != 1.0 and focus is not None:
            fx = r.x() + focus[0] / img.width() * r.width()
            fy = r.y() + focus[1] / img.height() * r.height()
            r = scaled_rect(r, scale, QPointF(fx, fy))
            # move focus point towards the visual centre while zooming
            k = (scale - 1) / 0.35
            r.translate((VIS.center().x() - fx) * min(k, 1) * 0.4, (VIS.center().y() - fy) * min(k, 1) * 0.4)
        p.save()
        clip_x = VIS.x() + 50
        p.setClipRect(QRectF(clip_x, 0, W - clip_x, H))  # never over the text column
        p.setOpacity(e * alpha)
        p.drawImage(r, img)
        p.setOpacity(1.0)
        if r.x() < clip_x + 90:  # soft edge where a zoomed screenshot gets cut
            from PySide6.QtGui import QLinearGradient
            g = QLinearGradient(clip_x, 0, clip_x + 90, 0)
            g.setColorAt(0, BG)
            g.setColorAt(1, with_alpha(BG, 0))
            p.fillRect(QRectF(clip_x, 0, 90, H), g)
        p.restore()
        return r

    def img_point(r: QRectF, img: QImage, x, y):
        return QPointF(r.x() + x / img.width() * r.width(), r.y() + y / img.height() * r.height())

    # ------------------------------------------------------------------ one frame
    def frame(t: float) -> QImage:
        img = QImage(W, H, QImage.Format.Format_RGB32)
        img.fill(BG)
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        # flat background on purpose: soft gradients show visible banding after H.264 compression

        # ---------------- 01 input: the drawing draws itself
        if t < S2 + 0.8:
            lt = t - S1
            fade = 1 - seg(t, S2, S2 + 0.6)
            p.setBrush(Qt.BrushStyle.NoBrush)
            for kind, data, wd, a0, b0 in strokes:
                f = seg(lt, a0, b0)
                if f <= 0:
                    continue
                if kind == "line":
                    pts = partial_polyline(data, out_cubic(f) if len(data) > 2 else in_out_cubic(f))
                    if len(pts) < 2:
                        continue
                    path = QPainterPath(demo_to_screen(*pts[0]))
                    for q in pts[1:]:
                        path.lineTo(demo_to_screen(*q))
                    p.setPen(QPen(with_alpha(INK, fade), wd * stroke_scale, Qt.PenStyle.SolidLine,
                                  Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
                    p.drawPath(path)
                elif kind == "fill":
                    path = QPainterPath(demo_to_screen(*data[0]))
                    for q in data[1:]:
                        path.lineTo(demo_to_screen(*q))
                    path.closeSubpath()
                    p.fillPath(path, with_alpha(INK, out_cubic(f) * fade))
                else:  # tree: grows from its base
                    tri, trunk, (bx, by) = data
                    s = out_back(f, 1.8)
                    base_pt = demo_to_screen(bx, by)
                    for poly in (tri, trunk):
                        path = QPainterPath()
                        for i, q in enumerate(poly):
                            sp = demo_to_screen(*q)
                            sp = QPointF(base_pt.x() + (sp.x() - base_pt.x()) * s, base_pt.y() + (sp.y() - base_pt.y()) * s)
                            path.moveTo(sp) if i == 0 else path.lineTo(sp)
                        path.closeSubpath()
                        p.fillPath(path, with_alpha(INK, min(1, f * 3) * fade))
            # file chip under the drawing
            e = out_cubic(seg(lt, 0.5, 1.1)) * (1 - seg(t, S2 - 0.4, S2))
            if e > 0:
                p.setFont(F_MONO)
                label = "landscape.png  ·  1200 × 1200 px"
                fm = QFontMetricsF(F_MONO)
                cw = fm.horizontalAdvance(label) + 44
                r = QRectF(MR.center().x() - cw / 2, MR.bottom() + 34 + (1 - e) * 12, cw, 42)
                p.setPen(QPen(with_alpha(QColor("#ffffff"), 0.16 * e), 1.2))
                p.setBrush(with_alpha(QColor("#ffffff"), 0.04 * e))
                p.drawRoundedRect(r, 21, 21)
                p.setPen(with_alpha(TEXT2, e))
                p.drawText(r, Qt.AlignmentFlag.AlignCenter, label)
            text_block(p, t, S1 + 0.5, S2, "01 — INPUT", ["Start with", "any drawing."],
                       "Line art, comics, logos – or a photo.")

        # ---------------- 02 printability: islands + real bridges
        if S2 - 0.1 < t < S3 + 0.8:
            lt = t - S2
            out3d = 1 - seg(t, S3 + 0.05, S3 + 0.6)          # 2D fades out while 3D takes over
            draw_layer(p, img_art, seg(lt, 0.0, 0.55) * out3d)
            # frame: drawn as a stroke, then replaced by the real frame mask
            fr = out_cubic(seg(lt, 0.15, 1.0))
            if 0 < fr < 1 or (lt < 1.15 and fr >= 1):
                fwid = base.frame_width_mm * PPM * k_mask
                rr = MR.adjusted(fwid / 2, fwid / 2, -fwid / 2, -fwid / 2)
                pts = [rr.topLeft(), rr.topRight(), rr.bottomRight(), rr.bottomLeft(), rr.topLeft()]
                pts = [(q.x(), q.y()) for q in pts]
                pp = partial_polyline(pts, fr)
                path = QPainterPath(QPointF(*pp[0]))
                for q in pp[1:]:
                    path.lineTo(QPointF(*q))
                p.setPen(QPen(INK, fwid, Qt.PenStyle.SolidLine, Qt.PenCapStyle.SquareCap, Qt.PenJoinStyle.MiterJoin))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawPath(path)
            draw_layer(p, img_frame, seg(lt, 1.0, 1.15) * out3d)
            # loose parts light up …
            isl = out_cubic(seg(lt, 0.55, 1.0)) * (1 - seg(lt, 2.6, 3.2))
            draw_layer(p, img_islands, isl * out3d)
            # … then the real bridges snap in one by one
            nb = len(bridge_pts)
            shown = 0
            for i, c in enumerate(bridge_pts):
                ti = 1.2 + i * 0.075
                f = seg(lt, ti, ti + 0.5)
                if f > 0:
                    shown += 1
                    ring(p, mask_to_screen(*c), lerp(4, 46, out_cubic(f)), (1 - f) * 0.9 * out3d, 2.2)
            reveal = seg(lt, 1.2, 1.2 + nb * 0.075 + 0.15)
            if reveal > 0:
                # reveal bridges in the same order via a growing per-bridge mask
                p.save()
                clip = QPainterPath()
                for i, c in enumerate(bridge_pts):
                    if lt >= 1.2 + i * 0.075:
                        clip.addEllipse(mask_to_screen(*c), 60, 60)
                p.setClipPath(clip)
                draw_layer(p, img_bridges, out3d)
                p.restore()
            text_block(p, t, S2 + 0.3, S3, "02 — PRINTABILITY", ["Loose parts?", "Bridged."],
                       "Every floating piece gets the shortest possible bridge – automatically.")
            e = out_cubic(seg(lt, 0.9, 1.4)) * (1 - seg(t, S3 - 0.4, S3 - 0.1))
            if e > 0:
                p.setFont(F_MONO)
                y = 372 + 30 + 2 * 84 + 26 + 120
                found = int(round(n_islands * seg(lt, 0.55, 1.0)))
                p.setPen(with_alpha(TEXT2, e))
                p.drawText(QPointF(LEFT, y), f"ISLANDS  {found:02d}")
                p.setPen(with_alpha(ORANGE, e))
                p.drawText(QPointF(LEFT + 210, y), f"BRIDGES  {min(shown, n_bridges):02d}")

        # ---------------- 03 3D: tilt + extrude   /   04 frames
        if S3 < t < S5 + 0.5:
            lt = t - S3
            if t < S4:
                el = lerp(89.9, 32, in_out_cubic(seg(lt, 0.25, 2.6)))
                az = lerp(-90, -114, in_out_cubic(seg(lt, 0.25, 2.6))) + 4 * seg(lt, 2.6, S4 - S3)
                zs = lerp(0.01, 1.0, out_cubic(seg(lt, 0.55, 2.4)))
                im3 = render3d("rect", shape_parts[proc.FRAME_RECT], el, az, zscale=zs)
                draw_layer(p, im3, seg(lt, 0.0, 0.5), QRectF(VIS))
            else:
                lt4 = t - S4
                el = lerp(32, 38, in_out_cubic(seg(lt4, 0, S5 - S4)))
                az = lerp(-110, -72, seg(lt4, 0, S5 - S4 + 0.5))
                step = 1.15
                idx = min(int(lt4 / step), len(shapes) - 1)
                tr = seg(lt4 - idx * step, 0, 0.28) if idx > 0 else 1.0
                fade_out = 1 - seg(t, S5 - 0.05, S5 + 0.45)
                if tr < 1:
                    prev = shapes[idx - 1][0]
                    imp = render3d(prev, shape_parts[prev], el, az)
                    rp = scaled_rect(QRectF(VIS), lerp(1.0, 0.965, out_cubic(tr)))
                    draw_layer(p, imp, (1 - tr) * fade_out, rp)
                cur = shapes[idx][0]
                imc = render3d(cur, shape_parts[cur], el, az)
                rc = scaled_rect(QRectF(VIS), lerp(1.035, 1.0, out_cubic(tr)))
                draw_layer(p, imc, tr * fade_out, rc)
            if t < S4:
                text_block(p, t, S3 + 0.3, S4, "03 — 3D", ["Extruded.", "Framed."],
                           "A watertight STL – ready for any slicer.")
            else:
                lt4 = t - S4
                text_block(p, t, S4 + 0.2, S5, "04 — FRAMES", ["Pick a frame."], None)
                idx = min(int(lt4 / 1.15), len(shapes) - 1)
                p.setFont(F_LIST)
                fm = QFontMetricsF(F_LIST)
                for i, (_, name) in enumerate(shapes):
                    e = out_cubic(seg(lt4, 0.35 + i * 0.07, 0.95 + i * 0.07)) * (1 - in_cubic(seg(t, S5 - 0.45 + i * 0.03, S5 - 0.1 + i * 0.03)))
                    if e <= 0:
                        continue
                    y = 372 + 30 + 84 + 60 + i * 58
                    active = i == idx
                    hl = seg(lt4 - i * 1.15, 0, 0.25) if active else 0.0
                    col = QColor("#ffffff") if active else TEXT2
                    p.setPen(with_alpha(col, e * (1.0 if active else 0.55)))
                    p.drawText(QPointF(LEFT + 34 + (1 - e) * 20, y + fm.ascent()), name)
                    if active:
                        p.setPen(Qt.PenStyle.NoPen)
                        p.setBrush(with_alpha(ORANGE, e))
                        p.drawEllipse(QPointF(LEFT + 9, y + fm.ascent() * 0.62), 6 * out_back(hl), 6 * out_back(hl))

        # ---------------- 05 in the app: two UI beats
        if S5 - 0.1 < t < S6 + 0.6:
            lt = t - S5
            ed = shots["editor.png"]
            mn = shots["main.png"]
            beat2 = 3.6
            a1 = 1 - seg(lt, beat2 - 0.1, beat2 + 0.35)
            r1 = draw_shot(p, ed, 0.25, lt, alpha=a1)
            if r1 is not None and a1 > 0:
                btn = QRectF(img_point(r1, ed, 962, 131), img_point(r1, ed, 1276, 164))
                e = out_cubic(seg(lt, 1.1, 1.6)) * a1
                if e > 0:
                    p.setPen(QPen(with_alpha(ORANGE, e), 2.5))
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.drawRoundedRect(btn.adjusted(-6, -6, 6, 6), 22, 22)
                    for k in range(2):  # two soft pulses
                        f = seg(lt, 1.5 + k * 0.7, 2.3 + k * 0.7)
                        if 0 < f < 1:
                            p.setPen(QPen(with_alpha(ORANGE, (1 - f) * 0.7 * a1), 2))
                            p.drawRoundedRect(btn.adjusted(-6 - 18 * f, -6 - 18 * f, 6 + 18 * f, 6 + 18 * f), 22 + 18 * f, 22 + 18 * f)
            zoom = lerp(1.0, 1.35, in_out_cubic(seg(lt, beat2 + 0.9, beat2 + 2.3)))
            a2 = 1 - seg(t, S6 - 0.05, S6 + 0.45)
            panel = (1271, 280)  # centre of the check panel in main.png
            r2 = draw_shot(p, mn, beat2 + 0.1, lt, scale=zoom, focus=panel, alpha=a2)
            if r2 is not None:
                box = QRectF(img_point(r2, mn, 1081, 183), img_point(r2, mn, 1462, 378))
                e = out_cubic(seg(lt, beat2 + 2.1, beat2 + 2.6)) * a2
                if e > 0:
                    p.setPen(QPen(with_alpha(ORANGE, e), 2.5))
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.drawRoundedRect(box.adjusted(-8, -8, 8, 8), 20, 20)
            text_block(p, t, S5 + 0.2, S5 + beat2, "05 — IN THE APP", ["AI background", "removal."],
                       "Runs locally on your PC. No upload, no account.")
            text_block(p, t, S5 + beat2 + 0.1, S6, "05 — IN THE APP", ["Checked before", "you print."],
                       "Thin lines, narrow gaps and the print bed size.")

        # ---------------- 06 print: layer by layer
        if S6 < t < END + 0.6:
            lt = t - S6
            zc = z_top * in_out_cubic(seg(lt, 0.45, 4.1))
            zc = max(zc, 0.05)
            layer = max(1, int(math.ceil(zc / LAYER - 1e-6)))
            el = lerp(42, 30, in_out_cubic(seg(lt, 0, 5.5)))
            az = lerp(-128, -98, seg(lt, 0, 6.0))
            im6 = render3d("plate", plate_parts, el, az, zclip=round(zc, 3), dist=DIST * 1.12)
            fade = seg(lt, 0.0, 0.45) * (1 - seg(t, END - 0.1, END + 0.5))
            draw_layer(p, im6, fade, QRectF(VIS))
            sub_y = text_block(p, t, S6 + 0.2, END, "06 — PRINT", ["Print it.", "Hang it."],
                               "Two colors with a back plate – the color change height is worked out for you.")
            e = out_cubic(seg(lt, 0.5, 1.0)) * (1 - seg(t, END - 0.4, END - 0.1))
            if e > 0:
                y = sub_y + 140
                p.setFont(F_MONO)
                p.setPen(with_alpha(QColor("#ffffff"), e))
                p.drawText(QPointF(LEFT, y), f"LAYER {layer:02d} / {n_layers:02d}")
                p.setPen(with_alpha(TEXT2, e))
                p.drawText(QPointF(LEFT + 230, y), f"Z {zc:4.2f} MM")
                cc = seg(zc, plate_z, plate_z + 0.25)
                if cc > 0:
                    p.setPen(Qt.PenStyle.NoPen)
                    p.setBrush(with_alpha(ORANGE, e * cc))
                    p.drawEllipse(QPointF(LEFT + 6, y + 30), 5, 5)
                    p.setPen(with_alpha(ORANGE, e * cc))
                    p.drawText(QPointF(LEFT + 22, y + 37), f"COLOR CHANGE AT {plate_z:.2f} MM")

        # ---------------- end card
        if t >= END:
            lt = t - END
            cx = W / 2
            e_logo = out_back(seg(lt, 0.35, 1.0), 1.6)
            if e_logo > 0:
                s = 150 * lerp(0.7, 1.0, e_logo)
                p.setOpacity(clamp(seg(lt, 0.35, 0.7)))
                p.drawImage(QRectF(cx - s / 2, 250 - s / 2 + 40, s, s), logo)
                p.setOpacity(1)
            p.setFont(font(112, QFont.Weight.Bold, "display", -2))
            fm = QFontMetricsF(p.font())
            title = "RemStudio 3D"
            e = out_cubic(seg(lt, 0.55, 1.2))
            p.save()
            p.setClipRect(QRectF(0, 380, W, 140))
            p.setPen(with_alpha(QColor("#ffffff"), e))
            p.drawText(QPointF(cx - fm.horizontalAdvance(title) / 2, 380 + fm.ascent() + (1 - e) * 120), title)
            p.restore()
            p.setFont(font(36, QFont.Weight.Normal, "text"))
            fm = QFontMetricsF(p.font())
            tag = "Turn drawings into 3D-printed wall art."
            e = out_cubic(seg(lt, 0.85, 1.5))
            p.setPen(with_alpha(QColor("#c9ccd2"), e))
            p.drawText(QPointF(cx - fm.horizontalAdvance(tag) / 2, 572 + (1 - e) * 14), tag)
            chips = [("Free & open source", True), ("Windows 10 / 11", False), ("English & German", False)]
            p.setFont(font(24, QFont.Weight.DemiBold, "text"))
            fm = QFontMetricsF(p.font())
            widths = [fm.horizontalAdvance(c) + 48 for c, _ in chips]
            x = cx - (sum(widths) + 16 * (len(chips) - 1)) / 2
            for i, ((c, primary), wd) in enumerate(zip(chips, widths)):
                e = out_cubic(seg(lt, 1.1 + i * 0.1, 1.6 + i * 0.1))
                r = QRectF(x, 640 + (1 - e) * 16, wd, 52)
                if primary:
                    p.setPen(Qt.PenStyle.NoPen)
                    p.setBrush(with_alpha(ORANGE, e))
                    p.drawRoundedRect(r, 26, 26)
                    p.setPen(with_alpha(QColor("#ffffff"), e))
                else:
                    p.setPen(QPen(with_alpha(QColor("#ffffff"), 0.22 * e), 1.5))
                    p.setBrush(with_alpha(QColor("#ffffff"), 0.05 * e))
                    p.drawRoundedRect(r, 26, 26)
                    p.setPen(with_alpha(QColor("#e6e7ea"), e))
                p.drawText(r, Qt.AlignmentFlag.AlignCenter, c)
                x += wd + 16
            p.setFont(font(26, QFont.Weight.Normal, "mono", 1))
            fm = QFontMetricsF(p.font())
            url = "github.com/Remomniac/RemStudio-3D"
            e = out_cubic(seg(lt, 1.6, 2.2))
            p.setPen(with_alpha(TEXT2, e))
            p.drawText(QPointF(cx - fm.horizontalAdvance(url) / 2, 820), url)
            ul = out_cubic(seg(lt, 1.9, 2.6))
            if ul > 0:
                p.setPen(QPen(ORANGE, 2.5))
                uw = fm.horizontalAdvance(url) * ul
                p.drawLine(QPointF(cx - uw / 2, 838), QPointF(cx + uw / 2, 838))

        progress_bar(p, t)
        p.end()
        return img

    # ------------------------------------------------------------------ output
    if args.preview:
        out_dir = os.path.join(ROOT, ".preview", "video")
        os.makedirs(out_dir, exist_ok=True)
        for tt in args.preview:
            fn = os.path.join(out_dir, f"frame_{tt:05.2f}.png")
            frame(tt).save(fn)
            print("  ", fn)
        r3d.view.close()
        return 0

    import imageio_ffmpeg
    n = int(TOTAL * args.fps)
    cmd = [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(args.fps), "-i", "-", "-c:v", "libx264", "-preset", "slow",
           "-crf", str(args.crf), "-pix_fmt", "yuv420p", "-movflags", "+faststart", args.out]
    enc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0 = time.time()
    for i in range(n):
        fr = frame(i / args.fps).convertToFormat(QImage.Format.Format_RGB888)
        assert fr.bytesPerLine() == W * 3
        enc.stdin.write(bytes(fr.constBits()))
        if i % args.fps == 0:
            el = time.time() - t0
            print(f"  {i / args.fps:5.1f}s / {TOTAL:.0f}s   ({el:.0f}s elapsed)", flush=True)
        app.processEvents()
    enc.stdin.close()
    enc.wait()
    r3d.view.close()
    size = os.path.getsize(args.out) / 1e6
    print(f"done: {args.out}  {size:.1f} MB  ({time.time() - t_start:.0f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
