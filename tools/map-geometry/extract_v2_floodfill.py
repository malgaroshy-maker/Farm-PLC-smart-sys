"""v2: flood-fill between ALL drawn lines; identify each field by label + legend area."""

import json
import math
import sys

import cv2
import numpy as np

src, out_json, out_debug = sys.argv[1], sys.argv[2], sys.argv[3]
img = cv2.imread(src)
H, W = img.shape[:2]
X1, Y0 = 1404, 82  # plot frame; legend is right of X1
M2_PER_PX2 = 0.2569  # measured from the 5 zones that closed cleanly in v1 (ratio 1.00)

ZONES = {  # id: (label point, legend m²)
    "zone_rumman_1": ((1084, 768), 4980.46),
    "zone_fruit_mix": ((512, 697), 10863.43),
    "zone_rumman_2": ((962, 866), 7085.35),
    "zone_zaytoun_2": ((825, 483), 1537.99),
    "zone_rumman_3": ((852, 652), 5447.01),
    "tank": ((668, 402), 88.29),
    "zone_rumman_4": ((1027, 604), 7080.64),
    "well": ((676, 371), 50.08),
    "zone_rumman_ummahat": ((722, 481), 1428.21),
    "zone_enab": ((790, 512), 701.73),
    "zone_rumman_5": ((920, 395), 6399.40),
    "zone_rumman_6": ((800, 262), 8139.91),
    "zone_zaytoun": ((470, 412), 22882.01),
    "zone_rumman_jadeed": ((637, 581), 9298.68),
}

walls = (img.min(axis=2) < 190).astype(np.uint8)
walls[:, X1 - 2:] = 1
walls[: Y0 + 2, :] = 1
free = (1 - walls).astype(np.uint8)
n, labels, stats, _ = cv2.connectedComponentsWithStats(free, connectivity=4)


def comp_at(x, y):
    return labels[y, x] if 0 <= x < W and 0 <= y < H else 0


def candidates(pt, max_steps=60):
    """Components reached by walking out of the label box in 8 directions."""
    x0, y0 = pt
    seen = {}
    start = comp_at(x0, y0)
    for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (-1, -1), (1, -1), (-1, 1)]:
        left_start, x, y = False, x0, y0
        for _ in range(max_steps):
            x, y = x + dx, y + dy
            c = comp_at(x, y)
            if c != start:
                left_start = True
            if left_start and c not in (0, start) and walls[y, x] == 0:
                seen[c] = stats[c, cv2.CC_STAT_AREA]
                break
    if start:
        seen[start] = stats[start, cv2.CC_STAT_AREA]
    return seen


out, debug = {}, img.copy()
for zid, (pt, m2) in ZONES.items():
    expected = m2 / M2_PER_PX2
    cands = candidates(pt)
    best = min(cands, key=lambda c: abs(math.log(max(cands[c], 1) / expected)))
    mask = (labels == best).astype(np.uint8) * 255
    mask = cv2.dilate(mask, np.ones((3, 3), np.uint8), iterations=1)  # give back the line width
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    c = max(cnts, key=cv2.contourArea)
    area = cv2.contourArea(c)
    approx = cv2.approxPolyDP(c, 1.2, True).reshape(-1, 2)
    out[zid] = {"points": approx.tolist(), "px_area": area, "area_ratio": round(area * M2_PER_PX2 / m2, 3)}
    cv2.polylines(debug, [approx.reshape(-1, 1, 2)], True, (0, 0, 255), 2)

# outer boundary: everything inside the frame that is not connected to the outside corners
outside = np.zeros_like(free)
for seed in [(20, 110), (1380, 110), (20, 930), (1380, 940), (700, 110)]:
    c = comp_at(*seed)
    if c:
        outside |= (labels == c).astype(np.uint8)
inside = np.zeros_like(free)
inside[Y0 + 3 : H - 2, 3 : X1 - 3] = 1
inside &= 1 - outside
inside = cv2.morphologyEx(inside * 255, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
cnts, _ = cv2.findContours(inside, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
c = max(cnts, key=cv2.contourArea)
approx = cv2.approxPolyDP(c, 1.5, True).reshape(-1, 2)
out["boundary"] = {
    "points": approx.tolist(),
    "px_area": cv2.contourArea(c),
    "area_ratio": round(cv2.contourArea(c) * M2_PER_PX2 / 119004.91, 3),
}
cv2.polylines(debug, [approx.reshape(-1, 1, 2)], True, (255, 0, 255), 2)

for z, r in sorted(out.items(), key=lambda kv: kv[1]["area_ratio"]):
    print(f"{z:22s} ratio={r['area_ratio']:5.3f} pts={len(r['points'])}")
cv2.imwrite(out_debug, debug)
json.dump({"frame": [0, Y0, X1, H], "m2_per_px2": M2_PER_PX2, "zones": out}, open(out_json, "w"), indent=1)
