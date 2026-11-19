"""Tests for Pydantic AI Provider Chain, Fallback, Dynamic Models, and Redaction (Milestone E)."""

import os

import pytest
import respx
from pydantic_ai import models
from pydantic_ai.exceptions import ModelAPIError
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.models.function import FunctionModel

from app.config import settings
from app.services.ai.agent import alarm_agent, clear_ai_cache, explain_alarm
from app.services.ai.providers import (
    fetch_apinex_models,
)
from app.services.ai.schemas import AlarmExplanation

# Strict requirement: Disable live external model requests in tests
models.ALLOW_MODEL_REQUESTS = False
os.environ["PYDANTIC_AI_NO_BANNER"] = "1"


@pytest.mark.asyncio
async def test_dynamic_model_fetching_from_apinex():
    """Verify dynamic model fetching from APInex GET /v1/models with cache."""
    with respx.mock(base_url="https://api.apinex.dev") as respx_mock:
        route = respx_mock.get("/v1/models").respond(
            200,
            json={
                "data": [
                    {"id": "gpt-4o-mini", "object": "model"},
                    {"id": "llama-3.3-70b-instruct", "object": "model"},
                    {"id": "claude-3-5-sonnet-20241022", "object": "model"},
                ]
            },
        )

        models_list = await fetch_apinex_models(force_refresh=True)
        assert route.called
        assert "gpt-4o-mini" in models_list
        assert "llama-3.3-70b-instruct" in models_list

        # Cached call
        cached_list = await fetch_apinex_models(force_refresh=False)
        assert route.call_count == 1
        assert cached_list == models_list


@pytest.mark.asyncio
async def test_dynamic_model_fetching_failure_fallback():
    """When APInex /v1/models fails, fall back to configured model."""
    with respx.mock(base_url="https://api.apinex.dev") as respx_mock:
        respx_mock.get("/v1/models").respond(502)
        models_list = await fetch_apinex_models(force_refresh=True)
        assert len(models_list) >= 1
        assert models_list[0] == (settings.apinex_model or "gpt-4o-mini")


@pytest.mark.asyncio
async def test_provider_chain_labels_primary_success(client):
    """Test Case 1: Primary provider succeeds -> labeled 'apinex' (or test provider)."""
    clear_ai_cache()
    expected = AlarmExplanation(
        alarm_code="ALM-004",
        severity="S2",
        title="Booster Pump Failed to Start",
        title_ar="فشل بدء مضخة التعزيز",
        diagnosis="Booster pump tripped on overload",
        diagnosis_ar="فصلت مضخة التعزيز بسبب الحمل الزائد",
        suggested_actions=["تحقق من القاطع الكهربائي", "افحص المضخة"],
        suggested_actions_en=["Check circuit breaker", "Inspect pump"],
        safety_critical=True,
        confidence=0.98,
        provider_used="apinex",
    )

    def primary_success(messages, info):
        tool = info.output_tools[0]
        return ModelResponse(parts=[ToolCallPart(tool_name=tool.name, args=expected.model_dump())])

    m_primary = FunctionModel(primary_success)
    with alarm_agent.override(model=m_primary):
        res = await explain_alarm(
            alarm_data={
                "alarm_code": "ALM-004",
                "name": "Booster Pump Failed to Start",
                "severity": "S2",
            },
            lang="ar",
        )
        assert isinstance(res, AlarmExplanation)
        assert res.alarm_code == "ALM-004"
        assert res.safety_critical is True


@pytest.mark.asyncio
async def test_provider_chain_fallback_to_gemini(client):
    """Test Case 2: Primary fails -> Fallback (Gemini) succeeds -> labeled accordingly."""

    def primary_fail(messages, info):
        raise ModelAPIError("APInex 503 Service Unavailable")

    expected = AlarmExplanation(
        alarm_code="ALM-006",
        severity="S2",
        title="Mainline Low Pressure",
        title_ar="انخفاض ضغط الخط الرئيسي",
        diagnosis="Low pressure detected",
        diagnosis_ar="رصد ضغط منخفض",
        safety_critical=True,
        confidence=0.92,
        provider_used="gemini",
    )

    def gemini_success(messages, info):
        tool = info.output_tools[0]
        return ModelResponse(parts=[ToolCallPart(tool_name=tool.name, args=expected.model_dump())])

    m_primary = FunctionModel(primary_fail)
    m_fallback = FunctionModel(gemini_success)

    fb = FallbackModel(m_primary, m_fallback, fallback_on=(Exception,))
    with alarm_agent.override(model=fb):
        res = await explain_alarm(
            alarm_data={"alarm_code": "ALM-006", "name": "Mainline Low Pressure", "severity": "S2"},
            lang="ar",
        )
        assert isinstance(res, AlarmExplanation)
        assert res.alarm_code == "ALM-006"
        assert res.safety_critical is True


@pytest.mark.asyncio
async def test_provider_chain_total_failure_rule_fallback():
    """Test Case 3: Both primary and secondary LLMs fail -> Rule-based fallback succeeds -> label 'rule_based'."""

    def always_fail(messages, info):
        raise RuntimeError("Total cloud LLM network outage")

    failing_model = FunctionModel(always_fail)
    with alarm_agent.override(model=failing_model):
        res = await explain_alarm(
            alarm_data={
                "alarm_code": "ALM-001",
                "name": "Emergency Stop Triggered",
                "name_ar": "تم تفعيل التوقف الطارئ",
                "severity": "S1",
                "current_value": 1.0,
                "threshold_value": 1.0,
            },
            lang="ar",
        )
        assert isinstance(res, AlarmExplanation)
        assert res.alarm_code == "ALM-001"
        assert res.provider_used == "rule_based"
        assert res.safety_critical is True
        assert len(res.suggested_actions) > 0
        assert len(res.suggested_actions_ar) > 0
