# Milestone C — Design Brief (decided with the owner, 2026-11-18)

## Audience & modes
- **Both** owners/investors and engineers.
- Clean app by default. Technical screens (Simulator page, fault buttons) are **admin-only, behind a "presenter" toggle**.

## Language & theme
- **Arabic by default, full RTL**, with a one-click EN toggle.
- **Keep the dark HMI look and refine it** (cyan accents). No light theme for now.
- Branding: **مزرعة الجروشي / Algaroshy Farm** with a generated **pomegranate + water-drop** logo.

## Map
- **Exact zone shapes** traced from the sketch (`docs/algaroshy_farm_layout_landscape_fixed.svg`, which is an embedded PNG plot of GPS data, ≈32.51°N).
  - No coordinate file exists in the project, so polygons are extracted by line colour and **verified against the legend areas**.
- **Photoreal (style A)** assets made with the owner's ChatGPT/Codex subscription (`codex exec -m gpt-6.1-terra`, image_generation). Samples are in `design/style-samples/`.
  - Crop textures clipped into each zone: pomegranate, olive, **grape on trellis rows**, mixed peach + apricot + **plum (عوينة)**.
  - Density: **all trees mature**.
  - **Drip irrigation on all zones**: show wet spots spreading under trees while a zone runs.
- Equipment, true top-down with clean alpha edges (regenerate; sample A had a yellow fringe):
  - **Water tank: big square concrete building, closed concrete roof** (hatch). Level is shown as an overlay gauge.
  - **Booster pump outside, next to the tank** on a concrete pad.
  - **Well & control room: small block room, wellhead outside.**
- Surroundings: **dirt tracks between fields** and **bare sandy land**. No boundary wall, no windbreaks.
- Pipes: **plausible mainline route** from the tank and booster along field edges to each zone valve. The owner will correct it later.
- Animations (all four):
  1. Water flowing in pipes, with speed following real flow.
  2. Zone irrigation shimmer / wet soil while running. Moisture tints the canopy.
  3. Equipment motion: pump spin, tank level, valve open/close.
  4. Day/night lighting following farm local time.

## Screens in scope
- Dashboard + live map (hero)
- Phone layout + installable PWA
- Zones list + equipment pages (pumps, valves, sensors)
- Event log / audit

## Data fixes to make alongside
- Mixed-fruit zone third crop is **plum (عوينة)**, not guava (كوبة). Fix the seed and contracts.
- Weather coordinates in config point at Tripoli city (32.887, 13.180), not the farm (≈32.51°N). Fix them before the weather work in Milestone E.
- Generated PNGs are 2–4 MB. Convert to WebP and size them for the map.
