"""Daily database backups and restore requests (Milestone G7).

- A consistent copy of the SQLite database is taken with SQLite's online backup API (safe while
  the API is running), every day at BACKUP_TIME on the farm's wall clock, and on demand.
- The newest BACKUP_KEEP copies are kept in BACKUP_DIR.
- Each copy also goes to BACKUP_USB_DIR (if set and plugged in) and to BACKUP_RCLONE_REMOTE
  with rclone (e.g. Google Drive), if set and rclone is installed.
- A restore is never applied to a running server: the API writes `restore.pending`, and the
  launcher swaps the file in on the next start, keeping the current DB as `pre-restore-*.db`.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import shutil
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from zoneinfo import ZoneInfo

from app.config import settings
from app.core.timeutil import utcnow
from app.database import _is_sqlite
from app.restore_db import open_readonly, validate_backup

log = logging.getLogger(__name__)

NAME_RE = re.compile(r"^farm-\d{8}-\d{6}\.db$")
PENDING = "restore.pending"
STATUS = "status.json"
_lock = asyncio.Lock()


def db_path() -> Path | None:
    if not _is_sqlite:
        return None
    raw = settings.database_url.split("///", 1)[-1]
    return Path(raw).resolve() if raw and raw != ":memory:" else None


def backup_dir() -> Path:
    d = Path(settings.backup_dir)
    if not d.is_absolute() and (p := db_path()) is not None:
        d = p.parent / d
    return d


def _read_status() -> dict:
    try:
        return json.loads((backup_dir() / STATUS).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _write_status(status: dict) -> None:
    d = backup_dir()
    d.mkdir(parents=True, exist_ok=True)
    (d / STATUS).write_text(json.dumps(status, indent=2), encoding="utf-8")


def list_backups() -> list[dict]:
    d = backup_dir()
    if not d.exists():
        return []
    out = []
    for f in sorted(d.glob("farm-*.db"), reverse=True):
        if NAME_RE.match(f.name):
            st = f.stat()
            created = datetime.strptime(f.name[5:20], "%Y%m%d-%H%M%S")
            out.append(
                {"name": f.name, "size_bytes": st.st_size, "created_at": created.isoformat()}
            )
    return out


def pending_restore() -> str | None:
    try:
        name = (backup_dir() / PENDING).read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return name if NAME_RE.match(name) else None


def rclone_path() -> str | None:
    return shutil.which("rclone")


def status() -> dict:
    s = _read_status()
    return {
        "enabled": db_path() is not None,
        "dir": str(backup_dir()),
        "keep": settings.backup_keep,
        "time": settings.backup_time,
        "usb_dir": settings.backup_usb_dir or None,
        "usb_present": bool(settings.backup_usb_dir) and Path(settings.backup_usb_dir).exists(),
        "drive_remote": settings.backup_rclone_remote or None,
        "rclone_found": rclone_path() is not None,
        "last": s.get("last"),
        "pending_restore": pending_restore(),
        "backups": list_backups(),
    }


def _copy_db(src: Path, dst: Path) -> None:
    tmp = dst.with_suffix(".part")
    s = open_readonly(src)
    try:
        d = sqlite3.connect(str(tmp))
        try:
            s.backup(d)
        finally:
            d.close()
    finally:
        s.close()
    tmp.replace(dst)


def _prune(d: Path, keep: int, preserve: str | None = None) -> list[str]:
    files = [f for f in sorted(d.glob("farm-*.db"), reverse=True) if NAME_RE.match(f.name)]
    removed = []
    for f in files[max(1, keep) :]:
        if f.name == preserve:
            continue
        f.unlink(missing_ok=True)
        removed.append(f.name)
    return removed


def _make(reason: str) -> dict:
    src = db_path()
    if src is None:
        raise RuntimeError("backups need the SQLite database")
    d = backup_dir()
    d.mkdir(parents=True, exist_ok=True)
    name = f"farm-{datetime.now():%Y%m%d-%H%M%S}.db"
    dst = d / name
    _copy_db(src, dst)
    result: dict = {
        "name": name,
        "at": utcnow().isoformat(),
        "reason": reason,
        "size_bytes": dst.stat().st_size,
        "usb": "off",
        "drive": "off",
    }
    result["pruned"] = _prune(d, settings.backup_keep, preserve=pending_restore())

    if settings.backup_usb_dir:
        usb = Path(settings.backup_usb_dir)
        if usb.exists():
            try:
                shutil.copy2(dst, usb / name)
                _prune(usb, settings.backup_keep)
                result["usb"] = "ok"
            except OSError as exc:
                result["usb"] = f"failed:{type(exc).__name__}"
        else:
            result["usb"] = "missing"

    if settings.backup_rclone_remote:
        exe = rclone_path()
        if exe is None:
            result["drive"] = "rclone_missing"
        else:
            try:
                r = subprocess.run(
                    [exe, "copy", str(dst), settings.backup_rclone_remote],
                    capture_output=True,
                    timeout=600,
                )
                result["drive"] = "ok" if r.returncode == 0 else f"failed:{r.returncode}"
            except (OSError, subprocess.TimeoutExpired) as exc:
                result["drive"] = f"failed:{type(exc).__name__}"

    _write_status({**_read_status(), "last": result})
    return result


async def make_backup(reason: str = "manual") -> dict:
    async with _lock:
        result = await asyncio.to_thread(_make, reason)
    log.info("Backup %s written (usb=%s, drive=%s)", result["name"], result["usb"], result["drive"])
    return result


def _request_restore(name: str) -> None:
    selected = backup_dir() / name
    if not NAME_RE.fullmatch(name) or not selected.is_file():
        raise FileNotFoundError(name)
    validate_backup(selected)
    with TemporaryDirectory(dir=selected.parent, prefix=".restore-request-") as directory:
        marker = Path(directory) / PENDING
        marker.write_text(name, encoding="utf-8")
        marker.replace(selected.parent / PENDING)


async def request_restore(name: str) -> None:
    async with _lock:
        await asyncio.to_thread(_request_restore, name)


async def cancel_restore() -> str | None:
    async with _lock:
        name = pending_restore()
        (backup_dir() / PENDING).unlink(missing_ok=True)
        return name


def _due(now_local: datetime, last_iso: str | None) -> bool:
    hh, mm = (int(x) for x in settings.backup_time.split(":"))
    if (now_local.hour, now_local.minute) < (hh, mm):
        return False
    if not last_iso:
        return True
    try:
        last = datetime.fromisoformat(last_iso).astimezone(now_local.tzinfo)
    except ValueError:
        return True
    return last.date() < now_local.date()


async def daily_loop() -> None:
    """Runs for the life of the API: one backup a day, after BACKUP_TIME (real wall clock)."""
    if db_path() is None:
        return
    tz = ZoneInfo(settings.farm_timezone)
    while True:
        try:
            last = (_read_status().get("last") or {}).get("at")
            if _due(datetime.now(tz), last):
                await make_backup("daily")
        except Exception:
            log.exception("Daily backup failed")
            _write_status({**_read_status(), "last_error_at": utcnow().isoformat()})
            await asyncio.sleep(3600)  # don't retry a failing backup every minute
        await asyncio.sleep(60)
