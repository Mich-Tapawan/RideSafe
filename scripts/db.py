import os
from pathlib import Path

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Column,
    Date,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    create_engine,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, relationship, sessionmaker

_engine = None
SessionLocal = None

EMBEDDING_DIM = 768


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


class RagDocument(Base):
    __tablename__ = "rag_documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(256), nullable=False)
    source_type = Column(String(32), nullable=False, index=True)
    barangay = Column(String(128), nullable=True, index=True)
    body_text = Column(Text, nullable=False)

    chunks = relationship(
        "RagChunk", back_populates="document", cascade="all, delete-orphan"
    )


class RagChunk(Base):
    __tablename__ = "rag_chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(
        Integer,
        ForeignKey("rag_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_text = Column(Text, nullable=False)
    embedding = Column(Vector(EMBEDDING_DIM), nullable=True)

    document = relationship("RagDocument", back_populates="chunks")


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


def is_postgres() -> bool:
    return get_database_url().startswith("postgresql")


def init_db():
    global _engine, SessionLocal
    if _engine is not None:
        return

    url = get_database_url()
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    _engine = create_engine(url, connect_args=connect_args)
    SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)

    if url.startswith("postgresql"):
        with _engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        Base.metadata.create_all(_engine)
    else:
        # Skip RAG tables on SQLite (pgvector unsupported)
        analytics = [
            t
            for t in Base.metadata.sorted_tables
            if t.name not in ("rag_documents", "rag_chunks")
        ]
        Base.metadata.create_all(_engine, tables=analytics)


def get_session():
    if SessionLocal is None:
        init_db()
    return SessionLocal()


def incident_count(session) -> int:
    return session.query(func.count(Incident.id)).scalar() or 0


def rag_chunk_count(session) -> int:
    try:
        return session.query(func.count(RagChunk.id)).scalar() or 0
    except Exception:
        return 0
