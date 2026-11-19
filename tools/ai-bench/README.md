# APInex AI Model Benchmark Tool (`tools/ai-bench`)

Automated benchmark runner evaluating APInex models across the three core AI tasks of the Algaroshy Farm Smart Irrigation System:

1. **Alarm Explanation (`alarm`)**: Explains active alarm `ALM-012` (*No flow detected*) on Pomegranate 2 (`zone_rumman_2`). Evaluates structured diagnosis, likely causes, step-by-step actions, and safety warning in Arabic.
2. **Tool Use (`tool`)**: Tests function calling with prompt *"ما حالة المنطقة رمان 2 الآن؟"*. The model must invoke `get_zone_state` and incorporate real telemetry (moisture: 38.5%, flow: 4.2 m³/h, pressure: 2.1 bar) into an Arabic response.
3. **Weather Advice (`advice`)**: Tests deterministic irrigation advice for an upcoming 06:00 run under forecasted 85% rain probability and 12.0 mm precipitation. The model must strictly recommend `skip`.

---

## Features

- **23 Free Models Pre-configured**: Covers every model listed with `free/` prefix on the APInex gateway.
- **Concurrency Control**: Defaults to `concurrency=2` via `asyncio.Semaphore(2)` to respect gateway rate limits.
- **Arabic Language Purity Scoring**:
  - Detects and counts foreign script pollution: Korean Hangul, CJK (Chinese / Japanese Kanji), Japanese Kana, and Cyrillic.
  - Detects disallowed English words ($\ge 3$ letters) outside an approved technical dictionary (`ALM`, `bar`, `PLC`, `VFD`, `MODBUS`, zone codes, etc.).
- **Safe Credential Handling**: Reads `APINEX_API_KEY` from the environment or `.env` file. Never prints, logs, or transmits credentials.
- **Dry-Run Mode**: Simulates full benchmark execution with canned responses for CI and offline testing without consuming API quota.
- **Outputs**: Prints GitHub-flavored Markdown comparison table and optionally saves structured JSON reports.

---

## Installation & Prerequisites

From the monorepo root:

```bash
# Python 3.11+ is required
pip install httpx
```

Ensure your `.env` contains:

```env
APINEX_API_KEY="your-apinex-api-key"
```

---

## Usage

### 1. Dry Run (No Network, No Quota Used)

```bash
python tools/ai-bench/ai_bench.py --dry-run
```

Simulates all 23 models across the 3 tasks and renders the Markdown summary table immediately.

### 2. Live Run on All Models

```bash
python tools/ai-bench/ai_bench.py --output benchmark_results.json
```

Runs all 23 models with 2 concurrent requests, prints the table, and saves full latency and purity telemetry to `benchmark_results.json`.

### 3. Test Specific Models

```bash
python tools/ai-bench/ai_bench.py --models free/deepseek-v4-pro-0813,free/muse-spark-1.3,free/gemini-3.8-flash
```

### 4. Test a Single Task

```bash
python tools/ai-bench/ai_bench.py --tasks alarm --runs 2
```

### 5. CLI Options Reference

| Option | Default | Description |
|--------|---------|-------------|
| `--models` | *All 23 free models* | Comma-separated model IDs to test |
| `--tasks` | `alarm,tool,advice` | Comma-separated tasks to run |
| `--runs` | `1` | Number of iterations per task |
| `--concurrency` | `2` | Maximum concurrent requests |
| `--base-url` | `https://api.apinex.bond/v1` | APInex gateway base URL |
| `--output` | `""` | Optional file path to export JSON results |
| `--dry-run` | `False` | Simulate responses without API calls |

---

## Methodology & Scoring

- **Pass Rate**: Fractions of runs that generated valid, compliant outputs meeting all task constraints.
- **Latency**: End-to-end wall-clock time per task in seconds.
- **Foreign Chars**: Total count of Hangul, CJK, Kana, or Cyrillic characters present in the Arabic response.
- **English Words**: Total count of Latin alphabet words ($\ge 3$ letters) appearing in Arabic sections that do not match technical abbreviations or field equipment terms.
