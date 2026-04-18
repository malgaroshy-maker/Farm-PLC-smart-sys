# Algaroshy Farm Smart Automated Irrigation System — Vibecode Pack

**Farm:** Algaroshy Farm  
**Originator:** Mahamed Algaroshy — محمد عادل الجروشي  
**Purpose:** This pack contains the core product, engineering, control, API, UI, simulation, and implementation documents needed to start vibecoding the project with AI coding agents and then evolve it into a real industrial deployment.

## Pack Contents

1. `PRD.md` — master product requirements document
2. `ARCHITECTURE.md` — system architecture, layers, services, deployment modes
3. `DOMAIN_MODEL.md` — business objects and state model
4. `DATABASE_SCHEMA.md` — relational schema, event tables, telemetry model
5. `API.md` — REST API design
6. `REALTIME_EVENTS.md` — WebSocket/MQTT event contracts
7. `IO_LIST.md` — PLC, sensors, actuators, tags, and I/O mapping
8. `PLC_CONTROL_LOGIC.md` — control philosophy, sequences, interlocks, state machines
9. `ALARM_MATRIX.md` — alarm severity, triggers, actions, notifications
10. `UI_WIREFRAMES.md` — web and Android screen definitions and UX rules
11. `SIMULATION_PLAN.md` — simulation-first plan for vibecoding and testing
12. `IMPLEMENTATION_PLAN.md` — phased build plan and repository structure
13. `HARDWARE_BOM_DRAFT.md` — preliminary hardware blocks and field instrumentation list
14. `TEST_PLAN.md` — acceptance tests, scenario tests, and commissioning checks
15. `AI_AGENT_RUNBOOK.md` — prompts, build order, and rules for AI coding agents
16. `farm_layout.svg` — current farm layout graphic reference

## Suggested Build Order

1. Read `PRD.md`
2. Read `ARCHITECTURE.md`
3. Build models from `DOMAIN_MODEL.md` and `DATABASE_SCHEMA.md`
4. Implement APIs from `API.md` and real-time contracts from `REALTIME_EVENTS.md`
5. Implement simulator and control logic from `PLC_CONTROL_LOGIC.md`
6. Add alarms from `ALARM_MATRIX.md`
7. Build UI from `UI_WIREFRAMES.md`
8. Validate with `SIMULATION_PLAN.md` and `TEST_PLAN.md`

## Important Notes

- This pack is intentionally detailed enough for coding agents to scaffold and implement a first working version.
- Thresholds, hydraulic limits, and final hardware sizing still need field validation.
- The PLC must remain the local source of safety and autonomous irrigation behavior.
- Cloud and mobile/web layers must never be a hard dependency for safe operation.

## Recommended First Prototype

- Simulation-first backend with Python + FastAPI
- Web app with React + Vite + TypeScript + Tailwind
- Android app with React Native + Expo + TypeScript for speed
- Shared TypeScript/Python schemas generated from common contracts
- Local simulation mode before connecting any real PLC or sensors
