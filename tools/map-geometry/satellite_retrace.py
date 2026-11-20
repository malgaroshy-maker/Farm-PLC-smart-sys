"""Satellite Imagery Georeferencing and Farm Geometry Retracing (Milestone F).

Georeferences Esri World Imagery (zoom 17, ~1.007 m/px) to the farm SVG viewBox
[0, 0, 1000, 886.8]. Re-traces blocks 6–15, buildings S1–S7 and C, tracks,
the eastern wadi, and farm boundary from satellite ground truth.

Generates:
1. design/satellite/overlay_comparison.png: satellite base + old outlines (orange) + new outlines (green)
2. Area comparison table: Sketch Legend vs Old Geometry vs New Geometry
"""

import json
import math
import os
import sys

import cv2
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
Z17_PATH = os.path.join(ROOT, "design", "satellite", "farm_esri_z17.jpg")
OLD_GEOM_PATH = os.path.join(ROOT, "packages", "map-model", "src", "farm-geometry.json")
OUTPUT_OVERLAY_PATH = os.path.join(ROOT, "design", "satellite", "overlay_comparison.png")

# Legend areas from survey ground truth (docs/MAP_SURVEY.md)
LEGEND_M2 = {
    "boundary": 119004.91,
    "zone_rumman_1": 4980.46,
    "zone_rumman_2": 7085.35,
    "zone_rumman_3": 5447.01,
    "zone_rumman_4": 7080.64,
    "zone_rumman_ummahat": 1428.21,
    "zone_enab": 701.73,
    "zone_zaytoun_2": 1537.99,
    "zone_rumman_5": 6399.40,
    "zone_rumman_6": 8139.91,
    "zone_zaytoun": 22882.01,
    "zone_rumman_jadeed": 9298.68,
    "zone_fruit_mix": 10863.43,
    "tank": 88.29,
    "well": 50.08,
}

# Esri tile resolution
M_PER_PX = 1.007
M2_PER_PX2 = M_PER_PX**2

# Similarity transform parameters between satellite pixel (sx, sy) and SVG viewBox (vx, vy):
# viewBox = [0, 0, 1000, 886.8]
# Fitted against control points: S6, S7, C, blocks 6, 7N, 7S, 8, 10, 11, 12, 13, 14, 15
SCALE_S = 2.0606
THETA_DEG = -4.80
THETA_RAD = math.radians(THETA_DEG)
A_COEF = SCALE_S * math.cos(THETA_RAD)
B_COEF = SCALE_S * math.sin(THETA_RAD)
TX = -353.3
TY = -493.0
S_SQ = SCALE_S**2


def sat_to_svg(sx: float, sy: float) -> tuple[float, float]:
    """Convert satellite image pixel (sx, sy) to SVG viewBox unit (vx, vy)."""
    vx = A_COEF * sx - B_COEF * sy + TX
    vy = B_COEF * sx + A_COEF * sy + TY
    return round(vx, 1), round(vy, 1)


def svg_to_sat(vx: float, vy: float) -> tuple[float, float]:
    """Convert SVG viewBox unit (vx, vy) to satellite image pixel (sx, sy)."""
    dx = vx - TX
    dy = vy - TY
    sx = (A_COEF * dx + B_COEF * dy) / S_SQ
    sy = (-B_COEF * dx + A_COEF * dy) / S_SQ
    return sx, sy


def poly_area_m2(pts: list[list[float]], is_sat_px: bool = True) -> float:
    """Calculate polygon area in m² using either satellite pixels or SVG coordinates."""
    p = np.array(pts, float)
    raw_area = 0.5 * abs(np.dot(p[:, 0], np.roll(p[:, 1], 1)) - np.dot(p[:, 1], np.roll(p[:, 0], 1)))
    if is_sat_px:
        return raw_area * M2_PER_PX2
    # In SVG viewBox space:
    # m2_per_unit2 = (m_per_px / scale_s)^2
    m2_per_unit2 = (M_PER_PX / SCALE_S) ** 2
    return raw_area * m2_per_unit2


