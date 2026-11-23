"""Deterministic irrigation advice (Milestone G2).

The server decides; the AI only explains. Every input and the rule that fired are kept,
so the operator can open "why?" and see exactly what the advice was based on.
"""

from dataclasses import dataclass, field


@dataclass
class AdviceInputs:
    rain_mm: float
    rain_pct: float
    temp_max_c: float
    et0_mm: float
    moisture_avg_pct: float | None = None
    moisture_min_pct: float | None = None
    water_48h_m3: float | None = None
    zones_count: int = 0


@dataclass
class AdviceDecision:
    action: str  # skip | extend | reduce | none
    duration_factor: float
    rule: str  # machine key, explained by the UI in AR/EN
    inputs: list[dict] = field(default_factory=list)


HEAVY_RAIN_PCT = 50.0
HEAVY_RAIN_MM = 2.0
HEAT_C = 38.0
HIGH_ET0 = 6.0
LOW_ET0 = 2.0
DRY_PCT = 25.0
MOIST_PCT = 45.0


def _inputs_list(i: AdviceInputs) -> list[dict]:
    rows = [
        {"key": "rain_mm", "value": round(i.rain_mm, 1), "unit": "mm"},
        {"key": "rain_pct", "value": round(i.rain_pct), "unit": "%"},
        {"key": "temp_max_c", "value": round(i.temp_max_c, 1), "unit": "°C"},
        {"key": "et0_mm", "value": round(i.et0_mm, 2), "unit": "mm"},
    ]
    if i.moisture_avg_pct is not None:
        rows.append({"key": "moisture_avg_pct", "value": round(i.moisture_avg_pct), "unit": "%"})
    if i.moisture_min_pct is not None:
        rows.append({"key": "moisture_min_pct", "value": round(i.moisture_min_pct), "unit": "%"})
    if i.water_48h_m3 is not None:
        rows.append({"key": "water_48h_m3", "value": round(i.water_48h_m3, 1), "unit": "m³"})
    if i.zones_count:
        rows.append({"key": "zones_count", "value": i.zones_count, "unit": ""})
    return rows


def decide(i: AdviceInputs) -> AdviceDecision:
    heavy_rain = i.rain_pct > HEAVY_RAIN_PCT or i.rain_mm > HEAVY_RAIN_MM
    hot = i.temp_max_c >= HEAT_C or i.et0_mm >= HIGH_ET0
    dry = i.moisture_avg_pct is not None and i.moisture_avg_pct < DRY_PCT
    moist = i.moisture_avg_pct is not None and i.moisture_avg_pct >= MOIST_PCT
    rows = _inputs_list(i)

    if heavy_rain and not dry:
        return AdviceDecision("skip", 0.0, "rain_skip", rows)
    if heavy_rain and dry:
        return AdviceDecision("reduce", 0.5, "rain_but_dry_reduce", rows)
    if hot:
        return AdviceDecision(
            "extend", 1.3 if dry else 1.2, "heat_dry_extend" if dry else "heat_extend", rows
        )
    if i.et0_mm < LOW_ET0 and moist:
        return AdviceDecision("reduce", 0.8, "cool_moist_reduce", rows)
    return AdviceDecision("none", 1.0, "normal", rows)


def _v(d: AdviceDecision, key: str):
    return next((r["value"] for r in d.inputs if r["key"] == key), None)


def explain(d: AdviceDecision) -> tuple[str, str, str, str]:
    """Plain (title_en, title_ar, reason_en, reason_ar) used when no AI model answers."""
    rain_mm, rain_pct = _v(d, "rain_mm"), _v(d, "rain_pct")
    tmax, et0, moist = _v(d, "temp_max_c"), _v(d, "et0_mm"), _v(d, "moisture_avg_pct")
    m_en = f" Soil moisture averages {moist} %." if moist is not None else ""
    m_ar = f" متوسط رطوبة التربة {moist} %." if moist is not None else ""
    texts = {
        "rain_skip": (
            "Skip irrigation — rain expected",
            "تخطي الري — أمطار متوقعة",
            f"Forecast: {rain_mm} mm of rain ({rain_pct} % chance).{m_en} Rain will cover the need.",
            f"التوقعات: {rain_mm} مم أمطار (احتمال {rain_pct} %).{m_ar} المطر يغطي الحاجة.",
        ),
        "rain_but_dry_reduce": (
            "Halve irrigation — rain expected but soil is dry",
            "تقليل الري إلى النصف — أمطار متوقعة والتربة جافة",
            f"Forecast: {rain_mm} mm of rain ({rain_pct} % chance), but the soil is dry.{m_en}",
            f"التوقعات: {rain_mm} مم أمطار (احتمال {rain_pct} %) لكن التربة جافة.{m_ar}",
        ),
        "heat_extend": (
            "Extend irrigation 20 % — hot day",
            "تمديد الري 20 % — يوم حار",
            f"Max {tmax} °C and ET₀ {et0} mm: the trees need more water.{m_en}",
            f"العظمى {tmax} °م والتبخر-نتح المرجعي ET₀ = {et0} مم: الأشجار تحتاج ماءً أكثر.{m_ar}",
        ),
        "heat_dry_extend": (
            "Extend irrigation 30 % — hot day and dry soil",
            "تمديد الري 30 % — يوم حار وتربة جافة",
            f"Max {tmax} °C and ET₀ {et0} mm with dry soil.{m_en}",
            f"العظمى {tmax} °م والتبخر-نتح المرجعي ET₀ = {et0} مم مع تربة جافة.{m_ar}",
        ),
        "cool_moist_reduce": (
            "Reduce irrigation 20 % — cool day, moist soil",
            "تقليل الري 20 % — يوم معتدل وتربة رطبة",
            f"ET₀ is only {et0} mm and the soil is still moist.{m_en}",
            f"التبخر-نتح المرجعي ET₀ = {et0} مم فقط والتربة ما زالت رطبة.{m_ar}",
        ),
    }
    return texts.get(d.rule, ("No change", "لا تغيير", "Conditions are normal.", "الظروف طبيعية."))
