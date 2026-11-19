# Prompt — Milestone E: AI that earns its place (APInex-first)

Paste this into a fresh agent session at the repo root.

---

You are continuing the Algaroshy Farm smart-irrigation project:
- pnpm + Turborepo monorepo
- FastAPI API in `apps/api`
- Python simulator in `apps/simulator`
- React 19 + Vite + Tailwind v4 web app in `apps/web`
- shared types in `packages/contracts`

Milestones A–D are done and on `master`: auth, safe commands, the simulator, alarms, the photoreal map, the virtual farm clock, programs + scheduler, the cycle log and reports.

**Your task: Milestone E (AI).** Ship four features well. Every one of them must still work when the AI service is down (a rule-based fallback), and every one of them must only **suggest**: no AI path may send a command or change a schedule on its own.

## 0. Read first
- `docs/AUDIT_AND_ROADMAP.md` (Milestone E), `docs/AI_FEATURES.md` (old wish-list: trim it to what ships), `docs/FARM_SITE.md` (**exact farm coordinates**), `docs/SIMULATION_TIME.md`, `docs/SCHEDULES.md`, `docs/ALARM_MATRIX.md`, `PROJECT_STATUS.md`.
- Code:
  - `apps/api/app/config.py` (`gemini_*`, `weather_*` settings) and `.env.example` (AI section)
  - `apps/api/app/models/ai.py` (unused AI tables: reuse or replace via a new migration)
  - `apps/api/app/services/{alarms,scheduler,cycles,telemetry,commands}.py`
  - `apps/api/app/core/{clock,alarm_catalog}.py`
  - `/health` (still reports `ai: not_implemented`)
  - `apps/web/src/{pages/AlarmCenter.tsx,pages/Schedules.tsx,pages/Dashboard.tsx,components/ZoneDrawer.tsx,components/dashboard/*,lib/i18n.ts,lib/clock.ts}`

## 1. Owner decisions (2026-11-19). Build exactly these, and record them in a new `docs/AI.md`
| # | Topic | Decision |
|---|-------|----------|
| 1 | Provider | **APInex primary, then direct Google Gemini, then rule-based.** APInex is an OpenAI-compatible gateway: `https://api.apinex.bond/v1`, `Authorization: Bearer $APINEX_API_KEY`, `POST /v1/chat/completions`, with one `model` string per vendor. Provider and model can be changed in `.env` **and** on an admin AI settings page. |
| 2 | Features | All four: **alarm assistant (AR/EN), weather-aware advisor, anomaly detection, daily briefing.** |
| 3 | Default models | **APInex free models** (`free/…`), e.g. `free/gemini-3.8-flash`. All are configurable. **Don't hard-code the list:** read `GET /v1/models` at runtime, cache it, and show it in the settings page. If a free model is rate-limited or slow, move on to the next step of the provider chain. |
| 4 | Weather | **Open-Meteo** (free, no key) at the farm site from `docs/FARM_SITE.md`: **32.516250, 14.070361**, `timezone=Africa/Tripoli`. Replace the old Tripoli placeholders in config and `.env.example`, and remove the OpenWeatherMap settings. |
| 5 | Assistant UI | **Both:** an "Explain / اشرح" button on every alarm (Alarm Center + zone panel) that opens a side panel with the explanation and follow-up questions, **plus** a floating assistant on every page that knows the live farm state. |
| 6 | Advisor UI | **Suggestion cards with one-tap approve** on the dashboard and the Schedules page (e.g. "Rain 80% at 06:00 → skip 'Morning' today"). Approve changes **only that day's run**. Reject records feedback. **Never auto-apply.** |
| 7 | Fallback provider | **Direct Gemini** (official key, its own provider), then rule-based answers. |

