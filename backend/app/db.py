from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import DATABASE_URL


class Base(DeclarativeBase):
    pass


def make_engine(url: str = DATABASE_URL):
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args, future=True)


engine = make_engine()
_session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def SessionLocal():
    """
    A function, not a sessionmaker instance, on purpose: every caller does
    `from app.db import SessionLocal` and then `SessionLocal()`. Because this
    re-reads the module-level `_session_factory` on every call, tests can
    repoint the whole app at an isolated database via `configure_engine`
    without having to chase down and monkeypatch every import site.
    """
    return _session_factory()


def configure_engine(url: str):
    """Test-only entry point: repoint the app at a fresh engine/DB."""
    global engine, _session_factory
    engine = make_engine(url)
    _session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return engine


def init_db(engine_=None):
    from app import models  # noqa: F401 ensure models are registered
    Base.metadata.create_all(bind=engine_ or engine)


def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
