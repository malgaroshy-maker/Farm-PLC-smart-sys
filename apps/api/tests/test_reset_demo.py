"""Tests for reset_demo: keeping programs and clearing operating history."""

import pytest
from sqlalchemy import select

from app.core.clock import clock
from app.database import async_session_factory
from app.models.alarm import Alarm
from app.models.program import Program, ProgramStep
from app.reset_demo import reset_history


@pytest.mark.asyncio
async def test_reset_demo_preserves_programs_and_clears_history(client, capsys):
    """Verify that reset_history keeps programs and steps, prints enabled program names, and clears alarms."""
    async with async_session_factory() as db:
        # Create a program with steps
        prog = Program(
            id="prog_test_keep",
            name="Test Preservation Program",
            enabled=True,
            start_time_local="06:00",
            weekday_mask="1,2,3,4,5,6,7",
        )
        db.add(prog)
        step = ProgramStep(
            id="step_test_keep",
            program_id="prog_test_keep",
            zone_id="zone_nakheel_1",
            step_order=1,
            duration_min=15,
        )
        db.add(step)

        # Create an alarm
        alarm = Alarm(
            id="alm_test_reset",
            alarm_code="ALM-001",
            severity="S1",
            category="hardware",
            status="active_unacked",
            triggered_at=clock.farm_now(),
        )
        db.add(alarm)
        await db.commit()

    # Run reset_history
    removed = await reset_history()

    # Capture stdout
    captured = capsys.readouterr()
    assert "Preserving enabled programs:" in captured.out
    assert "Test Preservation Program" in captured.out

    # Verify alarms cleared
    assert removed["alarms"] >= 1

    # Verify programs and steps still exist
    async with async_session_factory() as db:
        survived_prog = (
            await db.execute(select(Program).where(Program.id == "prog_test_keep"))
        ).scalar_one_or_none()
        assert survived_prog is not None
        assert survived_prog.name == "Test Preservation Program"

        survived_step = (
            await db.execute(select(ProgramStep).where(ProgramStep.id == "step_test_keep"))
        ).scalar_one_or_none()
        assert survived_step is not None
        assert survived_step.duration_min == 15
