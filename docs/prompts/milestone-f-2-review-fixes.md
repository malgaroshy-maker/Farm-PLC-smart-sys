# Prompt — Milestone F round 2: satellite map correction + review fixes

Paste this into the agent session that built `milestone-f-map-ui`, or into a fresh session at the repo root.

---

Branch `milestone-f-map-ui` (7f7a02b..99f7f80) was reviewed live, with the owner signed in.

**What works:**
- All suites pass (API 194, simulator 27, web 84, launcher 4), and the new migration applies to a fresh DB.
- At 375 px, no page scrolls sideways, and the bottom-nav targets are 53 px.
- The weather widget, model badges, elapsed-seconds counter, copy button, install prompt, timeline now-line and step reordering are all there.

**What doesn't:** the problems below. Fix them on `milestone-f-map-ui`.

## 1. The owner did NOT skip the satellite correction: do it now
- `design/DESIGN_BRIEF.md`, `docs/FARM_SITE.md` and `tools/map-geometry/README.md` say *"the owner decided to keep the current traced polygons"*. **That's wrong.** The owner's decision (2026-11-20) was **"use satellite imagery to correct the drawing"**.
- Fix the docs. **Never record a decision the owner didn't make.** If you assumed something, say so, and ask.
- Then do the work from the original prompt (`docs/prompts/milestone-f-map-ui-polish.md` §2):
  1. **Imagery: the source is decided and already checked** (2026-11-20).
     - The owner approved **Esri World Imagery for checking and tracing** this private farm app. Attribution: "Source: Esri, Maxar, Earthstar Geographics", noted in `design/satellite/README.md` and `tools/map-geometry/README.md`. Revisit the licence before any commercial product.
     - Run `tools/map-geometry/fetch_esri_tiles.py` inside `design/satellite/`. It stitches zoom-17 tiles (about 1.01 m/px; 16 tiles, 794×796 px) for the bbox lon 14.06610–14.07462, lat 32.51265–32.51985. Zoom 18 is fine for more detail. Images are git-ignored.
     - Note: the ArcGIS `export` endpoint returns HTTP 500 for this cached service, which is why the tiles are used instead.
     - **The owner confirmed it's the right place.** The farm is the irrigated orchard around the **central buildings**, with a north–south **gully (wadi) along the east side** and blocks running diagonally NW–SE.
     - The real irrigated footprint is roughly **510 × 600 m**. Our current map is **515 × 457 m** at its own scale (`m2_per_unit2` 0.26519 → 0.515 m/unit), so it's **squashed north–south and probably rotated**. Expect the georeferencing to fix both: rotate and scale, don't just shift.
  2. **Georeference** with ≥ 2 control points into the real map space. Note: the geometry's `viewBox` is **`0 0 1000 886.8`**, not `0 0 1000 650` as the README now says; fix that.
  3. **Re-trace** zones (polygons and row angles), tracks, building footprints (tank, booster pad, control room, wellhead), the farm boundary, and any visible pipe/valve evidence. Mark verified vs guessed.
     - **Block → zone mapping, buildings, boundary, entrance, wadi, pipes and trees are ALREADY CONFIRMED by the owner.** They're in **`docs/MAP_SURVEY.md`**, with approximate coordinates for every block and structure; the reference images are in `design/satellite/`. Follow that file exactly. Don't re-ask anything it answers.
     - Key points: zaytoun = blocks 6+9. Block 7 = rumman_6 (north) + rumman_5 (south). Block 8 = zaytoun_2 / enab / rumman_ummahat (east → west). **S6 = control room + well, S7 = tank, booster next to the tank.** S1–S3 = chicken house, S5 = workers' rooms, C = house. Blocks 1–5, 16, 17 aren't ours (faded context). Wadi drawn on the east.
     - This changes the equipment positions and kinds in `farm-geometry.json` (`equipment`) and the farm-life worker's home. Add the non-irrigation buildings as labelled, non-interactive footprints.
  4. Produce an **overlay image** (satellite + old + new outlines) and an **area table** (sketch legend vs old vs new). **Show it to the owner and get approval before replacing `farm-geometry.json`.**
  5. After approval: update the area test, regenerate tree placement, the walk graph, chip anchors and equipment positions. Compare before/after screenshots (desktop + phone, kept outside the repo). The map must look at least as good.

## 2. Security: tokens in the logs (must fix)
- The redaction filter is on `uvicorn.access`, but uvicorn logs the WebSocket line through **`uvicorn.error`**. Live, the log still shows:
  - the simulator service token: `WebSocket /ws?token=Yr9t…`
  - **the admin user's full JWT**, `WebSocket /ws?token=eyJhbGci…`, which anyone reading the log could use to act as admin until it expires
