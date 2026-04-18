# Contributing to Algaroshy Farm Smart Irrigation System

## Development Philosophy

1. **Simulation-first** — All features must work against the simulator before connecting to real hardware
2. **Shared contracts** — Use the `packages/contracts` package for schemas shared between services
3. **Arabic-first bilingual** — All user-facing text must support Arabic (primary) and English
4. **Safety-critical** — Never bypass PLC interlocks or safety logic from UI or backend
5. **Event-sourced** — All state changes produce audit log entries

---

## Getting Started

1. Read the documentation in order:
   - `docs/PRD.md` → `docs/ARCHITECTURE.md` → `docs/DOMAIN_MODEL.md` → `docs/DATABASE_SCHEMA.md`
   - Then `docs/API.md` → `docs/REALTIME_EVENTS.md` → `docs/IO_LIST.md`
   - Then `docs/PLC_CONTROL_LOGIC.md` → `docs/ALARM_MATRIX.md` → `docs/UI_WIREFRAMES.md`
   - Finally `docs/SIMULATION_PLAN.md` → `docs/IMPLEMENTATION_PLAN.md` → `docs/TEST_PLAN.md`

2. Set up your development environment using the instructions in `README.md`

3. Check `PROJECT_STATUS.md` for current phase and open tasks

---

## Code Standards

### Python (Backend + Simulator)
- Python 3.11+
- Type hints everywhere
- Pydantic models for all data contracts
- FastAPI dependency injection
- Alembic for database migrations
- `black` + `ruff` for formatting/linting
- `pytest` for testing

### TypeScript (Web + Mobile)
- Strict mode enabled
- Shared contract types imported from `packages/contracts`
- React functional components with hooks
- Zustand for state management
- React Query for server state
- ESLint + Prettier for formatting

---

## Commit Conventions

Use conventional commits:

```
feat(api): add zone start/stop endpoints
fix(simulator): correct pressure decay on pump stop
docs(alarm-matrix): add ALM-051 description
test(control): add dual-zone interlock test
refactor(web): extract map renderer into shared component
```

### Scopes
- `api`, `web`, `mobile`, `simulator`
- `contracts`, `map-model`, `ui`
- `db`, `docker`, `ci`
- Docs: `prd`, `alarm-matrix`, `architecture`, etc.

---

## Branch Strategy

- `main` — stable, tested code
- `develop` — integration branch
- `feature/<name>` — feature branches
- `fix/<name>` — bugfix branches
- `phase/<N>` — phase milestone branches

---

## Pull Request Checklist

- [ ] Code follows project style guidelines
- [ ] All new state changes produce event logs
- [ ] Commands return explicit accept/reject reason codes
- [ ] Role checks are enforced on control endpoints
- [ ] Arabic and English messages provided where needed
- [ ] Simulator compatibility maintained
- [ ] Tests added for new functionality
- [ ] No hardcoded zone names in business logic
- [ ] `PROJECT_STATUS.md` updated if milestone changed

---

## Architecture Rules (Non-Negotiable)

1. No UI may directly control hardware without backend validation
2. No backend may bypass PLC interlocks in production mode
3. Cloud services may be unavailable without breaking safe irrigation
4. All important state changes must produce auditable events
5. Simulation and production use the same normalized contracts
