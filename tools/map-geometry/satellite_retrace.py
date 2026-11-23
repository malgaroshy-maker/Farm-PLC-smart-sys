"""Check the satellite trace of the farm and draw it for owner review.

Input:  design/satellite/farm_esri_z17.jpg (+ .json), from fetch_esri_tiles.py (git-ignored)
        tools/map-geometry/satellite_trace.json  - block outlines, splits, tracks and
                                                    buildings traced by eye on that image
        packages/map-model/src/farm-geometry.json - the current (sketch) geometry
Output: design/satellite/trace_*.png (git-ignored) and a metrics table on stdout.

The outlines are traced by a person, not detected. This script does not move them; it
measures how well they fit the image (vegetation fill, bare sand, area vs legend, row
angle) so mistakes show up as numbers, and draws overlays for the owner to check.

Run from the repo root:
    uv run --no-project --with opencv-python-headless --with numpy --with shapely \
        --with pillow python tools/map-geometry/satellite_retrace.py
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import split, unary_union

ROOT = Path(__file__).resolve().parents[2]
SAT = ROOT / "design" / "satellite"
TRACE = json.loads((Path(__file__).with_name("satellite_trace.json")).read_text(encoding="utf-8"))
# The owner's original sketch geometry (pre-satellite), kept as an independent cross-check.
OLD = json.loads((Path(__file__).with_name("sketch-geometry.json")).read_text(encoding="utf-8"))
META = json.loads((SAT / "farm_esri_z17.json").read_text(encoding="utf-8"))
M_PER_PX = META["m_per_px"]
M2_PER_PX2 = M_PER_PX**2
ATTRIBUTION = "Source: Esri, Maxar, Earthstar Geographics"


# ---------------------------------------------------------------- georeference
def _merc(lat: float, lon: float, z: int) -> tuple[float, float]:
    n = 256 * 2**z
    s = math.sin(math.radians(lat))
    return (lon + 180) / 360 * n, (0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * n


_LON0, _LAT0, _LON1, _LAT1 = META["bbox"]
_Z = META["z"]
_X0, _Y0 = _merc(_LAT1, _LON0, _Z)
_OX = _X0 // 256 * 256 + round(_X0 - _X0 // 256 * 256)
_OY = _Y0 // 256 * 256 + round(_Y0 - _Y0 // 256 * 256)


def px_to_latlon(x: float, y: float) -> tuple[float, float]:
    n = 256 * 2**_Z
    X, Y = x + _OX, y + _OY
    lon = X / n * 360 - 180
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * Y / n))))
    return lat, lon


# ---------------------------------------------------------------- masks
def masks(img_bgr: np.ndarray) -> dict[str, np.ndarray]:
    f = img_bgr.astype(np.float32)
    b, g, r = f[..., 0], f[..., 1], f[..., 2]
    exg = cv2.GaussianBlur((2 * g - r - b) / (b + g + r + 1e-6), (0, 0), 1.5)
    val = cv2.GaussianBlur(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)[..., 2].astype(np.float32), (0, 0), 1.5)
    sand = (val > 120) & (exg < 0.06)
    veg = ((exg > 0.07) | (val < 75)) & ~sand
    # Orchard: close the soil gaps between tree rows (rows are ~5-7 m apart).
    # Orchard = vegetation density >= 45 % within ~7 m: rows count, open ground with a
    # few scattered trees (block 16) does not.
    density = cv2.blur(veg.astype(np.float32), (7, 7))
    orchard = (density >= 0.45).astype(np.uint8)
    return {"veg": veg, "sand": sand & ~orchard.astype(bool), "orchard": orchard.astype(bool), "exg": exg}


def raster(poly: Polygon, shape: tuple[int, int]) -> np.ndarray:
    m = np.zeros(shape, np.uint8)
    polys = [poly] if poly.geom_type == "Polygon" else list(poly.geoms)
    for p in polys:
        cv2.fillPoly(m, [np.round(np.asarray(p.exterior.coords) * 8).astype(np.int32)], 1, shift=3)
    return m.astype(bool)


# ---------------------------------------------------------------- zones
def _cut(poly: Polygon, a, b) -> list[Polygon]:
    (x0, y0), (x1, y1) = a, b
    dx, dy = x1 - x0, y1 - y0
    line = LineString([(x0 - 20 * dx, y0 - 20 * dy), (x1 + 20 * dx, y1 + 20 * dy)])
    return list(split(poly, line).geoms)


def build_zones() -> tuple[dict[str, Polygon], dict[str, Polygon]]:
    hw = TRACE["track_half_width_px"]
    blocks = {k: Polygon(v) for k, v in TRACE["blocks"].items()}
    for k, p in blocks.items():
        assert p.is_valid, f"block {k} outline is not a valid polygon"
    parts: dict[str, list[Polygon]] = {}
    s7 = TRACE["splits"]["7"]
    north, south = sorted(_cut(blocks["7"], *s7["line"]), key=lambda g: g.centroid.y)
    parts["7"] = {"north": north, "south": south}
    s8 = TRACE["splits"]["8"]
    rest, strips = blocks["8"], []
    for a, b in s8["lines"]:
        left, right = sorted(_cut(rest, a, b), key=lambda g: g.centroid.x)
        strips.append(left)
        rest = right
    strips.append(rest)
    parts["8"] = strips
    zones, raw = {}, {}
    for zid, z in TRACE["zones"].items():
        blk = z["block"]
        if "blocks" in z:
            raw[zid] = unary_union([blocks[b] for b in z["blocks"]])
        else:
            raw[zid] = parts[blk][z["part"]] if "part" in z else blocks[blk]
        zones[zid] = raw[zid].buffer(-hw, join_style="mitre")
    return zones, raw, blocks


# ---------------------------------------------------------------- rows
def row_orientation(gray: np.ndarray, region: np.ndarray) -> tuple[float | None, float | None, float]:
    """Dominant row direction (deg clockwise from north) and row spacing (m) by 2-D FFT.

    Returns (angle, spacing, peak_strength). At ~1 m/px only the row spacing (5-8 m) is
    resolvable; tree spacing inside a row (3-4 m) is too close to the pixel size.
    """
    ys, xs = np.nonzero(region)
    if len(xs) < 400:
        return None, None, 0.0
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    g = gray[y0:y1, x0:x1].astype(np.float32)
    m = region[y0:y1, x0:x1]
    g = np.where(m, g - g[m].mean(), 0)
    size = 256
    G = np.zeros((size, size), np.float32)
    h, w = min(g.shape[0], size), min(g.shape[1], size)
    G[:h, :w] = g[:h, :w] * np.outer(np.hanning(h), np.hanning(w))
    P = np.abs(np.fft.fftshift(np.fft.fft2(G))) ** 2
    fy, fx = np.meshgrid(np.fft.fftshift(np.fft.fftfreq(size)), np.fft.fftshift(np.fft.fftfreq(size)), indexing="ij")
    fr = np.hypot(fx, fy)
    band = (fr > 1 / 12.0) & (fr < 1 / 3.0)  # periods 3-12 px
    Pb = np.where(band, P, 0)
    iy, ix = np.unravel_index(np.argmax(Pb), Pb.shape)
    strength = float(Pb[iy, ix] / (np.median(P[band]) + 1e-9))
    kx, ky = fx[iy, ix], fy[iy, ix]
    period_px = 1 / math.hypot(kx, ky)
    # The wave vector is perpendicular to the rows. Image y points south, so a vector
    # (vx, vy) has compass bearing atan2(vx, -vy).
    row_dir_deg = (math.degrees(math.atan2(kx, -ky)) + 90) % 180  # bearing, 0-180
    return row_dir_deg, period_px * M_PER_PX, strength


# ---------------------------------------------------------------- old geometry
def fit_old(zones: dict[str, Polygon]) -> tuple[np.ndarray, dict[str, float]]:
    """Least-squares affine map from the old sketch units to image pixels (zone centroids)."""
    ids = [z for z in zones if z in OLD["features"] and z != "zone_fruit_mix"]
    src = np.array([Polygon(OLD["features"][z]["points"]).centroid.coords[0] for z in ids])
    dst = np.array([zones[z].centroid.coords[0] for z in ids])
    A = np.hstack([src, np.ones((len(ids), 1))])
    T, *_ = np.linalg.lstsq(A, dst, rcond=None)
    res = {z: float(np.hypot(*(A[i] @ T - dst[i])) * M_PER_PX) for i, z in enumerate(ids)}
    return T, res


def old_in_px(T: np.ndarray, pts) -> list[tuple[float, float]]:
    P = np.hstack([np.asarray(pts, float), np.ones((len(pts), 1))]) @ T
    return [tuple(p) for p in P]


# ---------------------------------------------------------------- drawing
def _font(size: int):
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def draw(img_rgb: Image.Image, crop, scale, layers, out: Path, title: str) -> None:
    x0, y0, x1, y1 = crop
    im = img_rgb.crop(crop).resize(((x1 - x0) * scale, (y1 - y0) * scale), Image.BICUBIC)
    d = ImageDraw.Draw(im, "RGBA")
    f = _font(13)

    def tp(p):
        return ((p[0] - x0) * scale, (p[1] - y0) * scale)

    for kind, items, colour in layers:
        for name, geom in items:
            if kind == "poly":
                polys = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
                for g in polys:
                    pts = [tp(p) for p in g.exterior.coords]
                    d.line(pts, fill=colour, width=2)
                if name:
                    c = tp(geom.representative_point().coords[0])
                    d.text(c, name, fill=(255, 255, 255), font=f, anchor="mm", stroke_width=2, stroke_fill=(0, 0, 0))
            elif kind == "line":
                d.line([tp(p) for p in geom], fill=colour, width=2)
    d.rectangle([0, im.height - 22, im.width, im.height], fill=(0, 0, 0, 170))
    d.text((6, im.height - 18), f"{title}   |   {ATTRIBUTION}", fill=(255, 255, 255), font=f)
    im.save(out)


def rect(c, length, width, deg) -> Polygon:
    a = math.radians(deg)
    ux, uy = math.cos(a), math.sin(a)
    vx, vy = -uy, ux
    hl, hw = length / 2 / M_PER_PX, width / 2 / M_PER_PX
    cx, cy = c
    return Polygon([(cx + sx * hl * ux + sy * hw * vx, cy + sx * hl * uy + sy * hw * vy)
                    for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))])


# ---------------------------------------------------------------- geometry for the app
GEOMETRY_OUT = ROOT / "packages/map-model/src/farm-geometry.json"


def write_geometry(zones: dict[str, Polygon], raw: dict[str, Polygon], blocks: dict[str, Polygon], metrics: dict) -> None:
    """North-up, true-scale map units: 1 unit = half a z17 pixel (~0.50 m)."""
    fx0, fy0, fx1, fy1 = TRACE["map_frame_px"]
    upp = 2.0  # units per pixel
    m_per_unit = M_PER_PX / upp

    def u(p) -> list[float]:
        return [round((p[0] - fx0) * upp, 1), round((p[1] - fy0) * upp, 1)]

    def ring(poly: Polygon, tol_px: float = 0.4) -> list[list[float]]:
        g = poly.simplify(tol_px, preserve_topology=True)
        if g.geom_type != "Polygon":
            g = max(g.geoms, key=lambda q: q.area)
        return [u(p) for p in list(g.exterior.coords)[:-1]]

    def line(pts) -> list[list[float]]:
        return [u(p) for p in pts]

    features: dict[str, dict] = {}
    for zid, p in zones.items():
        m = metrics[zid]
        spacing = m["row_spacing_m"]
        if spacing is not None and not 3.5 <= spacing <= 8.5:
            spacing = None
        override = TRACE.get("row_overrides", {}).get(zid, {})
        spacing = override.get("row_spacing_m", spacing)
        angle = override.get("row_angle_deg", m["row_angle_deg"])
        features[zid] = {
            "points": ring(p),
            "legend_m2": TRACE["zones"][zid]["legend_m2"],
            "area_m2": round(raw[zid].area * M2_PER_PX2),
            "row_angle_deg": None if angle is None else round(angle, 1),
            "row_spacing_m": None if spacing is None else round(spacing, 1),
            "tree_spacing_m": None,
        }
        if "row_count" in override:
            features[zid]["row_count"] = override["row_count"]
    b = {k: v for k, v in TRACE["buildings"].items() if isinstance(v, dict)}
    house = building_poly(b["resthouse"])
    # the rest house joins the farm along the entrance track
    link = LineString([house.centroid.coords[0], (343, 331)]).buffer(5 / M_PER_PX)
    extra = [Polygon(v["points"]) for v in TRACE["other_areas"].values()]
    farm = unary_union([*blocks.values(), Polygon(TRACE["yard"]["points"]), house.buffer(4 / M_PER_PX), link, *extra])
    boundary = farm.buffer(3 / M_PER_PX, join_style="mitre").buffer(-1 / M_PER_PX).simplify(1.0)
    if boundary.geom_type != "Polygon":
        boundary = max(boundary.geoms, key=lambda q: q.area)
    boundary = Polygon(boundary.exterior)
    old = OLD["features"]
    features["boundary"] = {"points": ring(boundary, 1.0), "legend_m2": old["boundary"]["legend_m2"],
                            "area_m2": round(boundary.area * M2_PER_PX2)}
    for key, bid in (("tank", "tank"), ("well", "control")):
        r = building_poly(b[bid])
        features[key] = {"points": ring(r, 0), "legend_m2": old[key]["legend_m2"], "area_m2": round(r.area * M2_PER_PX2)}

    net = TRACE["network"]
    trunks = {k: LineString(v) for k, v in net["mainline"].items()}
    valves = {}
    for zid, vp in net["valves"].items():
        pt = Point(vp)
        assert zones[zid].contains(pt), f"valve of {zid} is outside the zone"
        best = min(trunks, key=lambda k: trunks[k].distance(pt))
        tap = trunks[best].interpolate(trunks[best].project(pt))
        valves[zid] = {"tap": u(tap.coords[0]), "valve": u(vp), "trunk": best}

    lat0, lon0 = px_to_latlon(fx0, fy0)
    lat1, lon1 = px_to_latlon(fx1, fy1)
    geom = {
        "source": "Traced on Esri World Imagery z17 (tools/map-geometry/satellite_trace.json, owner-approved 2026-11-23). "
                  "Areas are measured on the satellite; legend_m2 is the owner's sketch legend.",
        "attribution": ATTRIBUTION,
        "georef": {
            "north_up": True,
            "m_per_unit": round(m_per_unit, 4),
            "image": TRACE["image"]["file"],
            "frame_px": [fx0, fy0, fx1, fy1],
            "units_per_px": upp,
            "top_left_latlon": [round(lat0, 6), round(lon0, 6)],
            "bottom_right_latlon": [round(lat1, 6), round(lon1, 6)],
        },
        "viewBox": [0, 0, (fx1 - fx0) * upp, (fy1 - fy0) * upp],
        "m2_per_unit2": round(m_per_unit**2, 5),
        "features": features,
        "network": {
            "guessed": True,
            "mainline": {k: line(v) for k, v in net["mainline"].items()},
            "refill": line(net["refill"]),
            "valves": valves,
        },
        "tracks": [line(v) for v in TRACE["tracks"].values()],
        # narrow footpaths between the block 8 strips (owner 2026-11-23)
        "paths": [line(blocks["8"].intersection(LineString(_extend(a, b))).coords) for a, b in TRACE["splits"]["8"]["lines"]],
        "equipment": {k: {"at": u(v["at"]), "kind": v["kind"]} for k, v in TRACE["equipment"].items()},
        "buildings": {
            k: {"points": ring(building_poly(v), 0), "kind": v["kind"], "sprite": v.get("sprite"), "name": v["en"], "name_ar": v["ar"]}
            for k, v in b.items() if k != "booster"
        },
        "other_trees": {k: {"points": ring(Polygon(v["points"]), 0), "species": ["almond", "lemon", "orange", "apricot", "plum"]}
                        for k, v in TRACE["other_areas"].items()},
        "surroundings": {
            "orchards": [ring(Polygon(v), 0) for v in TRACE["surroundings"]["orchards"].values()],
            "wadi": {"width": round(TRACE["surroundings"]["wadi"]["width_m"] / m_per_unit, 1),
                     "points": line(TRACE["surroundings"]["wadi"]["points"])},
        },
    }
    GEOMETRY_OUT.write_text(json.dumps(geom, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {GEOMETRY_OUT.relative_to(ROOT)}: viewBox {geom['viewBox']}, {m_per_unit:.4f} m/unit, "
          f"boundary {features['boundary']['area_m2']} m2")


def _extend(a, b, k: float = 3.0) -> list[tuple[float, float]]:
    (x0, y0), (x1, y1) = a, b
    dx, dy = x1 - x0, y1 - y0
    return [(x0 - k * dx, y0 - k * dy), (x1 + k * dx, y1 + k * dy)]


def building_poly(b: dict) -> Polygon:
    """A building traced as an outline, or a rotated rectangle (centre, size in m, angle)."""
    if "points" in b:
        return Polygon(b["points"])
    return rect(b["c"], b["len"], b["wid"], b["deg"])


# ---------------------------------------------------------------- main
def main() -> None:
    bgr = cv2.imread(str(SAT / "farm_esri_z17.jpg"))
    rgb = Image.open(SAT / "farm_esri_z17.jpg").convert("RGB")
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    mk = masks(bgr)
    shape = gray.shape
    cv2.imwrite(str(SAT / "trace_debug_orchard.png"), mk["orchard"].astype(np.uint8) * 255)
    cv2.imwrite(str(SAT / "trace_debug_sand.png"), mk["sand"].astype(np.uint8) * 255)

    zones, raw, blocks = build_zones()
    union = unary_union(list(zones.values()))
    # Coverage: orchard pixels near our blocks (within 8 m of a block outline) that a zone covers.
    near = raster(unary_union([b.buffer(8 / M_PER_PX) for b in blocks.values()]), shape)
    ours = raster(union, shape)
    orch_near = mk["orchard"] & near
    coverage = (orch_near & ours).sum() / max(orch_near.sum(), 1)

    rows = []
    metrics: dict[str, dict] = {}
    for zid, p in zones.items():
        m = raster(p, shape)
        n = m.sum()
        fill = (mk["orchard"] & m).sum() / n
        sand = (mk["sand"] & m).sum() / n
        area = raw[zid].area * M2_PER_PX2  # to the track centre line, like the sketch legend
        legend = TRACE["zones"][zid]["legend_m2"]
        ang, spacing, strength = row_orientation(gray, m)
        metrics[zid] = {"row_angle_deg": ang, "row_spacing_m": spacing, "strength": strength}
        rows.append((zid, TRACE["zones"][zid]["block"], area, p.area * M2_PER_PX2, legend, fill, sand, ang, spacing, strength))

    T, resid = fit_old(zones)

    print(f"{'zone':22s} {'block':5s} {'area m2':>8s} {'inset':>6s} {'legend':>8s} {'diff':>6s} {'fill':>5s} {'sand':>5s} {'row°':>5s} {'row m':>5s}  flags")
    for zid, blk, area, inset, legend, fill, sand, ang, spacing, strength in rows:
        diff = area / legend - 1
        flags = []
        if abs(diff) > 0.20:
            flags.append("AREA>20%")
        need = 0.70 if blk == "8" else 0.85
        if fill < need:
            flags.append(f"FILL<{need:.0%}")
        if sand > 0.15:
            flags.append("SAND>15%")
        if strength < 8:
            flags.append("rows weak")
        a = f"{ang:5.0f}" if ang is not None else "    -"
        s = f"{spacing:5.1f}" if spacing is not None else "    -"
        print(f"{zid:22s} {blk:5s} {area:8.0f} {inset:6.0f} {legend:8.0f} {diff:+6.0%} {fill:5.0%} {sand:5.0%} {a} {s}  {' '.join(flags)}")
    for name, pts in TRACE["controls"].items():
        if name == "about":
            continue
        m = raster(Polygon(pts), shape)
        print(f"control, {name}: fill {(mk['orchard'] & m).sum() / m.sum():.0%}, sand {(mk['sand'] & m).sum() / m.sum():.0%}")
    print(f"coverage of orchard pixels within 8 m of blocks 6-15 (includes neighbours' orchards and wadi trees): {coverage:.1%}")
    print("old sketch -> image affine fit, centroid residual (m):",
          ", ".join(f"{k.removeprefix('zone_')} {v:.0f}" for k, v in resid.items()))
    sx = math.hypot(T[0, 0], T[0, 1]) * M_PER_PX
    sy = math.hypot(T[1, 0], T[1, 1]) * M_PER_PX
    rot = math.degrees(math.atan2(T[0, 1], T[0, 0]))
    print(f"old sketch unit -> metres: x {sx:.3f}, y {sy:.3f} (old file says {math.sqrt(OLD['m2_per_unit2']):.3f}); rotation {rot:.1f} deg")

    # ---- overlays
    zone_layer = [(z.removeprefix("zone_"), p) for z, p in zones.items()]
    track_layer = [(k, v) for k, v in TRACE["tracks"].items()]
    bld_layer = [(k, building_poly(b)) for k, b in TRACE["buildings"].items() if isinstance(b, dict)]
    other_layer = [(k.replace("_", " "), Polygon(v["points"])) for k, v in TRACE["other_areas"].items()]
    crop = (170, 260, 600, 740)
    draw(rgb, crop, 2, [("line", track_layer, (255, 200, 0, 200)), ("poly", zone_layer, (255, 60, 60, 255)),
                        ("poly", other_layer, (200, 255, 120, 255)), ("poly", bld_layer, (80, 200, 255, 255))],
         SAT / "trace_overlay.png", "New trace: zones (red), other trees (lime), tracks (yellow), buildings (blue)")
    old_layer = [(None, Polygon(old_in_px(T, f["points"]))) for k, f in OLD["features"].items() if k.startswith("zone_")]
    draw(rgb, crop, 2, [("poly", old_layer, (255, 160, 0, 255)), ("poly", zone_layer, (60, 255, 120, 255))],
         SAT / "trace_vs_old.png", "New (green) vs old sketch best-fit (orange)")
    raw_layer = [(z.removeprefix("zone_"), p) for z, p in raw.items()]
    ticks = []
    for zid, *_rest in rows:
        ang = _rest[6]
        if ang is None:
            continue
        cx, cy = raw[zid].representative_point().coords[0]
        dx, dy = math.sin(math.radians(ang)) * 12, -math.cos(math.radians(ang)) * 12
        ticks.append((zid, [(cx - dx, cy - dy + 8), (cx + dx, cy + dy + 8)]))
    if len(sys.argv) == 6 and sys.argv[1] == "--zoom":
        zx0, zy0, zx1, zy1 = map(int, sys.argv[2:])
        draw(rgb, (zx0, zy0, zx1, zy1), max(2, 720 // max(zx1 - zx0, zy1 - zy0)),
             [("poly", old_layer, (255, 160, 0, 255)), ("line", track_layer, (255, 230, 0, 160)),
              ("poly", raw_layer, (60, 255, 120, 255)), ("line", ticks, (255, 0, 255, 255)),
              ("poly", bld_layer, (80, 200, 255, 255))],
             SAT / "trace_zoom.png", "Zoom: new to track centre (green), old fit (orange), measured row direction (magenta)")
    draw(rgb, crop, 2, [("poly", zone_layer, (255, 60, 60, 255)), ("line", ticks, (255, 0, 255, 255))],
         SAT / "trace_rows.png", "Measured row direction per zone (magenta)")
    print("wrote", ", ".join(p.name for p in sorted(SAT.glob("trace_*.png"))))
    if "--write" in sys.argv:
        write_geometry(zones, raw, blocks, metrics)


if __name__ == "__main__":
    main()
