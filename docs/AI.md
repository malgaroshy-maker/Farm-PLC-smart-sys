# 🧠 Artificial Intelligence System — Algaroshy Farm Smart Irrigation

**Document Type:** AI Architecture, Decisions, Prompts, Redaction, and Verification Specification  
**Status:** ✅ Milestone E Delivered (2026-11-19)  
**Farm Coordinates:** `32.516250, 14.070361` (Africa/Tripoli, UTC+2)  

---

## 1. Owner Decisions (2026-11-19)

| # | Topic | Decision |
|---|-------|----------|
| 1 | **Provider Chain** | **APInex primary**, then direct **Google Gemini**, then **rule-based fallback**. APInex is an OpenAI-compatible gateway (`https://api.apinex.bond/v1`, Bearer token, `POST /v1/chat/completions`). Provider and model are configurable in `.env` and via the Admin AI Settings UI. |
| 2 | **Shipped Features** | Four core features: **Alarm Assistant (AR/EN)**, **Weather-Aware Advisor**, **Statistical Anomaly Detection**, and **Daily Briefing**. All other exploratory concepts (crop vision, voice control, seasonal learning) are deferred. |
| 3 | **Default Models** | Benchmark-validated default chain: **`free/deepseek-v4-pro-0813`** (fastest, high accuracy) → **`free/muse-spark-1.3`** (cleanest Arabic) → **`gemini-2.5-flash`** (direct Google) → **rule-based offline**. Models are not hard-coded: runtime fetches `GET /v1/models` from APInex, enriches with metadata from `docs/AI_MODELS.md`, and surfaces them in Admin Settings. Models returning 400 or 402 are marked unavailable and excluded from fallback chains. |
| 4 | **Weather Provider** | **Open-Meteo API** (free, no key required) at the exact farm coordinates (`32.516250, 14.070361`, timezone=`Africa/Tripoli`). Replaced legacy Tripoli placeholder coordinates and removed OpenWeatherMap. |
| 5 | **Assistant UI** | Dual interface: an **"Explain / اشرح"** button on every alarm row (Alarm Center and Zone Drawer) opening a dedicated side panel, plus a **persistent floating assistant** with live farm telemetry badges, interactive chat, and `model_used` badges. |
| 6 | **Advisor UI** | Suggestion cards with **one-tap approve** (with 5-second undo toast) and reject with feedback. Approving applies a 1-day override for that specific run only. **Never auto-apply.** Requires `operator+` permission. Displays active `model_used` indicator. |
| 7 | **Reliability / Offline** | Every feature includes a zero-dependency **rule-based fallback** that produces identical structured schemas when all AI providers are unavailable, rate-limited, or disabled. |
| 8 | **Arabic Purity Guard** | Automated inspection of Arabic model responses for Hangul, CJK, Kana, Cyrillic, and disallowed English words outside domain terminology. Impure responses trigger a single retry with the next model in the fallback chain (logging `fallback_reason="language_purity"`). |
| 9 | **Zero Fake Fallbacks** | Complete elimination of hard-coded mock fallbacks (e.g. `14.2 m³/h`, fake `215ms` test latency). UI surfaces honest error states, real connection test metrics via `POST /api/v1/ai/test`, and authentic cycle baseline calibration data via `GET /api/v1/ai/baselines/{zone_id}`. |

---

## 2. Architecture & Provider Fallback Chain

```
┌────────────────────────────────────────────────────────────────────────┐
│                        FastAPI Application Layer                       │
│  /api/v1/ai/explain-alarm  /chat  /suggestions  /briefing  /settings   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                  Pydantic AI Multi-Tier Fallback Agent                 │
│                                                                        │
│   Tier 1: APInex Primary (free/deepseek-v4-pro-0813)                   │
│      │ (Timeout / HTTP 429/5xx / Malformed Output / Arabic Impurity)    │
│      ▼                                                                 │
│   Tier 2: APInex Secondary (free/muse-spark-1.3)                       │
│      │ (Timeout / HTTP 429/5xx / Malformed Output / Arabic Impurity)    │
│      ▼                                                                 │
│   Tier 3: GoogleProvider (Direct Gemini API: gemini-2.5-flash)         │
│      │ (Timeout / HTTP 429/5xx / Malformed Output / No Key)            │
│      ▼                                                                 │
│   Tier 4: Rule-Based Fallback Engine (Deterministic Offline Logic)     │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
       ┌────────────────────────────┼────────────────────────────┐
       ▼                            ▼                            ▼
┌──────────────┐             ┌──────────────┐             ┌──────────────┐
│  Read-Only   │             │   Payload    │             │  Structured  │
│  Farm Tools  │             │  Redaction   │             │ Pydantic DTO │
│ (No commands)│             │ (No secrets) │             │ (Validated)  │
└──────────────┘             └──────────────┘             └──────────────┘
```