def get_traced_features_sat():
    """Return dictionary of traced polygons, buildings, and tracks in satellite pixel coordinates.

    Ground truth based on docs/MAP_SURVEY.md:
    - Blocks 6 & 9: zone_zaytoun (olives west of buildings)
    - Block 7 north: zone_rumman_6
    - Block 7 south: zone_rumman_5
    - Block 8 east strip: zone_zaytoun_2
    - Block 8 middle strip: zone_enab
    - Block 8 west strip: zone_rumman_ummahat
    - Block 11: zone_rumman_jadeed
    - Block 10: zone_fruit_mix (bright green block)
    - Block 12: zone_rumman_3
    - Block 13: zone_rumman_4
    - Block 14: zone_rumman_2
    - Block 15: zone_rumman_1
    """
    # Precision corners measured on farm_esri_z17.jpg (794x796)
    # Block 7 north (rumman_6): legend = 8,139 m²
    # Bounded by east track/wadi, central buildings track, and north orchard track
    b7n = [
        [415.0, 312.0],
        [486.0, 316.0],
        [488.0, 396.0],
        [422.0, 393.0],
    ]

    # Block 7 south (rumman_5): legend = 6,399 m²
    # South of building cluster cross-track, north of block 8 cross-track
    b7s = [
        [423.0, 399.0],
        [489.0, 402.0],
        [492.0, 477.0],
        [428.0, 474.0],
    ]

    # Block 8: total area ≈ 3,668 m²
    # Order going west from rumman_5: zaytoun_2 (east) -> enab (middle) -> rumman_ummahat (west)
    # Block 8 bounds:
    # Top edge: y ~ 445..452, Bottom edge: y ~ 508..515, Left: x ~ 388, Right: x ~ 434
    # zaytoun_2: legend = 1,538 m² (~42% width)
    # enab: legend = 702 m² (~19% width)
    # rumman_ummahat: legend = 1,428 m² (~39% width)
    b8_top_r, b8_top_l = [434.0, 446.0], [388.0, 452.0]
    b8_bot_r, b8_bot_l = [438.0, 508.0], [392.0, 514.0]

    # Interpolate strip boundaries across top and bottom edges
    # Fractions: east strip takes 0.0 to 0.42, mid takes 0.42 to 0.61, west takes 0.61 to 1.0
    def interp(p1, p2, f):
        return [round(p1[0] + f * (p2[0] - p1[0]), 1), round(p1[1] + f * (p2[1] - p1[1]), 1)]

    t_e0, t_e1 = b8_top_r, interp(b8_top_r, b8_top_l, 0.42)
    t_m1 = interp(b8_top_r, b8_top_l, 0.61)
    t_w1 = b8_top_l

    b_e0, b_e1 = b8_bot_r, interp(b8_bot_r, b8_bot_l, 0.42)
    b_m1 = interp(b8_bot_r, b8_bot_l, 0.61)
    b_w1 = b8_bot_l

    b8_zaytoun_2 = [t_e0, t_e1, b_e1, b_e0]
    b8_enab = [t_e1, t_m1, b_m1, b_e1]
    b8_ummahat = [t_m1, t_w1, b_w1, b_m1]

    # Block 6 + 9 (zone_zaytoun): legend = 22,882 m²
    # Olives west of the buildings and west of block 11
    # Block 6 (north olive block)
    b6 = [
        [228.0, 360.0],
        [348.0, 368.0],
        [356.0, 456.0],
        [222.0, 452.0],
    ]
    # Block 9 (south olive block)
    b9 = [
        [220.0, 458.0],
        [312.0, 462.0],
        [298.0, 558.0],
        [178.0, 552.0],
    ]
    # Combined zone_zaytoun polygon perimeter
    zaytoun_poly = [
        [228.0, 360.0],
        [348.0, 368.0],
        [356.0, 456.0],
        [312.0, 462.0],
        [298.0, 558.0],
        [178.0, 552.0],
        [220.0, 458.0],
        [222.0, 452.0],
    ]

    # Block 11 (zone_rumman_jadeed): legend = 9,299 m²
    # East of block 9, west of block 8 / block 12
    b11 = [
        [316.0, 464.0],
        [382.0, 468.0],
        [370.0, 574.0],
        [296.0, 568.0],
    ]

    # Block 10 (zone_fruit_mix): legend = 10,863 m²
    # Bright green block south of blocks 9 & 11
    b10 = [
        [182.0, 562.0],
        [368.0, 578.0],
        [356.0, 646.0],
        [172.0, 638.0],
    ]

    # Block 12 (zone_rumman_3): legend = 5,447 m²
    # South of block 8, west of block 13, north of block 14
    b12 = [
        [418.0, 516.0],
        [484.0, 520.0],
        [486.0, 598.0],
        [420.0, 594.0],
    ]

    # Block 13 (zone_rumman_4): legend = 7,081 m²
    # East of block 12, north of block 15, west of wadi
    b13 = [
        [492.0, 482.0],
        [552.0, 486.0],
        [556.0, 570.0],
        [494.0, 566.0],
    ]

    # Block 14 (zone_rumman_2): legend = 7,085 m²
    # South of block 12, west of block 15
    b14 = [
        [458.0, 612.0],
        [532.0, 616.0],
        [534.0, 706.0],
        [460.0, 702.0],
    ]

    # Block 15 (zone_rumman_1): legend = 4,980 m²
    # East of block 14, south of block 13, west of wadi
    b15 = [
        [538.0, 598.0],
        [578.0, 602.0],
        [582.0, 684.0],
        [540.0, 680.0],
    ]

    # Buildings (from zoom_A_labelled and ground truth):
    # S6: Control room + well (366.3, 416.2)
    s6_building = [
        [362.5, 412.0],
        [370.0, 412.0],
        [370.0, 419.5],
        [362.5, 419.5],
    ]
    # S7: Closed concrete water tank (364.3, 436.9) + booster pad beside it
    s7_tank = [
        [361.0, 433.0],
        [368.5, 433.0],
        [368.5, 441.5],
        [361.0, 441.5],
    ]
    s7_booster = [
        [370.0, 434.5],
        [374.5, 434.5],
        [374.5, 440.0],
        [370.0, 440.0],
    ]
    # S1, S2, S3: Chicken house barn / brooder / storage
    s1_chicken = [
        [359.0, 375.0],
        [368.0, 375.0],
        [368.0, 384.0],
        [359.0, 384.0],
    ]
    s2_chicken = [
        [382.0, 391.0],
        [391.0, 391.0],
        [391.0, 399.0],
        [382.0, 399.0],
    ]
    s3_chicken = [
        [377.0, 371.0],
        [385.0, 371.0],
        [385.0, 378.0],
        [377.0, 378.0],
    ]
    # S5: Workers' rooms
    s5_workers = [
        [384.0, 407.0],
        [393.0, 407.0],
        [393.0, 415.0],
        [384.0, 415.0],
    ]
    # C: House near north entrance
    c_house = [
        [352.0, 300.0],
        [361.0, 300.0],
        [361.0, 308.0],
        [352.0, 308.0],
    ]

    # Main tracks
    tracks = [
        # North entrance past House C down to cluster A
        [[356.0, 180.0], [356.0, 300.0], [358.0, 370.0], [360.0, 430.0]],
        # Cluster A cross track east toward blocks 7 & 8
        [[360.0, 430.0], [420.0, 432.0], [490.0, 435.0]],
        # Track between block 6/9 and block 11/10
        [[356.0, 456.0], [312.0, 462.0], [298.0, 558.0], [356.0, 646.0]],
        # Central track east of block 11 toward blocks 8, 12, 14
        [[420.0, 432.0], [418.0, 520.0], [458.0, 612.0], [460.0, 702.0]],
        # East wadi track along blocks 7, 13, 15
        [[490.0, 316.0], [492.0, 402.0], [554.0, 486.0], [558.0, 570.0], [580.0, 680.0]],
    ]

    # Wadi (dry gully along east edge)
    wadi = [
        [510.0, 260.0],
        [506.0, 330.0],
        [515.0, 410.0],
        [570.0, 490.0],
        [575.0, 580.0],
        [600.0, 690.0],
        [610.0, 740.0],
    ]

    # Farm boundary: convex/concave envelope of our 10 irrigated zones + cluster A + C
    boundary = [
        [350.0, 280.0],
        [415.0, 308.0],
        [490.0, 312.0],
        [495.0, 400.0],
        [558.0, 482.0],
        [562.0, 568.0],
        [586.0, 600.0],
        [588.0, 688.0],
        [540.0, 712.0],
        [456.0, 710.0],
        [354.0, 654.0],
        [168.0, 644.0],
        [174.0, 548.0],
        [216.0, 450.0],
        [224.0, 355.0],
        [346.0, 358.0],
    ]

    return {
        "zones": {
            "zone_zaytoun": zaytoun_poly,
            "zone_rumman_6": b7n,
            "zone_rumman_5": b7s,
            "zone_zaytoun_2": b8_zaytoun_2,
            "zone_enab": b8_enab,
            "zone_rumman_ummahat": b8_ummahat,
            "zone_rumman_jadeed": b11,
            "zone_fruit_mix": b10,
            "zone_rumman_3": b12,
            "zone_rumman_4": b13,
            "zone_rumman_2": b14,
            "zone_rumman_1": b15,
        },
        "blocks_detail": {
            "block_6": b6,
            "block_9": b9,
        },
        "buildings": {
            "well": s6_building,
            "tank": s7_tank,
            "booster": s7_booster,
            "chicken_1": s1_chicken,
            "chicken_2": s2_chicken,
            "chicken_3": s3_chicken,
            "workers": s5_workers,
            "house_c": c_house,
        },
        "tracks": tracks,
        "wadi": wadi,
        "boundary": boundary,
    }


