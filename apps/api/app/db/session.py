from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.models import Base

_engine: Engine | None = None
_factory: sessionmaker[Session] | None = None


def configure(url: str | None = None) -> None:
    global _engine, _factory
    url = url or get_settings().database_url
    kwargs = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {"pool_pre_ping": True}
    _engine = create_engine(url, **kwargs)
    _factory = sessionmaker(bind=_engine, expire_on_commit=False)


def engine() -> Engine:
    if _engine is None:
        configure()
    return _engine  # type: ignore[return-value]


def create_tables() -> None:
    Base.metadata.create_all(engine())


def SessionLocal() -> Session:
    if _factory is None:
        configure()
    return _factory()  # type: ignore[misc]


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
