# 🌾 Algaroshy Farm — Smart Irrigation System

**Farm:** Algaroshy Farm, north-west Libya  
**Originator:** Mahamed Algaroshy — محمد عادل الجروشي  
**Status:** Milestones A–F done; Milestone G (hardening, AI, polish, PLC design, hardware research, demo video) in progress. See [PROJECT_STATUS.md](PROJECT_STATUS.md).

<div dir="rtl">

### ملخص بالعربية

نظام ري ذكي لمزرعة الجروشي: خريطة حيّة للمزرعة مرسومة من صور الأقمار الصناعية، تشغيل وإيقاف مناطق الري، جداول ري تلقائية، إنذارات مع إرشادات بالعربية، تقارير المياه والمضخات، ومساعد ذكي يشرح الإنذارات ويقترح تعديل الري حسب الطقس. يعمل اليوم مع محاكي يمثّل المزرعة ووحدة التحكم، وسيتصل لاحقاً بوحدة تحكم Siemens (PLC) عبر OPC UA. الواجهة عربية أولاً مع خيار الإنجليزية، وتعمل على الحاسوب والهاتف (تطبيق ويب قابل للتثبيت).

**دليل المشغّل:** من داخل التطبيق (صفحة «المساعدة»)، أو [docs/OPERATOR_GUIDE.md](docs/OPERATOR_GUIDE.md)، أو نسخة PDF للطباعة.

</div>

---

## Overview

A sensor-backed, remotely observable irrigation platform for Algaroshy Farm. It replaces manual monitoring and valve operation with automated control, live telemetry, alarms, scheduling and reporting. The PLC stays the local safety authority: the apps never bypass its interlocks, and the farm keeps running without internet.

### What it does today

- 🗺️ **Live farm map** traced from satellite imagery: every zone, tree row, pipe, valve, pump, tank and building, with animated water flow and day/night lighting.
- 🔧 **Zone control:** start/stop with a duration picker and interlock feedback, plus a global STOP ALL.
- 📅 **Schedules:** sequential irrigation programs on a weekly timeline with conflict checks.
- 🚨 **Alarms:** 50 alarm definitions (23 raised today) with severity, ack/reset and Arabic/English guidance.
- 📈 **Reports:** daily irrigation, water per zone, pump runtime and alarm history, with CSV export.
- 🧠 **AI:** explain any alarm, a farm assistant chat, a weather advisor whose decisions come from fixed server rules (the AI only explains them), statistical leak/clog detection, and a morning briefing.
- 🔔 **Notifications:** critical and major alarms and the briefing go to Telegram and phone push.
- ⚙️ **Settings:** feature switches, notification setup, zone and equipment admin, AI models.
- 🩺 **Health:** a status badge and panel for the database, controller link, scheduler, AI, weather and disk.
- 🔒 **Roles:** owner/admin, operator and viewer.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.11+, FastAPI, SQLAlchemy, Alembic, Pydantic |
| **AI** | Pydantic AI with APInex (OpenAI-compatible) and Google Gemini, then rule-based fallback; Open-Meteo weather |
| **Database** | SQLite with WAL (dev/demo); PostgreSQL planned for production |
| **Web app** | React 19, Vite, TypeScript, Tailwind CSS v4, Zustand |
| **Phone** | Installable PWA from the web app; web push |
| **Simulator** | Python physics engine that plays the farm and the PLC |
| **Real-time** | WebSocket, with polling fallback |
| **PLC** | Siemens S7-1500 via OPC UA (`asyncua`), behind a `ControllerAdapter` |

---

## Project Structure

```
Farm-PLC/
├── apps/
│   ├── api/            # FastAPI backend (alarms, commands, scheduler, AI, notifications)
│   ├── web/            # React + Vite web app (PWA)
│   └── simulator/      # Gateway + physics simulator; controller adapters (simulator, OPC UA)
├── packages/
│   ├── contracts/      # Shared types, enums, alarm catalog
│   └── map-model/      # Farm map geometry
├── tools/
│   ├── map-geometry/   # Satellite trace → farm-geometry.json
│   └── ai-bench/       # AI model benchmark
├── design/             # Design brief, approved samples, generated art
├── docs/               # Engineering docs and the operator guide
├── scripts/            # Launcher (start/stop/reset)
├── run.bat / run.sh    # One-command start
└── PROJECT_STATUS.md   # What works today (verified)
```

---

## Quick Start

### Prerequisites
- **Python 3.11+** (Windows: tick "Add python.exe to PATH" in the installer)
- **Node.js 20+** and **pnpm 9** (`corepack enable` once)

### Run
```bash
run.bat            # Windows, dev mode (hot reload)       → http://localhost:5173
run.bat demo       # Windows, demo mode (phones + PWA)    → http://localhost:4173
run.bat reset      # clear alarms/commands/events/telemetry first (keeps users + settings; combine: run.bat demo reset)
./run.sh           # macOS / Linux (same options)
```
That's all. On first run the launcher sets itself up:
1. creates `.env` from `.env.example` with generated secrets, and prints the admin login once
2. creates the Python venv and installs the requirements (and reinstalls when `requirements.txt` changes)
3. runs `pnpm install` (and again when `pnpm-lock.yaml` changes)
4. migrates and seeds the database