- Fix it properly:
  - move WS auth **out of the URL** (e.g. a first message `{type:"auth", token}` or the `Sec-WebSocket-Protocol` header), **and**
  - redact `token=` on **every** uvicorn logger (`uvicorn`, `uvicorn.error`, `uvicorn.access`) as a backstop.
  - Update the simulator client and the web store.
- Test **through a real running server** (start uvicorn on a free port in the test, connect a WS, capture the log output), not with a hand-built `LogRecord`. Assert that no token-looking string appears.
- Also quiet the access log in demo mode (it logs two lines a second from the simulator). For example, skip `/state/sync` and `/commands/pending` from the service account, or set `--no-access-log` in demo.

## 3. Daily briefing crashes (500)
- `GET /api/v1/ai/briefing` → `AttributeError: 'Alarm' object has no attribute 'name'`. The `Alarm` model has no `name`; use the catalog (`CATALOG[a.alarm_code].name/name_ar`). It crashes whenever there are alarms in the period.
- **The UI also printed the raw parse error** to the user: *"الموجز الصباحي للمزرعة: Unexpected token 'I', "Internal S"… is not valid JSON"*. `apiFetch` / the card must handle non-JSON error bodies and show a friendly AR/EN error state.
- Tests: a briefing with real `Alarm` rows (ORM, not dicts) in the window; the web card shows an error state for a 500 with a text body.

## 4. Weather widget shows the wrong hours
- `WeatherWidget.tsx` uses `forecast.current` and `hourly.slice(0, 6)`, which is **always the first 6 entries (midnight of day 1)**, not the next 6 hours.
- The docs claim it "fast-forwards to the farm virtual hour", but live, with the farm clock on **14 Dec**, it showed 17.6 °C / 10.8 km/h from the **20–21 Nov** forecast, as if it were current.
- Fix: choose the forecast hour that matches **farm time** (Africa/Tripoli). Show the next 6 hours from that point. If farm time is **outside the forecast range**, show "لا توجد توقعات لهذا الوقت" (no data), hide the overlays, and **never** show another day's values. The rain overlay and cloud tint must use that same hour.
- Tests: in range at 1×, a farm hour mid-forecast, farm time beyond the forecast → no data.

## 5. Phone nav: replace the duplicate
- The bottom nav has Dashboard **and** "Map", but `/map` renders the same `Dashboard` page, so one of the four slots is wasted. The owner chose: **replace "Map" with Zones** (keep Dashboard, Alarms, Schedules). Remove the `/map` route, or redirect it to `/`.
- The owner confirmed the other recorded choices (weather widget top-right, legend collapsed on phones, model badge always visible, reports default 7 days).

## 6. Items from the original prompt that are missing
- **Chip collision handling** on the map (labels must not overlap at any zoom; hide lower-priority chips).
- **Deep link** `/?zone=zone_rumman_2` focuses and opens that zone.
- **Fps measurement** on a phone-sized viewport (report the numbers).
- **Launcher address filter:** excluding all of `172.16–31.x.x` would hide real LANs that use that range. Only exclude known virtual adapters (by interface name: VirtualBox, vEthernet/Hyper-V, Docker, WSL) plus `169.254.x.x`.

## 7. Verify
- All green: api/simulator `pytest` + ruff, web vitest/eslint/build, the launcher tests, `alembic upgrade head`, and `run.bat --smoke`.
- **Live** (`run.bat demo`; the owner signs in; never type passwords):
  1. Grep the whole demo console output for `token=`: **zero** matches.
  2. The briefing card renders (with alarms present) or shows a friendly error.
  3. The weather widget at the real clock shows the current hour; at a far farm date it shows "no forecast".
  4. Phone bottom nav: Dashboard / Zones / Alarms / Schedules.
  5. Chips don't overlap, and the deep link works.
  6. The satellite overlay was approved and the new geometry is in.
- Also note: the farm clock was left in **simulated mode (14 Dec, 60×)** after your testing. Return to real time when you finish.
- Docs: `design/DESIGN_BRIEF.md` (correct the decisions), `tools/map-geometry/README.md`, `docs/FARM_SITE.md`, `docs/REALTIME_EVENTS.md` (WS auth change), `CHANGELOG.md`, `PROJECT_STATUS.md`.

## Rules
- Commit on `milestone-f-map-ui` only. **Don't merge or push.**
- **Ask the owner** for any decision not written here, and **never write a decision into the docs that the owner didn't make.**
- No fake data. Arabic-first i18n. Never print secrets or tokens. Don't commit screenshots or unlicensed imagery.
- Report honestly, with command output.
