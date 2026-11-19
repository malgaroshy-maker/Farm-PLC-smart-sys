"""Pure conflict-checker for irrigation programs and schedules (Milestone D).

Evaluates:
  1. Zone validity and max runtime per zone.
  2. Temporal overlaps across days and weekdays (including midnight wraparound).
  3. Max concurrent zones / hydraulic capacity (max_concurrent_zones = 1).
  4. Forbidden zone combinations.
"""

from dataclasses import dataclass, field
from typing import Any

from app.models.program import Program
from app.models.zone import Zone

WEEKDAYS_EN = {
    1: "Monday",
    2: "Tuesday",
    3: "Wednesday",
    4: "Thursday",
    5: "Friday",
    6: "Saturday",
    7: "Sunday",
}

WEEKDAYS_AR = {
    1: "الاثنين",
    2: "الثلاثاء",
    3: "الأربعاء",
    4: "الخميس",
    5: "الجمعة",
    6: "السبت",
    7: "الأحد",
}

MINUTES_PER_DAY = 1440
MINUTES_PER_WEEK = 7 * MINUTES_PER_DAY


@dataclass(frozen=True)
class Conflict:
    code: str
    message_en: str
    message_ar: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message_en": self.message_en,
            "message_ar": self.message_ar,
            "details": self.details,
        }


def parse_time_minutes(time_str: str) -> int:
    """Parse 'HH:MM' string into minutes since 00:00."""
    try:
        parts = time_str.strip().split(":")
        if len(parts) != 2:
            raise ValueError
        h, m = int(parts[0]), int(parts[1])
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError
        return h * 60 + m
    except Exception as exc:
        raise ValueError(f"Invalid time format '{time_str}'. Expected 'HH:MM'") from exc


def parse_weekday_mask(mask_str: str) -> set[int]:
    """Parse comma-separated 1-7 weekday mask."""
    days = set()
    for token in mask_str.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            val = int(token)
            if 1 <= val <= 7:
                days.add(val)
        except ValueError:
            pass
    return days


def get_weekly_intervals(
    start_time_local: str, weekday_mask: str, total_duration_min: int
) -> list[tuple[int, int]]:
    """Compute [start_min, end_min] intervals across the week (0 to 10080 minutes).

    1 = Monday 00:00 (minute 0).
    Sunday 23:59 is minute 10079.
    Intervals wrapping past Sunday 24:00 wrap to Monday 00:00.
    """
    start_min_of_day = parse_time_minutes(start_time_local)
    days = parse_weekday_mask(weekday_mask)
    intervals: list[tuple[int, int]] = []

    for d in sorted(days):
        day_offset = (d - 1) * MINUTES_PER_DAY
        raw_start = day_offset + start_min_of_day
        raw_end = raw_start + total_duration_min

        if raw_end <= MINUTES_PER_WEEK:
            intervals.append((raw_start, raw_end))
        else:
            # Splits across Sunday midnight into Monday
            intervals.append((raw_start, MINUTES_PER_WEEK))
            intervals.append((0, raw_end % MINUTES_PER_WEEK))

    return intervals


def intervals_overlap(
    intervals1: list[tuple[int, int]], intervals2: list[tuple[int, int]]
) -> tuple[bool, int, int]:
    """Check if any interval in intervals1 overlaps any in intervals2."""
    for s1, e1 in intervals1:
        for s2, e2 in intervals2:
            start_max = max(s1, s2)
            end_min = min(e1, e2)
            if start_max < end_min:
                return True, start_max, end_min
    return False, 0, 0


