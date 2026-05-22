"""
Database setup for the watchlist feature.

Uses SQLAlchemy with SQLite by default (zero infra, file-based). Override with
the DATABASE_URL env var to point at Postgres in production
(e.g. on Railway: postgresql+psycopg://user:pass@host:5432/db).

Note: on Railway's ephemeral filesystem a SQLite file resets on redeploy.
That's fine for a demo; set DATABASE_URL to a managed Postgres for persistence.
"""

import os
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

_DEFAULT_SQLITE = "sqlite:///" + os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "trialfinder.db"
)
DATABASE_URL = os.getenv("DATABASE_URL", _DEFAULT_SQLITE)

# check_same_thread is a SQLite-only arg; skip it for other backends.
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=_connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
Base = declarative_base()


def init_db() -> None:
    """Create tables if they don't exist. Safe to call on every startup."""
    # Import models so they're registered on Base before create_all.
    from db import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


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
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
