#!/usr/bin/env python3
"""
APInex AI Model Benchmark Tool — Algaroshy Farm Smart Irrigation System

Evaluates APInex models across the 3 core agricultural irrigation tasks:
  1. Alarm Explanation (ALM-012 "No flow" on Rumman 2 -> structured Arabic diagnosis)
  2. Tool Calling ("ما حالة المنطقة رمان 2 الآن؟" -> get_zone_state -> Arabic response)
  3. Weather Advice (85% rain / 12mm -> deterministic "skip" recommendation)

Features:
  - Concurrency control (asyncio.Semaphore(2) by default)
  - Arabic language purity scoring (detects Hangul, CJK, Kana, Cyrillic, and disallowed English)
  - Safe key handling: reads APINEX_API_KEY from .env / env var; NEVER logs or prints key
  - Outputs structured JSON report and GitHub-flavored Markdown comparison table
  - Dry-run mode for CI / synthetic testing without quota consumption
"""

import argparse
import asyncio
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import re
import sys
import time
from typing import Any

import httpx

# Configure logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("ai_bench")

# Regex for foreign non-Arabic / non-Latin characters (Hangul, CJK, Kana, Cyrillic)
FOREIGN_CHAR_RE = re.compile(
    r"[\uac00-\ud7af\u1100-\u11ff\u3130-\u318f"  # Korean Hangul
    r"\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff"  # CJK Unified Ideographs
    r"\u3040-\u309f\u30a0-\u30ff"              # Japanese Hiragana & Katakana
    r"\u0400-\u04ff]"                          # Cyrillic
)

# Allow-list of legitimate technical acronyms and domain terms that may appear in Arabic text
ENGLISH_ALLOW_LIST = {
    "alm", "bar", "plc", "vfd", "modbus", "sms", "gsm", "cctv", "ups", "wan",
    "utc", "gmt", "fao", "open", "close", "auto", "manual", "off", "min", "sec",
    "hour", "day", "http", "api", "jwt", "iso", "gps", "app", "et0", "sim",
    "rumman", "zaytoun", "enab", "tin", "nakhl", "khokh", "laymoun", "burtuqal",
    "toot", "sadir", "zone", "valve", "pump", "sensor"
}

ENGLISH_WORD_RE = re.compile(r"\b[A-Za-z]{3,}\b")

# The 23 free models listed on APInex free tier
FREE_MODELS_CATALOG: list[dict[str, Any]] = [
    {"id": "free/deepseek-v4-pro-0813", "multiplier": "×3", "tools": True, "vision": False, "status": "recommended"},
    {"id": "free/muse-spark-1.3", "multiplier": "×3", "tools": True, "vision": True, "status": "recommended"},
    {"id": "free/gemini-3.8-flash", "multiplier": "×3", "tools": True, "vision": True, "status": "active"},
    {"id": "free/hy4", "multiplier": "×2", "tools": True, "vision": True, "status": "active"},
    {"id": "free/hy4-flash", "multiplier": "×2", "tools": True, "vision": True, "status": "active"},
    {"id": "free/deepseek-v4.1-flash", "multiplier": "×3", "tools": True, "vision": True, "status": "active"},
    {"id": "free/qwen-3.8-max", "multiplier": "×3", "tools": True, "vision": True, "status": "active"},
    {"id": "free/glm-5.3-flash", "multiplier": "×3", "tools": True, "vision": True, "status": "active"},
    {"id": "free/glm-5.3-flashx", "multiplier": "×3", "tools": True, "vision": True, "status": "active"},
    {"id": "free/minimax-m3.1-flash", "multiplier": "×2", "tools": True, "vision": True, "status": "active"},
    {"id": "free/mimo-v2.6-pro", "multiplier": "×2", "tools": True, "vision": True, "status": "active"},
    {"id": "free/gemini-4-hydrogen", "multiplier": "×5", "tools": True, "vision": True, "status": "active"},
    {"id": "free/gpt-6-luna", "multiplier": "×3", "tools": True, "vision": True, "status": "avoid"},
    {"id": "free/kimi-k3", "multiplier": "×3", "tools": True, "vision": True, "status": "avoid"},
    {"id": "free/claude-opus-4.6", "multiplier": "×3", "tools": True, "vision": True, "status": "unavailable_402"},
    {"id": "free/claude-sonnet-4.6", "multiplier": "×3", "tools": True, "vision": True, "status": "unavailable_402"},
    {"id": "free/gemini-3.1-pro", "multiplier": "×3", "tools": True, "vision": True, "status": "unavailable_402"},
    {"id": "free/glm-5.3", "multiplier": "×3", "tools": True, "vision": True, "status": "unavailable_402"},
    {"id": "free/kimi-k2.8", "multiplier": "×3", "tools": True, "vision": True, "status": "unavailable_402"},
    {"id": "free/minimax-m3", "multiplier": "×3", "tools": True, "vision": True, "status": "unavailable_402"},
    {"id": "free/mimo-v2.6-flash", "multiplier": "×2", "tools": True, "vision": True, "status": "unavailable_402"},
    {"id": "free/deepseek-v4-flash-0731", "multiplier": "×3", "tools": True, "vision": True, "status": "unavailable_402"},
    {"id": "free/jev-1.13", "multiplier": "×1", "tools": False, "vision": False, "status": "unavailable_400"},
]


