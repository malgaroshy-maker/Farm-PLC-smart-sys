from datetime import UTC, datetime, time, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

import pytest
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import FunctionModel

from app.core.clock import clock
from app.database import async_session_factory
from app.models.irrigation_cycle import IrrigationCycle
from app.services.ai.agent import alarm_agent, chat, explain_alarm
from app.services.ai.rules import rule_service
from app.services.ai.tools import AIDeps, get_cycles, get_forecast, get_zone_state
from app.services.weather import weather_service
from tests.conftest import login, push_state


def test_offline_briefing_counts_critical_alarms_and_preserves_estimates():
    briefing = rule_service.daily_briefing(
        "2026-11-26",
        cycles=[{"outcome": "completed", "water_volume_m3": 0.7, "water_is_estimate": True}],
        alarms=[{"severity": "S3", "status": "active_unacked"}],
    )
    assert "1 active alarm" in briefing.alarms_overview
    assert "Estimated total: 0.7" in briefing.irrigation_overview
    assert "normal" not in briefing.summary.lower()


@pytest.mark.asyncio
async def test_explanation_uses_alarm_identity_and_server_safety(client):
    seen = []

    def respond(messages, info):
        seen.append(str(messages))
        return ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name=info.output_tools[0].name,
                    args={
                        "alarm_code": "UNKNOWN",
                        "severity": "S0",
                        "title": "Test",
                        "title_ar": "اختبار",
                        "diagnosis": "Check the site.",
                        "diagnosis_ar": "تحقّق من الموقع.",
                        "safety_critical": False,
                        "confidence": 0.99,
                    },
                )
            ]
        )

    with alarm_agent.override(model=FunctionModel(respond)):
        alarm = {"alarm_code": "ALM-005", "current_value": 1}
        first = await explain_alarm({**alarm, "zone_id": "audit-a"})
        second = await explain_alarm({**alarm, "zone_id": "audit-b"}, question="هل يتوقف الضخ؟")

    assert len(seen) == 2
    assert "audit-a" in seen[0] and "audit-b" in seen[1]
    assert "هل يتوقف الضخ؟" in seen[1]
    assert first.alarm_code == second.alarm_code == "ALM-005"
    assert first.severity == second.severity == "S3"
    assert first.safety_critical and second.safety_critical
    assert first.confidence is None and second.confidence is None


@pytest.mark.asyncio
async def test_tools_keep_missing_telemetry_and_synthetic_forecast_unavailable(client):
    ctx = SimpleNamespace(deps=AIDeps(session_factory=async_session_factory))
    zone = await get_zone_state(ctx, "zone_rumman_1")
    assert zone["flow_m3h"] is None and zone["pressure_bar"] is None
    assert zone["valve_open"] is None and zone["updated_at"] is None
    assert zone["data_fresh"] is False
    with patch.object(weather_service, "get_forecast", AsyncMock(return_value=None)):
        forecast = await get_forecast(ctx)
    assert forecast == {"available": False, "source": None, "days": []}


def test_provider_key_cannot_be_redirected_from_ai_settings(client):
    headers = login(client, "admin")
    response = client.put(
        "/api/v1/ai/settings",
        headers=headers,
        json={
            "apinex_base_url": "https://unexpected.example/v1",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_cycle_tool_resolves_zone_code_and_uses_farm_local_day(client):
    tz = ZoneInfo("Africa/Tripoli")
    day = clock.farm_now().astimezone(tz).date() - timedelta(days=1)
    local_midnight = datetime.combine(day, time.min, tzinfo=tz).astimezone(UTC)
    async with async_session_factory() as db:
        db.add_all(
            [
                IrrigationCycle(
                    id="audit_before_day",
                    zone_id="zone_rumman_1",
                    outcome="completed",
                    actual_start_at=local_midnight - timedelta(minutes=1),
                ),
                IrrigationCycle(
                    id="audit_inside_day",
                    zone_id="zone_rumman_1",
                    outcome="completed",
                    actual_start_at=local_midnight + timedelta(minutes=1),
                    water_estimate_m3=0.73,
                    water_is_estimate=True,
                ),
            ]
        )
        await db.commit()
    ctx = SimpleNamespace(deps=AIDeps(session_factory=async_session_factory))
    result = await get_cycles(ctx, zone_id="rumman_1", local_date=day.isoformat())
    assert [row["cycle_id"] for row in result["cycles"]] == ["audit_inside_day"]
    assert result["cycles"][0]["water_volume_m3"] == 0.73
    assert result["cycles"][0]["water_is_estimate"] is True
    assert "error" in await get_cycles(ctx, zone_id="nonexistent")
    answer = await chat("ما حجم مياه الري في rumman_1 أمس؟")
    assert answer.model_used == "farm_records"
    assert answer.references == ["get_cycles"]
    assert "0.73" in answer.reply_ar and "المقدّر" in answer.reply_ar


@pytest.mark.parametrize("language", ["ar", "en"])
def test_explain_a_real_alarm_by_its_id(client, language):
    """The Explain button sends the alarm's record id (it answered 500 for every alarm)."""
    push_state(client, plc_alarms=[{"code": "ALM-005", "device_id": "pump_booster_01"}])
    admin = login(client, "admin")
    [alarm] = [
        a
        for a in client.get("/api/v1/alarms", headers=admin).json()
        if a["alarm_code"] == "ALM-005"
    ]
    r = client.post(
        "/api/v1/ai/explain-alarm",
        headers=admin,
        json={"alarm_id": alarm["id"], "language": language},
    )
    assert r.status_code == 200, r.text
    assert r.json()["alarm_code"] == "ALM-005"
