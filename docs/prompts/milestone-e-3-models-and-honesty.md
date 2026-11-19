# Prompt — Milestone E round 3: model choice, Arabic purity, no fake data

Paste this into the agent session that built `milestone-e-ai`, or into a fresh session at the repo root.

---

The AI fix round (f77686c..e767933) was reviewed **live with the owner's APInex key**.

**What now works:**
- All suites pass (API 173, web 61), lint, format and build are clean, and the migration applies to a fresh DB.
- Dependencies are in `requirements.txt`.
- Tools use their own sessions: an alarm explanation and the chat now return **real AI answers** (`provider_used: apinex`, about 8 s each) with live tool data and the correct crops.
- Settings are persisted (`PUT /ai/settings`), the per-user rate limit exists, and tests can't reach the network.

**What's left:** the items below, plus the owner's model decisions. Fix them on `milestone-e-ai`.

Read **`docs/AI_MODELS.md`** first. It's the benchmark of all 23 APInex free models on this app's tasks: pass/fail, latency, Arabic purity and quota multipliers. It's now part of the spec.

## 1. Model choice (owner decisions)
- **The admin selects the model** for each feature in the AI settings page, from the live `GET /v1/models` list.
- Show each model with the data from `docs/AI_MODELS.md`:
  - display name and id
  - quota multiplier (×2/×3/×5)
  - tools ✓ and vision ✓
  - the verdict badge: ✓ recommended / ⚠ mixes languages / ⛔ subscription-only (402) / ⛔ no chat (400)
- Put the table in a small data file (e.g. `apps/api/app/services/ai/model_catalog.py`) that the settings API returns, not hard-coded in the UI.
- Models that return 402/400 at runtime get marked unavailable automatically, cached, and are never chosen by the fallback chain.
- **Default chain:** `free/deepseek-v4-pro-0813` → `free/muse-spark-1.3` → direct Gemini → rule-based.
  - Update `config.py`, `.env.example`, the migration seed / `ai_settings` defaults, and `docs/AI.md`.
  - Today they are `free/gemini-3.8-flash` → `free/glm-5.3-flash`, which the benchmark showed mix Korean/Japanese/English into Arabic. During the review the explanation literally contained `ですが`.
- Show **the model actually used** on every AI answer (Explain panel, chat, briefing, suggestion cards). `provider_used` alone isn't enough.

## 2. Arabic-purity guard (owner decision: detect and retry the next model)
- After every Arabic answer, scan all Arabic text fields for:
  - Hangul, CJK, Kana or Cyrillic characters
  - English words of 3+ letters outside an allow-list (ALM codes, units like bar and m³/h, PLC, zone ids, model names)
- If found, **retry once with the next model in the chain**, and record `fallback_reason="language_purity"` in the admin call log.
- If the retry is also impure, return the cleaner of the two and mark it.
- Unit tests with canned impure and pure outputs (`FunctionModel`), including the allow-list.
- Add the guard to `docs/AI.md`.

## 3. NO FAKE DATA (HMI honesty: must fix)
- **Test connection is fake.**
  - `AiSettings.tsx` calls `POST /api/v1/ai/test`, **which doesn't exist**, and on error the `catch` shows `ok: true` with an invented latency (`|| 215`). It always shows "success".
  - Build the endpoint (admin): one tiny structured call to the chosen provider/model, returning `{ok, provider, model_used, latency_ms, error?}`.
  - Show real failures in the UI.
- **Zone baseline is fake.**
  - `BaselineSection.tsx` calls `GET /api/v1/ai/baselines/{zone_id}`, **which doesn't exist**, and on error shows a hard-coded "calibrated / normal" baseline (14.2 m³/h, 2.45 bar) for every zone.
  - Build the endpoint from the anomaly detector's real per-zone baseline (median/MAD bands, cycle count, calibrated yes/no).
  - Show "not enough data yet (N/5 runs)" when uncalibrated, and an error state on failure. **Never invent numbers.**
- **Audit every `catch` in `apps/web/src` that replaces a failed request with made-up values** (mock, demo, placeholder or default objects shown as real), especially in `components/ai/*`, `pages/AiSettings.tsx` and `lib/api.ts`. Replace each with an honest empty or error state.
- Add a web test that fails if a known fake fallback returns, and an API test that every URL `lib/api.ts` calls exists in the FastAPI app (route-coverage test).

## 4. Benchmark tool
- Add `tools/ai-bench/` with a maintained version of the benchmark: the same three tasks (alarm explanation, tool use, weather advice), the pass/latency/purity scoring, concurrency 2, JSON output, and a README. It must read the key from `.env` and never print it.
- Add an admin "Run benchmark" action **only if it's cheap and safe**. Otherwise just document the CLI. Ask the owner if unsure.

## 5. Verify
- All green:
  - `pytest` + `ruff check` + `ruff format --check` (api, simulator)
  - `npx vitest run`, `npx eslint .`, `pnpm build` (web)
  - `alembic upgrade head` on a fresh DB and on `farm.db`
  - fresh clone + `run.bat --smoke`
- **Live with the real key.** Exactly one API and one simulator. The owner signs in; never type passwords.
  1. The settings page lists the models with multipliers and badges; the default is `deepseek-v4-pro-0813`.
  2. "Test connection" shows a **real** latency, and a real error when you pick a 402 model.
  3. "اشرح" on an alarm answers in clean Arabic with the model name shown. Force an impure answer in a test to see the guard retry.
  4. The zone panel baseline shows real data or "not enough data". Run the leak scenario and see ALM-046.
  5. The advisor suggestion and the briefing show the model used.
- Report latencies, fallback counts and any purity retries from the live run.
- Docs: `docs/AI.md`, `docs/AI_MODELS.md` (add a "how to re-run" section), `CHANGELOG.md`, and the test counts in `PROJECT_STATUS.md`.

## Rules
- Commit on `milestone-e-ai` only (and commit `docs/AI_MODELS.md` and this prompt file, which the reviewer left uncommitted). **Don't merge or push.**
- AI stays suggest-only, with read-only tools. New migrations only. Arabic-first i18n.
- Never print or log keys or prompt text. Don't commit screenshots or throwaway scripts.
- Report honestly, with command output.
