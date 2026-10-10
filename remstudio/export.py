"""Export: STL (einzeln / aufgeteilt), SVG und PNG."""
from __future__ import annotations

import math
import os

import cv2
import numpy as np

from . import mesh as meshmod
from . import processing as proc
from .i18n import T

PLA_DENSITY = 1.24  # g/cm³


def tile_grid(p: proc.Params) -> tuple[int, int]:
    """Anzahl Spalten/Zeilen, damit jedes Teil aufs Druckbett passt."""
    best = None
    for bx, by in ((p.bed_x_mm, p.bed_y_mm), (p.bed_y_mm, p.bed_x_mm)):
        bx = max(10.0, bx - 4)  # etwas Sicherheitsabstand
        by = max(10.0, by - 4)
        cols = max(1, math.ceil(p.width_mm / bx))
        rows = max(1, math.ceil(p.height_mm / by))
        if best is None or cols * rows < best[0] * best[1]:
            best = (cols, rows)
    return best


def fits_bed(p: proc.Params) -> bool:
    return tile_grid(p) == (1, 1)


def estimate_material(res: proc.Result, p: proc.Params) -> tuple[float, float]:
    """(Gramm, Meter Filament 1,75 mm) – grobe Schätzung bei 100 % Füllung."""
    ppm2 = res.ppm * res.ppm
    base = p.backplate_mm if p.backplate else 0.0
    vol = (res.mask > 0).sum() / ppm2 * p.art_height_mm
    if p.frame_shape != proc.FRAME_NONE and p.frame_height_mm > p.art_height_mm:
        vol += (res.frame_mask > 0).sum() / ppm2 * (p.frame_height_mm - p.art_height_mm)
    if p.backplate:
        vol += (res.outer_mask > 0).sum() / ppm2 * base
    cm3 = vol / 1000.0
    grams = cm3 * PLA_DENSITY
    meters = vol / (math.pi * 0.875 ** 2) / 1000.0
    return grams, meters


def export_all(res: proc.Result, p: proc.Params, folder: str, base_name: str, opts: dict, progress=None) -> list:
    """Schreibt die gewünschten Dateien und gibt ihre Pfade zurück.

    opts: separate (bool), combined (bool), split (bool), cols, rows, svg (bool), png (bool)
    """
    written = []
    os.makedirs(folder, exist_ok=True)

    def step(text, frac):
        if progress:
            progress(text, frac)

    cols, rows = (opts.get("cols", 1), opts.get("rows", 1)) if opts.get("split") else (1, 1)
    h, w = res.mask.shape
    xs = np.linspace(0, w, cols + 1).round().astype(int)
    ys = np.linspace(0, h, rows + 1).round().astype(int)
    n_tiles = cols * rows
    k = 0
    for r in range(rows):
        for c in range(cols):
            k += 1
            suffix = f"_teil_{r + 1}-{c + 1}" if n_tiles > 1 else ""
            step(T("Erzeuge 3D-Modell {k}/{n} …", k=k, n=n_tiles), 0.05 + 0.8 * (k - 1) / n_tiles)
            sub = _crop_result(res, ys[r], ys[r + 1], xs[c], xs[c + 1])
            parts = meshmod.build_meshes(sub, p)
            # auf Druckbett-Ursprung legen
            parts = {name: m for name, m in parts.items() if len(m.faces)}
            if not parts:
                continue
            lo = np.min([m.bounds()[0] for m in parts.values()], axis=0)
            parts = {name: m.translated(-lo[0], -lo[1], 0) for name, m in parts.items()}
            if opts.get("separate", True) or not p.backplate:
                for name, m in parts.items():
                    path = os.path.join(folder, f"{base_name}_{name}{suffix}.stl")
                    m.save_stl(path, f"{base_name} {name}")
                    written.append(path)
            if p.backplate and opts.get("combined", False):
                path = os.path.join(folder, f"{base_name}_komplett{suffix}.stl")
                meshmod.Mesh.concat(list(parts.values())).save_stl(path, f"{base_name} komplett")
                written.append(path)

    if opts.get("svg"):
        step(T("Schreibe SVG …"), 0.9)
        path = os.path.join(folder, f"{base_name}.svg")
        save_svg(res, path)
        written.append(path)
    if opts.get("png"):
        step(T("Schreibe PNG …"), 0.95)
        path = os.path.join(folder, f"{base_name}_vorlage.png")
        img = np.where(res.mask > 0, 0, 255).astype(np.uint8)
        ok, buf = cv2.imencode(".png", img)
        if ok:
            buf.tofile(path)
            written.append(path)
    step(T("Fertig"), 1.0)
    return written


def _crop_result(res: proc.Result, y0, y1, x0, x1) -> proc.Result:
    def c(a):
        return np.ascontiguousarray(a[y0:y1, x0:x1])
    return proc.Result(ppm=res.ppm, mask=c(res.mask), frame_mask=c(res.frame_mask), outer_mask=c(res.outer_mask),
                       islands=c(res.islands), bridges=c(res.bridges), thin=c(res.thin), narrow=c(res.narrow))


def save_svg(res: proc.Result, path: str):
    h_px, w_px = res.mask.shape
    w_mm, h_mm = w_px / res.ppm, h_px / res.ppm
    polys = meshmod.mask_polygons(res.mask, res.ppm, simplify_px=0.6)
    parts = []
    for item in polys:
        outer, holes = item[0], item[1]
        for ring in [outer] + holes:
            pts = " L ".join(f"{x:.3f},{h_mm - y:.3f}" for x, y in ring)
            parts.append(f"M {pts} Z")
    d = " ".join(parts)
    svg = (f'<?xml version="1.0" encoding="UTF-8"?>\n'
           f'<svg xmlns="http://www.w3.org/2000/svg" width="{w_mm:.2f}mm" height="{h_mm:.2f}mm" '
           f'viewBox="0 0 {w_mm:.3f} {h_mm:.3f}">\n'
           f'  <path d="{d}" fill="#000000" fill-rule="evenodd"/>\n</svg>\n')
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg)
