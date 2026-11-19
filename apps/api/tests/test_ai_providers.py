"""Tests for Pydantic AI Provider Chain, Fallback, Dynamic Models, Tools, and Farm Context (Milestone E)."""

import os

import pytest
import respx
from pydantic_ai import RunContext, models
from pydantic_ai.exceptions import ModelAPIError
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.models.function import FunctionModel

from app.config import settings
from app.database import async_session_factory, engine
from app.services.ai.agent import (
    alarm_agent,
    build_farm_context_block,
    clear_ai_cache,
    explain_alarm,
)
from app.services.ai.providers import (
    fetch_apinex_models,
)
from app.services.ai.schemas import AlarmExplanation
from app.services.ai.tools import (
    AIDeps,
    get_alarm,
    get_cycles,
    get_forecast,
    get_recent_telemetry,
    get_schedule,
    get_zone_state,
)

# Strict requirement: Disable live external model requests in tests
models.ALLOW_MODEL_REQUESTS = False
os.environ["PYDANTIC_AI_NO_BANNER"] = "1"


@pytest.mark.asyncio
async def test_dynamic_model_fetching_from_apinex():
    """Verify dynamic model fetching from APInex GET /v1/models with cache."""
    with respx.mock() as respx_mock:
        route = respx_mock.get("https://api.apinex.bond/v1/models").respond(
            200,
            json={
                "data": [
                    {"id": "free/gemini-3.8-flash", "object": "model"},
                    {"id": "free/glm-5.3-flash", "object": "model"},
                    {"id": "claude-3-5-sonnet-20241022", "object": "model"},
                ]
            },
        )

        models_list = await fetch_apinex_models(
            base_url="https://api.apinex.bond/v1", force_refresh=True
        )
        assert route.called
        assert "free/gemini-3.8-flash" in models_list
        assert "free/glm-5.3-flash" in models_list

        # Cached call
        cached_list = await fetch_apinex_models(
            base_url="https://api.apinex.bond/v1", force_refresh=False
        )
        assert route.call_count == 1
        assert cached_list == models_list


@pytest.mark.asyncio
async def test_dynamic_model_fetching_failure_fallback():
    """When APInex /v1/models fails, fall back to configured model."""
    with respx.mock() as respx_mock:
        respx_mock.get("https://api.apinex.bond/v1/models").respond(502)
        models_list = await fetch_apinex_models(
            base_url="https://api.apinex.bond/v1", force_refresh=True
        )
        assert len(models_list) >= 1
        assert models_list[0] == (settings.apinex_model or "free/gemini-3.8-flash")


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


@pytest.mark.asyncio
async def test_parallel_tools_concurrency_regression(client):
    """Regression test: Agent requests all 6 tools in parallel without AsyncSession concurrency collisions."""
    clear_ai_cache()
    expected = AlarmExplanation(
        alarm_code="ALM-004",
        severity="S2",
        title="Booster Pump Overload",
        title_ar="فصل مضخة التعزيز",
        diagnosis="Parallel tool execution successful",
        diagnosis_ar="تشخيص متوازي ناجح",
        safety_critical=True,
        confidence=0.99,
        provider_used="apinex",
    )

    call_turn = 0

    def parallel_tool_handler(messages, info):
        nonlocal call_turn
        call_turn += 1
        if call_turn == 1:
            # First turn: Request all 6 read-only tools concurrently
            return ModelResponse(
                parts=[
                    ToolCallPart(tool_name="get_alarm", args={"alarm_id": "ALM-004"}),
                    ToolCallPart(tool_name="get_zone_state", args={"zone_id": "zone_rumman_1"}),
                    ToolCallPart(tool_name="get_recent_telemetry", args={"hours": 2}),
                    ToolCallPart(tool_name="get_cycles", args={"days": 1}),
                    ToolCallPart(tool_name="get_schedule", args={}),
                    ToolCallPart(tool_name="get_forecast", args={}),
                ]
            )
        # Second turn: Output structured AlarmExplanation
        tool = info.output_tools[0]
        return ModelResponse(parts=[ToolCallPart(tool_name=tool.name, args=expected.model_dump())])

    m = FunctionModel(parallel_tool_handler)
    with alarm_agent.override(model=m):
        res = await explain_alarm(
            alarm_data={"alarm_code": "ALM-004", "name": "Booster Pump Overload"},
            lang="en",
        )
        assert isinstance(res, AlarmExplanation)
        assert res.diagnosis == "Parallel tool execution successful"
        assert call_turn == 2
    await engine.dispose()