def load_env_key() -> str:
    """Read APINEX_API_KEY from environment or workspace root .env file."""
    key = os.environ.get("APINEX_API_KEY", "").strip()
    if key:
        return key
    
    # Try finding .env file in parent directories
    candidates = [
        Path(".env"),
        Path("../../.env"),
        Path(__file__).resolve().parents[2] / ".env",
    ]
    for p in candidates:
        if p.is_file():
            try:
                for line in p.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line.startswith("APINEX_API_KEY="):
                        val = line.split("=", 1)[1].strip().strip("'\"")
                        if val:
                            return val
            except Exception as e:
                log.debug("Failed reading %s: %s", p, e)
    return ""


def calculate_arabic_purity(text: str) -> tuple[int, int]:
    """
    Returns (foreign_char_count, disallowed_english_words_count).
    foreign_char_count: Hangul, CJK, Kana, Cyrillic characters.
    disallowed_english_words_count: English words >= 3 letters not in allow-list.
    """
    if not text:
        return 0, 0
    foreign_chars = len(FOREIGN_CHAR_RE.findall(text))
    words = ENGLISH_WORD_RE.findall(text)
    disallowed_words = [
        w for w in words
        if w.lower() not in ENGLISH_ALLOW_LIST and not w.startswith("ALM-")
    ]
    return foreign_chars, len(disallowed_words)


@dataclass
class TaskResult:
    task_name: str
    passed: bool
    latency_s: float
    foreign_chars: int = 0
    disallowed_english_words: int = 0
    error: str | None = None
    output_preview: str = ""


@dataclass
class ModelBenchmarkResult:
    model_id: str
    multiplier: str
    tools: bool
    vision: bool
    passed_runs: int = 0
    total_runs: int = 0
    avg_latency_s: float = 0.0
    task_latencies: dict[str, float] = field(default_factory=dict)
    total_foreign_chars: int = 0
    total_disallowed_words: int = 0
    verdict: str = ""
    error_summary: str | None = None
    task_details: list[TaskResult] = field(default_factory=list)


# ── Benchmark Task Runners ───────────────────────────────────────────────────