### Pydantic AI Implementation
- Built with `pydantic-ai-slim[openai,google]>=2.71.0` (pinned in `requirements.txt` and `pyproject.toml`).
- Multi-tier fallback chain: APInex primary (`free/deepseek-v4-pro-0813`) → APInex secondary fallback (`free/muse-spark-1.3`) → Google Gemini direct (`gemini-2.5-flash`) → Rule-based deterministic offline fallback.
- Utilizes `FallbackModel` with dynamic per-model settings, feature-level timeouts (45s for explain/chat, 90s for advisor/briefing), and `UsageLimits(request_limit=5)`.
- Models are constructed dynamically per request from live database settings (`ai_settings` table) or `.env` defaults without requiring API restarts.
- Structured validation guarantees outputs strictly match Pydantic schemas (`AlarmExplanation`, `AdvisorSuggestion`, `DailyBriefing`, `ChatResponse`), all returning `model_used: str`.
- Requests are hashed (SHA-256) and cached in memory to eliminate redundant LLM calls.
- In-memory ring buffer records the last 20 AI calls (feature, provider, model, latency, fallback reason) for admin visibility in the settings page. No prompt text is logged.

### Arabic-Purity Guard (`apps/api/app/services/ai/purity.py`)
- Free models frequently inject foreign Asian scripts (Hangul, CJK, Katakana) or German/English words into Arabic replies.
- The purity guard inspects Arabic text with regex for:
  - Asian/Cyrillic scripts: `[\uac00-\ud7af\u4e00-\u9fff\u3040-\u30ff\u0400-\u04ff]`
  - Disallowed English words ($\ge 3$ letters) outside a domain dictionary (`ALM`, `bar`, `PLC`, `VFD`, `MODBUS`, zone codes).
- If pollution is detected, the request retries once with the next model in the fallback chain (recording `fallback_reason="language_purity"`). If the second model is also impure, the cleaner response is selected.

### Session-Per-Tool Concurrency Architecture
When Pydantic AI executes multiple tool calls in parallel within a single LLM turn, sharing a single SQLAlchemy `AsyncSession` causes `concurrent operations are not permitted` errors. To resolve this:
- `AIDeps` carries `session_factory: async_sessionmaker[AsyncSession]` rather than an open session.
- Each tool function (`get_alarm`, `get_zone_state`, `get_recent_telemetry`, `get_cycles`, `get_schedule`, `get_forecast`) opens its own short-lived read-only session:
  ```python
  async with ctx.deps.session_factory() as db:
      # read-only query
  ```
- Parallel tool execution remains fully enabled.
- If a tool encounters missing records or unexpected parameters, it returns a concise error string or `ModelRetry` rather than raising unhandled exceptions.

### Dynamic Farm-Context Injection
To ensure prompts and rule-based answers reflect genuine site data:
- `build_farm_context_block()` dynamically queries the `Zone` table and live telemetry snapshot.
- Injects real Arabic/English zone names, areas, valve IDs, current states, and verified crop species: pomegranate (رمان), olives (زيتون), grapes (عنب), and mixed fruit (خوخ، عوينة، مشمش).
- No farm crop lists or equipment constants are hard-coded in prompt strings.

---

## 3. Privacy, Safety & Redaction Rules

Because free/third-party AI providers may log prompts, the system enforces **zero-trust data sanitization** before any payload leaves the server:

1. **Payload Redaction (`apps/api/app/services/ai/redaction.py`):**
   - IPv4 and IPv6 addresses are masked (`<REDACTED_IP>`).
   - Email addresses are stripped (`<REDACTED_EMAIL>`).
   - Bearer / JWT tokens and API keys are masked (`<REDACTED_TOKEN>`).
   - Passwords and secret parameters are eliminated.
   - Operator and user personal names are replaced with generic roles (`<OPERATOR>`).
2. **Read-Only Context Tools (`apps/api/app/services/ai/tools.py`):**
   - `get_alarm(code)`: Fetches catalog alarm metadata and live active records.
   - `get_zone_state(zone_id)`: Fetches current status, flow, and pressure.
   - `get_recent_telemetry(zone_id, minutes)`: Retrieves recent flow/pressure samples.
   - `get_cycles(limit)`: Retrieves completed irrigation cycle logs.
   - `get_schedule()`: Reads active irrigation programs.
   - `get_forecast()`: Reads cached weather forecast.
   - **Crucial Rule:** Zero command, schedule modification, or valve control tools exist. The AI cannot physically actuate any field device.
3. **Safety Interlocks Prompts:**
   - Prompts mandate adherence to `PLC_CONTROL_LOGIC.md` and explicitly forbid advising operators to bypass hydraulic interlocks or run conflicting zones.
   - Every response contains a clear disclaimer: *"Suggestions only — inspect conditions on-site before acting / مقترحات استرشادية فقط — يرجى التحقق الميداني قبل التنفيذ"*.

---

## 4. Shipped Features

