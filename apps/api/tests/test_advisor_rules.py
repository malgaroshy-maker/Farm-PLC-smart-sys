"""Milestone G2: the server decides irrigation advice; inputs are kept for "why?"."""

from app.services.ai.advisor_rules import AdviceInputs, decide, explain


def _i(**kw):
    base = dict(rain_mm=0.0, rain_pct=0.0, temp_max_c=25.0, et0_mm=3.0, moisture_avg_pct=35.0)
    base.update(kw)
    return AdviceInputs(**base)


def test_heavy_rain_skips_unless_soil_is_dry():
    assert decide(_i(rain_mm=8, rain_pct=85)).action == "skip"
    d = decide(_i(rain_mm=8, rain_pct=85, moisture_avg_pct=18))
    assert (d.action, d.duration_factor, d.rule) == ("reduce", 0.5, "rain_but_dry_reduce")


def test_heat_extends_more_when_dry():
    assert decide(_i(temp_max_c=40)).duration_factor == 1.2
    assert decide(_i(et0_mm=6.5, moisture_avg_pct=20)).duration_factor == 1.3


def test_cool_and_moist_reduces_and_normal_is_none():
    assert decide(_i(et0_mm=1.5, moisture_avg_pct=50)).rule == "cool_moist_reduce"
    assert decide(_i()).action == "none"


def test_inputs_are_kept_and_explained_in_both_languages():
    d = decide(_i(rain_mm=8, rain_pct=85, water_48h_m3=12.5, zones_count=3))
    keys = [r["key"] for r in d.inputs]
    assert keys[:4] == ["rain_mm", "rain_pct", "temp_max_c", "et0_mm"]
    assert "water_48h_m3" in keys and "moisture_avg_pct" in keys
    t_en, t_ar, r_en, r_ar = explain(d)
    assert "8" in r_en and "85" in r_ar and "أمطار" in t_ar
