"""Reports endpoints — /api/v1/reports (Milestone D).

Generates:
  1. /reports/daily-irrigation
  2. /reports/water-usage
  3. /reports/pump-runtime
  4. /reports/alarm-history

Supports ?format=csv with UTF-8 BOM (\xef\xbb\xbf) and Arabic headers if requested.
"""

import csv
import io
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Header, Query, Response
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.clock import clock
from app.core.timeutil import as_utc
from app.database import get_db
from app.deps import Actor, get_actor
from app.models.alarm import Alarm
from app.models.irrigation_cycle import IrrigationCycle
from app.models.pump import Pump
from app.models.zone import Zone
from app.services.pump_history import pump_history_source, summarize_pump_history
from app.services.telemetry import known_cycle_water

router = APIRouter(prefix="/reports", tags=["Reports"])


def _parse_dates(
    from_date: str | None,
    to_date: str | None,
    from_alias: str | None = None,
    to_alias: str | None = None,
) -> tuple[datetime, datetime, date, date]:
    from_str = from_date or from_alias
    to_str = to_date or to_alias
    farm_tz = ZoneInfo(settings.farm_timezone)
    now_local = clock.farm_now().astimezone(farm_tz)
    today = now_local.date()

    if to_str:
        try:
            to_d = date.fromisoformat(to_str)
        except ValueError:
            to_d = today
    else:
        to_d = today

    if from_str:
        try:
            from_d = date.fromisoformat(from_str)
        except ValueError:
            from_d = to_d - timedelta(days=6)
    else:
        from_d = to_d - timedelta(days=6)

    if from_d > to_d:
        from_d = to_d

    from_dt = as_utc(datetime.combine(from_d, time.min, tzinfo=farm_tz))
    to_dt = as_utc(datetime.combine(to_d, time.max, tzinfo=farm_tz))
    return from_dt, to_dt, from_d, to_d


def _cycles_in_range(start: datetime, end: datetime):
    return select(IrrigationCycle).where(
        IrrigationCycle.actual_start_at >= start,
        IrrigationCycle.actual_start_at <= end,
        ~IrrigationCycle.id.startswith("cyc_base_", autoescape=True),
    )


def _is_arabic(accept_language: str | None, lang_param: str | None) -> bool:
    if lang_param == "ar":
        return True
    if accept_language and "ar" in accept_language.lower():
        return True
    return False


def _csv_response(rows: list[list[str | int | float | None]], filename: str) -> Response:
    output = io.StringIO()
    # Write UTF-8 BOM
    output.write("\ufeff")
    writer = csv.writer(output, lineterminator="\r\n")
    for row in rows:
        writer.writerow(
            "'" + cell
            if isinstance(cell, str)
            and (
                cell.lstrip().startswith(("=", "+", "-", "@"))
                or cell.startswith(("\t", "\r", "\n"))
            )
            else cell
            for cell in row
        )
    content = output.getvalue().encode("utf-8")
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _add_cycle_water(entry: dict, cycle: IrrigationCycle) -> None:
    value = known_cycle_water(cycle.water_estimate_m3, cycle.water_is_estimate)
    entry["water_has_gaps"] |= cycle.water_has_gaps or value is None
    if value is not None:
        entry["total_water_m3"] = (entry["total_water_m3"] or 0) + value
        entry["water_is_estimate"] |= cycle.water_is_estimate