def main():
    print("=" * 70)
    print("Algaroshy Farm: Satellite Georeferencing & Geometry Retracing")
    print("=" * 70)

    # 1. Load satellite image and old geometry
    if not os.path.exists(Z17_PATH):
        print(f"Error: satellite image {Z17_PATH} not found.")
        sys.exit(1)
    sat_img = cv2.imread(Z17_PATH)
    h_sat, w_sat = sat_img.shape[:2]
    print(f"Loaded satellite imagery: {w_sat}x{h_sat} px (~{M_PER_PX:.3f} m/px)")

    with open(OLD_GEOM_PATH, "r", encoding="utf-8") as f:
        old_geom = json.load(f)
    print("Loaded current map geometry (packages/map-model/src/farm-geometry.json)")

    # 2. Get traced features in satellite space
    traced = get_traced_features_sat()
    zones = traced["zones"]
    buildings = traced["buildings"]

    # 3. Compute area comparison table
    print("\n" + "-" * 70)
    print("AREA COMPARISON TABLE (m²)")
    print(f"{'Feature / Zone ID':24s} | {'Legend m²':>10s} | {'Old Geom m²':>11s} | {'New Sat m²':>10s} | {'New/Leg':>8s} | {'Notes'}")
    print("-" * 70)

    table_data = []
    old_m2_per_unit2 = old_geom.get("m2_per_unit2", 0.26519)

    for zid in LEGEND_M2:
        leg_m2 = LEGEND_M2[zid]

        # Old area
        old_feat = old_geom["features"].get(zid)
        if old_feat:
            p_old = np.array(old_feat["points"], float)
            raw_old = 0.5 * abs(np.dot(p_old[:, 0], np.roll(p_old[:, 1], 1)) - np.dot(p_old[:, 1], np.roll(p_old[:, 0], 1)))
            old_m2 = raw_old * old_m2_per_unit2
        else:
            old_m2 = 0.0

        # New area from satellite
        if zid in zones:
            pts_sat = zones[zid]
            new_m2 = poly_area_m2(pts_sat, is_sat_px=True)
        elif zid in buildings:
            pts_sat = buildings[zid]
            new_m2 = poly_area_m2(pts_sat, is_sat_px=True)
        elif zid == "boundary":
            pts_sat = traced["boundary"]
            new_m2 = poly_area_m2(pts_sat, is_sat_px=True)
        else:
            new_m2 = 0.0

        ratio = new_m2 / leg_m2 if leg_m2 > 0 else 1.0
        flag = "✓ verified" if 0.85 <= ratio <= 1.15 else "⚠ check"
        table_data.append((zid, leg_m2, old_m2, new_m2, ratio, flag))
        print(f"{zid:24s} | {leg_m2:10.1f} | {old_m2:11.1f} | {new_m2:10.1f} | {ratio:8.3f} | {flag}")

    print("-" * 70)

    # 4. Generate comparison overlay image (satellite + old orange + new green)
    overlay = sat_img.copy()

    # Draw old outlines in Orange/Red (projected from SVG to sat pixels)
    orange_bgr = (20, 140, 255)  # #ff8c14
    for fid, feat in old_geom["features"].items():
        old_pts_svg = feat["points"]
        old_pts_sat = [svg_to_sat(x, y) for x, y in old_pts_svg]
        pts_np = np.array(old_pts_sat, np.int32).reshape((-1, 1, 2))
        cv2.polylines(overlay, [pts_np], isClosed=True, color=orange_bgr, thickness=2, lineType=cv2.LINE_AA)

    # Draw new outlines in Bright Green / Cyan
    green_bgr = (50, 230, 50)  # #32e632
    cyan_bgr = (240, 220, 0)   # #00dcf0
    for zid, pts_sat in zones.items():
        pts_np = np.array(pts_sat, np.int32).reshape((-1, 1, 2))
        cv2.polylines(overlay, [pts_np], isClosed=True, color=green_bgr, thickness=2, lineType=cv2.LINE_AA)

    # Draw boundary in cyan
    b_np = np.array(traced["boundary"], np.int32).reshape((-1, 1, 2))
    cv2.polylines(overlay, [b_np], isClosed=True, color=cyan_bgr, thickness=2, lineType=cv2.LINE_AA)

    # Draw buildings in yellow
    yellow_bgr = (0, 240, 255)
    for bname, bpts in buildings.items():
        pts_np = np.array(bpts, np.int32).reshape((-1, 1, 2))
        cv2.fillPoly(overlay, [pts_np], color=yellow_bgr)
        cv2.polylines(overlay, [pts_np], isClosed=True, color=(0, 180, 200), thickness=1, lineType=cv2.LINE_AA)

    # Draw tracks in light grey dashed / thin
    for trk in traced["tracks"]:
        pts_np = np.array(trk, np.int32).reshape((-1, 1, 2))
        cv2.polylines(overlay, [pts_np], isClosed=False, color=(220, 220, 220), thickness=2, lineType=cv2.LINE_AA)

    # Draw wadi in light blue
    w_np = np.array(traced["wadi"], np.int32).reshape((-1, 1, 2))
    cv2.polylines(overlay, [w_np], isClosed=False, color=(255, 180, 80), thickness=3, lineType=cv2.LINE_AA)

    # Add Legend Banner on top
    cv2.rectangle(overlay, (10, 10), (450, 95), (20, 20, 20), -1)
    cv2.rectangle(overlay, (10, 10), (450, 95), (80, 80, 80), 1)

    cv2.putText(overlay, "Algaroshy Farm: Satellite Tracing Overlay", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.circle(overlay, (25, 48), 6, orange_bgr, -1)
    cv2.putText(overlay, "Orange: Old Geometry (traced from sketch)", (38, 52), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (220, 220, 220), 1, cv2.LINE_AA)
    cv2.circle(overlay, (25, 68), 6, green_bgr, -1)
    cv2.putText(overlay, "Green: New Retraced Geometry (Esri satellite)", (38, 72), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (220, 220, 220), 1, cv2.LINE_AA)
    cv2.putText(overlay, "Attribution: Source: Esri, Maxar, Earthstar Geographics", (20, 88), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (160, 160, 160), 1, cv2.LINE_AA)

    # Save overlay image
    os.makedirs(os.path.dirname(OUTPUT_OVERLAY_PATH), exist_ok=True)
    cv2.imwrite(OUTPUT_OVERLAY_PATH, overlay)
    print(f"\nOverlay comparison image successfully generated at:\n  {OUTPUT_OVERLAY_PATH}")

    return table_data


if __name__ == "__main__":
    main()
