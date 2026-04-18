# 🌾 Algaroshy Farm — Smart Automated Irrigation System

**Farm:** Algaroshy Farm  
**Originator:** Mahamed Algaroshy — محمد عادل الجروشي  
**Status:** Phase 0 — Project Initialization  

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

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.11+, FastAPI, SQLAlchemy, Alembic, Pydantic |
| **Database** | SQLite (dev/sim) → PostgreSQL (staging/prod) |
| **Web App** | React 18, Vite, TypeScript, Tailwind CSS, Zustand, React Query |
| **Mobile App** | React Native + Expo + TypeScript |
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
│   ├── mobile/            # React Native + Expo Android app
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

- Python 3.11+
- Node.js 20+ (LTS)
- npm or pnpm
- Git

### 1. Clone & Setup

```bash
git clone <repo-url>
cd Farm-PLC
```

### 2. Backend (API + Simulator)

```bash
cd apps/api
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
python seed.py
uvicorn main:app --reload --port 8000
```

### 3. Simulator

```bash
cd apps/simulator
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run_simulator.py
```

### 4. Web Dashboard

```bash
cd apps/web
npm install
npm run dev
```

### 5. Mobile App

```bash
cd apps/mobile
npm install
npx expo start
```

---

## Build Phases

| Phase | Name | Status |
|-------|------|--------|
| **0** | Contracts & Repo Setup | 🔄 In Progress |
| **1** | Domain + Database | ⬜ Pending |
| **2** | Simulator + Live State | ⬜ Pending |
| **3** | Web MVP | ⬜ Pending |
| **4** | Android MVP | ⬜ Pending |
| **5** | Schedules + Reports | ⬜ Pending |
| **6** | Alarm Completion | ⬜ Pending |
| **7** | PLC Adapter | ⬜ Pending |

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
| [AI Agent Runbook](docs/AI_AGENT_RUNBOOK.md) | Agent coding rules and prompts |

---

## Design Principles

1. **PLC is the local safety authority** — Cloud/apps never bypass interlocks
2. **Simulation-first development** — Build everything against the simulator first
3. **Arabic-first bilingual** — All UI and alarm messages in Arabic and English
4. **Event-sourced audit** — All control changes produce immutable event logs
5. **Shared contracts** — Same schemas across backend, simulator, web, and mobile

---

## License

Private — Algaroshy Farm. All rights reserved.
