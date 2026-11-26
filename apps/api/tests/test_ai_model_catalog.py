"""Tests for AI Model Catalog, Runtime Availability, Connection Test, and Baselines (Milestone E Round 3)."""

from unittest.mock import AsyncMock, patch

from conftest import login
from starlette.testclient import TestClient

from app.database import async_session_factory
from app.models.irrigation_cycle import IrrigationCycle
from app.services.ai.model_catalog import (
    STATIC_MODEL_CATALOG,
    get_model_metadata,
    is_model_available,
    mark_model_available,
    mark_model_unavailable,
    reset_unavailable_cache,
)
from app.services.ai.providers import build_fallback_chain
from app.services.anomaly import BaselineStats, ZoneBaseline, anomaly_detector


def test_catalog_contains_all_23_models():
    """Verify catalog has all 23 free models from docs/AI_MODELS.md with correct badges and quotas."""
    assert len(STATIC_MODEL_CATALOG) == 23

    # Recommended models
    ds = get_model_metadata("free/deepseek-v4-pro-0813")
    assert ds.verdict == "recommended"
    assert ds.verdict_badge == "✓"
    assert ds.quota_multiplier == 3
    assert ds.available is True

    # muse-spark-1.3 became subscription-only (re-tested 2026-11-23); minimax is the backup
    muse = get_model_metadata("free/muse-spark-1.3")
    assert muse.available is False
    assert muse.verdict == "unavailable"
    backup = get_model_metadata("free/minimax-m3.1-flash")
    assert backup.verdict == "recommended"
    assert backup.available is True

    # Quota multiplier checks
    hy4 = get_model_metadata("free/hy4")
    assert hy4.quota_multiplier == 2
    h2 = get_model_metadata("free/gemini-4-hydrogen")
    assert h2.quota_multiplier == 5

    # 402/400 models are marked unavailable
    opus = get_model_metadata("free/claude-opus-4.6")
    assert opus.available is False
    assert opus.verdict == "unavailable"
    assert opus.verdict_badge == "⛔"

    jev = get_model_metadata("free/jev-1.13")
    assert jev.available is False
    assert "HTTP 400" in (jev.unavailable_reason or "")


def test_runtime_unavailable_cache_tracking():
    """Verify runtime marking of 400/402 models dynamically updates availability and metadata."""
    reset_unavailable_cache()
    model = "free/glm-5.3-flash"
    assert is_model_available(model) is True

    # Mark unavailable after 402 error
    mark_model_unavailable(model, "HTTP 402: Subscription quota exhausted")
    assert is_model_available(model) is False

    meta = get_model_metadata(model)
    assert meta.available is False
    assert meta.verdict == "unavailable"
    assert meta.verdict_badge == "⛔"
    assert "Subscription quota exhausted" in (meta.unavailable_reason or "")

    # Restore
    mark_model_available(model)
    assert is_model_available(model) is True
    reset_unavailable_cache()


def test_fallback_chain_excludes_unavailable_models():
    """Verify that build_fallback_chain excludes models marked runtime unavailable."""
    reset_unavailable_cache()
    mark_model_unavailable("free/deepseek-v4-pro-0813", "HTTP 402")

    chain = build_fallback_chain()
    # Chain models should exclude deepseek and proceed with muse-spark or gemini
    model_names = [getattr(m, "model_name", str(m)) for m in chain.models]
    assert "free/deepseek-v4-pro-0813" not in model_names
    reset_unavailable_cache()


def test_api_models_endpoint_returns_catalog(client: TestClient):
    """GET /api/v1/ai/models returns model list, full catalog with badges, and new defaults."""
    res = client.get("/api/v1/ai/models", headers=login(client, "admin"))
    assert res.status_code == 200, res.text
    data = res.json()
    assert "models" in data
    assert "catalog" in data
    assert data["selected"] == "free/deepseek-v4-pro-0813"
    assert data["fallback"] == "gemini-2.5-flash"

    catalog_ids = [m["model_id"] for m in data["catalog"]]
    assert "free/deepseek-v4-pro-0813" in catalog_ids
    assert "free/muse-spark-1.3" in catalog_ids


