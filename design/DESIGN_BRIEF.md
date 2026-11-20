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

---

# Round 2 — UI, graphics & animation improvements (decided 2026-11-18)

Focus: **map realism, map animations, dashboard layout, pages & panels styling** (all four).

## Map
- **Individual tree sprites** replace the tiled crop textures. Each tree sits at real row spacing along its field's row direction, with slight size and rotation variation and its own shadow. Wet spots form under each tree, and dry trees yellow individually. Rendering must stay smooth with about 4,000 trees, so use a canvas or batched layer if SVG is too slow.
- Equipment sprites stay as they are. The owner did not ask for bigger or more detailed equipment.
- Animations:
  1. **Drip droplets and spreading wet rings** under trees while a zone runs.
  2. **Camera fly-to**: smooth zoom/pan to a selected zone, highlight it and dim the rest. Also auto-focus the zone of a new S2/S3 alarm, with a "back to farm" button.
  3. **Life on the farm**:
     - a **tractor** working along a field edge
     - **birds** flying across now and then
     - a **worker on foot** who idles near the control room and, when a zone/valve alarm is active, walks along the tracks to that zone and stays until it is acked or cleared
- Not wanted: wind sway or cloud shadows.

## Dashboard
- **Map + side column.** The map takes about 2/3, with compact KPIs on top. The right column shows the tank gauge, pumps, active alarms and trends:
  - tank level (24 h)
  - flow & pressure (1 h)
  - water used today by zone (m³, from telemetry until the cycle log in Milestone D)

## Style
- **Dark HMI with more depth.** Keep the cyan accent. Add glass panels, subtle gradients, softer corners, and better spacing and type scale across all pages and panels.
- **Custom icon set: duotone line icons** with a cyan accent, for crops, pump, valve, tank, sensors and alarms.

## New assets (style A photoreal unless noted)
- Tree sprites per crop: pomegranate, olive, grape (trellis row segment), peach / apricot / plum.
- Zone and equipment detail art for the zone drawer and equipment page (a crop photo per zone type, a pump cutaway).
- Login hero aerial artwork and empty-state illustrations (no alarms, no events).
- **Show samples first**: one tree per crop, 3 icons and one detail image. Generate the rest after approval.

## Round 2 — details (decided 2026-11-18)
- **Zone labels on the map**: a glass chip with the zone name, plus a live badge. The badge shows moisture % when idle, flow m³/h and a timer when irrigating, and an alarm icon when faulted. Hover/tap opens a tooltip with all values.
- **Alarms on the map**: a **pulsing severity-coloured ring** around the affected zone, and the **faulted equipment glows**.
- **Lighting**: follows farm time (Africa/Tripoli), with a manual override (unchanged).
- **Sound**: a short chime on new **S2/S3** alarms, with a **mute** toggle in the header that is remembered per viewer.
- **Zone panel order**: big live status (state, moisture, flow, timer), then controls, then history charts, then crop & hardware info.
- **Starting a zone**: a duration picker. It defaults to the zone's usual duration, with preset chips for 15 / 30 / 45 / 60 min and a slider up to the zone's max runtime. Confirm before starting.
- **Phone home**: a big status card first (all OK / alarms / zones running) with quick actions, then the map.
- **Motion**: rich by default, with a **reduce-motion** toggle. The OS reduce-motion setting is also respected.
- **Fruit follows the real season**, so each crop needs *two* tree sprites (fruiting / green):
  - pomegranate Sep–Nov
  - olives Oct–Dec
  - grapes Jul–Sep
  - apricot May–Jun
  - peach Jun–Aug
  - plum Jun–Aug
- **Water colour**: cyan, matching the HMI accent.
- **Login art**: a golden-hour photoreal aerial of pomegranate and olive rows, darkened behind the login card.
- **Empty states**: a calm photoreal vignette with a short reassuring line (e.g. "All clear — no active alarms").

