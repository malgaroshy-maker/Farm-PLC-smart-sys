"""Clear AI refusals, tolerant Arabic check, visible backup failures and an honest event log."""

import json

import pytest
from conftest import login
from sqlalchemy import select

from app.database import async_session_factory
from app.models.event_log import EventLog
from app.services import backup, login_throttle
from app.services.ai.arabic import normalize_text
from app.services.ai.purity import check_arabic_text_purity
from app.services.ai.rules import rule_service


@pytest.mark.parametrize(
    "order",
    ["شغّل منطقة الرمان", "أوقف الري الآن", "من فضلك ابدأ الري", "start zone 2", "please stop"],
)
def test_an_order_to_move_water_gets_a_clear_refusal(order):
    answer = rule_service.chat(order, lang="ar")
    assert "لا يشغّل الماء ولا يوقفه" in answer.reply_ar and "إيقاف الكل" in answer.reply_ar


@pytest.mark.parametrize("question", ["متى يبدأ الري القادم؟", "when does irrigation start?"])
def test_a_question_about_starting_is_not_refused(question):
    assert "لا يشغّل الماء" not in rule_service.chat(question, lang="ar").reply_ar


def test_bracketed_english_repeats_and_record_ids_do_not_fail_the_arabic_check():
    good = "الجريان الجاف (Dry Run) في pump_booster_01، راجع وحدة التحكم (PLC)."
    assert check_arabic_text_purity(good).is_pure
    assert normalize_text(good) == "الجريان الجاف في pump_booster_01، راجع وحدة التحكم (PLC)."
    assert not check_arabic_text_purity("افحص the filter قبل التشغيل").is_pure


def test_a_failed_or_old_backup_is_reported(monkeypatch):
    saved = {}
    monkeypatch.setattr(backup, "_read_status", lambda: saved)
    assert backup.health_code(60) == "backup_ok"
    assert backup.health_code(40 * 3600) == "backup_old"
    saved.update(last={"at": "2020-01-01T00:00:00+00:00"})
    assert backup.health_code(60) == "backup_old"
    saved.update(last_error_at="2020-01-02T00:00:00+00:00")
    assert backup.health_code(60) == "backup_failed"


def test_a_paused_name_is_not_pushed_out_by_new_names():
    login_throttle.reset()
    for _ in range(login_throttle.MAX_FAILURES):
        login_throttle.retry_after("target")
    for n in range(login_throttle._MAX_TRACKED + 50):
        login_throttle._all.clear()
        login_throttle.retry_after(f"noise-{n}")
    login_throttle._all.clear()
    assert login_throttle.retry_after("target") > 0
    login_throttle.reset()


def test_program_and_ai_changes_are_in_the_event_log(client):
    admin = login(client, "admin")
    made = client.post(
        "/api/v1/schedules",
        headers=admin,
        json={
            "name": "Audited",
            "start_time_local": "05:00",
            "weekday_mask": "1",
            "steps": [{"zone_id": "zone_enab", "step_order": 1, "duration_min": 10}],
        },
    )
    assert made.status_code == 201, made.text
    url = f"/api/v1/schedules/{made.json()['id']}"
    assert client.patch(url, headers=admin, json={"name": "Renamed"}).status_code == 200
    assert client.patch(f"{url}/toggle", headers=admin, json={"enabled": False}).status_code == 200
    assert client.delete(url, headers=admin).status_code == 204
    r = client.patch("/api/v1/pumps/pump_well_01", headers=admin, json={})
    assert r.status_code == 200, r.text
    r = client.put("/api/v1/ai/settings", headers=admin, json={"timeout_sec": 40})
    assert r.status_code == 200, r.text
    no_days = client.post(
        "/api/v1/schedules",
        headers=admin,
        json={
            "name": "Never",
            "start_time_local": "05:00",
            "weekday_mask": "",
            "steps": [{"zone_id": "zone_enab", "step_order": 1, "duration_min": 10}],
        },
    )
    assert no_days.status_code == 422

    async def events():
        async with async_session_factory() as db:
            return [
                (e.event_type, e.actor_id, json.loads(e.payload_json or "{}"))
                for e in await db.scalars(select(EventLog).order_by(EventLog.id))
            ]

    logged = [e for e in client.portal.call(events) if e[0] != "user.login"]
    assert [e[0] for e in logged] == [
        "schedule.created",
        "schedule.updated",
        "schedule.updated",
        "schedule.deleted",
        "device.changed",
        "ai.settings_changed",
    ]
    assert {e[1] for e in logged} == {"user_admin"}
