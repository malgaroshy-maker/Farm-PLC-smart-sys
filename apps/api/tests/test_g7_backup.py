"""G7 backups: online copy, keep-N pruning, USB copy, restore request, the daily due rule."""

import sqlite3
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest
from conftest import login

from app.config import settings
from app.services import backup


@pytest.fixture()
def bdir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "backup_dir", str(tmp_path / "b"))
    monkeypatch.setattr(settings, "backup_usb_dir", "")
    monkeypatch.setattr(settings, "backup_rclone_remote", "")
    return tmp_path / "b"


def test_backup_now_is_a_readable_copy_and_admin_only(client, bdir):
    op, admin = login(client, "operator"), login(client, "admin")
    assert client.post("/api/v1/backups", headers=op).status_code == 403
    r = client.post("/api/v1/backups", headers=admin)
    assert r.status_code == 200, r.text
    res = r.json()
    assert res["usb"] == "off" and res["drive"] == "off"
    con = sqlite3.connect(bdir / res["name"])
    try:
        assert con.execute("select count(*) from users").fetchone()[0] >= 1
    finally:
        con.close()
    st = client.get("/api/v1/backups", headers=admin).json()
    assert st["last"]["name"] == res["name"] and st["backups"][0]["name"] == res["name"]


def test_keep_prunes_and_usb_copy(client, bdir, tmp_path, monkeypatch):
    usb = tmp_path / "usb"
    usb.mkdir()
    monkeypatch.setattr(settings, "backup_keep", 2)
    monkeypatch.setattr(settings, "backup_usb_dir", str(usb))
    bdir.mkdir(parents=True)
    for n in ("farm-20260101-030000.db", "farm-20260102-030000.db", "farm-20260103-030000.db"):
        (bdir / n).write_bytes(b"x")
    res = client.post("/api/v1/backups", headers=login(client, "admin")).json()
    assert res["usb"] == "ok" and (usb / res["name"]).exists()
    left = sorted(p.name for p in bdir.glob("farm-*.db"))
    assert len(left) == 2 and res["name"] in left and "farm-20260101-030000.db" not in left


def test_missing_usb_and_rclone_are_reported(client, bdir, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "backup_usb_dir", str(tmp_path / "unplugged"))
    monkeypatch.setattr(settings, "backup_rclone_remote", "gdrive:Farm")
    monkeypatch.setattr(backup, "rclone_path", lambda: None)
    res = client.post("/api/v1/backups", headers=login(client, "admin")).json()
    assert res["usb"] == "missing" and res["drive"] == "rclone_missing"


def test_restore_request_and_cancel(client, bdir):
    admin = login(client, "admin")
    name = client.post("/api/v1/backups", headers=admin).json()["name"]
    assert client.post("/api/v1/backups/farm-x.db/restore", headers=admin).status_code == 404
    assert client.post("/api/v1/backups/..%2Ffarm.db/restore", headers=admin).status_code == 404
    r = client.post(f"/api/v1/backups/{name}/restore", headers=admin)
    assert r.status_code == 200 and (bdir / "restore.pending").read_text() == name
    assert client.get("/api/v1/backups", headers=admin).json()["pending_restore"] == name
    client.delete("/api/v1/backups/restore", headers=admin)
    assert not (bdir / "restore.pending").exists()


def test_daily_due_rule(monkeypatch):
    monkeypatch.setattr(settings, "backup_time", "03:00")
    tz = ZoneInfo("Africa/Tripoli")
    morning = datetime(2026, 11, 24, 3, 5, tzinfo=tz)
    assert not backup._due(datetime(2026, 11, 24, 2, 59, tzinfo=tz), None)
    assert backup._due(morning, None)
    assert backup._due(morning, datetime(2026, 11, 23, 1, 5, tzinfo=UTC).isoformat())
    assert not backup._due(morning, datetime(2026, 11, 24, 1, 2, tzinfo=UTC).isoformat())
