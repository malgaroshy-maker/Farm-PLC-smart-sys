"""Unit tests for Arabic Purity Guard and Retry Behavior (Milestone E Round 3)."""

import pytest
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import FunctionModel

from app.services.ai.agent import (
    alarm_agent,
    clear_ai_cache,
    explain_alarm,
    get_recent_ai_calls,
    reset_call_history,
)
from app.services.ai.purity import (
    check_arabic_text_purity,
    check_response_purity,
)
from app.services.ai.schemas import AlarmExplanation


def test_pure_arabic_with_allowed_technical_terms():
    """Valid Arabic text containing permitted engineering codes and units passes cleanly."""
    pure_text = (
        "تم رصد إنذار ALM-004 في المنطقة RUMMAN_1 بمعدل تدفق 4.2 m3/h وضغط 2.5 bar عبر جهاز PLC."
    )
    report = check_arabic_text_purity(pure_text)
    assert report.is_pure is True
    assert report.foreign_char_count == 0
    assert report.english_word_count == 0
    assert len(report.violating_words) == 0


def test_impure_foreign_scripts_detected():
    """Detects Hangul (Korean), CJK (Chinese), Kana (Japanese), and Cyrillic (Russian)."""
    # 1. Hangul
    korean_text = "فحص المضخة 오류 발생 عند بدء التشغيل"
    rep_korean = check_arabic_text_purity(korean_text)
    assert rep_korean.is_pure is False
    assert rep_korean.foreign_char_count == 4

    # 2. Chinese CJK
    cjk_text = "حالة الري 故障 في الصمام الرئيسي"
    rep_cjk = check_arabic_text_purity(cjk_text)
    assert rep_cjk.is_pure is False
    assert rep_cjk.foreign_char_count == 2

    # 3. Japanese Kana
    kana_text = "تحقق من الخط エラー الآن"
    rep_kana = check_arabic_text_purity(kana_text)
    assert rep_kana.is_pure is False
    assert rep_kana.foreign_char_count == 3

    # 4. Cyrillic
    cyrillic_text = "إنذار في المضخة ошибка في التيار"
    rep_cyrillic = check_arabic_text_purity(cyrillic_text)
    assert rep_cyrillic.is_pure is False
    assert rep_cyrillic.foreign_char_count == 6


def test_impure_english_words_outside_allow_list():
    """Flags English words of 3+ letters that are not in the technical allow-list."""
    # "warning", "system", "offline" are outside allow-list
    impure_text = "يوجد warning في system المزرعة وهو offline حالياً"
    report = check_arabic_text_purity(impure_text)
    assert report.is_pure is False
    assert report.english_word_count == 3
    assert "warning" in report.violating_words
    assert "system" in report.violating_words
    assert "offline" in report.violating_words


def test_check_response_purity_on_schema():
    """Audits nested Arabic fields of structured response schema."""
    clean_obj = AlarmExplanation(
        alarm_code="ALM-004",
        severity="S2",
        title="Overload",
        title_ar="فصل مضخة التعزيز",
        diagnosis="Tripped",
        diagnosis_ar="فصل القاطع الكهربائي بسبب زيادة الحمل على مضخة VFD",
        suggested_actions=["Inspect"],
        suggested_actions_ar=["افحص القاطع", "تحقق من PLC"],
        provider_used="apinex",
        model_used="free/deepseek-v4-pro-0813",
    )
    assert check_response_purity(clean_obj).is_pure is True

    # Inject Korean and unauthorized English in diagnosis_ar
    dirty_obj = clean_obj.model_copy(
        update={
            "diagnosis_ar": "فصل القاطع 전기 때문에 malfunction غير متوقع",
        }
    )
    dirty_rep = check_response_purity(dirty_obj)
    assert dirty_rep.is_pure is False
    assert dirty_rep.foreign_char_count == 5  # 전기 때문에
    assert "malfunction" in dirty_rep.violating_words


@pytest.mark.asyncio
async def test_agent_purity_guard_retries_and_logs_reason(client):
    """When model generates impure Arabic, agent retries with cleaner model and logs language_purity."""
    clear_ai_cache()
    reset_call_history()

    impure_first = AlarmExplanation(
        alarm_code="ALM-004",
        severity="S2",
        title="Pump Fault",
        title_ar="عطل المضخة",
        diagnosis="Motor trip",
        diagnosis_ar="فصلت المضخة 고장 مع failure في الخط",
        suggested_actions=["Check breaker"],
        suggested_actions_ar=["تحقق من القاطع"],
        provider_used="apinex",
        model_used="free/deepseek-v4-pro-0813",
    )

    pure_second = AlarmExplanation(
        alarm_code="ALM-004",
        severity="S2",
        title="Pump Fault",
        title_ar="عطل المضخة",
        diagnosis="Motor trip",
        diagnosis_ar="فصلت مضخة التعزيز بسبب الحمل الزائد على قاطع PLC",
        suggested_actions=["Check breaker"],
        suggested_actions_ar=["تحقق من القاطع"],
        provider_used="apinex",
        model_used="free/muse-spark-1.3",
    )

    call_count = 0

    def mock_model_handler(messages, info):
        nonlocal call_count
        call_count += 1
        tool = info.output_tools[0]
        # First call produces impure Arabic; second call produces clean Arabic
        chosen = impure_first if call_count == 1 else pure_second
        return ModelResponse(parts=[ToolCallPart(tool_name=tool.name, args=chosen.model_dump())])

    m = FunctionModel(mock_model_handler)

    with alarm_agent.override(model=m):
        res = await explain_alarm(
            alarm_data={"alarm_code": "ALM-004", "name": "Pump Overload"},
            lang="ar",
        )

    # Verify agent recognized impurity and retried
    assert call_count == 2
    assert res.diagnosis_ar == pure_second.diagnosis_ar
    assert "고장" not in res.diagnosis_ar

    # Verify recent calls recorded language_purity fallback reason
    recent = get_recent_ai_calls()
    assert len(recent) > 0
    latest = recent[0]
    assert latest["fallback_reason"] == "language_purity"
