"""v3: per-colour outline → bridge gaps (label boxes) → fill interior → pick by label + legend area.

Tries several bridge sizes per zone and keeps the result closest to the legend area.
"""

import json
import math
import sys

import cv2
import numpy as np

src, out_json, out_debug = sys.argv[1], sys.argv[2], sys.argv[3]
img = cv2.imread(src)
H, W = img.shape[:2]
X1, Y0 = 1404, 82
M2 = 0.2569

COLORS = {
    "blue": (31, 119, 180), "orange": (255, 127, 14), "green": (44, 160, 44),
    "red": (214, 39, 40), "purple": (148, 103, 189), "brown": (140, 86, 75),
    "pink": (227, 119, 194), "gray": (127, 127, 127), "olive": (188, 189, 34),
    "cyan": (23, 190, 207), "black": (0, 0, 0),
}
ZONES = {
    "boundary": ("black", (700, 500), 119004.91),
    "zone_rumman_1": ("blue", (1084, 768), 4980.46),
    "zone_fruit_mix": ("blue", (512, 697), 10863.43),
    "zone_rumman_2": ("orange", (962, 866), 7085.35),
    "zone_zaytoun_2": ("orange", (812, 470), 1537.99),
    "zone_rumman_3": ("green", (852, 652), 5447.01),
    "tank": ("green", (668, 402), 88.29),
    "zone_rumman_4": ("red", (1027, 604), 7080.64),
    "well": ("red", (676, 371), 50.08),
    "zone_rumman_ummahat": ("purple", (745, 500), 1428.21),
    "zone_enab": ("brown", (777, 488), 701.73),
    "zone_rumman_5": ("pink", (920, 395), 6399.40),
    "zone_rumman_6": ("gray", (800, 262), 8139.91),
    "zone_zaytoun": ("olive", (470, 412), 22882.01),
    "zone_rumman_jadeed": ("cyan", (637, 581), 9298.68),
}


def outline(colour, tol):
    bgr = np.array(COLORS[colour][::-1], dtype=np.int16)
    diff = np.abs(img.astype(np.int16) - bgr).max(axis=2)
    m = (diff <= tol).astype(np.uint8) * 255
    m[:, X1 - 3:] = 0
    m[: Y0 + 3, :] = 0
    if colour == "black":  # drop text: keep only long thick strokes
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    return m


def interiors(m, k):
    closed = cv2.morphologyEx(m, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    cnts, hier = cv2.findContours(closed, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    out = []
    for i, c in enumerate(cnts):
        if hier[0][i][3] != -1 and cv2.contourArea(c) > 40:  # a hole = enclosed field
            out.append(c)
    return out


def score(c, pt, expected):
    area = cv2.contourArea(c)
    d = cv2.pointPolygonTest(c, pt, True)  # >0 inside
    dist_pen = 0 if d >= 0 else min(-d / 40.0, 3)
    return abs(math.log(max(area, 1) / expected)) + dist_pen


results, debug = {}, img.copy()
for zid, (colour, pt, m2) in ZONES.items():
    expected = m2 / M2
    best = None
    for tol in (30, 45, 60) if colour != "black" else (60, 80):
        m = outline(colour, tol)
        for k in (3, 5, 9, 13, 19, 27):
            for c in interiors(m, k):
                s = score(c, pt, expected)
                if best is None or s < best[0]:
                    best = (s, c, tol, k)
    if best is None:
        print(f"{zid:22s} NO CANDIDATE")
        continue
    s, c, tol, k = best
    # the hole sits inside the stroke; grow by ~half the line width
    mask = np.zeros((H, W), np.uint8)
    cv2.drawContours(mask, [c], -1, 255, -1)
    mask = cv2.dilate(mask, np.ones((3, 3), np.uint8), iterations=1)
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    c = max(cnts, key=cv2.contourArea)
    approx = cv2.approxPolyDP(c, 1.0 if expected < 3000 else 1.4, True).reshape(-1, 2)
    area = cv2.contourArea(approx.reshape(-1, 1, 2))
    results[zid] = {
        "points": approx.tolist(),
        "area_ratio": round(area * M2 / m2, 3),
        "tol": tol,
        "bridge": k,
    }
    cv2.polylines(debug, [approx.reshape(-1, 1, 2)], True, (0, 0, 255) if zid != "boundary" else (255, 0, 255), 2)

for z, r in sorted(results.items(), key=lambda kv: kv[1]["area_ratio"]):
    flag = "" if 0.9 <= r["area_ratio"] <= 1.1 else "   <-- CHECK"
    print(f"{z:22s} ratio={r['area_ratio']:5.3f} pts={len(r['points']):3d} tol={r['tol']} bridge={r['bridge']}{flag}")
cv2.imwrite(out_debug, debug)
json.dump({"frame": [0, Y0, X1, H], "m2_per_px2": M2, "zones": results}, open(out_json, "w"), indent=1)