@router.get("/daily-irrigation")
async def daily_irrigation_report(
    from_date: str | None = Query(default=None),
    to_date: str | None = Query(default=None),
    from_: str | None = Query(default=None, alias="from"),
    to_: str | None = Query(default=None, alias="to"),
    format: str = Query(default="json"),
    lang: str | None = Query(default=None),
    accept_language: str | None = Header(default=None),
    _: Actor = Depends(get_actor),
    db: AsyncSession = Depends(get_db),
):
    """Daily irrigation summary (m³, cycle counts by outcome, duration)."""
    from_dt, to_dt, from_d, to_d = _parse_dates(from_date, to_date, from_, to_)
    farm_tz = ZoneInfo(settings.farm_timezone)

    # Query cycles in range
    res = await db.execute(_cycles_in_range(from_dt, to_dt))
    cycles = res.scalars().all()

    # Aggregate by farm-local date
    by_date: dict[str, dict] = {}
    curr = from_d
    while curr <= to_d:
        d_str = curr.isoformat()
        by_date[d_str] = {
            "date": d_str,
            "total_water_m3": None,
            "water_has_gaps": False,
            "water_is_estimate": False,
            "cycle_count": 0,
            "completed_count": 0,
            "aborted_count": 0,
            "skipped_count": 0,
            "faulted_count": 0,
            "manual_stop_count": 0,
            "total_duration_min": 0,
        }
        curr += timedelta(days=1)

    for c in cycles:
        if not c.actual_start_at:
            continue
        c_local_date = as_utc(c.actual_start_at).astimezone(farm_tz).date().isoformat()
        if c_local_date in by_date:
            entry = by_date[c_local_date]
            entry["cycle_count"] += 1
            if c.outcome == "completed":
                entry["completed_count"] += 1
            elif c.outcome == "aborted":
                entry["aborted_count"] += 1
            elif c.outcome == "skipped":
                entry["skipped_count"] += 1
            elif c.outcome == "faulted":
                entry["faulted_count"] += 1
            elif c.outcome == "manual_stop":
                entry["manual_stop_count"] += 1

            _add_cycle_water(entry, c)
            entry["total_duration_min"] += c.actual_duration_min or 0

    results = sorted(by_date.values(), key=lambda x: x["date"])
    for row in results:
        if row["total_water_m3"] is not None:
            row["total_water_m3"] = round(row["total_water_m3"], 3)

    if format.lower() == "csv":
        ar = _is_arabic(accept_language, lang)
        headers = (
            [
                "التاريخ",
                "إجمالي المياه (م³)",
                "إجمالي الدورات",
                "الدورات المكتملة",
                "الملغاة / المتوقفة",
                "المتخطاة",
                "إجمالي المدة (دقيقة)",
                "يتضمن تقديرات",
                "قراءات ناقصة",
            ]
            if ar
            else [
                "Date",
                "Total Water (m³)",
                "Total Cycles",
                "Completed Cycles",
                "Aborted / Faulted",
                "Skipped",
                "Total Duration (min)",
                "Includes estimates",
                "Missing readings",
            ]
        )
        csv_rows = [headers]
        for r in results:
            csv_rows.append(
                [
                    r["date"],
                    r["total_water_m3"],
                    r["cycle_count"],
                    r["completed_count"],
                    r["aborted_count"] + r["faulted_count"] + r["manual_stop_count"],
                    r["skipped_count"],
                    r["total_duration_min"],
                    r["water_is_estimate"],
                    r["water_has_gaps"],
                ]
            )
        return _csv_response(csv_rows, f"daily_irrigation_{from_d}_{to_d}.csv")

    return results


