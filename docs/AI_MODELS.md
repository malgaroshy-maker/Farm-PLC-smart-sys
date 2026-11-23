# AI models — APInex free-model benchmark

**Run on:** 2026-11-19, with the owner's APInex key, through `https://api.apinex.bond/v1`. Pydantic AI 2.71.0 with the OpenAI-compatible provider.

**What was tested:** every model whose id starts with `free/` in `GET /v1/models` (23 models), on the three jobs this application actually gives the AI:

| Task | What it checks |
|------|----------------|
| **Alarm explanation** | ALM-012 "no flow" on Rumman 2 (0.3 vs 3.0 m³/h, pump running, high pressure) → structured `AlarmExplanation` (Arabic summary, causes, ≥ 2 steps, safety note) |
| **Tool use** | "ما حالة المنطقة رمان 2 الآن؟" → the model must call `get_zone_state` and answer in Arabic with the real numbers (38.5 % moisture, 4.2 m³/h, 2.1 bar) |
| **Weather advice** | 85 % rain / 12 mm before a 06:00 program → structured `Advice`; the correct answer is **skip** |

**Two passes:**
1. All 23 models, 6 requests in parallel, to check pass/fail.
2. The 14 working models, 2 runs per task, 2 requests in parallel, to measure realistic latency and **Arabic purity**. Purity counts Korean/Chinese/Japanese/Cyrillic characters and English words of 3+ letters in the Arabic text, excluding an allow-list (ALM, bar, PLC, zone ids…).

The **quota multiplier** (×N) comes from the APInex model page, from the owner's screenshots of 2026-11-19. Even free models consume quota at that rate.

## Results (working models)

| Model | ×quota | Tools | Vision | Pass | Alarm (s) | Tool (s) | Advice (s) | Foreign chars | English words | Verdict |
|-------|:-----:|:-----:|:------:|:----:|:--------:|:-------:|:---------:|:-------------:|:-------------:|---------|
| `free/deepseek-v4-pro-0813` | ×3 | ✓ | — | 6/6 | 8.4 | 4.8 | 3.9 | 3 | 2 | **Recommended default:** fast and almost clean |
| `free/muse-spark-1.3` | ×3 | ✓ | ✓ | 6/6 | 7.2 | 53.6 | 40.6 | **0** | 4 | **Recommended second:** cleanest Arabic, slow or variable |
| `free/gemini-3.8-flash` | ×3 | ✓ | ✓ | 6/6 | 6.5 | 4.8 | 2.1 | 5 | 8 | Fast; mixes in Korean and English words |
| `free/hy4` | ×2 | ✓ | ✓ | 6/6 | 29.2 | 37.3 | 3.5 | 2 | 7 | Cheaper; slow |
| `free/hy4-flash` | ×2 | ✓ | ✓ | 6/6 | 6.5 | 4.8 | 3.3 | 10 | 5 | Cheap and fast; noticeable mixing |
| `free/deepseek-v4.1-flash` | ×3 | ✓ | ✓ | 6/6 | 8.8 | 5.5 | 2.7 | 12 | 4 | Fast; mixing |
| `free/qwen-3.8-max` | ×3 | ✓ | ✓ | 6/6 | 9.9 | 49.8 | 3.5 | 2 | 13 | English words in Arabic |
| `free/glm-5.3-flash` | ×3 | ✓ | ✓ | 6/6 | 9.1 | 30.0 | 2.4 | 9 | 9 | Mixing; large prompts (2.3k input tokens) |
| `free/glm-5.3-flashx` | ×3 | ✓ | ✓ | 6/6 | 9.2 | 39.3 | 4.3 | 5 | 10 | Mixing |
| `free/minimax-m3.1-flash` | ×2 | ✓ | ✓ | 6/6 | 27.1 | 47.8 | 46.4 | 5 | 5 | Slow |
| `free/mimo-v2.6-pro` | ×2 | ✓ | ✓ | 6/6 | 31.5 | 4.0 | 41.6 | 13 | 11 | Slow and mixing |
| `free/gemini-4-hydrogen` | ×5 | ✓ | ✓ | 6/6 | 6.3 | 28.4 | 3.2 | 10 | 12 | Most expensive; mixing |
| `free/gpt-6-luna` | ×3 | ✓ | ✓ | 6/6 | 35.2 | 5.1 | 3.8 | 2 | 18 | **Avoid:** answered the Arabic question in English |
| `free/kimi-k3` | ×3 | ✓ | ✓ | 6/6 | 7.2 | 5.1 | 42.4 | 20 | 48 | **Avoid:** heavy English/German mixing |

