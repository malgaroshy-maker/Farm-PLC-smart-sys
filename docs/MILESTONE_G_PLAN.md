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

## G7: Field readiness (before G5) ✅ built 2026-11-24, owner review pending (details in CHANGELOG)
Gaps found during the hardware research. Owner decisions (2026-11-24): do these **before G5**.
Still open: the owner confirms the per-crop soil levels (proposed values are not used until confirmed); the PLC side of the fallback program, panel switches and power-cut rule is G5 work.
- **PLC fallback program.** The PLC keeps a copy of today's schedule and runs it if the server or app is down; it resyncs when the server returns. (Today the schedules live only in the app.)
- **Manual mode in the app.** The PLC reports the panel switches (zone On/Auto/Off, pump Hand/Off/Auto); the app shows "zone in manual", never fights it, and logs it (ALM-042).
- **Unexpected-flow alarm.** Flow with no zone on means a leak or a valve opened by hand (ALM-021 is defined but never raised).
- **Power-cut recovery.** A zone interrupted by a power cut resumes its remaining time only if power was out less than 30 minutes (and tank and pressure are fine); otherwise the run is marked interrupted and the owner is alerted.
- **Farm server installer.** One-time setup on the farm laptop or mini PC: starts at boot, restarts itself on a crash, no terminal window.
- **Daily database backup** with a restore button (none exists today).
- **Secure remote access + HTTPS** through a free VPN (Tailscale) on the farm server; its HTTPS also makes phone push work without paid hosting.
- **Soil sensors + thresholds.** Read wireless (MQTT from the LoRaWAN gateway) or wired (PLC/Modbus) soil sensors; per-crop start/stop moisture levels; soil-based irrigation.
- **Pump health inputs.** Energy meters, well level, filter clogging and starter faults: values on the dashboard plus alarms.
- **Modbus TCP adapter** for cheaper controllers (S7-200 SMART, LOGO!, Delta) and the radio boxes' timed valve commands.
- Not chosen for now: OPC UA security (certificates and user login), on-farm weather station.

## G5: PLC program (next)
Owner decisions (2026-11-23): TIA Portal V19 + PLCSIM Advanced, driven through TiaCommander.
Owner decisions (2026-11-24):
- **CPU:** ET 200SP CPU 1512SP-1 PN (the hardware report's pick).
- **Link to the app:** the PLC serves **both** OPC UA and Modbus TCP; each installation picks one (`CONTROLLER_ADAPTER=opcua|modbus`).
- **Scope:**
  - tags, data blocks and the command handshake (the app can never bypass PLC interlocks);
  - zone and pump logic: sequencing, interlocks, timers, faults and alarms;
  - G7 field rules in the PLC: panel switches, 30-minute power-cut resume, fallback schedule, well dry-run trip;
  - a local HMI screen in the control room: **MTP1000 Unified Comfort** (10"), Arabic + English switch.
- **PLC language:** all SCL.
- **Zone valves:** designed for both wired outputs and radio boxes over Modbus, chosen per zone in a config DB.
- **Test:** in PLCSIM Advanced with the app connected through both adapters. See the `tia-portal-openness` skill.

## G6: Docs refresh ✅ done 2026-11-23 (details in CHANGELOG)
- `PROJECT_STATUS.md`: the map is now the satellite trace.
- `README.md`.
- An Arabic operator guide.

## R: Hardware research report ✅ done 2026-11-24 (interactive page + docs/HARDWARE_RESEARCH.md / .ar.md)
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