## 2. Stack and practices (checked with context7)
- **LLM layer: [Pydantic AI](https://ai.pydantic.dev)** (`pydantic-ai-slim[openai,google]`; pin the version you install).
  - APInex: `OpenAIChatModel('<model>', provider=OpenAICompatibleProvider('apinex', base_url=settings.apinex_base_url, api_key=settings.apinex_api_key))`.
  - Gemini: the Google provider with its own key.
  - Chain: Pydantic AI **`FallbackModel(apinex_model, gemini_model)`**, and on total failure your rule-based service.
  - **Structured output** (`output_type=` a Pydantic model) for every feature, so answers are validated and never parsed from free text. For example `AlarmExplanation{summary, likely_causes[], steps[], safety_note, confidence, language}` and `AdvisorSuggestion{...}`.
  - **Tools** for live context instead of dumping everything into the prompt: `get_alarm`, `get_zone_state`, `get_recent_telemetry`, `get_cycles`, `get_schedule`, `get_forecast`. Tools are read-only. Command or schedule tools are **not allowed**.
  - Timeouts on every call (e.g. 15 s, then fall back); retries with backoff on 429/5xx through the provider's HTTP client; a per-feature token budget; a cache of identical requests.
- **Weather: Open-Meteo** `GET https://api.open-meteo.com/v1/forecast`:
  - `latitude=32.516250&longitude=14.070361&timezone=Africa/Tripoli`
  - `hourly=precipitation_probability,precipitation,temperature_2m,relative_humidity_2m,wind_speed_10m,et0_fao_evapotranspiration`
  - `daily=precipitation_sum,precipitation_probability_max,et0_fao_evapotranspiration,temperature_2m_max`
  - `forecast_days=3`
  - Cache it (refresh every 3 h), store a snapshot, and handle 429/503. With no network, the advisor says "no forecast" and suggests nothing.
- **Anomaly detection: no LLM.** Per-zone baselines of flow and pressure from completed cycles (median + MAD / robust z-score, minimum N runs before alerting), checked live while a zone runs:
  - high flow + low pressure → **leak**
  - low flow + high pressure → **clogged emitters**
  - Raise new catalog alarms (S2), e.g. ALM-046 "Possible leak" and ALM-047 "Possible clogged emitters", in `alarm_catalog.py` + contracts + `ALARM_MATRIX.md` (contracts-sync test), with debounce. The simulator's **leak** scenario must trigger the leak alarm, and normal runs must not.
- **Testing:**
  - `pydantic_ai.models.ALLOW_MODEL_REQUESTS = False` in the test suite.
  - `TestModel` / `FunctionModel` via `agent.override(model=...)` for every agent, so tests never hit the network or need keys.
  - Mock Open-Meteo with `respx` or httpx `MockTransport`.
  - A test for each step of the provider chain: APInex fails → Gemini answers; both fail → rule-based. Each case is labelled in the response.
- **Time:** all AI features run on **farm time** (`clock.farm_now()`):
  - the briefing schedule ("each morning")
  - forecast alignment with program start times
  - anomaly windows

  At 360× the advisor and briefing must follow simulated days, using the cached forecast and never calling Open-Meteo once per simulated hour.

## 3. Privacy and safety (free models chosen, so be strict)
- Free third-party models may log prompts. **Send only what a feature needs:** farm telemetry, zone/crop names, alarm codes, cycle stats. **Never send** user names, emails, tokens, passwords, IPs or the `.env`. Add a redaction step and a test that checks the outgoing payload.
- Store keys only in `.env`. The settings page shows whether a key is set, **never the key itself**. Keys are never logged.
- **Admin-only AI toggle per feature**, plus a global "AI off" switch. When the AI is off or failing, the UI shows the rule-based answer, clearly labelled ("إجابة تلقائية بدون ذكاء اصطناعي").
- Every AI answer shows which provider/model produced it (or "rule-based") and a short disclaimer: *suggestions only — check on site*. Prompts must forbid instructions that bypass interlocks, and the system prompt must restate the safety rules from `PLC_CONTROL_LOGIC.md`.
- Rate-limit AI endpoints per user. Log AI calls (feature, provider, model, latency, tokens, fallback used) to the event log **without the prompt text**.

## 4. Features (all bilingual: answer in the UI language, Arabic first)
1. **Alarm assistant.**
   - `POST /api/v1/ai/explain-alarm {alarm_id, question?, lang}` returns `AlarmExplanation`.
   - `POST /api/v1/ai/chat {messages, lang}` powers the floating assistant (stream if practical) and uses the read-only tools.
   - Rule-based fallback: the catalog's message and guidance plus live values.
   - UI: an "اشرح / Explain" button in the Alarm Center rows and the zone panel alarms; the side panel with follow-ups; the floating assistant bubble on every page, shown only when AI is enabled.
2. **Weather-aware advisor.**
   - Before each upcoming program run (next 24 farm-hours), compare the forecast (rain probability/amount, ET₀, heat) with crop needs, and create **suggestions**: skip, shorten X%, extend X%, or move earlier/later.
   - Rules first (deterministic thresholds, documented in `docs/AI.md`). The LLM only writes the bilingual explanation.
   - `GET /api/v1/ai/suggestions`, `POST /api/v1/ai/suggestions/{id}/approve|reject`.
   - Approving creates a **one-day override** for that program run, which the scheduler must honour (skip or adjusted duration), with an event-log entry and a cycle-log note. It needs operator+ (ask the owner if you think admin-only is safer).
   - Expired suggestions disappear.
   - Cards on the dashboard side column and the Schedules page, with forecast icons (add duotone FarmIcons in the existing style).
3. **Anomaly detection.** As in §2, plus a small "baseline" section in the zone panel (normal flow/pressure band) and the anomaly alarms with AR/EN guidance.
4. **Daily briefing.**
   - Generated each farm morning (configurable time, default 06:00 farm time) from yesterday's cycle log, water, alarms, anomalies, today's programs and the forecast.
   - Stored, so it isn't regenerated on every view. `GET /api/v1/ai/briefing?date=`.
   - Card on the dashboard and the phone status screen. Rule-based fallback: a templated summary with the same numbers.

## 5. Settings and ops
- **Admin "AI" settings page:**
  - provider order
  - model per feature (from APInex `/v1/models`)
  - feature toggles
  - a "Test connection" button that shows latency and the model actually used
  - key status (set or not set)
  - the farm location (prefilled from `FARM_SITE.md`)
- `.env.example` gets `APINEX_API_KEY`, `APINEX_BASE_URL=https://api.apinex.bond/v1`, `AI_PRIMARY_MODEL`, `AI_FALLBACK_MODEL`, `GEMINI_API_KEY`, `AI_ENABLED`, the per-feature toggles, the Open-Meteo settings, and the farm coordinates. **Never** a real key.
- `/health` reports `ai: ok | degraded (fallback) | off | not_configured` and `weather: ok | stale | off`.

## 6. Tests (minimum)
- Provider chain (APInex → Gemini → rule-based) and timeouts, with structured-output validation (a malformed model answer falls back).
- Redaction (outgoing prompts contain no names, emails or tokens).
- Advisor rules: rain skip, heat extend, no forecast → no suggestion. Approve gives a one-day override that the scheduler applies exactly once; reject applies nothing.
- Anomaly: the leak scenario raises ALM-046, a normal day raises nothing, and there are no alerts before the minimum baseline runs.
- Briefing: generated once per farm day; the 360× clock gives one per simulated day; the numbers match the reports.
- Permissions: viewer can read, operator approves, admin configures.
- Web: Explain panel, floating assistant, suggestion card approve/reject, settings page, i18n keys.
- Keep everything green:
  - `pytest` + `ruff check` + `ruff format --check` (api, simulator)
  - `npx vitest run`, `npx eslint .`, `pnpm build` (no chunk warning: lazy-load the AI pages and panels)
  - `alembic upgrade head` on a fresh DB and on `farm.db`

## 7. Live check (browser)
Run **exactly one** API and **one** simulator, starting from `run.bat reset`.
1. With **no keys**, everything works on rule-based answers, clearly labelled.
2. With an APInex key, Explain on an alarm gives an Arabic answer showing the free model's name. Break the APInex key and confirm Gemini or rule-based takes over.
3. Create a program, check that the advisor shows a suggestion with the real Open-Meteo forecast for the farm site, approve it, and confirm the scheduler skips or adjusts only that run.
4. Run the leak scenario and confirm ALM-046 appears.
5. Jump to 06:00 at 360× and confirm the daily briefing appears.
6. Check the phone layout.

The owner supplies the keys. Never print them, and ask the owner to type them into `.env` themselves.

## 8. Docs
- `docs/AI.md` (decisions, architecture, prompts and redaction rules, advisor thresholds, anomaly method)
- Trim `docs/AI_FEATURES.md` to what ships, and mark the rest as deferred.
- `docs/API.md`, `docs/ALARM_MATRIX.md`, `docs/REALTIME_EVENTS.md`, `CHANGELOG.md`
- `PROJECT_STATUS.md`: move the AI gap and the weather-location gap to "What works", and update test counts.
- `docs/AUDIT_AND_ROADMAP.md`: mark Milestone E.

## Rules
- Work on branch `milestone-e-ai`. Commit in logical steps. **Don't merge or push.** The owner's reviewer reviews first.
- AI never issues commands or edits schedules on its own: only an operator's approval does, through the normal command and scheduler paths and their interlocks.
- The owner wants to be asked about every UI choice not covered above. Ask in **one round** of multiple-choice questions, each with a recommended option, before building that part.
- New migrations only. Farm time vs real time as in the clock guard test. Arabic-first i18n, glass `.panel`, FarmIcons, reduce-motion.
- Never print secrets. Don't commit screenshots or throwaway scripts.
- Report honestly: what you built, how you verified it (with command output), and what you couldn't verify (e.g. no key available).
