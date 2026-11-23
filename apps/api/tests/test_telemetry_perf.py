"""Milestone G1: telemetry stays fast — composite index, WAL, downsampling of old data."""

import asyncio
from datetime import timedelta

from sqlalchemy import func, select, text

from app.core.clock import clock
from app.database import async_session_factory, engine
from app.models.telemetry import TelemetryPoint
from app.services.telemetry import downsample_old


def test_chart_query_uses_composite_index(client):
    async def plan():
        async with engine.connect() as conn:
            rows = (
                await conn.execute(
                    text(
                        "EXPLAIN QUERY PLAN SELECT ts, value_numeric FROM telemetry_points "
                        "WHERE metric_key = 'tank_level_pct' AND zone_id IS NULL AND ts >= '2026-01-01' "
                        "ORDER BY ts"
                    )
                )
            ).all()
            return " ".join(str(r[-1]) for r in rows)

    assert "ix_telemetry_metric_zone_ts" in asyncio.run(plan())


def test_sqlite_runs_in_wal_mode(client):
    async def mode():
        async with engine.connect() as conn:
            return (await conn.execute(text("PRAGMA journal_mode"))).scalar()

    assert asyncio.run(mode()).lower() == "wal"


def test_downsample_keeps_recent_full_and_thins_old(client):
    async def run():
        now = clock.farm_now()
        async with async_session_factory() as db:
            await db.execute(
                text("DELETE FROM telemetry_points WHERE metric_key = 'zone.moisture_pct'")
            )
            # 3 days ago: 60 samples, 10 s apart (= 2 buckets of 5 min) -> thinned to 2
            old = now - timedelta(days=3)
            for i in range(60):
                db.add(
                    TelemetryPoint(
                        metric_key="zone.moisture_pct",
                        farm_id="farm_algaroshy",
                        zone_id="zone_enab",
                        ts=old + timedelta(seconds=10 * i),
                        value_numeric=30.0,
                    )
                )
            # 1 hour ago: 30 samples -> untouched
            recent = now - timedelta(hours=1)
            for i in range(30):
                db.add(
                    TelemetryPoint(
                        metric_key="zone.moisture_pct",
                        farm_id="farm_algaroshy",
                        zone_id="zone_enab",
                        ts=recent + timedelta(seconds=10 * i),
                        value_numeric=31.0,
                    )
                )
            await db.commit()
            removed = await downsample_old(db)
            await db.commit()

            def count(since, until):
                return (
                    select(func.count())
                    .select_from(TelemetryPoint)
                    .where(
                        TelemetryPoint.metric_key == "zone.moisture_pct",
                        TelemetryPoint.ts >= since,
                        TelemetryPoint.ts < until,
                    )
                )

            old_left = (
                await db.execute(count(old - timedelta(minutes=1), old + timedelta(hours=1)))
            ).scalar()
            recent_left = (await db.execute(count(recent - timedelta(minutes=1), now))).scalar()
            return removed, old_left, recent_left

    removed, old_left, recent_left = asyncio.run(run())
    assert removed >= 57
    assert 2 <= old_left <= 3  # one per 5-minute bucket (bucket edges may split into 3)
    assert recent_left == 30


def test_rotating_log_file_redacts_tokens(tmp_path, monkeypatch):
    import logging
    from logging.handlers import RotatingFileHandler

    from app import main
    from app.config import settings

    path = tmp_path / "logs" / "api.log"
    monkeypatch.setattr(settings, "log_file", str(path))
    root = logging.getLogger()
    before = list(root.handlers)
    try:
        main.install_file_logging()
        logging.getLogger("app").warning("GET /ws?token=abcdef123456 done")
        for h in root.handlers:
            h.flush()
        text_out = path.read_text(encoding="utf-8")
        assert "done" in text_out and "abcdef123456" not in text_out
        assert any(isinstance(h, RotatingFileHandler) for h in root.handlers)
    finally:
        for h in list(root.handlers):
            if h not in before:
                root.removeHandler(h)
                h.close()


def test_series_ignores_samples_after_farm_now(client):
    """Samples left from a simulated 'future' (clock jumped back) must not leak into charts."""

    async def run():
        from app.services.telemetry import series

        now = clock.farm_now()
        async with async_session_factory() as db:
            await db.execute(
                text("DELETE FROM telemetry_points WHERE metric_key = 'main_flow_m3h'")
            )
            for i in range(10):
                db.add(
                    TelemetryPoint(
                        metric_key="main_flow_m3h",
                        farm_id="farm_algaroshy",
                        ts=now - timedelta(minutes=5 + i),
                        value_numeric=2.0,
                    )
                )
            for i in range(50):
                db.add(
                    TelemetryPoint(
                        metric_key="main_flow_m3h",
                        farm_id="farm_algaroshy",
                        ts=now + timedelta(days=3, minutes=i),
                        value_numeric=99.0,
                    )
                )
            await db.commit()
            return await series(db, "main_flow_m3h", None, 60, 60)

    pts = asyncio.run(run())
    assert 1 <= len(pts) <= 61
    assert all(p["max"] == 2.0 for p in pts)
