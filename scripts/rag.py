"""Gemini embeddings + RAG retrieval/answer helpers."""

import logging
import os
import re

from scripts.db import (
    EMBEDDING_DIM,
    RagChunk,
    RagDocument,
    get_session,
    is_postgres,
    rag_chunk_count,
)

logger = logging.getLogger(__name__)

EMBED_MODEL = os.environ.get("GEMINI_EMBED_MODEL", "text-embedding-004")
CHAT_MODEL = os.environ.get("GEMINI_CHAT_MODEL", "gemini-2.0-flash")


class RagUnavailable(Exception):
    """Raised when RAG cannot run (SQLite, missing key, empty corpus)."""


def _api_key() -> str:
    key = os.environ.get("GOOGLE_API_KEY", "").strip()
    if not key:
        raise RagUnavailable(
            "GOOGLE_API_KEY is not set. Add it to the environment to use the chatbot."
        )
    return key


def _client():
    from google import genai

    return genai.Client(api_key=_api_key())


def _extract_embedding_values(result) -> list[list[float]]:
    embeddings = getattr(result, "embeddings", None)
    if embeddings:
        return [list(emb.values) for emb in embeddings]
    emb = getattr(result, "embedding", None)
    if emb is not None:
        return [list(emb.values)]
    raise RuntimeError("Gemini embed_content returned no embeddings")


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed one or more texts with Gemini. Returns 768-dim vectors."""
    if not texts:
        return []
    client = _client()
    vectors: list[list[float]] = []
    for text_item in texts:
        result = client.models.embed_content(
            model=EMBED_MODEL,
            contents=text_item,
        )
        batch = _extract_embedding_values(result)
        vec = batch[0]
        if len(vec) != EMBEDDING_DIM:
            raise RuntimeError(
                f"Unexpected embedding dim {len(vec)}; expected {EMBEDDING_DIM}"
            )
        vectors.append(vec)
    return vectors


def chunk_text(body: str, size: int = 700, overlap: int = 80) -> list[str]:
    body = re.sub(r"\s+", " ", body).strip()
    if not body:
        return []
    if len(body) <= size:
        return [body]
    chunks = []
    start = 0
    while start < len(body):
        end = min(start + size, len(body))
        chunks.append(body[start:end].strip())
        if end >= len(body):
            break
        start = max(0, end - overlap)
    return [c for c in chunks if c]


def search_chunks(query: str, k: int = 6) -> list[dict]:
    if not is_postgres():
        raise RagUnavailable(
            "The chatbot requires PostgreSQL with pgvector. Use Docker Compose or Render."
        )
    session = get_session()
    try:
        if rag_chunk_count(session) == 0:
            raise RagUnavailable(
                "RAG corpus is empty. Run: python -m scripts.build_rag_corpus"
            )
        query_vec = embed_texts([query])[0]
        rows = (
            session.query(RagChunk, RagDocument)
            .join(RagDocument, RagDocument.id == RagChunk.document_id)
            .filter(RagChunk.embedding.isnot(None))
            .order_by(RagChunk.embedding.cosine_distance(query_vec))
            .limit(k)
            .all()
        )
        return [
            {
                "title": doc.title,
                "chunk_text": chunk.chunk_text,
                "barangay": doc.barangay,
                "source_type": doc.source_type,
            }
            for chunk, doc in rows
        ]
    finally:
        session.close()


def answer_question(message: str) -> dict:
    message = (message or "").strip()
    if not message:
        raise ValueError("Message is required.")
    if len(message) > 1000:
        raise ValueError("Message must be at most 1000 characters.")

    hits = search_chunks(message, k=6)
    if not hits:
        return {
            "answer": "I could not find relevant RideSafe data for that question.",
            "sources": [],
        }

    context_blocks = []
    sources = []
    seen = set()
    for i, hit in enumerate(hits, start=1):
        label = hit["title"]
        if hit.get("barangay"):
            label = f"{hit['title']} ({hit['barangay']})"
        context_blocks.append(f"[{i}] {label}\n{hit['chunk_text']}")
        key = (hit["title"], hit.get("barangay"))
        if key not in seen:
            seen.add(key)
            sources.append(
                {
                    "title": hit["title"],
                    "barangay": hit.get("barangay"),
                    "source_type": hit.get("source_type"),
                }
            )

    context = "\n\n".join(context_blocks)
    system = (
        "You are RideSafe Assistant for Imus City traffic accident data (2022–Nov 2024). "
        "Answer ONLY using the provided context. If the context is insufficient, say you do not know. "
        "Do not invent numbers. Be concise and clear for stakeholders. "
        "When relevant, mention barangay names and hours from the context."
    )
    prompt = f"{system}\n\nContext:\n{context}\n\nUser question: {message}\n\nAnswer:"

    client = _client()
    response = client.models.generate_content(model=CHAT_MODEL, contents=prompt)
    answer = getattr(response, "text", None) or str(response)
    return {"answer": answer.strip(), "sources": sources}
