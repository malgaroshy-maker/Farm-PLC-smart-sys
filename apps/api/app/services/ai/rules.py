"""Rule-Based Fallback Service for AI Core (Milestone E).

Provides deterministic, offline-first responses when external AI providers
(APInex / Gemini) are unavailable, offline, or fail.
Strictly returns structured Pydantic models.
"""

from typing import Any

from app.core.alarm_catalog import ALARM_CATALOG
from app.services.ai.schemas import (
    AdvisorSuggestion,
    AlarmExplanation,
    ChatResponse,
    DailyBriefing,
)
from app.services.weather import WeatherForecast


class RuleBasedService:
    """Deterministic fallback service for AI features."""

    def explain_alarm(self, alarm_data: dict[str, Any], lang: str = "ar") -> AlarmExplanation:
        """Generate structured explanation using ALARM_CATALOG and live readings."""
        alarm_code = alarm_data.get("alarm_code", "UNKNOWN")
        spec = ALARM_CATALOG.get(alarm_code)

        title_en = spec.name if spec else alarm_data.get("name", f"Alarm {alarm_code}")
        title_ar = spec.name_ar if spec else alarm_data.get("name_ar", f"تنبيه {alarm_code}")
        severity = spec.severity if spec else alarm_data.get("severity", "S2")

        guidance_en = (
            spec.guidance_en
            if spec
            else alarm_data.get("guidance_en", "Check field sensors and pumps.")
        )
        guidance_ar = (
            spec.guidance_ar
            if spec
            else alarm_data.get("guidance_ar", "تحقق من الحساسات والمضخات في الموقع.")
        )

        causes_en = [
            f"Sensor threshold exceeded: value={alarm_data.get('current_value')} (threshold={alarm_data.get('threshold_value')})",
            "Possible hydraulic line obstruction or valve state mismatch.",
        ]
        causes_ar = [
            f"تجاوز حد الحساس: القيمة الحالية={alarm_data.get('current_value')} (الحد={alarm_data.get('threshold_value')})",
            "احتمال وجود انسداد في خط الري أو عدم توافق في حالة الصمامات.",
        ]

        actions_en = [
            guidance_en,
            "Inspect physical pipe for leaks or physical damage.",
            "Verify booster pump pressure and well supply level.",
        ]
        actions_ar = [
            guidance_ar,
            "فحص الخط الرئيسي للتأكد من عدم وجود تسريبات أو تلف في الأنابيب.",
            "التحقق من ضغط مضخة التعزيز ومستوى المياه في خزان الإمداد.",
        ]

        diag_en = f"Diagnostic: {title_en}. {guidance_en}"
        diag_ar = f"التشخيص: {title_ar}. {guidance_ar}"

        return AlarmExplanation(
            alarm_code=alarm_code,
            severity=severity,
            title=title_en,
            title_ar=title_ar,
            diagnosis=diag_en,
            diagnosis_ar=diag_ar,
            probable_causes=causes_en,
            probable_causes_ar=causes_ar,
            suggested_actions=actions_en,
            suggested_actions_ar=actions_ar,
            safety_critical=(severity in ("S1", "S2")),
            confidence=1.0,
            provider_used="rule_based",
            model_used="rule_based",
        )

    def weather_advisor(
        self,
        forecast: WeatherForecast,
        target_date: str,
        affected_zones: list[str] | None = None,
        program_id: str | None = None,
        lang: str = "ar",
    ) -> AdvisorSuggestion:
        """Evaluate deterministic thresholds and formulate recommendation."""
        zones = affected_zones or []

        # Find day forecast matching target_date
        day_summary = None
        for day in forecast.daily:
            if day.date == target_date:
                day_summary = day
                break
        if not day_summary and forecast.daily:
            day_summary = forecast.daily[0]

        if not day_summary:
            return AdvisorSuggestion(
                action="none",
                target_date=target_date,
                affected_zone_ids=zones,
                program_id=program_id,
                duration_factor=1.0,
                title="No Weather Data Available",
                title_ar="لا تتوفر بيانات طقس",
                reasoning="Weather forecast could not be loaded; continuing scheduled irrigation as normal.",
                reasoning_ar="تعذر تحميل توقعات الطقس، سيستمر الري المجدول كالمعتاد دون تعديل.",
                confidence=0.5,
                provider_used="rule_based",
                model_used="rule_based",
            )

        precip_mm = day_summary.precipitation_total_mm
        precip_prob = day_summary.precipitation_probability_pct
        temp_max = day_summary.temp_max_c
        et0 = day_summary.et0_mm

        # Threshold 1: Rain > 50% or precip > 2.0 mm -> Skip irrigation
        if precip_prob > 50.0 or precip_mm > 2.0:
            return AdvisorSuggestion(
                action="skip",
                target_date=target_date,
                affected_zone_ids=zones,
                program_id=program_id,
                duration_factor=0.0,
                title=f"Skip Irrigation — Rain Expected ({precip_mm:.1f}mm, {precip_prob:.0f}%)",
                title_ar=f"تخطي دورة الري — أمطار متوقعة ({precip_mm:.1f} ملم، {precip_prob:.0f}%)",
                reasoning=(
                    f"Forecast predicts {precip_prob:.0f}% chance of rain with {precip_mm:.1f}mm accumulation on {target_date}. "
                    "Skipping irrigation conserves groundwater and prevents waterlogging."
                ),
                reasoning_ar=(
                    f"تشير التوقعات إلى احتمال هطول أمطار بنسبة {precip_prob:.0f}% بكمية {precip_mm:.1f} ملم يوم {target_date}. "
                    "تخطي الري يوفر مخزون المياه الجوفية ويمنع تشبع التربة الزائد."
                ),
                confidence=0.95,
                provider_used="rule_based",
                model_used="rule_based",
            )

        # Threshold 2: Heat (> 38°C) or High ET0 (> 6.0 mm) -> Extend duration by 20%
        if temp_max >= 38.0 or et0 >= 6.0:
            return AdvisorSuggestion(
                action="extend",
                target_date=target_date,
                affected_zone_ids=zones,
                program_id=program_id,
                duration_factor=1.2,
                title=f"Extend Irrigation (+20%) — High Heat & ET0 ({temp_max:.1f}°C, {et0:.1f}mm)",
                title_ar=f"تمديد مدة الري (+20%) — ارتفاع درجات الحرارة والتبخر ({temp_max:.1f}م°، {et0:.1f} ملم)",
                reasoning=(
                    f"Extreme heat detected with max temperature {temp_max:.1f}°C and reference evapotranspiration ET0 of {et0:.1f}mm. "
                    "Extending irrigation duration by 20% compensates for increased evaporative loss."
                ),
                reasoning_ar=(
                    f"رصد موجة حرارة بدرجة عظمى {temp_max:.1f}م° ومعدل تبخر نتح {et0:.1f} ملم. "
                    "يُوصى بزيادة زمن الري بنسبة 20% لتعويض الفاقد بالتبخر وحماية الأشجار والمحاصيل."
                ),
                confidence=0.90,
                provider_used="rule_based",
                model_used="rule_based",
            )

        # Default: Normal conditions -> No adjustment
        return AdvisorSuggestion(
            action="none",
            target_date=target_date,
            affected_zone_ids=zones,
            program_id=program_id,
            duration_factor=1.0,
            title="Normal Weather — Maintain Schedule",
            title_ar="الطقس معتدل — الاستمرار بالجدول المعتاد",
            reasoning=(
                f"Conditions on {target_date} are favorable (Max {temp_max:.1f}°C, Rain {precip_mm:.1f}mm, ET0 {et0:.1f}mm). "
                "Current irrigation schedule is optimal."
            ),
            reasoning_ar=(
                f"الأحوال الجوية ليوم {target_date} ملائمة ومستقرة (عظمى {temp_max:.1f}م°، مطر {precip_mm:.1f} ملم، تبخر {et0:.1f} ملم). "
                "الجدول المعتمد حالياً مناسب تماماً."
            ),
            confidence=0.95,
            provider_used="rule_based",
            model_used="rule_based",
        )

    def daily_briefing(
        self,
        date_str: str,
        cycles: list[dict[str, Any]] | None = None,
        alarms: list[dict[str, Any]] | None = None,
        forecast: WeatherForecast | None = None,
        lang: str = "ar",
        cycles_summary: Any | None = None,
        alarms_summary: Any | None = None,
    ) -> DailyBriefing:
        """Synthesize daily farm operations summary, alarms, and weather."""
        c_list = (
            cycles
            if cycles is not None
            else (cycles_summary if isinstance(cycles_summary, list) else [])
        )
        if not isinstance(c_list, list):
            c_list = []
        a_list = (
            alarms
            if alarms is not None
            else (alarms_summary if isinstance(alarms_summary, list) else [])
        )
        if not isinstance(a_list, list):
            a_list = []

        total_water = sum(c.get("water_volume_m3", 0.0) for c in c_list)
        completed = [c for c in c_list if c.get("outcome") == "completed"]
        aborted = [c for c in c_list if c.get("outcome") in ("aborted", "faulted")]

        cur_temp = forecast.current.temperature_c if forecast and forecast.current else None
        today_fc = forecast.daily[0] if forecast and forecast.daily else None
        t_max = today_fc.temp_max_c if today_fc else None
        p_prob = today_fc.precipitation_probability_pct if today_fc else None
        et0 = (
            today_fc.et0_mm
            if today_fc
            else (forecast.current.et0_mm if forecast and forecast.current else None)
        )

        title_en = f"Daily Operations Briefing — {date_str}"
        title_ar = f"التقرير اليومي للعمليات — {date_str}"

        # Only report weather values we actually have — never invent defaults.
        parts_en: list[str] = []
        parts_ar: list[str] = []
        if cur_temp is not None:
            parts_en.append(f"Current temp {cur_temp:.1f}°C")
            parts_ar.append(f"درجة الحرارة الحالية {cur_temp:.1f}م°")
        if t_max is not None:
            parts_en.append(f"forecast high {t_max:.1f}°C")
            parts_ar.append(f"العظمى المتوقعة {t_max:.1f}م°")
        if p_prob is not None:
            parts_en.append(f"rain chance {p_prob:.0f}%")
            parts_ar.append(f"احتمال الأمطار {p_prob:.0f}%")
        if et0 is not None:
            parts_en.append(f"ET₀ {et0:.2f} mm")
            parts_ar.append(f"التبخر-نتح المرجعي ET₀ = {et0:.2f} مم")

        if parts_en:
            w_summary_en = ", ".join(parts_en) + "."
            w_summary_ar = "، ".join(parts_ar) + "."
        else:
            w_summary_en = "No weather forecast available."
            w_summary_ar = "لا تتوفر توقعات للطقس."

        irr_en = f"Executed {len(c_list)} cycle(s) delivering {total_water:.1f} m³ of water ({len(completed)} completed, {len(aborted)} interrupted)."
        irr_ar = f"تم تنفيذ {len(c_list)} دورة ري بإجمالي استهلاك {total_water:.1f} م³ ({len(completed)} مكتملة، {len(aborted)} متوقفة)."

        active_alarms = [a for a in a_list if a.get("status") == "active"]
        alm_en = (
            f"{len(active_alarms)} active alarm(s) requiring attention."
            if active_alarms
            else "All systems normal. No active alarms."
        )
        alm_ar = (
            f"يوجد {len(active_alarms)} إنذار نشط يتطلب المتابعة."
            if active_alarms
            else "جميع الأنظمة تعمل بشكل طبيعي ولا توجد إنذارات نشطة."
        )

        recs_en = [
            "Monitor soil moisture on olive and pomegranate zones.",
            "Verify mainline filter delta pressure before next cycle.",
        ]
        recs_ar = [
            "مراقبة رطوبة التربة في مناطق الزيتون والرمان.",
            "التحقق من فرق ضغط فلتر الخط الرئيسي قبل بدء الدورة التالية.",
        ]

        summary_en = f"Farm operations normal on {date_str}. Delivered {total_water:.1f} m³ of water with {len(active_alarms)} active alarms."
        summary_ar = f"عمليات المزرعة مستقرة ليوم {date_str}. تم ضخ {total_water:.1f} م³ مياه، مع وجود {len(active_alarms)} إنذار نشط."

        return DailyBriefing(
            date=date_str,
            title=title_en,
            title_ar=title_ar,
            summary=summary_en,
            summary_ar=summary_ar,
            weather_summary=w_summary_en,
            weather_summary_ar=w_summary_ar,
            irrigation_overview=irr_en,
            irrigation_overview_ar=irr_ar,
            alarms_overview=alm_en,
            alarms_overview_ar=alm_ar,
            recommendations=recs_en,
            recommendations_ar=recs_ar,
            provider_used="rule_based",
            model_used="rule_based",
        )

    @staticmethod
    def _live_answer(msg: str, f: dict) -> tuple[str, str] | None:
        """Answer tank / next-irrigation / dryness / alarm questions from live facts."""
        if not f:
            return None
        from app.seed import ZONES

        names = {z["id"]: (z["name"], z["name_ar"]) for z in ZONES}
        stale_en = "" if f.get("fresh", True) else " (live data may be old)"
        stale_ar = "" if f.get("fresh", True) else " (قد تكون البيانات الحية قديمة)"
        if any(w in msg for w in ("tank", "خزان", "الخزان")) and f.get("tank_pct") is not None:
            t = f["tank_pct"]
            return (
                f"The water tank is at {t:.0f} %{stale_en}.",
                f"مستوى الخزان الآن {t:.0f} %{stale_ar}.",
            )
        if any(w in msg for w in ("next", "schedule", "موعد", "القادم", "الجدول", "متى")):
            r = f.get("next_run")
            if r:
                return (
                    f"Next irrigation: {r['zone_en']} at {r['time']} for {r['minutes']} min.",
                    f"الري القادم: {r['zone_ar']} الساعة {r['time']} لمدة {r['minutes']} دقيقة.",
                )
            return (
                "No irrigation is scheduled in the next 24 hours.",
                "لا يوجد ري مجدول خلال 24 ساعة القادمة.",
            )
        if any(w in msg for w in ("dry", "moisture", "جفاف", "جافة", "رطوبة")) and f.get("driest"):
            zid, m = f["driest"][0]
            en_n, ar_n = names.get(zid, (zid, zid))
            return (
                f"The driest zone now is {en_n} at {m:.0f} % soil moisture (farm average {f.get('moisture_avg', m):.0f} %){stale_en}.",
                f"أكثر منطقة جفافاً الآن {ar_n} برطوبة تربة {m:.0f} % (متوسط المزرعة {f.get('moisture_avg', m):.0f} %){stale_ar}.",
            )
        if any(w in msg for w in ("alarm", "إنذار", "انذار")) and "alarm_count" in f:
            n = f["alarm_count"]
            if n == 0:
                return ("There are no active alarms.", "لا توجد إنذارات نشطة.")
            return (
                f"There are {n} active alarm(s); open the Alarm Center for details.",
                f"يوجد {n} إنذار نشط؛ افتح مركز الإنذارات للتفاصيل.",
            )
        return None

    def chat(self, message: str, lang: str = "ar", facts: dict | None = None) -> ChatResponse:
        """Deterministic assistant replies for farm queries.

        With `facts` (the latest live snapshot) it answers common questions with real
        numbers even when every AI model is down (Milestone G2).
        """
        msg_lower = message.lower()
        live = self._live_answer(msg_lower, facts or {})
        if live:
            en, ar = live
            return ChatResponse(
                reply=en, reply_ar=ar, provider_used="rule_based", model_used="rule_based"
            )

        if any(w in msg_lower for w in ("alarm", "fault", "إنذار", "عطل", "تنبيه")):
            en = "I can inspect current active alarms, provide root-cause diagnostics, and recommend PLC acknowledgment steps."
            ar = "يمكنني فحص الإنذارات النشطة، وتقديم تشخيص للأسباب المحتملة، واقتراح خطوات المعالجة والتحقق."
        elif any(w in msg_lower for w in ("weather", "rain", "طقس", "مطر", "حرارة")):
            en = "Live forecast is retrieved from Open-Meteo for Algaroshy Farm (32.516250, 14.070361). I automatically advise skipping or extending cycles."
            ar = "يتم جلب الطقس المباشر لمزرعة الجروشي من Open-Meteo، وأقدم توصيات بتخطي الري عند المطر أو تمديده أثناء موجات الحر."
        elif any(w in msg_lower for w in ("zone", "crop", "منطقة", "محصول", "رمان", "زيتون")):
            en = "Algaroshy Farm has 12 irrigation zones: pomegranates (including the mother trees), olives, grapes, and a mixed block of peach, apricot and plum. You can ask about the live flow and pressure of any zone."
            ar = "تضم مزرعة الجروشي 12 منطقة ري: الرمان (ومنها رمان الأمهات)، والزيتون، والعنب، ومنطقة فواكه مختلطة من الخوخ والمشمش والعوينة. يمكنك السؤال عن التدفق والضغط الحالي لأي منطقة."
        else:
            en = "I am the Algaroshy Farm AI Assistant. I can assist with alarms, weather-aware scheduling, irrigation summaries, and system diagnostics."
            ar = "مرحباً بك، أنا المساعد الذكي لمزرعة الجروشي. يمكنني مساعدتك في تشخيص الإنذارات، والتوصيات المرتبطة بالطقس، وتقارير الري المجدول."

        return ChatResponse(
            reply=ar if lang == "ar" else en,
            reply_ar=ar,
            references=["docs/AI_FEATURES.md", "docs/ALARM_MATRIX.md"],
            provider_used="rule_based",
            model_used="rule_based",
        )

    chat_reply = chat


rule_service = RuleBasedService()