async def run_alarm_task(
    client: httpx.AsyncClient,
    base_url: str,
    api_key: str,
    model_id: str,
    dry_run: bool = False,
) -> TaskResult:
    """Task 1: Alarm Explanation for ALM-012."""
    if dry_run:
        await asyncio.sleep(0.05)
        mock_arabic = (
            "تشخيص الإنذار: لم يتم رصد أي تدفق في المنطقة رمان 2 رغم تشغيل مضخة التعزيز. "
            "الأسباب المحتملة: عطل في صمام المنطقة أو انسداد الخط. "
            "الخطوات: 1. فحص الصمام valve_rumman_2 يدوياً. 2. التحقق من ضغط الخط الرئيسي. "
            "ملاحظة أمان: لا تقم بتجاوز قفل الأمان الهيدروليكي."
        )
        return TaskResult(
            task_name="alarm",
            passed=True,
            latency_s=0.5,
            foreign_chars=0,
            disallowed_english_words=1,  # valve_rumman_2 has valve/rumman
            output_preview=mock_arabic[:80],
        )

    prompt = (
        "You are Algaroshy Farm AI Assistant. Respond in Arabic. "
        "Alarm ALM-012 (No flow detected) is active on zone_rumman_2 (Pomegranate 2). "
        "Measured flow: 0.3 m³/h (expected: 3.0 m³/h). Main pressure: 3.8 bar. Booster pump is running. "
        "Provide: 1) Short Arabic diagnosis summary. 2) At least 2 likely causes. "
        "3) Step-by-step operator actions. 4) A safety warning."
    )
    t0 = time.monotonic()
    try:
        resp = await client.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model_id,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
                "max_tokens": 800,
            },
            timeout=60.0,
        )
        elapsed = time.monotonic() - t0
        if resp.status_code != 200:
            return TaskResult(
                task_name="alarm",
                passed=False,
                latency_s=elapsed,
                error=f"HTTP {resp.status_code}: {resp.text[:120]}",
            )
        data = resp.json()
        content = data["choices"][0]["message"].get("content", "")
        foreign, disallowed = calculate_arabic_purity(content)
        # Check basic criteria
        passed = len(content.strip()) > 50
        return TaskResult(
            task_name="alarm",
            passed=passed,
            latency_s=round(elapsed, 2),
            foreign_chars=foreign,
            disallowed_english_words=disallowed,
            output_preview=content[:80].replace("\n", " "),
        )
    except Exception as e:
        return TaskResult(
            task_name="alarm",
            passed=False,
            latency_s=round(time.monotonic() - t0, 2),
            error=str(e),
        )


