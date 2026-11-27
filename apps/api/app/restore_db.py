"""Validate and restore a Farm-PLC SQLite backup before the API starts."""

import sqlite3
import sys
import time
from contextlib import closing
from pathlib import Path
from shutil import copy2
from tempfile import TemporaryDirectory

_REQUIRED_TABLES = {"farms", "users", "zones"}


class InvalidBackup(ValueError):
    """The supplied file is not a readable Farm-PLC database."""


def open_readonly(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)


def _validate(source: sqlite3.Connection) -> None:
    try:
        if source.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
            raise InvalidBackup("SQLite integrity check failed")
        tables = {
            name
            for (name,) in source.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
    except sqlite3.DatabaseError as exc:
        raise InvalidBackup("Unreadable SQLite backup") from exc
    if not _REQUIRED_TABLES <= tables:
        raise InvalidBackup("Missing Farm-PLC tables")


def validate_backup(path: Path) -> None:
    with closing(open_readonly(path)) as source:
        _validate(source)


def _save_live_database(live: Path, recovery: Path) -> bool:
    """Return false for a corrupt live database that needs a byte-for-byte archive."""
    try:
        with closing(open_readonly(live)) as original:
            if original.execute("PRAGMA quick_check(1)").fetchone() != ("ok",):
                return False
            with TemporaryDirectory(dir=recovery.parent, prefix=".farm-recovery-") as directory:
                part = Path(directory) / "recovery.db"
                with closing(sqlite3.connect(part)) as saved:
                    original.backup(saved)
                part.replace(recovery)
    except sqlite3.DatabaseError as exc:
        error_code = getattr(exc, "sqlite_errorcode", 0) & 0xFF
        if error_code in (sqlite3.SQLITE_CORRUPT, sqlite3.SQLITE_NOTADB):
            return False
        raise
    return True


def _replace_corrupt_database(source: sqlite3.Connection, live: Path, recovery: Path) -> None:
    with TemporaryDirectory(dir=live.parent, prefix=".farm-restore-") as temp_dir:
        restored = Path(temp_dir) / "restored.db"
        with closing(sqlite3.connect(restored)) as destination:
            source.backup(destination)

        copy2(live, recovery)
        sidecars = []
        for suffix in ("-wal", "-shm", "-journal"):
            original = live.with_name(live.name + suffix)
            if original.exists():
                saved = recovery.with_name(recovery.name + suffix)
                copy2(original, saved)
                sidecars.append((original, saved))

        try:
            for original, _ in sidecars:
                original.unlink()
            restored.replace(live)
        except OSError:
            for original, saved in sidecars:
                if not original.exists():
                    copy2(saved, original)
            raise


def restore_database(backup: Path, live: Path, recovery: Path) -> None:
    """Save all committed live data, including WAL data, before the restore transaction."""
    if len({backup.resolve(), live.resolve(), recovery.resolve()}) != 3:
        raise InvalidBackup("Backup, live database and recovery paths must be distinct")
    with closing(open_readonly(backup)) as source:
        _validate(source)
        if live.exists():
            if recovery.exists():
                raise FileExistsError(recovery)
            if not _save_live_database(live, recovery):
                _replace_corrupt_database(source, live, recovery)
                return
        # SQLite commits the restored pages together and manages any WAL sidecars.
        with closing(sqlite3.connect(live)) as destination:
            source.backup(destination)


def _end_all_sign_ins(live: Path) -> None:
    """A restore brings back old accounts: nobody stays signed in across it."""
    with closing(sqlite3.connect(live)) as db, db:
        columns = {row[1] for row in db.execute("PRAGMA table_info(users)")}
        if "token_version" in columns:
            db.execute("UPDATE users SET token_version = ?", (int(time.time()),))


def main() -> int:
    if len(sys.argv) != 4:
        return 1
    try:
        paths = [Path(value) for value in sys.argv[1:]]
        restore_database(*paths)
        _end_all_sign_ins(paths[1])
    except InvalidBackup:
        return 2
    except (OSError, sqlite3.Error):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
