# Farm map geometry

**Current source (2026-11-23): the satellite trace below.** The older sketch-based tools in this folder are kept for history.

`packages/map-model/src/farm-geometry.json` was originally traced from the owner's sketch
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
2. **Trace (owner-approved 2026-11-23).**
   - `satellite_trace.json` holds the outlines **traced by eye** on `farm_esri_z17.jpg` (z17 pixel coordinates): blocks along the track centre lines (neighbours share edges), the block 7 split, the block 8 strip lines, tracks, buildings, the guessed pipe/valve routes, the mixed-fruit strip, the surroundings and the wadi. Each decision cites `docs/MAP_SURVEY.md` or the owner's answer.
   - `satellite_retrace.py` does not move the outlines. It measures them against the image and draws the overlays:
     ```
     uv run --no-project --with opencv-python-headless --with numpy --with shapely --with pillow python tools/map-geometry/satellite_retrace.py [--zoom x0 y0 x1 y1] [--write]
     ```
     `--write` regenerates `packages/map-model/src/farm-geometry.json`: north-up, true scale, 1 unit = ½ z17 pixel = 0.5035 m, viewBox 900 × 980 (frame px 165–615 × 255–745). Zone polygons are inset by half a track width (2 m).
   - **Checks.** Fill and sand use an orchard mask (vegetation density ≥ 45 % within 7 m). The controls prove that mask can tell orchard from ground: block 16 gives fill 54 % / sand 31 %, the wadi 2 % / 94 %. Every zone is 99–100 % orchard with ≤ 1 % sand.
   - **Independent cross-check.** The owner's old sketch (kept as `sketch-geometry.json`), fitted to the trace with one affine map (x 0.452, y 0.538 m/unit, rotation 0.5°), lands within **1–5 m** at every zone centroid. The old map had the wrong aspect, but it was not rotated.
   - Row bearing and spacing come from a 2-D FFT per zone. At ~1 m/px only the row spacing is resolvable; tree spacing within a row uses the crop default.

   | zone | block | satellite m² | legend m² | diff | row bearing | row spacing |
   |---|---|---:|---:|---:|---:|---:|
   | zaytoun | 6+9 | 21,090 | 22,882 | −8 % | 56° | 6.1 m |
   | rumman_6 | 7 N | 7,791 | 8,140 | −4 % | 158° | 4.0 m |
   | rumman_5 | 7 S | 6,616 | 6,399 | +3 % | 158° | 4.0 m |
   | rumman_ummahat | 8 W | 1,614 | 1,428 | +13 % | 155° | 5.0 m (big mother trees) |
   | enab | 8 mid | 734 | 702 | +5 % | 155° | 2.8 m trellis |
   | zaytoun_2 | 8 E | 1,737 | 1,538 | +13 % | 154° | 7.5 m (profile) |
   | fruit_mix | 10+17 | 10,871 | 10,863 | +0 % | 54° | 5.4 m |
   | rumman_jadeed | 11 | 10,760 | 9,299 | +16 % | 55° | 4.0 m |
   | rumman_3 | 12 | 5,230 | 5,447 | −4 % | 153° | 4.1 m |
   | rumman_4 | 13 | 7,891 | 7,081 | +11 % | 158° | 4.0 m |
   | rumman_2 | 14 | 7,730 | 7,085 | +9 % | 154° | 4.1 m |
   | rumman_1 | 15 | 5,595 | 4,980 | +12 % | 157° | 4.0 m |

   Areas run to the track centre line, like the sketch legend. The farm boundary (blocks 6–15 and 17, the building yard, house C and the mixed-fruit strip) is **9.97 ha**. The seed's `total_area_ha` is 11.9, from the sketch boundary.
   - Pipes and valves are **guessed** (`network.guessed: true`): they run along the tracks from the tank (S7) and the well (S6).
