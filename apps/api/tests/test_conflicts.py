"""Unit tests for the schedule conflict checker (apps/api/app/services/conflicts.py)."""

import pytest

from app.models.program import Program, ProgramStep
from app.models.zone import Zone
from app.services.conflicts import check_program_conflicts, get_weekly_intervals, parse_time_minutes


def make_zone(zone_id: str, max_runtime: int = 60, enabled: bool = True) -> Zone:
    z = Zone()
    z.id = zone_id
    z.code = f"Z_{zone_id}"
    z.name = f"Zone {zone_id}"
    z.name_ar = f"منطقة {zone_id}"
    z.max_runtime_min = max_runtime
    z.enabled = enabled
    return z


def make_program(
    prog_id: str,
    name: str,
    start_time: str,
    days: str,
    steps: list[tuple[str, int]],
    enabled: bool = True,
) -> Program:
    p = Program()
    p.id = prog_id
    p.name = name
    p.start_time_local = start_time
    p.weekday_mask = days
    p.enabled = enabled
    p.steps = []
    for idx, (zid, dur) in enumerate(steps, start=1):
        st = ProgramStep()
        st.id = f"{prog_id}_step_{idx}"
        st.program_id = prog_id
        st.zone_id = zid
        st.step_order = idx
        st.duration_min = dur
        p.steps.append(st)
    return p


def test_parse_time_minutes():
    assert parse_time_minutes("00:00") == 0
    assert parse_time_minutes("06:30") == 390
    assert parse_time_minutes("23:59") == 1439
    with pytest.raises(ValueError):
        parse_time_minutes("25:00")
    with pytest.raises(ValueError):
        parse_time_minutes("invalid")


def test_weekly_intervals_wrap_sunday_to_monday():
    # Sunday is day 7. Starts at 23:30, runs for 60 min (until Monday 00:30)
    intervals = get_weekly_intervals("23:30", "7", 60)
    # Day 7 offset = 6 * 1440 = 8640. 23:30 = 1410 min. Total start = 10050.
    # Total minutes in week = 10080.
    # Interval 1: 10050 to 10080
    # Interval 2: 0 to 30
    assert (10050, 10080) in intervals
    assert (0, 30) in intervals


def test_conflict_free_candidate():
    zones = {
        "z1": make_zone("z1", 60),
        "z2": make_zone("z2", 45),
    }
    existing = [
        make_program("p1", "Morning", "06:00", "1,3,5", [("z1", 30)]),
    ]
    candidate_steps = [{"zone_id": "z2", "duration_min": 30}]
    # Candidate runs at 08:00 on Monday
    conflicts = check_program_conflicts(
        candidate_name="Afternoon",
        candidate_start_time="08:00",
        candidate_weekday_mask="1,3,5",
        candidate_steps=candidate_steps,
        existing_programs=existing,
        zones_by_id=zones,
    )
    assert len(conflicts) == 0


def test_conflict_max_runtime_exceeded():
    zones = {"z1": make_zone("z1", max_runtime=45)}
    candidate_steps = [{"zone_id": "z1", "duration_min": 50}]
    conflicts = check_program_conflicts(
        candidate_name="Long Run",
        candidate_start_time="06:00",
        candidate_weekday_mask="1",
        candidate_steps=candidate_steps,
        existing_programs=[],
        zones_by_id=zones,
    )
    assert len(conflicts) == 1
    assert conflicts[0].code == "MAX_RUNTIME_EXCEEDED"
    assert "exceeds maximum allowed runtime" in conflicts[0].message_en
    assert "تتجاوز الحد الأقصى" in conflicts[0].message_ar


def test_conflict_disabled_zone():
    zones = {"z1": make_zone("z1", enabled=False)}
    candidate_steps = [{"zone_id": "z1", "duration_min": 20}]
    conflicts = check_program_conflicts(
        candidate_name="Disabled Zone Run",
        candidate_start_time="06:00",
        candidate_weekday_mask="1",
        candidate_steps=candidate_steps,
        existing_programs=[],
        zones_by_id=zones,
    )
    assert any(c.code == "ZONE_DISABLED" for c in conflicts)


def test_conflict_overlap_same_day():
    zones = {"z1": make_zone("z1", 60), "z2": make_zone("z2", 60)}
    # Program 1 runs Mon 06:00 - 07:00 (60 min)
    existing = [make_program("p1", "Program 1", "06:00", "1", [("z1", 60)])]

    # Candidate starts at 06:30 for 30 min on Monday -> overlaps!
    candidate_steps = [{"zone_id": "z2", "duration_min": 30}]
    conflicts = check_program_conflicts(
        candidate_name="Program 2",
        candidate_start_time="06:30",
        candidate_weekday_mask="1",
        candidate_steps=candidate_steps,
        existing_programs=existing,
        zones_by_id=zones,
    )
    assert any(c.code == "SCHEDULE_OVERLAP" for c in conflicts)
    assert "Program 1" in conflicts[0].message_en


def test_no_overlap_different_days():
    zones = {"z1": make_zone("z1", 60)}
    # Existing runs Mon, Wed (1, 3)
    existing = [make_program("p1", "Mon/Wed", "06:00", "1,3", [("z1", 60)])]

    # Candidate runs Tue, Thu (2, 4) at exact same time -> NO overlap
    candidate_steps = [{"zone_id": "z1", "duration_min": 60}]
    conflicts = check_program_conflicts(
        candidate_name="Tue/Thu",
        candidate_start_time="06:00",
        candidate_weekday_mask="2,4",
        candidate_steps=candidate_steps,
        existing_programs=existing,
        zones_by_id=zones,
    )
    assert len(conflicts) == 0


def test_overlap_across_midnight():
    zones = {"z1": make_zone("z1", 120), "z2": make_zone("z2", 60)}
    # Existing starts Monday at 23:30, runs for 90 min (ends Tuesday 01:00)
    existing = [make_program("p1", "Night Program", "23:30", "1", [("z1", 90)])]

    # Candidate starts Tuesday at 00:30 for 30 min -> overlaps with Monday's run!
    candidate_steps = [{"zone_id": "z2", "duration_min": 30}]
    conflicts = check_program_conflicts(
        candidate_name="Tuesday Early",
        candidate_start_time="00:30",
        candidate_weekday_mask="2",
        candidate_steps=candidate_steps,
        existing_programs=existing,
        zones_by_id=zones,
    )
    assert any(c.code == "SCHEDULE_OVERLAP" for c in conflicts)


def test_disabled_existing_program_ignored():
    zones = {"z1": make_zone("z1", 60)}
    # Existing is disabled
    existing = [make_program("p1", "Disabled Prog", "06:00", "1", [("z1", 60)], enabled=False)]

    # Candidate runs at same time
    candidate_steps = [{"zone_id": "z1", "duration_min": 60}]
    conflicts = check_program_conflicts(
        candidate_name="Active Prog",
        candidate_start_time="06:00",
        candidate_weekday_mask="1",
        candidate_steps=candidate_steps,
        existing_programs=existing,
        zones_by_id=zones,
    )
    assert len(conflicts) == 0
