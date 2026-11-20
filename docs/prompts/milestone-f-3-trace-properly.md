# Prompt — Milestone F round 3: trace the farm properly + last fixes

Paste this into the agent session that worked on `milestone-f-map-ui`, or into a fresh session at the repo root.

---

The round-2 work on `milestone-f-map-ui` was reviewed live.

**What works:**
- Tokens are gone from every log: WS auth is now a first message, and the logs show `WebSocket /ws` only.
- The noisy sync logs are quiet, and the daily briefing loads (200).
- The phone nav is Dashboard / Zones / Alarms / Schedules.
- All suites pass (API 196, simulator 27, web 89, launcher 4).
- You correctly did **not** replace `farm-geometry.json` before approval.

**What doesn't:** the issues below, the biggest being that the satellite tracing is wrong.

## 0. Commit first
All your round-2 work is **uncommitted** (25 modified files plus `tools/map-geometry/satellite_retrace.py` and `design/satellite/README.md`). Commit it on `milestone-f-map-ui` in logical commits before starting. **Don't merge or push.**

## 1. The tracing is wrong: redo it so it follows the real edges
Look at `design/satellite/overlay_comparison.png`:
- Every new polygon in `satellite_retrace.py` is an **upright quadrilateral** with hand-typed corners. The real blocks are **tilted**: rows and tracks run roughly **NW→SE**.
- The boxes cut across rows, leave real orchard outside (west side of block 7, the edges of block 6), and **`zone_fruit_mix` (block 10) covers bare sand with no trees**.
- The tracks are straight guessed lines, not the visible dirt tracks.
- The block → zone mapping itself is right. Keep it exactly as in **`docs/MAP_SURVEY.md`**.

Redo the trace **from the image**, not from guessed rectangles:

1. **Vegetation mask.** Compute a vegetation index on `farm_esri_z17.jpg`:
   - e.g. Excess Green `ExG = 2G − R − B` (normalised) + Otsu threshold + morphological close/open
   - plus a **sand/track mask** (bright, low saturation)

   Save both masks as debug images (git-ignored).
2. **Block outlines.**
   - For each confirmed block (6–15, with the splits of 7 and 8 from `MAP_SURVEY.md`), seed from the survey's centre point and grow the region inside the vegetation mask, bounded by the track mask.
   - Take the outline and simplify it (Douglas–Peucker, tolerance ≈ 2 m). Blocks are often parallelograms, so allow 4–8 vertices; **don't force axis-aligned shapes**.
   - Neighbouring blocks must **share edges** along the track between them. Snap common edges; no gaps or overlaps beyond the track width.
3. **Splits inside one block:**
   - **Block 7:** split at the cross-track level with the building cluster: rumman_6 to the north, rumman_5 to the south.
   - **Block 8:** three strips, zaytoun_2 (east, next to rumman_5) → enab → rumman_ummahat (west). Use the visible strip boundaries (row texture changes) where you can see them, and the legend area ratios only where you can't.
