# Farm site — مزرعة الجروشي

The owner provided the exact location on 2026-11-19.

| Field | Value |
|-------|-------|
| Coordinates (DMS) | **32°30'58.5"N 14°04'13.3"E** |
| Coordinates (decimal) | **32.516250, 14.070361** |
| Timezone | Africa/Tripoli (UTC+2, no DST) |
| Google Maps | https://www.google.com/maps?q=32.516250,14.070361 |

## Use in the system
- **Weather (Milestone E):** Open-Meteo forecast at `latitude=32.516250&longitude=14.070361&timezone=Africa/Tripoli`. This replaces the old Tripoli-city placeholder (`32.8872, 13.1803`) in `apps/api/app/config.py` and `.env.example` (`WEATHER_LATITUDE` / `WEATHER_LONGITUDE`).
- **Sun position:** day/night lighting on the map and the evapotranspiration estimates should use these coordinates rather than a fixed sunrise/sunset curve.
- **Map:** the farm geometry in `packages/map-model` was traced from the owner's sketch. Satellite imagery at these coordinates can later be used to check zone outlines, track and pipe routes, and the positions of the tank, booster and well room. Any correction goes through `tools/map-geometry/` and the area test.
  - *Milestone F update (2026-11-20):* The owner decided to keep the verified traced polygons for Milestone F (areas within ±12% of surveyed sketch). The workflow and bounding box (±400 m) are documented in `tools/map-geometry/README.md` for future aerial calibration.