It then starts the **API, simulator and web app in one window** with tagged logs (`[api] [sim] [web]`), waits until live data is flowing, and opens the browser. **Ctrl+C or closing the window stops everything.** If something is left over after a crash, run `stop.bat` / `./stop.sh`. It only stops this app's own processes.

| Setting (`.env`) | Default | Notes |
|---|---|---|
| `API_PORT` | 8000 | **The one place to change the API port.** The launcher points the simulator and the web proxy at it. If another program holds the port, the launcher stops with a clear message. |
| `WEB_PORT` | 5173 (dev) / 4173 (demo) | |
| `TIMESCALE` | 1 | Simulator speed. 60 = one simulated minute per real second. |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | admin / generated | Used when the database is first seeded |
| `APINEX_API_KEY`, `GEMINI_API_KEY` | empty | Optional. Without keys the AI features answer with fixed rules. |
| `TELEGRAM_BOT_TOKEN` | empty | Optional. Settings → Notifications explains the setup. |
| `CONTROLLER_ADAPTER` | simulator | `opcua` + `OPCUA_TAGMAP` to drive a PLC; see [CONTROLLER_ADAPTER](docs/CONTROLLER_ADAPTER.md). |

**Demo mode** builds the production app, makes it reachable from phones on the same Wi-Fi (the launcher prints the URLs), and makes it installable ("Add to Home screen"). Admins can show the Simulator page with the **presenter mode** switch in the sidebar.

`node scripts/start.mjs --smoke` starts everything, checks that it's healthy, and stops again. Use it as a quick self-test.

### Tests
```bash
cd apps/api && .venv/Scripts/python -m pytest -q      # Linux/macOS: .venv/bin/python
cd apps/simulator && ../api/.venv/Scripts/python -m pytest -q
pnpm lint && pnpm build && pnpm test
```

---

## Roadmap

Progress is tracked in [PROJECT_STATUS.md](PROJECT_STATUS.md); the current plan is [docs/MILESTONE_G_PLAN.md](docs/MILESTONE_G_PLAN.md).

**A** foundations ✅ → **B** simulator + alarms ✅ → **C** demo UI + PWA ✅ → **D** schedules + reports ✅ → **E** AI ✅ → **F** satellite map + weather ✅ → **G** hardening ✅, PLC design (next), hardware research report, demo video → production (PLC on site, hosting).

---

## Deployment Modes

- **Mode A — Pure simulation:** no hardware; the full stack runs against the simulator. Today's mode.
- **Mode B — Local pilot:** simulator or PLC (PLCSIM Advanced first) on the local network; web on LAN/VPN.
- **Mode C — Production hybrid:** PLC on site, optional cloud sync, remote apps. Control stays local.

---

## Documentation

All engineering documents are in [`/docs`](./docs/):

| Document | Description |
|----------|-------------|
| [Operator guide](docs/OPERATOR_GUIDE.md) | How to use the app (Arabic + English): daily operation and administration |
| [PRD](docs/PRD.md) | Master product requirements |
| [Architecture](docs/ARCHITECTURE.md) | System layers, services, deployment |
| [Domain Model](docs/DOMAIN_MODEL.md) | Business objects and state models |
| [Database Schema](docs/DATABASE_SCHEMA.md) | Tables, indexes, telemetry model |
| [API](docs/API.md) | REST API design |
| [Realtime Events](docs/REALTIME_EVENTS.md) | WebSocket event contracts |
| [IO List](docs/IO_LIST.md) | PLC tags, sensors, actuators |
| [PLC Control Logic](docs/PLC_CONTROL_LOGIC.md) | Control philosophy, sequences, interlocks |
| [Controller Adapter](docs/CONTROLLER_ADAPTER.md) | Simulator and OPC UA adapters, command handshake |
| [Alarm Matrix](docs/ALARM_MATRIX.md) | 50 alarm definitions with full behavior |
| [Schedules](docs/SCHEDULES.md) / [Simulation Time](docs/SIMULATION_TIME.md) | Programs, scheduler and the virtual farm clock |
| [Simulation Plan](docs/SIMULATION_PLAN.md) | Simulator design and test scenarios |
| [Map Survey](docs/MAP_SURVEY.md) / [Farm Site](docs/FARM_SITE.md) | How the map was traced, site facts |
| [AI](docs/AI.md) / [AI Models](docs/AI_MODELS.md) | AI features and the model benchmark |
| [Hardware BOM](docs/HARDWARE_BOM_DRAFT.md) | Preliminary hardware list |
| [Test Plan](docs/TEST_PLAN.md) | Acceptance tests and commissioning |
| [Milestone G plan](docs/MILESTONE_G_PLAN.md) | Current milestone |

---

## Design Principles

1. **The PLC is the local safety authority.** Cloud and apps never bypass interlocks.
2. **Simulation first.** Everything is built and tested against the simulator before hardware.
3. **Arabic-first, bilingual.** Every screen and alarm message in Arabic and English.
4. **Audited.** Every control change is written to an immutable event log.
5. **Shared contracts.** The same schemas across backend, simulator and web.
6. **AI suggests, humans decide.** AI never controls equipment directly.
7. **Works offline.** Every AI feature falls back to fixed rules.

---

## License

Private — Algaroshy Farm. All rights reserved.
