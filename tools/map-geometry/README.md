# Farm map geometry

`packages/map-model/src/farm-geometry.json` was traced from the owner's sketch
(`docs/algaroshy_farm_layout_landscape_fixed.svg`, an embedded PNG plot of GPS data at ≈32.51°N).
No original coordinate file exists. If one turns up (KML/GeoJSON), replace this tracing.

## How it was made
1. `extract_v1_by_colour.py` traces each zone's own line colour (matplotlib tab10). This is exact where outlines are closed.
2. `extract_v2_floodfill.py` flood-fills between *all* drawn lines and picks the region by label and legend area.
3. `extract_v3_bridged.py` uses per-colour outlines with gap bridging, for outlines broken by label boxes.
4. `finalize.py` takes the sharpest source per zone, uses hand-read quads for the three thin strips (from a 4× crop), closes the boundary where it runs off the sketch, and normalises to a 1000-wide viewBox.
5. `network.py` adds the **plausible** mainline, valves, dirt tracks and equipment positions (edit its waypoints to correct them).

## Verification (area ÷ legend)
All 15 features fall within ±12%. Most are within ±5%. The small, consistent overshoot comes from line thickness.
`packages/map-model/src/index.test.ts` enforces this. `verification_overlay.png` shows the traced polygons over the sketch.

| feature | ratio | feature | ratio |
|---|---|---|---|
| Pomegranate 1 | 0.98 | Olives | 1.01 |
| Pomegranate 2 | 1.00 | Olives 2 | 1.07 |
| Pomegranate 3 | 1.05 | Grapes | 1.11 |
| Pomegranate 4 | 1.00 | Mothers | 1.08 |
| Pomegranate 5 | 1.03 | New Pomegranate | 1.04 |
| Pomegranate 6 | 1.00 | Fruit mix | 1.00 |
| Tank | 1.11 | Well room | 1.11 |
| Boundary | 1.08 | | |

Requires `opencv-python-headless` and `numpy`.

## Satellite Imagery & Georeferencing Workflow (Milestone F)

On 2026-11-20, the owner decided to keep the current traced polygons for Milestone F and prepare the satellite georeferencing workflow for when satellite imagery is provided:

1. **Bbox Coordinates:** Site centroid is `32.516250, 14.070361` (32°30'58.5"N, 14°04'13.3"E).
   ±400 m bounding box:
   - Latitude: `[32.51265, 32.51985]`
   - Longitude: `[14.06611, 14.07461]`
2. **Imagery Storage:** Store high-resolution satellite imagery or orthophotos under `design/satellite/` (e.g. `design/satellite/site_ortho.png`). Document imagery source, capture date, resolution, and licensing in `design/satellite/README.md`.
3. **Control Point Georeferencing:**
   - Map ground control points (GCPs): tank corner, wellhead enclosure, mainline boundary tees, and road intersections.
   - Transform coordinates into the SVG coordinate space (`viewBox="0 0 1000 650"`).
   - Re-run `network.py` and `finalize.py` with updated waypoints.
4. **Validation:** Ensure re-traced zone polygons maintain area ratios within ±12% of the surveyed legend in `packages/map-model/src/index.test.ts`.

