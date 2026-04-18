# AI_AGENT_RUNBOOK.md

## 1. Purpose

This file tells AI coding agents how to build the project without drifting away from the intended architecture.

## 2. Global Rules for Agents

1. Respect `PRD.md` and do not invent conflicting business rules.
2. Keep PLC/local control as the safety authority.
3. Use shared schemas/contracts whenever possible.
4. Prefer small iterative commits and testable slices.
5. Keep simulation mode working at all times.
6. Do not hardcode zone names in business logic; use seeded config.
7. All commands must return explicit accept/reject reason codes.
8. All important state changes must create events and audit logs.
9. Keep Arabic-first bilingual support in data models and UI where relevant.
10. Never bypass role checks for control commands.

## 3. Recommended Prompt to Start an AI Coding Session

```text
Read these docs in order: README.md, PRD.md, ARCHITECTURE.md, DOMAIN_MODEL.md, DATABASE_SCHEMA.md, API.md, REALTIME_EVENTS.md, IO_LIST.md, PLC_CONTROL_LOGIC.md, ALARM_MATRIX.md, UI_WIREFRAMES.md, SIMULATION_PLAN.md, IMPLEMENTATION_PLAN.md, TEST_PLAN.md.

Goal:
Build the first working simulation-first version of Algaroshy Farm Smart Automated Irrigation System.

Constraints:
- Backend: FastAPI
- Web: React + Vite + TypeScript + Tailwind
- Mobile: React Native + Expo + TypeScript
- Use shared contracts
- Keep the simulator as a first-class runtime
- Implement only what is needed for the first vertical slice
- Return a concrete file plan before coding
```

## 4. Best Vertical Slice

Ask the agent to build this first:
- auth stub
- seeded farm/zones/devices
- simulator with one or two zones
- `GET /state/map`
- WebSocket zone and alarm events
- web dashboard with live map
- start/stop zone commands
- one no-flow alarm scenario
- one daily irrigation report endpoint

## 5. Best Follow-Up Prompt

```text
Implement the smallest end-to-end slice that proves the architecture:
1. seed two zones
2. build simulator state loop
3. implement current-state and command endpoints
4. emit WebSocket updates
5. build a simple map dashboard
6. support one alarm: no flow
7. add tests for valid start, invalid start, and alarm emission
```

## 6. Review Checklist for Agent Output

- Are contracts explicit?
- Are commands validated?
- Is there a state machine instead of scattered booleans?
- Is the simulator deterministic?
- Are alarms persisted and broadcast?
- Does the map show stale data clearly?
- Are there tests?

## 7. Anti-Patterns to Avoid

- putting control rules only in frontend
- directly coupling UI to raw PLC tag names
- mixing alarm text, thresholds, and logic everywhere
- skipping event logging
- allowing cloud dependency for critical operation