Every working model produced valid structured output, called the tool correctly, and chose **skip** for the rain case. They differ mainly in **speed** and **Arabic quality**.

## Not usable with this key
| Model | Reason |
|-------|--------|
| `free/claude-opus-4.6`, `free/claude-sonnet-4.6`, `free/gemini-3.1-pro`, `free/glm-5.3`, `free/kimi-k2.8`, `free/minimax-m3`, `free/mimo-v2.6-flash`, `free/deepseek-v4-flash-0731` | HTTP **402**: "available only with a subscription", even though they're listed as free |
| `free/jev-1.13` | HTTP 400: a "group decision" model that can't do chat completions (64K context, no tools per the model page) |

## Owner decisions
- **The admin chooses the model** in the AI settings page from the live `/v1/models` list. This document's verdicts show next to each model (✓ recommended / ⚠ mixing / ⛔ subscription or no chat), and models that return 402 or 400 are marked unavailable.
- **Default chain:** `free/deepseek-v4-pro-0813` → `free/muse-spark-1.3` → direct Gemini → rule-based.
- **Arabic-purity guard:** if an Arabic answer contains Korean, Chinese, Japanese or Cyrillic characters, or English words outside the allow-list, retry once with the next model in the chain, and log it in the admin AI call log.

## Notes
- Latency is a snapshot from one evening and varies a lot on the free tier. Some answers took 40–55 s, so timeouts must be per feature and the UI must show progress.
- Re-run the benchmark when APInex changes its catalogue. The maintained CLI tool lives in `tools/ai-bench/`.

## How to re-run the benchmark

A maintained benchmark CLI tool is available in [`tools/ai-bench/`](../tools/ai-bench/README.md):

### Prerequisites
- Python 3.11+
- `pip install httpx`
- Valid `APINEX_API_KEY` set in `.env` or environment

### Commands

1. **Dry-run (offline simulation, zero quota consumption):**
   ```bash
   python tools/ai-bench/ai_bench.py --dry-run
   ```

2. **Full live benchmark run (all 23 models, concurrency 2):**
   ```bash
   python tools/ai-bench/ai_bench.py --output benchmark_results.json
   ```

3. **Benchmark specific candidate models:**
   ```bash
   python tools/ai-bench/ai_bench.py --models free/deepseek-v4-pro-0813,free/muse-spark-1.3,free/gemini-3.8-flash --runs 2
   ```

4. **Benchmark a single task (e.g. tool calling):**
   ```bash
   python tools/ai-bench/ai_bench.py --tasks tool --runs 2
   ```

The runner enforces `asyncio.Semaphore(2)` concurrency, evaluates Arabic language purity (Hangul, CJK, Kana, Cyrillic, and disallowed English words), outputs a Markdown comparison table, and records structured JSON results.

## Re-test 2026-11-23 (Milestone G2)
All 22 free models were tested in parallel on two tasks: a chat answer from the live snapshot and a structured alarm explanation.
- **Working:** `deepseek-v4-pro-0813` (fastest; default), `minimax-m3.1-flash` (**new backup**: the only one with clean Arabic on both tasks), `deepseek-v4.1-flash`, `deepseek-v4-flash-0731`, `glm-5.3-flash`, `glm-5.3-flashx`, `gemini-4-hydrogen`. Most of these mix in English or Italian words such as "downstream" and "quindi"; the purity guard catches them.
- **Now 402 (subscription only):** `muse-spark-1.3` (the previous backup), `gemini-3.8-flash`, `hy4`, `hy4-flash`, `mimo-v2.6-pro`, `kimi-k3`, plus the earlier list.
- **Errored or timed out:** `gpt-6-luna`, `qwen-3.8-max`.
- **Speed varies with provider load:** `deepseek-v4-pro` took 4.5 s alone and 14–20 s at busy times. Tool round-trips added 20–40 s per answer before the G2 two-step chat.
