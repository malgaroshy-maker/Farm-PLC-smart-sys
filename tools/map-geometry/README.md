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

## Satellite Imagery & Georeferencing (Milestone F)

On 2026-11-20, the owner decided: Use satellite imagery to correct the drawing. Keep our generated photoreal map (offline, consistent look), but re-trace zones, tracks, buildings (tank, booster, control room, wellhead) and the mainline/valves to match reality.
Attribution: **Source: Esri, Maxar, Earthstar Geographics** (noted in `design/satellite/README.md` and here; revisit the licence before any commercial product).

1. **Bbox Coordinates & Tile Stitching:**
   - Site centroid: `32.516250, 14.070361` (32°30'58.5"N, 14°04'13.3"E).
   - ±400 m bounding box: lon `14.06610–14.07462`, lat `32.51265–32.51985`.
   - Stitched with `tools/map-geometry/fetch_esri_tiles.py` (zoom 17, ~1.007 m/px, 16 tiles, 794×796 px).
2. **True North-Up Georeferencing:**
   - North-up true orientation ($\theta = 0.0^\circ$).
   - SVG coordinate space: `viewBox="0 0 1000 886.8"`, $S = 1.6$, `m2_per_unit2 = 0.396113` ($1\text{ unit} \approx 0.629\text{ m}$).
3. **Precision Retracing & Quantitative Acceptance Metrics:**
   - Automated via `tools/map-geometry/satellite_retrace.py`.
   - Vegetation mask computed via normalized Excess Green ($ExG > 0.07$) + morphological close/open.
   - Sand / track mask isolates dirt tracks (brightness $V > 115$, saturation $S < 85$, $ExG < 0.08$).
   - Tilted zone polygons derived from satellite ground truth, snapped along visible dirt tracks.
   - Strip 8 split into 3 sub-strips: `zone_rumman_ummahat` (west), `zone_enab` (middle), `zone_zaytoun_2` (east).
   - Dominant row angle, row spacing, and tree spacing measured per zone via 2D FFT.
   - Real building footprints for S1–S3, S5, S6 (control/well), S7 (tank + booster), and C (house).
   - **Acceptance Criteria Verification:**
     * Vegetation fill $\ge 85\%$ per zone (strip 8 $\ge 70\%$): **All 12 zones pass** (87.9% – 100.0%).
     * Bare-sand check: no zone $> 15\%$ sand: **All 12 zones pass** (all $< 10.5\%$).
     * Blocks 6–15 Agricultural Vegetation Coverage: **91.3%** (target $\ge 90.0\%$, **Pass**).
4. **Approval Workflow & Deliverables:**
   - `design/satellite/overlay_v2.png`: 2× zoom satellite base + new zone outlines + zone labels.
   - `design/satellite/overlay_comparison_v2.png`: satellite base + new outlines (green) + old outlines (orange).
   - `design/satellite/app_vs_satellite.png`: side-by-side comparison of the rendered app map vs satellite image.
   - `packages/map-model/src/farm-geometry.json` is preserved unmodified until the owner explicitly approves the comparison.