### Feature 1: AI Alarm Assistant (Bilingual AR/EN)
- **Endpoints:** `POST /api/v1/ai/explain-alarm`, `POST /api/v1/ai/chat`.
- **Behavior:** Takes an active alarm ID, pulls the alarm matrix definition and live sensor readings, and produces structured troubleshooting advice in Arabic or English.
- **Rule-Based Fallback:** If offline, synthesizes guidance directly from `app/core/alarm_catalog.py` and current telemetry values.
- **UI:** An "Explain / اشرح" button on every alarm row in Alarm Center and Zone Drawer opening a side panel, plus a persistent floating assistant on all pages.

### Feature 2: Weather-Aware Irrigation Advisor
- **Weather Integration:** `apps/api/app/services/weather.py` fetches hourly and daily data from Open-Meteo (`precipitation_probability`, `precipitation`, `temperature_2m`, `et0_fao_evapotranspiration`, `wind_speed_10m`).
- **Caching:** 3-hour cache stored in database table `weather_cache`. Respects virtual farm time (`clock.farm_now()`).
- **Deterministic Thresholds:**
  - **Rain Skip:** Precipitation probability $\ge 50\%$ OR expected rainfall $\ge 2.0\text{ mm}$ within the scheduled window $\rightarrow$ Suggests skipping the run.
  - **Heat/Drought Extension:** Max temperature $\ge 38^\circ\text{C}$ OR $\text{ET}_0 \ge 7.0\text{ mm/day}$ $\rightarrow$ Suggests extending duration by $+20\%$.
  - **No Forecast:** If weather API is unreachable and cache expired, generates no suggestion.
- **One-Day Overrides:** Approving a suggestion (`POST /api/v1/ai/suggestions/{id}/approve`) records a `ProgramOverride` for that farm date. The scheduler (`app/services/scheduler.py`) honors this override exactly once and marks it applied. Rejecting records operator feedback.

### Feature 3: Statistical Anomaly Detection (No LLM)
- **Engine:** `apps/api/app/services/anomaly.py`. Pure robust statistical analysis using Median and Median Absolute Deviation (MAD / robust z-score).
- **Baselines:** Computed per zone from completed cycles in `irrigation_cycles` (minimum $N=3$ runs required).
- **Live Detection Rules:**
  - **Mainline Leak:** High flow ($z > +2.5$) and low pressure ($z < -2.0$) $\rightarrow$ Raises **ALM-046** (*"Possible leak / تسريب محتمل في الخط الرئيسي"*).
  - **Clogged Emitters:** Low flow ($z < -2.5$) and high pressure ($z > +2.0$) $\rightarrow$ Raises **ALM-047** (*"Possible clogged emitters / انسداد محتمل في النقاطات"*).
- **Filtering:** 15-second grace period ignores valve travel and pump ramp-up pressure spikes; 10-second debounce prevents false alarms.

### Feature 4: Daily Morning Briefing
- **Generation:** Scheduled at `06:00` farm time on `clock.farm_now()`.
- **Synthesis:** Aggregates yesterday's water consumption, cycle count and outcomes, tripped alarms, detected anomalies, today's upcoming programs, and today's weather forecast.
- **Storage:** Persisted in `ai_briefings` table (`GET /api/v1/ai/briefing?date=YYYY-MM-DD`).
- **UI:** Top hero collapsible card on the main dashboard feed and mobile status screen.

---

## 5. Settings, Operations & Health

- **Admin Page (`/settings/ai`):** Allows configuring provider order, selecting specific models per feature (dynamically populated from APInex enriched with metadata from `docs/AI_MODELS.md`), toggling AI globally or per-feature, running a live connection latency test (`POST /api/v1/ai/test`), and viewing recent AI calls.
- **Model Catalog Metadata (`model_catalog.py`):** Exposes 23 APInex models with quota multipliers (×2/×3/×5), tools ✓, vision ✓, and verdict badges (✓ recommended, ⚠ mixing, ⛔ subscription-only 402, ⛔ no chat 400). Runtime tracking caches 400/402 failures to exclude broken models from fallback selection.
- **Zone Baseline Calibration (`GET /api/v1/ai/baselines/{zone_id}`):** Directly queries `apps/api/app/services/anomaly.py` to retrieve true median and MAD flow and pressure bands. Returns `calibrated: true` when $\ge 5$ runs exist, or `calibrated: false` with honest run count ("بيانات غير كافية بعد (N/5 دورات)"). No hardcoded fake numbers.
- **Connection Test Endpoint (`POST /api/v1/ai/test`):** Performs a live probe against the primary provider, returning real measured latency in milliseconds, the model used, and detailed error messages on failure (no simulated success fallbacks).
- **Health Checks (`/health`):**
  - `ai`: `ok` (AI operational) | `degraded` (fallback active) | `off` (disabled) | `not_configured`.
  - `weather`: `ok` (fresh forecast) | `stale` (cache expired) | `off`.
