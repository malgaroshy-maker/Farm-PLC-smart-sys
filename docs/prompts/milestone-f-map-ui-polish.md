# Prompt — Milestone F: map accuracy, weather on the map, UI polish

Paste this into a fresh agent session at the repo root.

---

You are continuing the Algaroshy Farm smart-irrigation project:
- pnpm + Turborepo monorepo
- FastAPI API in `apps/api`
- Python simulator in `apps/simulator`
- React 19 + Vite + Tailwind v4 web app in `apps/web`
- farm geometry in `packages/map-model` (traced by `tools/map-geometry/`)

Milestones A–E are done and on `master`: the photoreal animated map, the farm clock, programs, the cycle log, reports, and AI on APInex.

**Your task: Milestone F.** Make the map match the real farm, put the weather on it, and polish the UI.

**PLC** (decided, *not* in this milestone): Siemens S7-1200/1500 via OPC UA. It's recorded in `PROJECT_STATUS.md` and `docs/AUDIT_AND_ROADMAP.md`. Don't start the adapter here.

## 0. Read first
- `docs/FARM_SITE.md`: exact site **32.516250, 14.070361**, i.e. 32°30'58.5"N 14°04'13.3"E.
- `design/DESIGN_BRIEF.md` (all the owner's map/UI decisions so far), `docs/AUDIT_AND_ROADMAP.md` (Milestone F), `PROJECT_STATUS.md`.
- Map code:
  - `tools/map-geometry/` (trace, network, optimise scripts and the README)
  - `packages/map-model` (geometry + area test)
  - `apps/web/src/components/map/{FarmMap.tsx,MapCanvases.tsx,FarmLife.tsx,trees.ts,life.ts}`
- AI/UI code:
  - `apps/web/src/components/ai/*`
  - `apps/web/src/pages/{Dashboard,Schedules,Reports,ZonesPage,EquipmentPage,AlarmCenter,AiSettings}.tsx`
  - `apps/web/src/layouts/DashboardLayout.tsx`, `apps/web/src/lib/i18n.ts`, `apps/web/src/index.css`
- Weather service: `apps/api/app/services/weather.py` and `GET /api/v1/ai/weather/*`.

## 1. Owner decisions (2026-11-20). Record them in `design/DESIGN_BRIEF.md` under "Milestone F"
| # | Topic | Decision |
|---|-------|----------|
| 1 | Satellite | **Use satellite imagery to correct the drawing.** Keep our generated photoreal map (offline, consistent look), but re-trace zones, tracks, buildings (tank, booster, control room, wellhead) and the mainline/valves to match reality. **No satellite base layer in the app.** |
| 2 | Location touches | **Weather on the map:** wind direction arrow, rain/cloud overlay, and a temperature chip from the live Open-Meteo forecast for the farm site. (Real sunrise/sunset, north arrow + scale and surroundings were *not* chosen.) |
| 3 | UI polish | **All four areas:** dashboard & map interactions, AI panels, Schedules & Reports, phone experience. |

## 2. Map accuracy from satellite (do this first; the owner confirms)
1. **Get imagery** of the site bbox (about ±400 m around the coordinates) for **tracing only**. Store it in `design/satellite/` (git-ignored if large), with its source, date, bbox and licence in a `README.md`.
   - Prefer a provider whose terms allow this use (e.g. Esri World Imagery export with attribution, or a screenshot the owner exports from Google Earth with known corner coordinates).
   - If licensing is unclear, **ask the owner to provide the image**. Don't ship the imagery in the app.
2. **Georeference** the image to the map's coordinate system (`FARM.viewBox`) using the site coordinates and at least 2 control points. Document the transform in `tools/map-geometry/README.md`.
3. **Re-trace** in `tools/map-geometry/`:
   - zone polygons and row direction (angle)
   - dirt tracks
   - building footprints and positions
   - the farm boundary
   - visible pipe/valve evidence. Keep the plausible network where nothing is visible, and mark which parts are verified and which are guessed.
4. **Compare old vs new:**
   - Produce an overlay image (old outlines, new outlines, satellite) and a table of per-zone area (sketch legend vs old vs new) for the owner.
   - **Ask the owner to approve before replacing `farm-geometry.json`.** Show them the overlay.
   - Update the area test to the approved values and tolerances.
5. After approval:
   - regenerate trees (`trees.ts` placement follows the new polygons and angles)
   - re-run the farm-life walk graph (`life.ts`)
   - check the label chip positions and equipment sprites
   - all map tests pass
   - **the map must look at least as good as before.** Compare screenshots at desktop and phone widths.

## 3. Weather on the map
- Small glass widget on the map (top corner, RTL-aware):
  - current temperature
  - wind arrow rotated to the **real wind direction** (meteorological "from" direction, documented)
  - wind speed
  - rain probability for the next hours
- A subtle **rain overlay** animation on the map when it's raining now or the next-hour rain probability is ≥ 60 %, and a **cloud-shadow** tint when cloud cover is high. Both respect **reduce motion** and stay cheap: canvas or CSS, no per-frame React renders.
- Data comes from the existing cached weather service (API), never from Open-Meteo directly in the browser. Add `cloud_cover`, `wind_direction_10m` and `wind_speed_10m` to the fetch if missing.
- When there's no forecast: hide the overlays and show "لا توجد بيانات طقس". **Never invent values.**
- Follows the **farm clock** (at 360× the widget shows the forecast hour for farm time, from the cached forecast).
- Tooltip with the next 6 hours. Arabic-first, with `bdi` for numbers.

## 4. UI polish (ask the owner before each bigger visual change)
**Before building, ask the owner one round of multiple-choice questions** (recommended option first) for anything not decided here. For example:
- whether the legend should be collapsible
- where the weather widget goes
- whether the AI model badge should be always shown or only on hover
- the default report range
- the phone bottom-nav items

1. **Dashboard & map interactions:**
   - smooth zoom/pan inertia; double-tap / double-click to zoom
   - chips that stay readable at all zoom levels without overlapping (collision-avoid or hide the lower-priority chips)
   - a clearer legend
   - hover and tap details for equipment
   - a "focus zone" deep link (`/?zone=zone_rumman_2`)
   - performance: about 60 fps on a mid-range phone. Measure and report.
2. **AI panels:**
   - consistent loading state with elapsed seconds (free models take 5–25 s)
   - a cancel button
   - a model badge (`model_used`)
   - when rule-based, show **why** (`fallback_reason` → a friendly AR/EN text)
   - copy button, and follow-up suggestions
   - the floating assistant must not cover the map controls or the phone bottom nav
   - briefing and suggestion cards: readable Arabic typography and an expand/collapse
3. **Schedules & Reports:**
   - timeline readability (labels, now-line on the farm clock, conflict highlights)
   - the edit drawer flow (step reorder by drag *and* buttons, duration chips)
   - reports: chart axis/labels in Arabic, sticky table header, empty states, a visible CSV download
4. **Phone experience:**
   - bottom nav with ≥ 44 px touch targets
   - safe-area insets, landscape
   - PWA install prompt (an "Add to home screen" hint in the user's language)
   - Arabic font sizes at small widths, no horizontal scroll on any page
   - check every page at 375×812

## 5. Small issues found in the 2026-11-20 run (`run.bat demo reset`)
- **The simulator's service token appears in the API access log.** Uvicorn logs `WebSocket /ws?token=…` on every connect. Redact the query string in access logs, or move the WS auth to a header/first message, and keep the access log quiet in demo mode (it logs two lines per second from the simulator).
- **The launcher lists VirtualBox/link-local addresses** (`169.254.x.x`, `192.168.56.1`) as "Phone on the same Wi-Fi". Filter out link-local and virtual-adapter addresses, and prefer the active Wi-Fi/Ethernet interface.
- **`run.bat reset` keeps user-created test programs** (e.g. "Live Trio 3-Zone", enabled daily 06:00). Ask the owner whether reset should also remove programs. Recommended: keep them, but print the enabled programs in the reset summary so nothing fires by surprise.

## 6. Tests and verification
- Keep everything green:
  - `pytest` + `ruff check` + `ruff format --check` (api, simulator)
  - `npx vitest run`, `npx eslint .`, `pnpm build` (no chunk warning) in web
  - map-model tests (updated areas)
  - `alembic upgrade head` if you touch models
  - `run.bat --smoke`
- New tests:
  - geometry (polygons valid, areas within the approved tolerance, every zone has a valve point and a chip anchor)
  - weather widget (wind arrow rotation, no-data state, rain-overlay threshold)
  - chip collision logic, deep link
  - the access-log redaction
  - the launcher address filter
- **Live:** run `run.bat demo reset`. **The owner signs in; never type passwords.**
  - Check desktop 1440×1000 and phone 375×812.
  - Before/after screenshots of the map (kept **outside** the repo) for the owner.
  - Report fps measurements and the AI panel latencies.

## 7. Docs
- `design/DESIGN_BRIEF.md` (Milestone F decisions + results)
- `tools/map-geometry/README.md` (satellite workflow, georeferencing, verified vs guessed parts)
- `docs/FARM_SITE.md` (imagery source and date)
- `CHANGELOG.md`
- `PROJECT_STATUS.md` (Milestone F status, test counts)
- `docs/AUDIT_AND_ROADMAP.md` (mark Milestone F)

## Rules
- Work on branch `milestone-f-map-ui`. Commit in logical steps. **Don't merge or push.** The owner's reviewer reviews first.
- **Ask the owner** before replacing the farm geometry and before any visual change not decided above.
- **No fake data** anywhere (weather, baselines, AI). Show honest empty or error states.
- Arabic-first i18n, glass `.panel`, FarmIcons, reduce motion. Farm time vs real time as in the clock guard.
- Never print secrets or tokens. Don't commit screenshots, satellite tiles you're not licensed to store, or throwaway scripts.
- Report honestly, with command output, including what you couldn't verify.