## Round 2 — status (2026-11-18)
All of the above is implemented on branch `ui-round-2`. Approved samples are in `design/samples-r2/`. Final assets are in `apps/web/public/map` (trees, farm-life sprites) and `apps/web/public/art` (detail, login and empty-state art).

---

# Milestone F — Map Weather & UI Polish (decided 2026-11-20)

## Owner decisions

| # | Topic | Decision |
|---|-------|----------|
| 1 | Satellite / Geometry | Use satellite imagery to correct the drawing. Keep our generated photoreal map (offline, consistent look), but re-trace zones, tracks, buildings (tank, booster, control room, wellhead) and the mainline/valves to match reality. Attribution: "Source: Esri, Maxar, Earthstar Geographics". Show overlay & area table to owner before replacing geometry. |
| 2 | Weather widget position | Top-right corner of the map (above the zoom controls). |
| 3 | Legend collapsibility | Collapsed by default on mobile (< 640px), expanded on desktop. Toggle button always visible; preference saved in `farm.legendOpen`. |
| 4 | AI model badge | Always visible — small, unobtrusive gray badge below the answer (`model_used` stripped of `free/` prefix + provider, or amber fallback notice). |
| 5 | Default report range | Last 7 days (`Africa/Tripoli` local time). |
| 6 | Phone bottom navigation | 4 primary items: Dashboard (`/`), Zones (`/zones`), Alarms (`/alarms`), Schedules (`/schedules`). `/map` redirects to `/`. |

## Weather on the map
- **WeatherWidget (`WeatherWidget.tsx`)**: Glass panel (`.panel`) top-right of map.
  - Temperature in `<bdi>{temp}°C</bdi>`.
  - Wind arrow rotated to meteorological "from" convention (points toward source).
  - Wind speed (`km/h`) and precipitation probability badge (`💧 {prob}%`).
  - Condition icons (🌤️, 🌧️, ⛈️, ☁️, 🌫️).
  - Hover/tap tooltip with next 6 hourly forecast items.
  - Mobile responsive: collapses to compact badge on mobile with tap-to-expand.
  - Virtual clock sync: fast-forwards forecast to match farm virtual hour at $\ge 10\times$ speed.
  - Honest no-data state: "لا توجد بيانات طقس" / "No weather data" on API unavailability.
- **WeatherOverlay (`WeatherOverlay.tsx`)**: High-performance canvas layer (`pointer-events: none`).
  - Animated raindrops via `requestAnimationFrame` when raining or precipitation probability $\ge 60\%$.
  - Cloud-shadow tint (opacity 0.08) when `cloud_cover_pct` $\ge 70\%$.
  - Respects `prefers-reduced-motion`: shows static blue tint without frame animation.

## UI Polish & Phone Experience
- **Navigation & Mobile layout**:
  - 4 bottom navigation items with guaranteed $\ge 44\text{px}$ touch targets.
  - Safe-area insets (`env(safe-area-inset-bottom)`, `env(safe-area-inset-top)`).
  - Floating AI assistant offset so it never obscures the bottom nav bar.
  - PWA install prompt banner with dismiss memory (`farm.installDismissed`).
  - Viewport-fit cover and horizontal scroll prevention at $375\text{px}$ width.
- **AI Panels (`ModelBadge.tsx`)**:
  - Model badge displayed on Alarm Assistant, Floating Chat, and Daily Briefing.
  - Dynamic elapsed seconds counter ("جاري التفكير... (٣ ث)" / "Thinking... (3s)") during AI queries.
  - Friendly rule-based banner with ⚠️ callout when fallback is triggered.
  - One-click copy-to-clipboard on AI answers with 2-second checkmark confirmation.
  - Contextual follow-up suggestion chips in Floating Assistant.
- **Schedules & Reports**:
  - Vertical now-line on 24h schedule timeline linked to virtual farm clock.
  - Distinct Arabic day initials (`ن`, `ث`, `ر`, `خ`, `ج`, `س`, `ح`).
  - Step reordering in edit drawer with functional `↑ / ↓` controls.
  - Default 7-day range in Reports with sticky table headers and prominent CSV export.

