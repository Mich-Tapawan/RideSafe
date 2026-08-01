import logging
import os
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

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
from sqlalchemy.pool import NullPool

_engine = None
SessionLocal = None

EMBEDDING_DIM = 768
logger = logging.getLogger(__name__)

# Hosts that typically do not need (or reject) forced SSL.
_LOCAL_DB_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "db"})


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


def _set_query_param(url: str, key: str, value: str) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    query[key] = [value]
    flat = [(k, v) for k, vals in query.items() for v in vals]
    return urlunparse(parsed._replace(query=urlencode(flat)))


def _normalize_database_url(url: str) -> str:
    """Normalize Postgres URLs for SQLAlchemy + cloud hosts (Supabase, Render)."""
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)

    if not url.startswith("postgresql"):
        return url

    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    query = parse_qs(parsed.query, keep_blank_values=True)

    # Supabase / managed Postgres require TLS; local Compose does not.
    if host and host not in _LOCAL_DB_HOSTS and "sslmode" not in query:
        url = _set_query_param(url, "sslmode", "require")

    return url


def _is_supabase_transaction_pooler(url: str) -> bool:
    """Supabase transaction pooler uses port 6543 (PgBouncer transaction mode)."""
    parsed = urlparse(url)
    return parsed.port == 6543


def _engine_kwargs(url: str) -> dict:
    if url.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}

    kwargs = {
        "pool_pre_ping": True,
        "pool_recycle": int(os.environ.get("DB_POOL_RECYCLE", "300")),
    }

    # Transaction-mode poolers should not use SQLAlchemy's own pool.
    if _is_supabase_transaction_pooler(url):
        kwargs["poolclass"] = NullPool
        return kwargs

    kwargs["pool_size"] = int(os.environ.get("DB_POOL_SIZE", "2"))
    kwargs["max_overflow"] = int(os.environ.get("DB_MAX_OVERFLOW", "2"))
    return kwargs


def get_database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if url:
        return _normalize_database_url(url.strip())
    data_dir = Path(".data")
    data_dir.mkdir(exist_ok=True)
    return f"sqlite:///{data_dir / 'ridesafe.db'}"


def is_postgres() -> bool:
    return get_database_url().startswith("postgresql")


def _ensure_pgvector(engine) -> None:
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    except Exception as exc:
        logger.warning(
            "Could not CREATE EXTENSION vector (%s). "
            "On Supabase: Dashboard → Database → Extensions → enable \"vector\", then restart.",
            exc,
        )


def _ensure_vector_index(engine) -> None:
    """HNSW index for cosine retrieval; safe to skip if extension/index unavailable."""
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS rag_chunks_embedding_hnsw_idx
                    ON rag_chunks
                    USING hnsw (embedding vector_cosine_ops)
                    """
                )
            )
    except Exception as exc:
        logger.warning("Could not create rag_chunks HNSW index (%s).", exc)


def init_db():
    global _engine, SessionLocal
    if _engine is not None:
        return

    url = get_database_url()
    _engine = create_engine(url, **_engine_kwargs(url))
    SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)

    if url.startswith("postgresql"):
        _ensure_pgvector(_engine)
        Base.metadata.create_all(_engine)
        _ensure_vector_index(_engine)
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
