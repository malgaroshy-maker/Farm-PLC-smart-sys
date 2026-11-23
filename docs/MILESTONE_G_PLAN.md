# Milestone G: hardening, polish, research and demo video

**Decided with the owner on 2026-11-23.** Claude builds this in its own session, not through an agent prompt.

**Order:** hardening and polish first, then the hardware research, then the demo video (so the video shows the polished app).

Context: the owner is the only user for now; users and roles UI is deferred. Hosting is still to be decided. The owner has **TIA Portal and PLCSIM Advanced**, but no real PLC yet.

## G1: Performance and reliability ✅ done 2026-11-23 (details in CHANGELOG)
- **Measure first.** Fps on a phone-sized viewport, bundle size, and API latency (p50/p95) for the dashboard calls. Record the baseline numbers in the report.
- **Fewer requests.**
  - Shared polling store, so cards that appear twice (e.g. the next-irrigation card on phone and desktop) don't fetch twice.
  - Pause polling when the tab is hidden.
- **Map speed.**
  - Tree canvas drawing cost on phones.
  - Only re-render what changed on each WS tick.
- **Live connection.**
  - WS reconnect with backoff.
  - A clear stale-data indicator, and nothing that looks live when it isn't.
  - Friendly error states for every API failure.
- **Server.**
  - SQLite in WAL mode.
  - Telemetry retention and downsampling.
  - Log rotation.
  - Crash-safe startup.
  - A health page covering API, DB, simulator/PLC link, AI provider and weather.

## G2: AI ✅ done 2026-11-23 (details in CHANGELOG)
- **Faster.** Stream replies, cache repeated questions, and trim prompts. Today answers take 5–22 s.
- **Smarter advice.**
  - Combine weather (ET₀, rain), soil moisture, and each zone's cycle history and baseline.
  - Show the reasoning and the numbers used.
- **Cleaner Arabic.** A farm glossary, the purity guard on every output, and consistent units and Western digits.
- **Reliability.** Model health status, a usage/cost view, and a clear fallback notice when APInex is slow or down.

## G3: Ready for future features ("scalability") ✅ done 2026-11-23 (details in CHANGELOG)
- **Config-driven.** Zones, valves and equipment come from config and geometry, not hard-coded lists.
- **Extension points.**
  - The PLC adapter interface (`read_tags`, `write_command`, `health`), with the simulator as the first implementation.
  - Notification channels.
  - Feature flags.

## G4: UI polish ✅ done 2026-11-23 (details in CHANGELOG)
Accessibility, empty and error states, an Arabic text review across all pages, consistent spacing and typography.

## G5: PLC preparation (design only)
Owner decisions (2026-11-23): an S7-1500 for now (the hardware research report picks the final CPU); TIA Portal V19 + PLCSIM Advanced, driven through TiaCommander.
- **OPC UA tag map.** Zones, valves, pumps, tank, flow, pressure, alarms, heartbeat.
- **PLC data blocks and command handshake.** The cloud/app can never bypass PLC interlocks.
- **Test plan with PLCSIM Advanced.** See the `tia-portal-openness` skill.

## G6: Docs refresh
- `PROJECT_STATUS.md`: the map is now the satellite trace.
- `README.md`.
- An Arabic operator guide.

## R: Hardware research report
- **Deliverable.** A shareable report page (private link), plus a copy in `docs/`.
- **Covers:**
  - PLC and control panel: S7-1200/1500, I/O, HMI, UPS, cabinet.
  - Field sensors: soil moisture, flow, pressure, tank level, weather station.
  - Valves, pumps and VFDs: zone valves, filters, fertigation dosing.
  - Comms and power: wired vs LoRa/wireless, 4G router/VPN, solar backup.
- **Prices.** Three tiers (basic / recommended / premium), in **USD and LYD at 1 USD = 11 LYD**, with notes on importing into Libya and the sources used.

## V: Demo video
- **Format.** Arabic, 3–5 minutes, **music and Arabic captions only (no voice)**.
- **Footage.**
  - Real screen recordings of a scripted demo run.
  - Farm/drone/PLC/sensor scenes as **Codex-generated still images**, animated with pan and zoom. No video-generation credits.
- **Shows** every current feature, plus coming soon: real PLC and sensors, phone alerts, fertigation, solar and remote access.
- **Steps.** Script and shot list first, owner approval, then generate, record and edit.