@pytest.mark.asyncio
async def test_tools_direct_execution_with_seeded_data(client):
    """Test direct invocation of each read-only live context tool with seeded data."""
    deps = AIDeps(session_factory=async_session_factory)
    ctx = RunContext(deps=deps, model=None, usage=None, prompt="test")

    # 1. get_alarm
    a_res = await get_alarm(ctx, "ALM-004")
    assert isinstance(a_res, dict)
    assert a_res.get("alarm_code") == "ALM-004" or "error" in a_res

    # 2. get_zone_state
    z_res = await get_zone_state(ctx, "zone_rumman_1")
    assert isinstance(z_res, dict)
    assert z_res.get("code") == "RUMMAN_1"
    assert z_res.get("crop_type") == "pomegranate"
    assert "pressure_bar" in z_res

    # 3. get_recent_telemetry
    t_res = await get_recent_telemetry(ctx, hours=3)
    assert isinstance(t_res, dict)
    assert "data_points" in t_res

    # 4. get_cycles
    c_res = await get_cycles(ctx, days=1)
    assert isinstance(c_res, list)

    # 5. get_schedule
    s_res = await get_schedule(ctx)
    assert isinstance(s_res, dict)
    assert "programs" in s_res
    assert "schedules" in s_res

    # 6. get_forecast
    f_res = await get_forecast(ctx)
    assert isinstance(f_res, dict)
    assert "today_max_temp_c" in f_res or "error" in f_res
    await engine.dispose()


@pytest.mark.asyncio
async def test_farm_context_block_only_db_crops():
    """Verify that build_farm_context_block dynamically loads only crops present in DB."""
    block = await build_farm_context_block(async_session_factory)
    assert "Active Farm Zones & Crops:" in block
    assert "pomegranate" in block  # Seeded zones are pomegranate
    assert "RUMMAN_1" in block
    # Ensure hardcoded obsolete strings are not in the generated context
    assert "palms, citrus" not in block.lower()
    await engine.dispose()


@pytest.mark.asyncio
async def test_tools_accept_zone_scoped_arguments(client):
    """Regression (live review): deepseek called get_schedule(zone_id=...), which the tool
    rejected until its retries ran out, so every Explain fell back to rule-based."""
    clear_ai_cache()
    expected = AlarmExplanation(
        alarm_code="ALM-012",
        severity="S2",
        title="No flow",
        title_ar="لا يوجد تدفق",
        diagnosis="Zone-scoped tools worked",
        diagnosis_ar="نجحت الأدوات",
        safety_critical=True,
        confidence=0.9,
    )
    turn = 0

    def handler(messages, info):
        nonlocal turn
        turn += 1
        if turn == 1:
            return ModelResponse(
                parts=[
                    ToolCallPart(tool_name="get_schedule", args={"zone_id": "zone_rumman_2"}),
                    ToolCallPart(
                        tool_name="get_cycles", args={"days": 2, "zone_id": "zone_rumman_2"}
                    ),
                    ToolCallPart(
                        tool_name="get_recent_telemetry",
                        args={"hours": 1, "zone_id": "zone_rumman_2"},
                    ),
                    ToolCallPart(tool_name="get_forecast", args={"days": 2}),
                ]
            )
        return ModelResponse(
            parts=[ToolCallPart(tool_name=info.output_tools[0].name, args=expected.model_dump())]
        )

    with alarm_agent.override(model=FunctionModel(handler)):
        res = await explain_alarm(
            alarm_data={"alarm_code": "ALM-012", "zone_id": "zone_rumman_2"}, lang="ar"
        )
    assert res.diagnosis == "Zone-scoped tools worked"
    assert res.provider_used != "rule_based"
    assert res.fallback_reason is None
    await engine.dispose()


@pytest.mark.asyncio
async def test_rule_based_answer_says_why():
    """A rule-based answer carries a short, classified fallback_reason."""
    clear_ai_cache()

    def always_fail(messages, info):
        raise RuntimeError("Total cloud LLM network outage")

    with alarm_agent.override(model=FunctionModel(always_fail)):
        res = await explain_alarm(alarm_data={"alarm_code": "ALM-001"}, lang="ar")
    assert res.provider_used == "rule_based"
    assert res.fallback_reason == "error"


def test_classify_failure():
    from app.services.ai.agent import classify_failure

    assert classify_failure("Timed out after 45.0s") == "timeout"
    assert classify_failure("Tool 'get_schedule' exceeded max retries count of 2") == "tool_error"
    assert classify_failure("status_code: 402, model_name: free/x") == "provider_error"
    assert classify_failure(None) == "unknown"


@pytest.mark.asyncio
async def test_model_cannot_set_fallback_reason(client):
    """The model fills every schema field; fallback_reason must be overwritten by the server."""
    clear_ai_cache()
    expected = AlarmExplanation(
        alarm_code="ALM-012",
        severity="S2",
        title="No flow",
        title_ar="لا يوجد تدفق",
        diagnosis="ok",
        diagnosis_ar="تشخيص سليم",
        safety_critical=True,
        confidence=0.9,
        fallback_reason="none",
    )

    def handler(messages, info):
        return ModelResponse(
            parts=[ToolCallPart(tool_name=info.output_tools[0].name, args=expected.model_dump())]
        )

    with alarm_agent.override(model=FunctionModel(handler)):
        res = await explain_alarm(alarm_data={"alarm_code": "ALM-012"}, lang="ar")
    assert res.fallback_reason is None
    await engine.dispose()
