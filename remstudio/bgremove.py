"""Hintergrund entfernen: KI-Modelle (ONNX), GrabCut und Masken-Werkzeuge.

Die Masken sind uint8-Bilder: 255 = Motiv behalten, 0 = Hintergrund entfernen.
"""
from __future__ import annotations

import os
import urllib.request

import cv2
import numpy as np

MODEL_URL = "https://github.com/danielgatis/rembg/releases/download/v0.0.0/{name}.onnx"

# name -> (Anzeige-Text, Eingabegröße, Mittelwert, Standardabweichung, ungefähre Größe in MB)
MODELS = {
    "isnet-anime": ("Comic / Zeichentrick / Anime", 1024, (0.485, 0.456, 0.406), (1.0, 1.0, 1.0), 176),
    "isnet-general-use": ("Fotos / echte Personen & Objekte", 1024, (0.5, 0.5, 0.5), (1.0, 1.0, 1.0), 179),
    "u2netp": ("Schnell & klein (einfache Motive)", 320, (0.485, 0.456, 0.406), (0.229, 0.224, 0.225), 5),
}
DEFAULT_MODEL = "isnet-anime"


def models_dir() -> str:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    d = os.path.join(base, "RemStudio", "models")
    os.makedirs(d, exist_ok=True)
    return d


def model_path(name: str) -> str:
    return os.path.join(models_dir(), f"{name}.onnx")


def model_available(name: str) -> bool:
    p = model_path(name)
    return os.path.isfile(p) and os.path.getsize(p) > 1_000_000


def download_model(name: str, progress=None, cancelled=None):
    """Lädt ein Modell herunter. progress(fraction), cancelled() -> bool."""
    url = MODEL_URL.format(name=name)
    dst = model_path(name)
    tmp = dst + ".part"
    req = urllib.request.Request(url, headers={"User-Agent": "RemStudio3D"})
    with urllib.request.urlopen(req, timeout=30) as r:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        with open(tmp, "wb") as f:
            while True:
                if cancelled and cancelled():
                    raise InterruptedError("abgebrochen")
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if progress and total:
                    progress(done / total)
    if total and os.path.getsize(tmp) != total:
        os.remove(tmp)
        raise IOError("Download unvollständig")
    os.replace(tmp, dst)


_sessions: dict = {}


def _session(name: str):
    if name not in _sessions:
        import onnxruntime as ort
        opts = ort.SessionOptions()
        opts.log_severity_level = 3
        try:
            _sessions[name] = ort.InferenceSession(model_path(name), opts, providers=["CPUExecutionProvider"])
        except Exception:
            # beschädigte Datei -> löschen, damit sie neu geladen wird
            try:
                os.remove(model_path(name))
            except OSError:
                pass
            raise
    return _sessions[name]


def ai_mask(bgr: np.ndarray, name: str = DEFAULT_MODEL) -> np.ndarray:
    """Weiche Motiv-Maske (uint8 0..255) in Bildgröße."""
    _, size, mean, std, _ = MODELS[name]
    h, w = bgr.shape[:2]
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    im = cv2.resize(rgb, (size, size), interpolation=cv2.INTER_AREA if max(h, w) > size else cv2.INTER_CUBIC)
    x = im.astype(np.float32)
    x /= max(1.0, float(x.max()))
    x = (x - np.array(mean, np.float32)) / np.array(std, np.float32)
    x = x.transpose(2, 0, 1)[None].astype(np.float32)
    sess = _session(name)
    out = sess.run(None, {sess.get_inputs()[0].name: x})[0][0, 0]
    mi, ma = float(out.min()), float(out.max())
    out = (out - mi) / max(1e-6, ma - mi)
    mask = cv2.resize(out, (w, h), interpolation=cv2.INTER_LINEAR)
    return np.clip(mask * 255, 0, 255).astype(np.uint8)


