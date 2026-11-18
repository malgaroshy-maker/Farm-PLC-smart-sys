"""Plausible irrigation network + tracks + equipment, drawn in sketch pixels.

Routes follow the corridors between fields seen in the sketch. The owner will
correct them later, so edit the waypoints here and re-run:

    python tools/map-geometry/network.py <sketch.png> packages/map-model/src/farm-geometry.json

The script appends `network`, `tracks` and `equipment` to the geometry file
(same coordinate transform) and writes network_overlay.png for checking.
"""

import json
import sys

import cv2
import numpy as np

sketch, geo_path = sys.argv[1], sys.argv[2]
geo = json.load(open(geo_path, encoding="utf-8"))
T = geo["transform_from_sketch_px"]


def to_map(p):
    return [round((p[0] - T["minx"]) * T["scale"], 1), round((p[1] - T["miny"]) * T["scale"], 1)]


TANK = (668, 402)
WELL = (676, 371)

# ── Mainline (tree from the tank), sketch px ────────────────────────────
TRUNKS = {
    # south-east: corridor between New Pomegranate and the three strips
    "trunk_se": [TANK, (684, 428), (708, 470), (770, 582), (790, 640), (832, 742)],
    # east branch: corridor between Pomegranate 3 and 4, to the 1/2/4 junction
    "branch_e": [(776, 572), (874, 526), (936, 640), (982, 690)],
    # north-east: past the well, between Olives and Pomegranate 6
    "trunk_ne": [TANK, (700, 386), (764, 372)],
    # south-west: corridor between Olives and New Pomegranate
    "trunk_sw": [TANK, (664, 444), (560, 503), (494, 545)],
}

# zone valve = where the lateral leaves the mainline (point on the trunk) → zone edge
VALVES = {
    "zone_zaytoun": ((660, 410), (648, 404)),
    "zone_rumman_jadeed": ((690, 440), (676, 458)),
    "zone_rumman_ummahat": ((690, 440), (706, 446)),
    "zone_enab": ((700, 460), (738, 430)),
    "zone_zaytoun_2": ((700, 460), (760, 420)),
    "zone_rumman_3": ((776, 572), (790, 566)),
    "zone_rumman_2": ((832, 742), (848, 762)),
    "zone_rumman_4": ((982, 690), (976, 676)),
    "zone_rumman_1": ((982, 690), (1004, 698)),
    "zone_rumman_5": ((764, 372), (790, 372)),
    "zone_rumman_6": ((764, 372), (772, 350)),
    "zone_fruit_mix": ((494, 545), (486, 560)),
}

# well → tank refill line
REFILL = [WELL, (672, 386), TANK]

# dirt tracks (wider, under pipes): main corridors + farm entrance from the east
TRACKS = [
    [(640, 330), (700, 386), (764, 372), (900, 318)],
    [(684, 428), (708, 470), (770, 582), (790, 640), (840, 760)],
    [(776, 572), (874, 526), (936, 640), (986, 692), (1170, 650)],
    [(664, 444), (560, 503), (494, 545), (430, 610)],
]

EQUIPMENT = {
    "tank": {"at": TANK, "kind": "tank_building"},
    "booster": {"at": (684, 414), "kind": "booster_pad"},
    "well_room": {"at": WELL, "kind": "control_room"},
    "wellhead": {"at": (662, 362), "kind": "wellhead"},
}

network = {
    "mainline": {k: [to_map(p) for p in v] for k, v in TRUNKS.items()},
    "refill": [to_map(p) for p in REFILL],
    "valves": {z: {"tap": to_map(a), "valve": to_map(b)} for z, (a, b) in VALVES.items()},
}
geo["network"] = network
geo["tracks"] = [[to_map(p) for p in t] for t in TRACKS]
geo["equipment"] = {k: {"at": to_map(v["at"]), "kind": v["kind"]} for k, v in EQUIPMENT.items()}
json.dump(geo, open(geo_path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)

# overlay for checking
img = cv2.imread(sketch)
for t in TRACKS:
    cv2.polylines(img, [np.array(t, np.int32)], False, (120, 170, 210), 9)
for pts in TRUNKS.values():
    cv2.polylines(img, [np.array(pts, np.int32)], False, (255, 140, 0), 3)
cv2.polylines(img, [np.array(REFILL, np.int32)], False, (255, 0, 255), 2)
for a, b in VALVES.values():
    cv2.line(img, a, b, (255, 140, 0), 2)
    cv2.circle(img, b, 5, (0, 0, 255), -1)
for e in EQUIPMENT.values():
    cv2.circle(img, e["at"], 6, (0, 0, 0), 2)
cv2.imwrite(str(__import__("pathlib").Path(__file__).with_name("network_overlay.png")), img)
print("network written:", len(VALVES), "valves,", len(TRUNKS), "trunks")
