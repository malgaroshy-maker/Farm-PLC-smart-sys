# Satellite Imagery for Farm Tracing (Milestone F)

**Source:** Esri World Imagery (zoom 17 tiles stitched via `tools/map-geometry/fetch_esri_tiles.py`)  
**Attribution:** Source: Esri, Maxar, Earthstar Geographics  
**Usage:** Tracing and geometric verification for private farm management system. Revisit the licence before any commercial product. Images are git-ignored.  

## Site Details
- **Centroid:** 32.516250°N, 14.070361°E (32°30'58.5"N 14°04'13.3"E)
- **Bounding Box:** lon [14.06610, 14.07462], lat [32.51265, 32.51985] (±400 m)
- **Resolution:** Zoom 17 (~1.007 m/pixel), 794 × 796 px (16 stitched tiles)

## Reference Images
- `farm_esri_z17.jpg`: Base satellite mosaic
- `farm_numbered.jpg`: Ground truth blocks 1–17 and building clusters A–C
- `farm_proposal.jpg`: Confirmed block-to-zone mapping (blocks 6–15)
- `zoom_A_labelled.jpg`: High-resolution crop of structures S1–S8 (chicken house, workers, control room/well S6, tank S7, house C)
