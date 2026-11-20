# Map survey: satellite + owner answers (2026-11-20)

This is the ground truth for re-drawing the farm map (Milestone F). The owner confirmed each item below by looking at the satellite images.

**Imagery:** Esri World Imagery, zoom 17 (about 1.01 m/px), stitched by `tools/map-geometry/fetch_esri_tiles.py`. Attribution: **Source: Esri, Maxar, Earthstar Geographics**. Approved for checking and tracing this private farm app; revisit the licence before any commercial product.

**Bbox:** lon 14.06610–14.07462, lat 32.51265–32.51985 (±400 m around the site, see [FARM_SITE.md](FARM_SITE.md)).

**Images** (git-ignored, in `design/satellite/`):
- `farm_esri_z17.jpg` (+ `.json` metadata)
- `farm_numbered.jpg`: blocks 1–17 and buildings A–C
- `farm_proposal.jpg`: the mapping below, confirmed
- `zoom_A_labelled.jpg`: structures S1–S8

`farm_numbered.jpg` and `farm_proposal.jpg` are a 2× crop of the z17 image: crop origin (60, 90) in z17 pixels, so z17_px = 60 + X/2, 90 + Y/2. `zoom_A_labelled.jpg` is a 4× crop at origin (200, 280).

The image date is unknown, and the owner is **not sure** whether anything has changed since (new blocks, trees, buildings, tracks). Trace what's visible, and flag anything that looks inconsistent with the zone legend areas.

## What is the farm
- **Ours (irrigated by this system):** blocks **6–15**.
- **Not ours:** blocks **1, 2, 3, 4, 5, 16, 17**, the building cluster B (far north-west), and the shed on the north-east edge. Show these as **faded, non-clickable surroundings** with no labels.
- **Wadi:** the dry stream bed along the **east side**, drawn as a realistic dry gully in the faded surroundings.
- **Entrance:** from the **north track**, past house **C**, down to the buildings.

## Block → zone (confirmed)
Approximate centre points (lat, lon) are read from the image, ±10 m.

| Zone | Block | Centre ≈ | Legend area (m²) | Notes |
|------|-------|----------|-----------------:|-------|
| `zone_zaytoun` | **6 + 9** | 32.516141, 14.069239 (6) · 32.515237, 14.068675 (9) | 22,882 | West of the buildings. 6 and 9 are one zone. |
| `zone_rumman_6` | **7, north part** | 32.516684, 14.070929 | 8,140 | Split of block 7 at the cross-track level with the building cluster: north of it is rumman_6. |
| `zone_rumman_5` | **7, south part** | 32.515915, 14.071036 | 6,399 | South of that line. |
| `zone_zaytoun_2` | **8, east strip** | 32.515531, 14.070526 (block 8) | 1,538 | Next to rumman_5. |
| `zone_enab` | **8, middle strip** | ↑ | 702 | |
| `zone_rumman_ummahat` | **8, west strip** | ↑ | 1,428 | Nearest rumman_jadeed (block 11). |
| `zone_rumman_jadeed` | **11** | 32.515056, 14.069748 | 9,299 | |
| `zone_fruit_mix` | **10** | 32.514694, 14.069158 | 10,863 | Bright green block. |
| `zone_rumman_3` | **12** | 32.514785, 14.070929 | 5,447 | |
| `zone_rumman_4` | **13** | 32.515101, 14.071599 | 7,081 | |
| `zone_rumman_2` | **14** | 32.513880, 14.071412 | 7,085 | |
| `zone_rumman_1` | **15** | 32.514061, 14.071975 | 4,980 | |

Block 8 order, from the rumman_5 side going west: **zaytoun_2 → enab → rumman_ummahat**.

## Buildings (confirmed)
| Label | What | Centre ≈ (lat, lon) | On the map |
|-------|------|---------------------|------------|
| **S1, S2, S3** | **Chicken house: barn/brooder (عنبر / حضانة)**, plus storage and tools | 32.516424, 14.069990 · 32.516277, 14.070245 · 32.516463, 14.070183 | Real footprint, labelled, not interactive |
| **S5** | **Workers' rooms** | 32.516096, 14.070298 | Real footprint, labelled |
| **S6** | **Control room + well** | 32.516085, 14.070030 | Interactive equipment: control room and wellhead (replaces the old `well_room`/`wellhead` positions) |
| **S7** | **Water tank** (closed concrete) | 32.515897, 14.070009 | Interactive: tank with level gauge |
| next to S7 | **Booster pump** | beside the tank | Interactive: booster pad next to the tank |
| **C** | **House** (small house to stay in) | 32.517103, 14.069923 | Real footprint, labelled |
| S4, S8 | Unknown, skipped by the owner | — | Don't draw as buildings; ground or trees only |

The building cluster is **not** all control/well. Only S6 is the control room and well, and S7 is the tank.

## Pipes
- The mainline runs **along the tracks between blocks**, starting from S6 (well) and S7 (tank/booster). Each block's valve sits at its corner next to the track.
- Pipes aren't visible from the satellite, so mark the routes **guessed** in the geometry metadata.

## Trees
- Measure each block's **real row direction and row/tree spacing** from the image, and place trees on those rows (`trees.ts`). Individual tree detection is **not** required.

## Process
1. Georeference the image into the map's coordinate space. The current geometry is squashed north–south and probably rotated: the real footprint is about 510 × 600 m, the old map 515 × 457 m.
2. Trace the blocks, tracks, building footprints, the wadi edge and the farm boundary (around blocks 6–15 and the building cluster).
3. Show the owner an **overlay** (satellite + old + new) and an **area table** (legend vs old vs new) **before** replacing `farm-geometry.json`.
