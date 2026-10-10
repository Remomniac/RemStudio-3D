"""Beispielbild, damit man das Programm sofort ausprobieren kann."""
import math

import cv2
import numpy as np


def demo_image() -> np.ndarray:
    W = H = 1200
    img = np.full((H, W, 3), 255, np.uint8)
    k = (20, 20, 20)
    # Sonne mit Strahlen (Strahlen sind lose Teile -> werden automatisch verbunden)
    c = (850, 330)
    cv2.circle(img, c, 120, k, 14, cv2.LINE_AA)
    for i in range(12):
        a = math.radians(i * 30 + 15)
        p1 = (int(c[0] + 155 * math.cos(a)), int(c[1] + 155 * math.sin(a)))
        p2 = (int(c[0] + 215 * math.cos(a)), int(c[1] + 215 * math.sin(a)))
        cv2.line(img, p1, p2, k, 14, cv2.LINE_AA)
    # Berge
    m1 = np.array([[0, 900], [260, 520], [400, 700], [600, 380], [900, 860], [1200, 640]], np.int32)
    cv2.polylines(img, [m1], False, k, 16, cv2.LINE_AA)
    snow = np.array([[530, 480], [600, 380], [670, 490], [630, 470], [600, 500], [565, 465]], np.int32)
    cv2.fillPoly(img, [snow], k, cv2.LINE_AA)
    # Hügel
    pts = np.array([[x, int(980 + 40 * math.sin(x / 140.0))] for x in range(0, 1201, 20)], np.int32)
    cv2.polylines(img, [pts], False, k, 14, cv2.LINE_AA)
    # Tannen
    for x, y, s in ((180, 1080, 1.0), (300, 1100, 0.8), (1000, 1070, 1.1)):
        tri = np.array([[x, y - int(260 * s)], [x - int(80 * s), y - int(40 * s)], [x + int(80 * s), y - int(40 * s)]],
                       np.int32)
        cv2.fillPoly(img, [tri], k, cv2.LINE_AA)
        cv2.rectangle(img, (x - int(14 * s), y - int(40 * s)), (x + int(14 * s), y), k, -1)
    # Vögel
    for x, y, s in ((300, 250, 1.0), (390, 200, 0.8), (450, 300, 0.7)):
        cv2.ellipse(img, (x - int(30 * s), y), (int(30 * s), int(18 * s)), 0, 200, 340, k, 9, cv2.LINE_AA)
        cv2.ellipse(img, (x + int(30 * s), y), (int(30 * s), int(18 * s)), 0, 200, 340, k, 9, cv2.LINE_AA)
    return img
