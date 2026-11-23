"""Milestone G2: AI calls are logged and summarized for the admin usage view."""

import asyncio

from conftest import login

from app.services.ai.agent import log_ai_call


class _U:
    requests = 2
    input_tokens = 1200
    output_tokens = 300


def test_usage_summarizes_logged_calls(client):
    async def seed():
        await log_ai_call(None, "chat", "apinex", "free/deepseek-v4-pro-0813", 4500.0, None, _U())
        await log_ai_call(
            None, "chat", "rule_based", "offline_rules", 30000.0, "timeout: Timed out"
        )
        await log_ai_call(
            None, "explain_alarm", "apinex", "free/deepseek-v4-pro-0813", 9000.0, None, _U()
        )

    asyncio.run(seed())
    body = client.get("/api/v1/ai/usage?days=1", headers=login(client, "admin")).json()
    assert body["total"]["calls"] >= 3
    chat = next(f for f in body["by_feature"] if f["name"] == "chat")
    assert chat["calls"] >= 2 and chat["fallbacks"] >= 1 and chat["rule_based"] >= 1
    ds = next(m for m in body["by_model"] if m["name"] == "free/deepseek-v4-pro-0813")
    assert ds["input_tokens"] >= 2400 and ds["requests"] >= 4
    assert body["fallback_reasons"].get("timeout", 0) >= 1
    assert body["recent"][0]["feature"] in {"chat", "explain_alarm"}


def test_usage_is_admin_only(client):
    assert client.get("/api/v1/ai/usage", headers=login(client, "viewer")).status_code == 403
