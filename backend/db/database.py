"""
Database setup for the watchlist feature.

Uses SQLAlchemy with SQLite by default (zero infra, file-based). Override with
the DATABASE_URL env var to point at Postgres in production
(e.g. on Railway: postgresql+psycopg://user:pass@host:5432/db).

Note: on Railway's ephemeral filesystem a SQLite file resets on redeploy.
That's fine for a demo; set DATABASE_URL to a managed Postgres for persistence.
"""

import os
import threading
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

_DEFAULT_SQLITE = "sqlite:///" + os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "trialfinder.db"
)
# Note: os.getenv returns "" (not None) when the var is present but blank, as
# in `DATABASE_URL=` in a .env file. Treat blank the same as unset.
DATABASE_URL = os.getenv("DATABASE_URL", "").strip() or _DEFAULT_SQLITE

# Railway and Heroku hand out "postgresql://..." but SQLAlchemy 2 with
# psycopg 3 needs the driver named explicitly. Normalize it so users don't
# have to hand-edit the variable.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgresql://", "postgresql+psycopg://", 1
    )

# check_same_thread is a SQLite-only arg; skip it for other backends.
if DATABASE_URL.startswith("sqlite"):
    _connect_args = {"check_same_thread": False}
    _engine_kwargs = {}
else:
    # Fail fast instead of hanging. Without an explicit timeout a wrong host
    # can block for a minute or more, which stalls startup and makes the
    # platform healthcheck report "service unavailable".
    _connect_args = {"connect_timeout": 10}
    _engine_kwargs = {
        # Recycle before typical managed-Postgres idle timeouts, and verify
        # the connection before handing it out, so the first request after a
        # quiet period does not fail on a dead socket.
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_size": 5,
        "max_overflow": 5,
    }

engine = create_engine(
    DATABASE_URL, connect_args=_connect_args, future=True, **_engine_kwargs
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
Base = declarative_base()

# Signals that tables exist and the database is usable.
#
# Schema setup runs in a background thread at startup so the HTTP listener can
# bind immediately (a blocking connect made platform healthchecks fail). That
# creates a short window where a request could arrive before the tables exist,
# so request-scoped sessions wait on this event first.
_db_ready = threading.Event()

# How long a request will wait for startup to finish before giving up.
DB_READY_TIMEOUT_SECONDS = float(os.getenv("DB_READY_TIMEOUT", "20"))


def wait_until_ready(timeout: float | None = None) -> bool:
    """Block until the schema is ready. Returns False on timeout."""
    return _db_ready.wait(
        DB_READY_TIMEOUT_SECONDS if timeout is None else timeout
    )


def is_ready() -> bool:
    return _db_ready.is_set()


def init_db() -> None:
    """
    Create tables on first boot. If a table exists but is missing columns
    that the current models define (i.e. schema drift from an older
    trialfinder.db), drop everything and recreate. Pre-launch, this is safe
    because we have no real user data yet. In production, replace this with
    Alembic migrations.
    """
    from sqlalchemy import inspect
    from db import models  # noqa: F401 — ensure models register on Base

    inspector = inspect(engine)
    needs_reset = False

    for table_name, table in Base.metadata.tables.items():
        if not inspector.has_table(table_name):
            continue
        existing_cols = {c["name"] for c in inspector.get_columns(table_name)}
        expected_cols = {c.name for c in table.columns}
        missing = expected_cols - existing_cols
        if missing:
            import logging
            logging.getLogger(__name__).warning(
                "Schema drift on %s — missing columns %s. Dropping and "
                "recreating all tables (dev-only auto-migration).",
                table_name,
                sorted(missing),
            )
            needs_reset = True
            break

    if needs_reset:
        Base.metadata.drop_all(bind=engine)

    Base.metadata.create_all(bind=engine)
    _db_ready.set()


@contextmanager
def session_scope():
    """Provide a transactional scope for a series of operations."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# FastAPI dependency
def get_db():
    """
    Request-scoped session.

    Waits for background schema setup to finish before handing out a session,
    so an early request cannot hit "no such table". Health checks do not use
    this dependency, so liveness stays instant regardless.
    """
    if not _db_ready.is_set() and not wait_until_ready():
        from fastapi import HTTPException

        raise HTTPException(
            status_code=503,
            detail="The service is still starting up. Please try again in a moment.",
            headers={"Retry-After": "5"},
        )

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
