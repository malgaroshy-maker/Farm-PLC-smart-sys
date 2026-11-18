"""Extract zone polygons from the farm sketch by line colour and verify against legend areas."""

import json
import sys

import cv2
import numpy as np

src, out_json, out_debug = sys.argv[1], sys.argv[2], sys.argv[3]
img = cv2.imread(src)  # BGR
H, W = img.shape[:2]
PLOT = (0, 82, 1404, H)  # x0, y0, x1, y1 — legend lives at x > 1405

# matplotlib tab10 colours (RGB)
COLORS = {
    "blue": (31, 119, 180), "orange": (255, 127, 14), "green": (44, 160, 44),
    "red": (214, 39, 40), "purple": (148, 103, 189), "brown": (140, 86, 75),
    "pink": (227, 119, 194), "gray": (127, 127, 127), "olive": (188, 189, 34),
    "cyan": (23, 190, 207), "black": (0, 0, 0),
}
# zone id → (colour, approximate label position in the image, legend area m²)
ZONES = {
    "boundary":            ("black", (700, 500), 119004.91),
    "zone_rumman_1":       ("blue", (1084, 768), 4980.46),
    "zone_fruit_mix":      ("blue", (512, 697), 10863.43),
    "zone_rumman_2":       ("orange", (962, 866), 7085.35),
    "zone_zaytoun_2":      ("orange", (812, 470), 1537.99),
    "zone_rumman_3":       ("green", (852, 652), 5447.01),
    "tank":                ("green", (668, 402), 88.29),
    "zone_rumman_4":       ("red", (1027, 604), 7080.64),
    "well":                ("red", (676, 371), 50.08),
    "zone_rumman_ummahat": ("purple", (750, 500), 1428.21),
    "zone_enab":           ("brown", (775, 485), 701.73),
    "zone_rumman_5":       ("pink", (920, 395), 6399.40),
    "zone_rumman_6":       ("gray", (800, 262), 8139.91),
    "zone_zaytoun":        ("olive", (470, 412), 22882.01),
    "zone_rumman_jadeed":  ("cyan", (637, 581), 9298.68),
}


def colour_mask(rgb, tol):
    bgr = np.array(rgb[::-1], dtype=np.int16)
    diff = np.abs(img.astype(np.int16) - bgr).max(axis=2)
    m = (diff <= tol).astype(np.uint8) * 255
    x0, y0, x1, y1 = PLOT
    clip = np.zeros_like(m)
    clip[y0:y1, x0:x1] = m[y0:y1, x0:x1]
    return clip


def regions_for(colour):
    tol = 30 if colour != "black" else 60
    m = colour_mask(COLORS[colour], tol)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    m = cv2.dilate(m, np.ones((3, 3), np.uint8))
    contours, hierarchy = cv2.findContours(m, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    out = []
    for i, c in enumerate(contours):
        # inner contours (holes) of the outline = the enclosed field
        if hierarchy[0][i][3] != -1 and cv2.contourArea(c) > 300:
            out.append(c)
    return out


results, debug = {}, img.copy()
by_colour: dict[str, list] = {}
for zid, (colour, label, _) in ZONES.items():
    by_colour.setdefault(colour, regions_for(colour))
    cands = by_colour[colour]
    # pick the region that contains the label point, else the nearest centroid
    inside = [c for c in cands if cv2.pointPolygonTest(c, label, False) >= 0]
    if inside:
        c = min(inside, key=cv2.contourArea)  # smallest enclosing (avoid outer boundary)
    else:
        def dist(c):
            m = cv2.moments(c)
            cx, cy = m["m10"] / m["m00"], m["m01"] / m["m00"]
            return (cx - label[0]) ** 2 + (cy - label[1]) ** 2
        c = min(cands, key=dist) if cands else None
    if c is None:
        print("MISSING", zid)
        continue
    approx = cv2.approxPolyDP(c, 1.2, True)
    results[zid] = {"px_area": float(cv2.contourArea(c)), "points": approx.reshape(-1, 2).tolist()}
    cv2.polylines(debug, [approx], True, (0, 0, 255), 2)
    cv2.putText(debug, zid.replace("zone_", ""), tuple(int(v) for v in approx.reshape(-1, 2).mean(0)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)

# area check: m² per px² should be the same for every zone
scales = {z: ZONES[z][2] / r["px_area"] for z, r in results.items() if r["px_area"] > 0}
ref = np.median([s for z, s in scales.items() if z.startswith("zone_")])
print(f"median m²/px² = {ref:.4f}")
for z, s in sorted(scales.items(), key=lambda kv: kv[1] / ref):
    print(f"{z:22s} px={results[z]['px_area']:9.0f}  ratio={s / ref:5.2f}  pts={len(results[z]['points'])}")

cv2.imwrite(out_debug, debug)
json.dump({"plot": PLOT, "m2_per_px2": ref, "zones": results}, open(out_json, "w"), indent=1)