async def run_tool_task(
    client: httpx.AsyncClient,
    base_url: str,
    api_key: str,
    model_id: str,
    dry_run: bool = False,
) -> TaskResult:
    """Task 2: Tool Call 'get_zone_state' for 'ما حالة المنطقة رمان 2 الآن؟'."""
    if dry_run:
        await asyncio.sleep(0.05)
        mock_arabic = (
            "حالة المنطقة رمان 2: تعمل حالياً، رطوبة التربة 38.5%، والتدفق 4.2 m³/h عند ضغط 2.1 bar."
        )
        return TaskResult(
            task_name="tool",
            passed=True,
            latency_s=0.6,
            foreign_chars=0,
            disallowed_english_words=0,
            output_preview=mock_arabic[:80],
        )

    tools_spec = [
        {
            "type": "function",
            "function": {
                "name": "get_zone_state",
                "description": "Get current telemetry and status for an irrigation zone",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "zone_id": {"type": "string", "description": "Zone identifier e.g. zone_rumman_2"}
                    },
                    "required": ["zone_id"],
                },
            },
        }
    ]

    t0 = time.monotonic()
    try:
        # Step 1: Model should call get_zone_state
        resp1 = await client.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model_id,
                "messages": [{"role": "user", "content": "ما حالة المنطقة رمان 2 الآن؟"}],
                "tools": tools_spec,
                "tool_choice": "auto",
                "temperature": 0.1,
                "max_tokens": 400,
            },
            timeout=60.0,
        )
        elapsed1 = time.monotonic() - t0
        if resp1.status_code != 200:
            return TaskResult(
                task_name="tool",
                passed=False,
                latency_s=elapsed1,
                error=f"Step 1 HTTP {resp1.status_code}: {resp1.text[:120]}",
            )
        data1 = resp1.json()
        choice1 = data1["choices"][0]["message"]
        tool_calls = choice1.get("tool_calls", [])

        if not tool_calls:
            # Model replied directly without calling tool
            content = choice1.get("content", "")
            return TaskResult(
                task_name="tool",
                passed=False,
                latency_s=round(elapsed1, 2),
                error="Model did not call get_zone_state tool",
                output_preview=content[:60],
            )

        # Step 2: Feed back realistic sensor reading
        tool_call_id = tool_calls[0]["id"]
        tool_output = json.dumps({
            "zone_id": "zone_rumman_2",
            "state": "running",
            "flow_m3h": 4.2,
            "pressure_bar": 2.1,
            "moisture_pct": 38.5,
        })
        messages = [
            {"role": "user", "content": "ما حالة المنطقة رمان 2 الآن؟"},
            choice1,
            {"role": "tool", "tool_call_id": tool_call_id, "content": tool_output},
        ]

        resp2 = await client.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model_id,
                "messages": messages,
                "temperature": 0.1,
                "max_tokens": 400,
            },
            timeout=60.0,
        )
        elapsed_total = time.monotonic() - t0
        if resp2.status_code != 200:
            return TaskResult(
                task_name="tool",
                passed=False,
                latency_s=round(elapsed_total, 2),
                error=f"Step 2 HTTP {resp2.status_code}: {resp2.text[:120]}",
            )

        final_content = resp2.json()["choices"][0]["message"].get("content", "")
        foreign, disallowed = calculate_arabic_purity(final_content)
        # Verify numbers from tool call appear in response
        has_numbers = any(num in final_content for num in ("38.5", "4.2", "2.1"))
        return TaskResult(
            task_name="tool",
            passed=has_numbers,
            latency_s=round(elapsed_total, 2),
            foreign_chars=foreign,
            disallowed_english_words=disallowed,
            error=None if has_numbers else "Numbers from tool result missing in answer",
            output_preview=final_content[:80].replace("\n", " "),
        )
    except Exception as e:
        return TaskResult(
            task_name="tool",
            passed=False,
            latency_s=round(time.monotonic() - t0, 2),
            error=str(e),
        )


async def run_weather_advice_task(
    client: httpx.AsyncClient,
    base_url: str,
    api_key: str,
    model_id: str,
    dry_run: bool = False,
) -> TaskResult:
    """Task 3: Weather Advice on 85% rain / 12mm -> must output 'skip'."""
    if dry_run:
        await asyncio.sleep(0.05)
        mock_arabic = (
            '{"action": "skip", "reason_ar": "يُنصح بتخطي دورة الري نظراً لاحتمال هطول أمطار بنسبة 85% وهطول متوقع 12 ملم."}'
        )
        return TaskResult(
            task_name="advice",
            passed=True,
            latency_s=0.4,
            foreign_chars=0,
            disallowed_english_words=0,
            output_preview=mock_arabic[:80],
        )

    prompt = (
        "You are an agricultural irrigation advisor. "
        "A scheduled irrigation run is set for 06:00 tomorrow morning. "
        "Weather forecast: Precipitation probability 85%, expected rainfall 12.0 mm. "
        "According to farm rules, if rain >= 50% or precipitation >= 2mm, irrigation must be skipped. "
        "Output JSON only with keys 'action' (must be exactly 'skip', 'extend', or 'proceed') "
        "and 'reason_ar' in Arabic."
    )
    t0 = time.monotonic()
    try:
        resp = await client.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model_id,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 400,
            },
            timeout=60.0,
        )
        elapsed = time.monotonic() - t0
        if resp.status_code != 200:
            return TaskResult(
                task_name="advice",
                passed=False,
                latency_s=round(elapsed, 2),
                error=f"HTTP {resp.status_code}: {resp.text[:120]}",
            )
        content = resp.json()["choices"][0]["message"].get("content", "")
        foreign, disallowed = calculate_arabic_purity(content)

        # Check for skip decision
        action_skip = '"action": "skip"' in content.lower() or "skip" in content.lower()
        return TaskResult(
            task_name="advice",
            passed=action_skip,
            latency_s=round(elapsed, 2),
            foreign_chars=foreign,
            disallowed_english_words=disallowed,
            error=None if action_skip else "Did not recommend 'skip' for 85% rain / 12mm",
            output_preview=content[:80].replace("\n", " "),
        )
    except Exception as e:
        return TaskResult(
            task_name="advice",
            passed=False,
            latency_s=round(time.monotonic() - t0, 2),
            error=str(e),
        )