4. **Row direction and spacing per block:**
   - Measure the dominant row angle (2-D FFT or Hough on the block's vegetation mask) and the row/tree spacing (autocorrelation along and across the rows).
   - Store `row_angle_deg`, `row_spacing_m` and `tree_spacing_m` per zone, and feed them to `trees.ts` (this replaces the current per-crop defaults where measured).
5. **Tracks:**
   - Skeletonise the track mask and trace the real tracks as polylines (the main north entrance track past house C, the cross-tracks between blocks, the track along the wadi).
   - The farm-life walk graph (`life.ts`) and the pipe routes (mainline along the tracks, valves at block corners next to the track) follow these tracks. Pipes stay marked **guessed**.
6. **Buildings:** trace real footprints for S1–S3 (chicken house), S5 (workers' rooms), S6 (control room + well), S7 (tank) with the booster next to it, and C (house), at the survey positions.
7. **Boundary and surroundings:**
   - The farm boundary wraps blocks 6–15, the building cluster and house C.
   - Blocks 1–5, 16, 17, the wadi (east) and the neighbours' buildings are **faded context**: not interactive, no labels.
8. **Georeference to the app.**
   - Keep north-up and true scale (1.007 m/px at z17).
   - Update `viewBox`, `m2_per_unit2` and the transform metadata. Check that the map still fits the dashboard aspect, and adjust the layout if the new aspect is taller.
9. **Quantitative acceptance (print these in your report):**
   - **Vegetation fill:** ≥ 85 % of each zone polygon's pixels are vegetation, except block 8 strips (≥ 70 %).
   - **Coverage:** ≥ 90 % of the vegetation pixels of blocks 6–15 fall inside some zone polygon.
   - **No bare-sand zones:** no zone polygon has > 15 % sand-mask pixels.
   - **Areas:** each zone's area vs the sketch legend. Report the difference, and **flag any zone with > 20 % difference** for the owner instead of bending the polygon to match the legend. The satellite wins over the legend unless the owner says otherwise.
   - **Row angle:** the measured angle per zone, and the trees in the rendered map visually align with the satellite rows.
10. **Owner approval.**
    - Produce three images:
      - `overlay_v2.png`: satellite + new outlines + zone labels, 2× zoom
      - the same with the old outlines in a second colour
      - a side-by-side of the **rendered app map** vs the satellite
    - Plus the table from step 9.
    - **Ask the owner to approve before replacing `farm-geometry.json`.** Only after approval: update the area test (new expected areas and tolerances), regenerate trees, the walk graph, chip anchors and equipment, and check desktop + phone screenshots (outside the repo).
- Put the tracing code in `tools/map-geometry/satellite_retrace.py` (rewrite it). It must be **re-runnable** (image in → geometry out + overlays + metrics) and documented in `tools/map-geometry/README.md`. No hand-typed corner coordinates except the survey seed points.

## 2. Launcher still offers virtual addresses
- In demo mode the launcher still prints **`192.168.56.1`** (VirtualBox) as "Phone on the same Wi-Fi", and Vite's own Network list shows `169.254.x.x` and `192.168.56.1`.
- Filter by **interface name** (VirtualBox, vEthernet/Hyper-V, Docker, WSL, VMware, Loopback) plus `169.254.0.0/16` for **both** the launcher's list and the Vite `--host` output. Bind Vite to the chosen LAN address, or suppress its list.
- Test with mocked `os.networkInterfaces()` that includes a VirtualBox adapter.

## 3. Briefing text errors
- The live briefing said **"all 13 irrigation zones"**. The farm has **12**. Build the facts block from the DB (zone count, names, crops) and assert it in a test.
- It contained a garbled mixed-language phrase, **"…وإ pent reference = 3.28 مم"**. Run the briefing (and advisor) output through the **Arabic-purity guard** like the explain and chat answers, with retry on the next model.
- Format ET₀ as a proper Arabic phrase ("التبخر-نتح المرجعي ET₀ = 3.28 مم").

## 4. Verify
- All green:
  - api/simulator `pytest` + ruff
  - web vitest/eslint/build
  - launcher tests
  - map-model tests (updated areas, only after approval)
  - `run.bat --smoke`
- **Live** (`run.bat demo`; the owner signs in; never type passwords):
  - the phone list shows only real LAN addresses
  - the briefing says 12 zones with clean Arabic
  - after approval, the new map renders correctly with trees on the real row directions at desktop 1440×1000 and phone 375×812
- Docs: `tools/map-geometry/README.md` (method + metrics), `docs/MAP_SURVEY.md` (add the measured row angles, spacing and final areas), `design/DESIGN_BRIEF.md`, `CHANGELOG.md`, `PROJECT_STATUS.md`.

## Rules
- Commit on `milestone-f-map-ui` only. **Don't merge or push.** The owner's reviewer reviews again.
- **Ask the owner** before replacing the geometry and for anything not covered by `MAP_SURVEY.md`. Never write a decision into the docs that the owner didn't make.
- No fake data. Don't commit imagery (git-ignored), screenshots or throwaway scripts. Attribution: "Source: Esri, Maxar, Earthstar Geographics".
- Report honestly with command output and the metrics table.