@router.get("/water-usage")
async def water_usage_report(
    from_date: str | None = Query(default=None),
    to_date: str | None = Query(default=None),
    from_: str | None = Query(default=None, alias="from"),
    to_: str | None = Query(default=None, alias="to"),
    zone_id: str | None = Query(default=None),
    format: str = Query(default="json"),
    lang: str | None = Query(default=None),
    accept_language: str | None = Header(default=None),
    _: Actor = Depends(get_actor),
    db: AsyncSession = Depends(get_db),
):
    """Water usage per zone over a date range."""
    from_dt, to_dt, from_d, to_d = _parse_dates(from_date, to_date, from_, to_)

    zones_res = await db.execute(select(Zone))
    zones = {z.id: z for z in zones_res.scalars().all()}

    query = _cycles_in_range(from_dt, to_dt)
    if zone_id:
        query = query.where(IrrigationCycle.zone_id == zone_id)

    cycles = (await db.execute(query)).scalars().all()

    by_zone: dict[str, dict] = {}
    for zid, z in zones.items():
        if zone_id and zid != zone_id:
            continue
        by_zone[zid] = {
            "zone_id": zid,
            "zone_name": z.name,
            "zone_name_ar": z.name_ar,
            "crop_type": z.crop_type,
            "total_water_m3": None,
            "water_has_gaps": False,
            "water_is_estimate": False,
            "cycle_count": 0,
            "completed_count": 0,
            "total_duration_min": 0,
        }

    for c in cycles:
        if c.zone_id in by_zone:
            entry = by_zone[c.zone_id]
            entry["cycle_count"] += 1
            if c.outcome == "completed":
                entry["completed_count"] += 1
            _add_cycle_water(entry, c)
            entry["total_duration_min"] += c.actual_duration_min or 0

    results = sorted(by_zone.values(), key=lambda x: x["zone_id"])
    for row in results:
        if row["total_water_m3"] is not None:
            row["total_water_m3"] = round(row["total_water_m3"], 3)

    if format.lower() == "csv":
        ar = _is_arabic(accept_language, lang)
        headers = (
            [
                "معرف المنطقة",
                "اسم المنطقة",
                "المحصول",
                "إجمالي المياه (م³)",
                "عدد الدورات",
                "الدورات المكتملة",
                "إجمالي المدة (دقيقة)",
                "يتضمن تقديرات",
                "قراءات ناقصة",
            ]
            if ar
            else [
                "Zone ID",
                "Zone Name",
                "Crop Type",
                "Total Water (m³)",
                "Cycles Count",
                "Completed Cycles",
                "Total Duration (min)",
                "Includes estimates",
                "Missing readings",
            ]
        )
        csv_rows = [headers]
        for r in results:
            name = r["zone_name_ar"] if ar and r["zone_name_ar"] else r["zone_name"]
            csv_rows.append(
                [
                    r["zone_id"],
                    name,
                    r["crop_type"] or "",
                    r["total_water_m3"],
                    r["cycle_count"],
                    r["completed_count"],
                    r["total_duration_min"],
                    r["water_is_estimate"],
                    r["water_has_gaps"],
                ]
            )
        return _csv_response(csv_rows, f"water_usage_{from_d}_{to_d}.csv")

    return results


@router.get("/pump-runtime")
async def pump_runtime_report(
    from_date: str | None = Query(default=None),
    to_date: str | None = Query(default=None),
    from_: str | None = Query(default=None, alias="from"),
    to_: str | None = Query(default=None, alias="to"),
    pump_id: str | None = Query(default=None),
    format: str = Query(default="json"),
    lang: str | None = Query(default=None),
    accept_language: str | None = Header(default=None),
    _: Actor = Depends(get_actor),
    db: AsyncSession = Depends(get_db),
):
    """Pump runtimes and starts over date range."""
    from_dt, to_dt, from_d, to_d = _parse_dates(from_date, to_date, from_, to_)

    query = select(Pump).order_by(Pump.id)
    if pump_id:
        query = query.where(Pump.id == pump_id)
    pumps = (await db.scalars(query)).all()
    stop = min(to_dt + timedelta(microseconds=1), as_utc(clock.farm_now()))
    source = pump_history_source()
    faults = dict(
        (
            await db.execute(
                select(Alarm.device_id, func.count())
                .where(
                    Alarm.category == "equipment",
                    Alarm.device_type == "pump",
                    Alarm.device_id.in_([pump.id for pump in pumps]),
                    Alarm.triggered_at >= from_dt,
                    Alarm.triggered_at < stop,
                )
                .group_by(Alarm.device_id)
            )
        ).all()
    )

    results: list[dict] = []
    for p in pumps:
        history = await summarize_pump_history(db, p.id, from_dt, stop, source)
        results.append(
            {
                "pump_id": p.id,
                "pump_name": p.name,
                "pump_name_ar": p.name_ar,
                "pump_type": p.pump_type,
                **history,
                "total_runtime_hours": history["runtime_hours"],
                "starts_count": history["start_count"],
                "faults_count": faults.get(p.id, 0),
            }
        )

    if format.lower() == "csv":
        ar = _is_arabic(accept_language, lang)
        headers = (
            [
                "معرف المضخة",
                "اسم المضخة",
                "النوع",
                "عدد مرات التشغيل",
                "ساعات التشغيل",
                "عدد الأعطال",
                "تغطية السجل",
                "المصدر",
            ]
            if ar
            else [
                "Pump ID",
                "Pump Name",
                "Type",
                "Starts Count",
                "Runtime (hours)",
                "Faults Count",
                "History coverage",
                "Source",
            ]
        )
        coverage_ar = {"unavailable": "غير متاح", "partial": "جزئي", "complete": "كامل"}
        csv_rows = [headers]
        for r in results:
            name = r["pump_name_ar"] if ar and r["pump_name_ar"] else r["pump_name"]
            csv_rows.append(
                [
                    r["pump_id"],
                    name,
                    r["pump_type"],
                    r["start_count"],
                    r["runtime_hours"],
                    r["faults_count"],
                    coverage_ar[r["history_status"]] if ar else r["history_status"],
                    ("محاكاة" if source == "simulation" else "المتحكم") if ar else source,
                ]
            )
        return _csv_response(csv_rows, f"pump_runtime_{from_d}_{to_d}.csv")

    return results


