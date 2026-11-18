# 🌾 Algaroshy Farm — Smart Automated Irrigation System

**Farm:** Algaroshy Farm  
**Originator:** Mahamed Algaroshy — محمد عادل الجروشي  
**Status:** Milestones A–C done (foundations, simulator + alarms, demo UI + PWA). See [PROJECT_STATUS.md](PROJECT_STATUS.md)  

---

## Overview

A PLC-driven, sensor-backed, remotely observable and controllable smart irrigation platform for Algaroshy Farm. The system replaces manual monitoring and valve operation with automated control, real-time telemetry, alarms, scheduling, and reporting — while maintaining safe local-first operation even without internet.

### Key Capabilities

- 🗺️ **Live Farm Map** — Top-down interactive map with animated flow pipelines
- 🔧 **Zone Control** — Start/stop/schedule irrigation per zone with interlock protection
- 📊 **Real-Time Monitoring** — Pressure, flow, tank level, soil moisture, pump status
- 🚨 **Alarm System** — 50 alarm types with severity levels, operator guidance (AR/EN), and SMS fallback
- 📅 **Smart Scheduling** — Daily/weekly/seasonal programs with conflict detection
- 📈 **Reports** — Water usage, pump runtime, alarm history, irrigation logs
- 🔒 **Role-Based Access** — Owner/Admin, Operator, Viewer roles
- 🏭 **Local-First** — PLC handles safety; operates without internet dependency
- 🧠 **AI-Powered** — 10 smart AI features (see below)

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.11+, FastAPI, SQLAlchemy, Alembic, Pydantic |
| **AI / ML** | Google Gemini 2.5 API, NumPy, APScheduler |
| **Database** | SQLite (dev/sim) → PostgreSQL (staging/prod) |
| **Web App** | React 19, Vite 8, TypeScript, Tailwind CSS v4, Zustand, React Query |
| **Mobile** | PWA from the web app (installable on Android) |
| **Simulator** | Python engine (shared domain models, deterministic tick loop) |
| **Real-Time** | WebSocket (apps), MQTT (edge/PLC integration) |
| **PLC** | Siemens-oriented (Modbus/OPC UA adapter) |

---

## Project Structure

```
Farm-PLC/
├── apps/
│   ├── api/               # FastAPI backend
│   ├── web/               # React + Vite web dashboard
│   └── simulator/         # Python simulation engine
├── packages/
│   ├── contracts/          # Shared schemas, enums, types
│   ├── ui/                 # Shared UI components
│   ├── map-model/          # Farm map geometry and rendering model
│   └── test-scenarios/     # Simulation test scripts
├── infra/
│   ├── docker/             # Docker compose and Dockerfiles
│   └── db/                 # Migration scripts and seed data
├── docs/                   # Full documentation pack (16 files + SVGs)
├── .env.example            # Environment variable template
├── .gitignore              # Git ignore rules
├── CHANGELOG.md            # Version changelog
├── CONTRIBUTING.md         # Contribution guidelines
├── LICENSE                 # Project license
└── README.md               # This file
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

Progress is tracked in [PROJECT_STATUS.md](PROJECT_STATUS.md), and the plan is in [docs/AUDIT_AND_ROADMAP.md](docs/AUDIT_AND_ROADMAP.md):
**A** foundations ✅ → **B** simulator + alarms ✅ → **C** demo UI + PWA ✅ → **D** schedules + reports → **E** AI → production track (PLC adapter, hosting).

### 🧠 AI Features

| # | Feature | Status |
|---|---------|--------|
| 1 | AI Alarm Assistant (bilingual AR/EN) | ⬜ |
| 2 | Smart Irrigation Scheduling | ⬜ |
| 3 | Predictive Maintenance | ⬜ |
| 4 | Anomaly Detection (leaks, faults) | ⬜ |
| 5 | Weather-Aware Advisor | ⬜ |
| 6 | Water Usage Optimizer | ⬜ |
| 7 | Daily AI Insights Report | ⬜ |
| 8 | Crop Health Vision (future) | ⬜ |
| 9 | Arabic Voice Control (future) | ⬜ |
| 10 | Seasonal Learning Model (future) | ⬜ |

---

## Deployment Modes

- **Mode A — Pure Simulation**: No real hardware. Full stack against simulator. Used during development.
- **Mode B — Local Pilot**: Simulator or PLC on local network. Web on LAN/VPN.
- **Mode C — Production Hybrid**: PLC on-site, optional cloud sync, remote apps. Control stays local.

---

## Documentation

All detailed engineering documents are in [`/docs`](./docs/):

| Document | Description |
|----------|-------------|
| [PRD](docs/PRD.md) | Master product requirements |
| [Architecture](docs/ARCHITECTURE.md) | System layers, services, deployment |
| [Domain Model](docs/DOMAIN_MODEL.md) | Business objects and state models |
| [Database Schema](docs/DATABASE_SCHEMA.md) | Tables, indexes, telemetry model |
| [API](docs/API.md) | REST API design |
| [Realtime Events](docs/REALTIME_EVENTS.md) | WebSocket/MQTT event contracts |
| [IO List](docs/IO_LIST.md) | PLC tags, sensors, actuators |
| [PLC Control Logic](docs/PLC_CONTROL_LOGIC.md) | Control philosophy, sequences, interlocks |
| [Alarm Matrix](docs/ALARM_MATRIX.md) | 50 alarm definitions with full behavior |
| [UI Wireframes](docs/UI_WIREFRAMES.md) | Screen definitions and UX rules |
| [Simulation Plan](docs/SIMULATION_PLAN.md) | Simulator design and test scenarios |
| [Implementation Plan](docs/IMPLEMENTATION_PLAN.md) | Build phases and folder structure |
| [Hardware BOM](docs/HARDWARE_BOM_DRAFT.md) | Preliminary hardware list |
| [Test Plan](docs/TEST_PLAN.md) | Acceptance tests and commissioning |
| [AI Features](docs/AI_FEATURES.md) | 🧠 10 AI feature specifications |
| [AI Agent Runbook](docs/AI_AGENT_RUNBOOK.md) | Agent coding rules and prompts |

---

## Design Principles

1. **PLC is the local safety authority** — Cloud/apps never bypass interlocks
2. **Simulation-first development** — Build everything against the simulator first
3. **Arabic-first bilingual** — All UI and alarm messages in Arabic and English
4. **Event-sourced audit** — All control changes produce immutable event logs
5. **Shared contracts** — Same schemas across backend, simulator, web, and mobile
6. **AI suggests, humans decide** — AI never directly controls equipment; operator/PLC has final authority
7. **Offline-resilient AI** — All AI features degrade gracefully with local fallbacks

---

## License

Private — Algaroshy Farm. All rights reserved.
