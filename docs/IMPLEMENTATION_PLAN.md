# IMPLEMENTATION_PLAN.md

## 1. Recommended Build Phases

### Phase 0 — Contracts and Repo Setup
Create:
- monorepo or multi-app workspace
- shared contracts package
- docs folder
- env examples
- basic CI

### Phase 1 — Domain + Database
Implement:
- core schema
- migrations
- seed data
- farm/zone/device CRUD
- event log

### Phase 2 — Simulator + Live State
Implement:
- simulator engine
- current-state endpoints
- WebSocket events
- command handling

### Phase 3 — Web MVP
Implement:
- login
- dashboard
- live map
- zone controls
- alarm center

### Phase 4 — Android MVP
Implement:
- login
- home
- live map
- alarms
- zone detail

### Phase 5 — Schedules + Reports
Implement:
- schedules CRUD
- scheduler service
- cycle logging
- basic reports

### Phase 6 — Alarm Completion
Implement:
- ack/reset
- notification routing
- SMS hooks
- recurring fault analytics

### Phase 7 — PLC Adapter
Implement:
- PLC integration bridge
- normalized tag ingest
- write command adapter
- simulator/PLC mode switch

## 2. Suggested Folder Structure

```text
apps/api
apps/web
apps/mobile
apps/simulator
packages/contracts
packages/ui
packages/map-model
packages/test-scenarios
```

## 3. MVP Milestone

A working MVP means:
- simulator runs farm logic
- web app shows live map and alarms
- user can start/stop zones
- reports show cycles and alarms
- Android app shows status and alarms

## 4. Post-MVP

- better agronomic logic
- cloud backup
- actual PLC connection
- production hardening
