"""Milestone G2: deterministic Arabic clean-up and real farm names in the purity guard."""

from app.services.ai.arabic import normalize_output, normalize_text
from app.services.ai.purity import check_response_purity
from app.services.ai.rules import rule_service
from app.services.ai.schemas import ChatResponse


def test_digits_and_terms_are_normalized():
    assert normalize_text("الخزان ٨٠٪ وET₀ = ٢٫٨ مم") == "الخزان 80٪ وET₀ = 2.8 مم"
    assert normalize_text("معدل التبخر والتعرق اليومي") == "معدل التبخر-نتح اليومي"
    assert normalize_text("التبخر والنتح") == "التبخر-نتح"


def test_normalize_output_walks_all_text_fields():
    r = ChatResponse(reply="ok", reply_ar="المستوى ٨٠ %", references=["١٢"])
    normalize_output(r)
    assert r.reply_ar == "المستوى 80 %" and r.references == ["12"]


def test_real_farm_names_pass_the_purity_guard():
    r = ChatResponse(reply="x", reply_ar='موعد الري القادم برنامج "Live Trio" الساعة 06:00')
    assert not check_response_purity(r).is_pure
    assert check_response_purity(r, {"LIVE", "TRIO"}).is_pure


def test_rule_based_chat_uses_live_facts_and_real_crops():
    facts = {
        "tank_pct": 80.0,
        "fresh": True,
        "driest": [("zone_enab", 22.0)],
        "moisture_avg": 35.0,
        "next_run": {"time": "06:00", "zone_ar": "عنب", "zone_en": "Grapes", "minutes": 15},
        "alarm_count": 0,
        "zone_inventory": [("zone_enab", "Grapes", "عنب", "grape")],
    }
    assert "80 %" in rule_service.chat("ما حالة الخزان؟", facts=facts).reply_ar
    assert "06:00" in rule_service.chat("متى موعد الري القادم؟", facts=facts).reply_ar
    assert "22 %" in rule_service.chat("أي منطقة الأكثر جفافاً؟", facts=facts).reply_ar
    crops = rule_service.chat("ما المحاصيل في كل منطقة؟", facts=facts).reply_ar
    assert "النخيل" not in crops and "الحمضيات" not in crops and "العنب" in crops