# ── Benchmark Controller ─────────────────────────────────────────────────────


async def benchmark_model(
    model_meta: dict[str, Any],
    base_url: str,
    api_key: str,
    tasks_to_run: list[str],
    runs_per_task: int,
    semaphore: asyncio.Semaphore,
    dry_run: bool = False,
) -> ModelBenchmarkResult:
    """Benchmark a single model across requested tasks with concurrency control."""
    model_id = model_meta["id"]
    res = ModelBenchmarkResult(
        model_id=model_id,
        multiplier=model_meta.get("multiplier", "×1"),
        tools=model_meta.get("tools", True),
        vision=model_meta.get("vision", False),
    )

    # Known unusable models in catalog can be flagged directly if dry_run isn't forcing test
    if not dry_run and model_meta.get("status") in ("unavailable_402", "unavailable_400"):
        res.verdict = "⛔ " + ("subscription-only (402)" if "402" in model_meta["status"] else "no chat (400)")
        res.error_summary = "Pre-screened as unavailable on this key"
        return res

    async with semaphore:
        log.info("Testing model: %s", model_id)
        async with httpx.AsyncClient() as client:
            task_fns = {
                "alarm": run_alarm_task,
                "tool": run_tool_task,
                "advice": run_weather_advice_task,
            }

            for t_name in tasks_to_run:
                fn = task_fns[t_name]
                t_latencies: list[float] = []
                for _ in range(runs_per_task):
                    res.total_runs += 1
                    tr = await fn(client, base_url, api_key, model_id, dry_run=dry_run)
                    res.task_details.append(tr)
                    if tr.passed:
                        res.passed_runs += 1
                        t_latencies.append(tr.latency_s)
                        res.total_foreign_chars += tr.foreign_chars
                        res.total_disallowed_words += tr.disallowed_english_words
                    else:
                        if not res.error_summary:
                            res.error_summary = tr.error

                if t_latencies:
                    res.task_latencies[t_name] = round(sum(t_latencies) / len(t_latencies), 1)

    # Calculate overall average latency
    all_lats = [tr.latency_s for tr in res.task_details if tr.passed]
    res.avg_latency_s = round(sum(all_lats) / len(all_lats), 1) if all_lats else 0.0

    # Determine verdict
    pass_rate = (res.passed_runs / res.total_runs) if res.total_runs else 0.0
    if pass_rate == 1.0:
        if res.total_foreign_chars == 0 and res.total_disallowed_words <= 5:
            res.verdict = "✓ Recommended default: clean Arabic & fast"
        elif res.total_foreign_chars > 15 or res.total_disallowed_words > 20:
            res.verdict = "⚠ Avoid: heavy mixing or English responses"
        else:
            res.verdict = "✓ Operational: minor language mixing"
    elif pass_rate > 0.5:
        res.verdict = "⚠ Flaky: partial failures or timeouts"
    else:
        res.verdict = "⛔ Failed / Unavailable"

    return res