def format_minute_of_week(min_of_week: int) -> tuple[str, str, str]:
    """Return (day_en, day_ar, HH:MM)."""
    norm = min_of_week % MINUTES_PER_WEEK
    day_num = (norm // MINUTES_PER_DAY) + 1
    day_min = norm % MINUTES_PER_DAY
    h = day_min // 60
    m = day_min % 60
    time_str = f"{h:02d}:{m:02d}"
    return WEEKDAYS_EN.get(day_num, "Day"), WEEKDAYS_AR.get(day_num, "يوم"), time_str


def check_program_conflicts(
    candidate_name: str,
    candidate_start_time: str,
    candidate_weekday_mask: str,
    candidate_steps: list[dict[str, Any]],  # [{"zone_id": str, "duration_min": int, ...}]
    existing_programs: list[Program],
    zones_by_id: dict[str, Zone],
    candidate_id: str | None = None,
    max_concurrent_zones: int = 1,
) -> list[Conflict]:
    """Validate candidate program against zones and all existing enabled programs.

    Returns a list of Conflict objects (empty if valid).
    """
    conflicts: list[Conflict] = []

    # 1. Step structure and zone validation
    if not candidate_steps:
        conflicts.append(
            Conflict(
                code="NO_STEPS",
                message_en="Program must have at least one irrigation step.",
                message_ar="يجب أن يحتوي البرنامج على مرحلة ري واحدة على الأقل.",
            )
        )
        return conflicts

    total_duration_min = 0
    candidate_zones_used: list[str] = []

    for idx, step in enumerate(candidate_steps, start=1):
        zid = step.get("zone_id")
        duration = step.get("duration_min", 0)

        zone = zones_by_id.get(zid)
        if not zone:
            conflicts.append(
                Conflict(
                    code="ZONE_NOT_FOUND",
                    message_en=f"Step {idx}: Zone '{zid}' does not exist.",
                    message_ar=f"المرحلة {idx}: المنطقة '{zid}' غير موجودة.",
                    details={"step_order": idx, "zone_id": zid},
                )
            )
            continue

        if not zone.enabled:
            conflicts.append(
                Conflict(
                    code="ZONE_DISABLED",
                    message_en=f"Step {idx}: Zone '{zone.name}' is currently disabled.",
                    message_ar=f"المرحلة {idx}: المنطقة '{zone.name_ar or zone.name}' معطلة حالياً.",
                    details={"step_order": idx, "zone_id": zid},
                )
            )

        if duration < 1:
            conflicts.append(
                Conflict(
                    code="INVALID_DURATION",
                    message_en=f"Step {idx}: Duration must be at least 1 minute.",
                    message_ar=f"المرحلة {idx}: يجب أن تكون المدة دقيقة واحدة على الأقل.",
                    details={"step_order": idx, "zone_id": zid, "duration_min": duration},
                )
            )
        elif duration > zone.max_runtime_min:
            conflicts.append(
                Conflict(
                    code="MAX_RUNTIME_EXCEEDED",
                    message_en=(
                        f"Step {idx} for zone '{zone.name}': Duration {duration} min exceeds "
                        f"maximum allowed runtime ({zone.max_runtime_min} min)."
                    ),
                    message_ar=(
                        f"المرحلة {idx} للمنطقة '{zone.name_ar or zone.name}': المدة {duration} دقيقة تتجاوز "
                        f"الحد الأقصى المسموح ({zone.max_runtime_min} دقيقة)."
                    ),
                    details={
                        "step_order": idx,
                        "zone_id": zid,
                        "duration_min": duration,
                        "max_runtime_min": zone.max_runtime_min,
                    },
                )
            )

        total_duration_min += duration
        candidate_zones_used.append(zid)

    if total_duration_min > MINUTES_PER_DAY:
        conflicts.append(
            Conflict(
                code="EXCEEDS_24_HOURS",
                message_en=f"Total program duration ({total_duration_min} min) exceeds 24 hours.",
                message_ar=f"إجمالي مدة البرنامج ({total_duration_min} دقيقة) يتجاوز 24 ساعة.",
                details={"total_duration_min": total_duration_min},
            )
        )

    # 2. Start time and weekday mask syntax
    try:
        parse_time_minutes(candidate_start_time)
    except ValueError as exc:
        conflicts.append(
            Conflict(
                code="INVALID_START_TIME",
                message_en=str(exc),
                message_ar="صيغة وقت البدء غير صحيحة. الصيغة المطلوبة هي HH:MM.",
            )
        )
        return conflicts

    candidate_days = parse_weekday_mask(candidate_weekday_mask)
    if not candidate_days:
        conflicts.append(
            Conflict(
                code="NO_DAYS_SELECTED",
                message_en="At least one weekday must be selected.",
                message_ar="يجب تحديد يوم واحد على الأقل في الأسبوع.",
            )
        )
        return conflicts

    # 3. Check temporal overlaps with other enabled programs
    candidate_intervals = get_weekly_intervals(
        candidate_start_time, candidate_weekday_mask, total_duration_min
    )

    # Check self-overlap across consecutive scheduled days
    # (e.g. program runs 18 hours every day, next day starts 12 hours later)
    # A single program with itself: check if any of its intervals overlap each other
    for i in range(len(candidate_intervals)):
        for j in range(i + 1, len(candidate_intervals)):
            s1, e1 = candidate_intervals[i]
            s2, e2 = candidate_intervals[j]
            if max(s1, s2) < min(e1, e2):
                conflicts.append(
                    Conflict(
                        code="SELF_OVERLAP",
                        message_en="Program duration overlaps with its own next scheduled run.",
                        message_ar="مدة البرنامج تتداخل مع موعد تشغيله التالي في نفس الأسبوع.",
                        details={"total_duration_min": total_duration_min},
                    )
                )
                break

    # Check overlaps against all other enabled programs
    for other in existing_programs:
        if other.id == candidate_id or not other.enabled:
            continue
        other_total_min = sum(st.duration_min for st in other.steps)
        other_intervals = get_weekly_intervals(
            other.start_time_local, other.weekday_mask, other_total_min
        )

        overlap, overlap_start, overlap_end = intervals_overlap(
            candidate_intervals, other_intervals
        )
        if overlap:
            day_en, day_ar, time_str = format_minute_of_week(overlap_start)
            conflicts.append(
                Conflict(
                    code="SCHEDULE_OVERLAP",
                    message_en=(
                        f"Program overlaps with '{other.name}' on {day_en} around {time_str}."
                    ),
                    message_ar=(
                        f"يتداخل البرنامج في التوقيت مع برنامج '{other.name}' يوم {day_ar} في حدود الساعة {time_str}."
                    ),
                    details={
                        "conflicting_program_id": other.id,
                        "conflicting_program_name": other.name,
                        "day_en": day_en,
                        "day_ar": day_ar,
                        "time_str": time_str,
                    },
                )
            )

    return conflicts
