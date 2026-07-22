import os
from pathlib import Path

from sqlalchemy import (
    Column,
    Date,
    Integer,
    String,
    Time,
    create_engine,
    func,
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker

_engine = None
SessionLocal = None


class Base(DeclarativeBase):
    pass


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date_committed = Column(Date, nullable=True)
    time_committed = Column(Time, nullable=True)
    barangay = Column(String(128), nullable=False, index=True)


class OffenseStat(Base):
    __tablename__ = "offense_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    year = Column(Integer, nullable=False, index=True)
    offense_type = Column(String(256), nullable=False)
    count = Column(Integer, nullable=False, default=0)


class BarangayStat(Base):
    __tablename__ = "barangay_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    year = Column(Integer, nullable=False, index=True)
    barangay_name = Column(String(128), nullable=False, index=True)
    count = Column(Integer, nullable=False, default=0)


class DailyOffenseCount(Base):
    __tablename__ = "daily_offense_counts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    offense_date = Column(Date, nullable=False, index=True)
    count = Column(Integer, nullable=False, default=0)


def _normalize_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


def get_database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if url:
        return _normalize_database_url(url)
    data_dir = Path(".data")
    data_dir.mkdir(exist_ok=True)
    return f"sqlite:///{data_dir / 'ridesafe.db'}"


def init_db():
    global _engine, SessionLocal
    if _engine is not None:
        return

    url = get_database_url()
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    _engine = create_engine(url, connect_args=connect_args)
    SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(_engine)


def get_session():
    if SessionLocal is None:
        init_db()
    return SessionLocal()


def incident_count(session) -> int:
    return session.query(func.count(Incident.id)).scalar() or 0