def generate_markdown_table(results: list[ModelBenchmarkResult]) -> str:
    """Format benchmark results into Markdown table."""
    lines = [
        "| Model | ×quota | Tools | Vision | Pass | Alarm (s) | Tool (s) | Advice (s) | Foreign chars | English words | Verdict |",
        "|-------|:-----:|:-----:|:------:|:----:|:--------:|:-------:|:---------:|:-------------:|:-------------:|---------|",
    ]
    for r in results:
        tools_mark = "✓" if r.tools else "—"
        vision_mark = "✓" if r.vision else "—"
        pass_str = f"{r.passed_runs}/{r.total_runs}"
        alm_s = f"{r.task_latencies.get('alarm', '—')}"
        tool_s = f"{r.task_latencies.get('tool', '—')}"
        adv_s = f"{r.task_latencies.get('advice', '—')}"
        lines.append(
            f"| `{r.model_id}` | {r.multiplier} | {tools_mark} | {vision_mark} | "
            f"{pass_str} | {alm_s} | {tool_s} | {adv_s} | "
            f"{r.total_foreign_chars} | {r.total_disallowed_words} | {r.verdict} |"
        )
    return "\n".join(lines)


# ── CLI Interface ────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="APInex AI Model Benchmark Tool for Algaroshy Farm Smart Irrigation"
    )
    parser.add_argument(
        "--models",
        type=str,
        default="",
        help="Comma-separated list of model IDs to test (default: all 23 free APInex models)",
    )
    parser.add_argument(
        "--tasks",
        type=str,
        default="alarm,tool,advice",
        help="Comma-separated tasks to run (default: alarm,tool,advice)",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=1,
        help="Number of iterations per task (default: 1)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=2,
        help="Max simultaneous requests (default: 2)",
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default="https://api.apinex.bond/v1",
        help="APInex gateway URL (default: https://api.apinex.bond/v1)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="",
        help="Path to write output JSON results",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate responses without making real network requests or consuming API quota",
    )
    return parser


async def async_main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    api_key = load_env_key()
    if not api_key and not args.dry_run:
        log.error("APINEX_API_KEY is not set in environment or .env. Use --dry-run to simulate without key.")
        return 1

    tasks_to_run = [t.strip() for t in args.tasks.split(",") if t.strip()]
    valid_tasks = {"alarm", "tool", "advice"}
    if not all(t in valid_tasks for t in tasks_to_run):
        log.error("Invalid task specified. Must be subset of: %s", valid_tasks)
        return 1

    # Resolve target models
    if args.models:
        selected_ids = [m.strip() for m in args.models.split(",") if m.strip()]
        models_to_test = [
            next((m for m in FREE_MODELS_CATALOG if m["id"] == mid), {"id": mid, "multiplier": "×3", "tools": True, "vision": False})
            for mid in selected_ids
        ]
    else:
        models_to_test = FREE_MODELS_CATALOG

    log.info("Starting benchmark on %d models (concurrency=%d, dry_run=%s)", len(models_to_test), args.concurrency, args.dry_run)
    semaphore = asyncio.Semaphore(args.concurrency)

    benchmark_tasks = [
        benchmark_model(
            model_meta=m,
            base_url=args.base_url,
            api_key=api_key,
            tasks_to_run=tasks_to_run,
            runs_per_task=args.runs,
            semaphore=semaphore,
            dry_run=args.dry_run,
        )
        for m in models_to_test
    ]

    results = await asyncio.gather(*benchmark_tasks)

    # Render Markdown table
    md_table = generate_markdown_table(results)
    print("\n" + md_table + "\n")

    # Save JSON if requested
    if args.output:
        out_path = Path(args.output)
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "dry_run": args.dry_run,
            "tasks": tasks_to_run,
            "runs_per_task": args.runs,
            "results": [asdict(r) for r in results],
        }
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        log.info("JSON report saved to %s", out_path)

    return 0


def main():
    try:
        sys.exit(asyncio.run(async_main()))
    except KeyboardInterrupt:
        log.info("Interrupted by user")
        sys.exit(130)


if __name__ == "__main__":
    main()
