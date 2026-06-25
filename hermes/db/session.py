"""PostgreSQL session and schema initialization."""

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from hermes.config import settings
from hermes.db.base import Base
from hermes.db.models import (  # noqa: F401 — register ORM models
    ActivityORM,
    CompanyORM,
    ContactORM,
    FollowUpORM,
    MemoryORM,
    ProposalORM,
)

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(),
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
    return _SessionLocal


@contextmanager
def get_session() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    """Create tables if they do not exist."""
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_memory_content_fts
                ON memory_entries
                USING gin (to_tsvector('english', content))
                """
            )
        )
        conn.commit()


def reset_engine() -> None:
    """Reset cached engine (useful for tests)."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None
