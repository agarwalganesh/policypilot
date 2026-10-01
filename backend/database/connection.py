"""
PolicyPilot — Database Layer
SQLAlchemy engine + session factory + base model.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.config import get_logger, get_settings

logger = get_logger(__name__)
settings = get_settings()


class Base(DeclarativeBase):
    pass


def _create_engine():
    url = settings.database_url
    is_sqlite = url.startswith("sqlite")
    kwargs: dict = {"echo": (settings.flask_env == "development")}
    if not is_sqlite:
        kwargs.update({"pool_size": 5, "max_overflow": 10, "pool_pre_ping": True})
    else:
        # SQLite: allow multi-threaded access for Flask dev server
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(url, **kwargs)


engine = _create_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """Context manager that yields a DB session and handles commit/rollback."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def health_check() -> bool:
    """Return True if the database is reachable."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.error("database_health_check_failed", error=str(exc))
        return False