def grabcut(bgr: np.ndarray, rect=None, mask: np.ndarray | None = None, keep: np.ndarray | None = None,
            remove: np.ndarray | None = None, max_side: int = 720, iters: int = 4) -> np.ndarray:
    """Kantenfolgende Segmentierung (ohne KI).

    rect: (x0, y0, x1, y1) – alles außerhalb ist sicher Hintergrund.
    mask: bisherige Maske (wird als „wahrscheinlich“ verwendet).
    keep/remove: bool-Masken mit sicheren Hinweisen (Pinselstriche)."""
    h, w = bgr.shape[:2]
    f = min(1.0, max_side / max(h, w))
    sw, sh = max(8, int(round(w * f))), max(8, int(round(h * f)))
    small = cv2.resize(bgr, (sw, sh), interpolation=cv2.INTER_AREA) if f < 1 else bgr.copy()

    def rs(m, interp=cv2.INTER_NEAREST):
        return cv2.resize(m.astype(np.uint8), (sw, sh), interpolation=interp) if f < 1 else m.astype(np.uint8)

    gc = np.full((sh, sw), cv2.GC_PR_BGD, np.uint8)
    if mask is not None:
        m = rs(mask, cv2.INTER_AREA)
        gc[m >= 128] = cv2.GC_PR_FGD
        # sehr sichere Bereiche festlegen (stabilisiert das Ergebnis)
        gc[cv2.erode((m >= 250).astype(np.uint8), np.ones((5, 5), np.uint8)) > 0] = cv2.GC_FGD
        gc[cv2.erode((m <= 5).astype(np.uint8), np.ones((9, 9), np.uint8)) > 0] = cv2.GC_BGD
    if rect is not None:
        x0, y0, x1, y1 = [int(round(v * f)) for v in rect]
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(sw, x1), min(sh, y1)
        outside = np.ones((sh, sw), bool)
        outside[y0:y1, x0:x1] = False
        if mask is None:
            gc[~outside] = cv2.GC_PR_FGD
        gc[outside] = cv2.GC_BGD
    if keep is not None and keep.any():
        gc[rs(keep) > 0] = cv2.GC_FGD
    if remove is not None and remove.any():
        gc[rs(remove) > 0] = cv2.GC_BGD
    if not ((gc == cv2.GC_FGD) | (gc == cv2.GC_PR_FGD)).any() or not (
            (gc == cv2.GC_BGD) | (gc == cv2.GC_PR_BGD)).any():
        return mask if mask is not None else np.full((h, w), 255, np.uint8)
    bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    cv2.grabCut(small, gc, None, bgd, fgd, iters, cv2.GC_INIT_WITH_MASK)
    res = np.where((gc == cv2.GC_FGD) | (gc == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
    if f < 1:
        res = cv2.resize(res, (w, h), interpolation=cv2.INTER_LINEAR)
        res = np.where(res >= 128, 255, 0).astype(np.uint8)
    # Pinselstriche in voller Auflösung exakt übernehmen
    if keep is not None:
        res[keep > 0] = 255
    if remove is not None:
        res[remove > 0] = 0
    return res


def refine(mask: np.ndarray, grow_px: float = 0.0, smooth_px: float = 0.0, fill_holes: bool = False,
           largest_only: bool = False) -> np.ndarray:
    """Masken-Nachbearbeitung: wachsen/schrumpfen, glätten, Löcher füllen, Streuteile entfernen."""
    m = np.where(mask >= 128, 255, 0).astype(np.uint8)
    if largest_only:
        n, lab, stats, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
        if n > 2:
            areas = stats[1:, cv2.CC_STAT_AREA]
            keep = np.zeros(n, bool)
            big = areas.max()
            # größtes Teil + alle Teile, die mind. 15 % davon groß sind (z. B. abgetrennte Hand)
            keep[1:] = areas >= big * 0.15
            m = np.where(keep[lab], 255, 0).astype(np.uint8)
    if fill_holes:
        h, w = m.shape
        pad = cv2.copyMakeBorder(m, 1, 1, 1, 1, cv2.BORDER_CONSTANT, value=0)
        ff = pad.copy()
        cv2.floodFill(ff, np.zeros((h + 4, w + 4), np.uint8), (0, 0), 255)
        m = cv2.bitwise_or(m, cv2.bitwise_not(ff)[1:-1, 1:-1])
    if grow_px:
        r = int(round(abs(grow_px)))
        if r > 0:
            k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
            m = cv2.dilate(m, k) if grow_px > 0 else cv2.erode(m, k)
    if smooth_px > 0:
        m = cv2.GaussianBlur(m, (0, 0), smooth_px)
        m = np.where(m >= 128, 255, 0).astype(np.uint8)
    return m


def mask_bbox(mask: np.ndarray, margin_frac: float = 0.02):
    """Rechteck um das Motiv der Maske (mit etwas Rand) oder None."""
    pts = cv2.findNonZero((mask >= 128).astype(np.uint8))
    if pts is None:
        return None
    h, w = mask.shape
    x, y, bw, bh = cv2.boundingRect(pts)
    m = int(round(max(w, h) * margin_frac))
    return [max(0, x - m), max(0, y - m), min(w, x + bw + m), min(h, y + bh + m)]


def composite(bgr: np.ndarray, mask: np.ndarray, outline_px: float = 0.0) -> np.ndarray:
    """Motiv auf weißem Hintergrund (optional mit schwarzer Umrisslinie)."""
    a = (mask.astype(np.float32) / 255.0)[..., None]
    out = (bgr.astype(np.float32) * a + 255.0 * (1 - a)).astype(np.uint8)
    if outline_px >= 0.5:
        m = mask >= 128
        r = max(1, int(round(outline_px)))
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
        ring = (cv2.dilate(m.astype(np.uint8), k) > 0) & ~cv2.erode(m.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
        out[ring] = (20, 20, 20)
    return out