@router.get("/alarm-history")
async def alarm_history_report(
    from_date: str | None = Query(default=None),
    to_date: str | None = Query(default=None),
    from_: str | None = Query(default=None, alias="from"),
    to_: str | None = Query(default=None, alias="to"),
    severity: str | None = Query(default=None),
    zone_id: str | None = Query(default=None),
    format: str = Query(default="json"),
    lang: str | None = Query(default=None),
    accept_language: str | None = Header(default=None),
    _: Actor = Depends(get_actor),
    db: AsyncSession = Depends(get_db),
):
    """Historical alarms in date range grouped by alarm code."""
    from_dt, to_dt, from_d, to_d = _parse_dates(from_date, to_date, from_, to_)

    query = select(Alarm).where(
        Alarm.triggered_at >= from_dt,
        Alarm.triggered_at <= to_dt,
    )
    if severity:
        query = query.where(Alarm.severity == severity)
    if zone_id:
        query = query.where(Alarm.zone_id == zone_id)

    alarms = (await db.execute(query.order_by(desc(Alarm.triggered_at)))).scalars().all()

    grouped: dict[str, dict] = {}
    from app.core.alarm_catalog import CATALOG

    for a in alarms:
        code = a.alarm_code
        if code not in grouped:
            catalog_item = CATALOG.get(code)
            title = catalog_item.name if catalog_item else (a.message_en or code)
            title_ar = catalog_item.name_ar if catalog_item else (a.message_ar or code)
            sev = a.severity or (catalog_item.severity if catalog_item else "S1")
            grouped[code] = {
                "alarm_code": code,
                "count": 0,
                "severity": sev,
                "title": title,
                "title_ar": title_ar,
            }
        grouped[code]["count"] += 1

    results = sorted(grouped.values(), key=lambda x: x["count"], reverse=True)

    if format.lower() == "csv":
        ar = _is_arabic(accept_language, lang)
        headers = (
            [
                "كود الإنذار",
                "اسم الإنذار",
                "الخطورة",
                "عدد مرات الحدوث",
            ]
            if ar
            else [
                "Alarm Code",
                "Alarm Title",
                "Severity",
                "Occurrences",
            ]
        )
        csv_rows = [headers]
        for r in results:
            name = r["title_ar"] if ar and r["title_ar"] else r["title"]
            csv_rows.append(
                [
                    r["alarm_code"],
                    name,
                    r["severity"],
                    r["count"],
                ]
            )
        return _csv_response(csv_rows, f"alarm_history_{from_d}_{to_d}.csv")

    return results
