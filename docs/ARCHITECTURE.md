# ARCHITECTURE.md

## 1. Architecture Goal

Provide a structure that supports:

- local-first PLC control
- simulation-first development
- web + Android supervision
- telemetry storage
- alarming and notifications
- future hardware integration

## 2. Architecture Layers

### 2.1 Field Layer
Contains:
- pumps
- actuated valves
- pressure sensors
- flow sensors
- tank level
- moisture sensors
- optional future well level, power meter, weather station

### 2.2 Control Layer
Contains:
- Siemens-oriented PLC logic
- local control cabinet
- HMI-ready control tags
- interlocks, sequencing, retries, modes, and alarm triggers

### 2.3 Edge / Integration Layer
Contains:
- PLC adapter service
- telemetry gateway
- local persistence buffer
- MQTT/OPC UA/Modbus abstraction
- command validator

### 2.4 Backend Layer
Contains:
- REST API
- WebSocket event service
- alarm engine
- schedule service
- reporting service
- notification service
- auth and RBAC
- device/zone configuration

### 2.5 Frontend Layer
Contains:
- web dashboard
- Android app
- map visualization
- alarm center
- schedule editor
- reports and trends

## 3. Deployment Modes

### 3.1 Mode A — Pure Simulation
Used for vibecoding.
Components:
- simulator engine
- backend
- web app
- Android app
- SQLite or PostgreSQL
No real PLC required.

### 3.2 Mode B — Local Pilot
Used for first field pilot.
Components:
- simulator or PLC
- local backend on industrial PC or mini server
- web app on LAN/VPN
- Android app
- optional GSM gateway
May run fully on-site.

### 3.3 Mode C — Production Hybrid
Used for mature deployment.
Components:
- PLC on site
- edge integration service
- local database and buffer
- optional cloud sync backend
- remote monitoring apps
Control remains on site.

## 4. Recommended Tech Stack

### Backend
- Python 3.11+
- FastAPI
- SQLAlchemy
- Alembic
- PostgreSQL for central
- SQLite optional for pure simulation/local dev
- Pydantic models
- WebSockets
- Redis optional for queueing
- Celery/RQ optional for jobs
- MQTT client or OPC UA adapter for PLC bridge

### Web
- React 18
- Vite
- TypeScript
- Tailwind CSS
- React Query
- Zustand or Redux Toolkit
- SVG map renderer

### Android
Recommended fastest shared-code path:
- React Native + Expo + TypeScript

Alternative:
- Kotlin + Jetpack Compose

### Simulator
- Python service sharing backend domain models
- deterministic tick loop
- scenario injector
- event playback support

## 5. Service Boundaries

### 5.1 auth-service responsibilities
- login/logout
- tokens
- user/role permissions

### 5.2 config-service responsibilities
- zones
- crops
- source preferences
- thresholds
- zone combinations
- schedule rules

### 5.3 control-service responsibilities
- validate commands
- write commands to simulator or PLC adapter
- track command lifecycle
- return immediate status

### 5.4 telemetry-service responsibilities
- ingest measurements
- ingest device states
- store time-series points
- compute freshness and staleness

### 5.5 alarm-service responsibilities
- evaluate derived alarms
- persist alarm history
- broadcast alarm events
- manage ack/reset logic

### 5.6 report-service responsibilities
- aggregate daily logs
- runtime summaries
- water usage summaries
- export reports

### 5.7 notification-service responsibilities
- push/email/SMS routing
- escalation
- retry queues

## 6. Data Flow

1. PLC or simulator produces states and telemetry
2. edge adapter or simulator publishes normalized events
3. backend persists telemetry and device state
4. alarm engine evaluates thresholds and derived faults
5. backend emits live events over WebSocket
6. web and mobile update UI in real time
7. reports are generated from event and telemetry stores

## 7. Command Flow

1. user issues command from web/mobile
2. backend authenticates and checks role
3. backend validates business rules
4. backend sends command to simulator or PLC adapter
5. control layer accepts/rejects based on interlocks
6. result and resulting state changes are broadcast back to UI

## 8. Design Rules

- no UI may directly control hardware without backend validation
- no backend may bypass PLC interlocks in production
- cloud services may be unavailable without breaking safe irrigation
- all important state changes must produce auditable events
- simulation and production should use the same normalized contracts whenever possible

## 9. Repository Layout

```text
apps/
  api/
  web/
  mobile/
  simulator/
packages/
  contracts/
  ui/
  map-model/
  control-rules/
infra/
  docker/
  db/
docs/
  pack files
```
