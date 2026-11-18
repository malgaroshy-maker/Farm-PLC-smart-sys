"""Assemble final geometry: v3 polygons + hand-read strip quads + closed boundary + v2 olives.

Writes map-model geometry in a 0..1000 x 0..(1000*aspect) viewBox, verifies areas.
"""

import json
import subprocess
import sys

import cv2
import numpy as np

sp = sys.argv[1]
out_path = sys.argv[2]
img = cv2.imread(f"{sp}/farm_sketch.png")
H, W = img.shape[:2]
X1, Y0 = 1404, 82
M2 = 0.2569
LEGEND = {
    "boundary": 119004.91, "zone_rumman_1": 4980.46, "zone_rumman_2": 7085.35,
    "zone_rumman_3": 5447.01, "zone_rumman_4": 7080.64, "zone_rumman_ummahat": 1428.21,
    "zone_enab": 701.73, "zone_rumman_5": 6399.40, "zone_rumman_6": 8139.91,
    "zone_zaytoun": 22882.01, "zone_rumman_jadeed": 9298.68, "zone_fruit_mix": 10863.43,
    "zone_zaytoun_2": 1537.99, "tank": 88.29, "well": 50.08,
}

v3 = json.load(open(f"{sp}/zones_px.json"))["zones"]

# v2 olives (re-run v2 just for this zone's polygon)
subprocess.run([sys.executable, "-I", f"{sp}/extract_zones2.py", f"{sp}/farm_sketch.png",
                f"{sp}/zones_v2.json", f"{sp}/zones_debug_v2.png"], check=True, capture_output=True)
v2 = json.load(open(f"{sp}/zones_v2.json"))["zones"]
v1 = json.load(open(f"{sp}/zones_v1.json"))["zones"]
# sharpest source per zone (v3's large bridge rounds corners)
FROM_V1 = {"zone_rumman_1", "zone_rumman_2", "zone_rumman_4", "zone_rumman_6", "zone_fruit_mix"}
FROM_V2 = {"zone_rumman_5", "zone_rumman_jadeed", "zone_zaytoun"}


def crop_pt(x, y):  # from the 4x crop (offset 670,390)
    return [670 + x / 4, 390 + y / 4]


STRIPS = {
    "zone_rumman_ummahat": [crop_pt(95, 235), crop_pt(245, 160), crop_pt(520, 640), crop_pt(350, 710)],
    "zone_enab": [crop_pt(245, 160), crop_pt(325, 115), crop_pt(595, 605), crop_pt(520, 640)],
    "zone_zaytoun_2": [crop_pt(335, 110), crop_pt(505, 48), crop_pt(785, 522), crop_pt(605, 595)],
}

# boundary: union of ALL drawn lines (coloured zone edges cover the black line in places),
# flood-fill from outside; everything not reachable is the farm.
m = (img.min(axis=2) < 190).astype(np.uint8) * 255
m[:, X1 - 3:] = 0
m[: Y0 + 3, :] = 0
m[H - 3:, 900:950] = 255  # only the SE corner runs off the sketch; the V-notch stays open (outside)
m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
ff = m.copy()
mask = np.zeros((H + 2, W + 2), np.uint8)
cv2.floodFill(ff, mask, (5, Y0 + 10), 128)
inside = (ff != 128).astype(np.uint8) * 255
inside = cv2.morphologyEx(inside, cv2.MORPH_OPEN, np.ones((9, 9), np.uint8))
cnts, _ = cv2.findContours(inside, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
boundary = cv2.approxPolyDP(max(cnts, key=cv2.contourArea), 2.0, True).reshape(-1, 2).tolist()

polys = {}
for zid in LEGEND:
    if zid in STRIPS:
        polys[zid] = STRIPS[zid]
    elif zid == "boundary":
        polys[zid] = boundary
    elif zid in FROM_V1:
        polys[zid] = v1[zid]["points"]
    elif zid in FROM_V2:
        polys[zid] = v2[zid]["points"]
    else:
        polys[zid] = v3[zid]["points"]


def area(pts):
    p = np.array(pts, float)
    return 0.5 * abs(np.dot(p[:, 0], np.roll(p[:, 1], 1)) - np.dot(p[:, 1], np.roll(p[:, 0], 1)))


ok = True
for zid, pts in polys.items():
    r = area(pts) * M2 / LEGEND[zid]
    flag = "" if 0.88 <= r <= 1.12 else "  <-- CHECK"
    ok &= not flag
    print(f"{zid:22s} ratio={r:5.3f} pts={len(pts)}{flag}")

# normalise into a viewBox: x 0..1000, y scaled the same (keeps shapes; areas stay proportional)
allpts = np.array(polys["boundary"], float)
minx, miny = allpts.min(0) - 20
maxx, maxy = allpts.max(0) + 20
s = 1000.0 / (maxx - minx)
vb_h = round((maxy - miny) * s, 1)


def norm(pts):
    return [[round((x - minx) * s, 1), round((y - miny) * s, 1)] for x, y in pts]


m2_per_unit2 = M2 / (s * s)
geo = {
    "source": "docs/algaroshy_farm_layout_landscape_fixed.svg (traced by line colour; areas verified against legend)",
    "viewBox": [0, 0, 1000, vb_h],
    "m2_per_unit2": round(m2_per_unit2, 5),
    "transform_from_sketch_px": {"minx": float(minx), "miny": float(miny), "scale": s},
    "features": {zid: {"points": norm(p), "legend_m2": LEGEND[zid]} for zid, p in polys.items()},
}
json.dump(geo, open(out_path, "w"), indent=1)

dbg = img.copy()
for zid, p in polys.items():
    cv2.polylines(dbg, [np.array(p, np.int32).reshape(-1, 1, 2)], True, (255, 0, 255) if zid == "boundary" else (0, 0, 255), 2)
cv2.imwrite(f"{sp}/zones_final_debug.png", dbg)
print("viewBox height", vb_h, "| all within ±12%:", ok)
