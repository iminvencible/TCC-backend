from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def build_engine(database_url: str):
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    created_engine = create_engine(database_url, pool_pre_ping=True, connect_args=connect_args)
    if database_url.startswith("mysql"):

        @event.listens_for(created_engine, "connect")
        def set_utc_timezone(dbapi_connection, _):
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute("SET time_zone = '+00:00'")
            finally:
                cursor.close()

    return created_engine


engine = build_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