def test_api_test_endpoint_admin_only_and_runtime_marking(client: TestClient, monkeypatch):
    """POST /api/v1/ai/test requires admin role and marks 400/402 models unavailable."""
    reset_unavailable_cache()
    from types import SimpleNamespace

    from app.config import settings
    from app.services.ai.schemas import ChatResponse

    monkeypatch.setattr(settings, "apinex_api_key", "offline-fixture")

    # Viewer role -> 403 Forbidden
    viewer = login(client, "viewer")
    r_forbidden = client.post(
        "/api/v1/ai/test", json={"model": "free/deepseek-v4-pro-0813"}, headers=viewer
    )
    assert r_forbidden.status_code == 403

    admin = login(client, "admin")

    # Mock successful test ping
    with patch("pydantic_ai.Agent.run", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = SimpleNamespace(
            output=ChatResponse(reply="OK"),
            response=SimpleNamespace(model_name="free/deepseek-v4-pro-0813"),
        )
        r_ok = client.post(
            "/api/v1/ai/test",
            json={"provider": "apinex", "model": "free/deepseek-v4-pro-0813"},
            headers=admin,
        )
        assert r_ok.status_code == 200, r_ok.text
        data = r_ok.json()
        assert data["ok"] is True
        assert data["model_used"] == "free/deepseek-v4-pro-0813"
        assert data["latency_ms"] >= 0.0

    # Mock 402 failure -> model marked unavailable
    test_target = "free/hy4"
    from pydantic_ai.exceptions import ModelHTTPError

    with patch("pydantic_ai.Agent.run", side_effect=ModelHTTPError(402, test_target)):
        r_fail = client.post(
            "/api/v1/ai/test",
            json={"provider": "apinex", "model": test_target},
            headers=admin,
        )
        assert r_fail.status_code == 200
        fail_data = r_fail.json()
        assert fail_data["ok"] is False
        assert "402" in fail_data["error"]
        assert is_model_available(test_target) is False

    reset_unavailable_cache()


def test_api_baselines_endpoint(client: TestClient):
    """GET /api/v1/ai/baselines/{zone_id} returns real median/MAD bands and calibration status."""
    operator = login(client, "operator")

    # 1. Zone with no completed runs -> not calibrated
    res = client.get("/api/v1/ai/baselines/zone_rumman_1", headers=operator)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["zone_id"] == "zone_rumman_1"
    assert data["calibrated"] is False
    assert "not enough data yet" in data["message"]

    # 2. Seed an anomaly baseline in detector with min 5 runs
    b_flow = BaselineStats(median=12.5, mad=0.8, scale=1.18, count=6)
    b_press = BaselineStats(median=2.4, mad=0.15, scale=0.22, count=6)
    zb = ZoneBaseline(
        zone_id="zone_rumman_1",
        flow=b_flow,
        pressure=b_press,
        runs_count=6,
        computed_at=None,
    )
    anomaly_detector.set_baseline(zb)

    # Insert 6 completed cycles into DB
    import asyncio

    from app.core.clock import clock

    async def _seed_cycles():
        now = clock.farm_now()
        async with async_session_factory() as s:
            for i in range(6):
                s.add(
                    IrrigationCycle(
                        id=f"cyc_test_baseline_{i}",
                        zone_id="zone_rumman_1",
                        outcome="completed",
                        actual_start_at=now,
                        actual_end_at=now,
                        water_estimate_m3=12.5,
                        actual_duration_min=20.0,
                    )
                )
            await s.commit()

    asyncio.run(_seed_cycles())

    res2 = client.get("/api/v1/ai/baselines/zone_rumman_1", headers=operator)
    assert res2.status_code == 200
    calib_data = res2.json()
    assert calib_data["calibrated"] is True
    assert calib_data["flow_median_m3h"] == 12.5
    assert calib_data["pressure_median_bar"] == 2.4
    assert calib_data["flow_min_normal_m3h"] > 0
    assert calib_data["status"] == "normal"
