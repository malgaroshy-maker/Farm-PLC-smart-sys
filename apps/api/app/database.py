"""
Async SQLAlchemy database engine and session management.
"""

from collections.abc import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings

_is_sqlite = settings.database_url.startswith("sqlite")

# SQLite: one connection per session avoids cross-event-loop reuse (tests,
# background tasks) and "database is locked" surprises from pooled handles.
_engine_kwargs = {"poolclass": NullPool, "connect_args": {"timeout": 15}} if _is_sqlite else {}

engine = create_async_engine(settings.database_url, echo=settings.app_debug, **_engine_kwargs)

if _is_sqlite:

    @event.listens_for(engine.sync_engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _record) -> None:  # pragma: no cover - exercised via engine
        # WAL: readers (charts, dashboard) never block the writer (telemetry, monitor) and
        # a crash cannot corrupt the DB mid-write. NORMAL sync is safe with WAL.
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.execute("PRAGMA busy_timeout=15000")
        cur.close()


async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
