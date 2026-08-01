"""Gemini embeddings + RAG retrieval/answer helpers (with allowlisted live tools)."""

import logging
import os
import re
import time

from scripts.chat_tools import (
    begin_tool_trace,
    format_tool_context,
    get_tool_trace,
    select_and_run_tools,
)
from scripts.db import (
    EMBEDDING_DIM,
    RagChunk,
    RagDocument,
    get_session,
    is_postgres,
    rag_chunk_count,
)

logger = logging.getLogger(__name__)

EMBED_MODEL = os.environ.get("GEMINI_EMBED_MODEL", "gemini-embedding-001")
CHAT_MODEL = os.environ.get("GEMINI_CHAT_MODEL", "gemini-flash-latest")
CHAT_FALLBACK_MODELS = [
    m.strip()
    for m in os.environ.get(
        "GEMINI_CHAT_FALLBACKS",
        "gemini-flash-lite-latest,gemini-3.5-flash-lite,gemini-3.1-flash-lite",
    ).split(",")
    if m.strip()
]

# Render sets RENDER=true. Lean mode keeps /api/chat under free-tier proxy limits.
LEAN_CHAT = os.environ.get("LEAN_CHAT", "").lower() in ("1", "true", "yes") or (
    os.environ.get("RENDER", "").lower() in ("true", "1")
)


class RagUnavailable(Exception):
    """Raised when RAG cannot run (SQLite, missing key, empty corpus)."""


def _api_key() -> str:
    key = os.environ.get("GOOGLE_API_KEY", "").strip()
    if not key:
        raise RagUnavailable(
            "GOOGLE_API_KEY is not set. Add it to the environment to use the chatbot."
        )
    return key


def _http_timeout_ms() -> int:
    raw = os.environ.get("GEMINI_HTTP_TIMEOUT_MS")
    if raw:
        try:
            return max(5_000, int(raw))
        except ValueError:
            pass
    return 45_000 if LEAN_CHAT else 90_000


def _client():
    from google import genai
    from google.genai import types

    return genai.Client(
        api_key=_api_key(),
        http_options=types.HttpOptions(timeout=_http_timeout_ms()),
    )


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
    from google.genai import types

    client = _client()
    vectors: list[list[float]] = []
    config = types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIM)
    for text_item in texts:
        result = client.models.embed_content(
            model=EMBED_MODEL,
            contents=text_item,
            config=config,
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


def search_chunks(query: str, k: int = 8) -> list[dict]:
    if not is_postgres():
        raise RagUnavailable(
            "The chatbot requires PostgreSQL with pgvector. Use Docker Compose or Render."
        )
    session = get_session()
    try:
        if rag_chunk_count(session) == 0:
            return []
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


def _chat_models() -> list[str]:
    if LEAN_CHAT:
        # Prefer fast/lite models first on free Render to finish under proxy limits.
        ordered = []
        for name in (
            os.environ.get("GEMINI_CHAT_MODEL_LEAN", "gemini-flash-lite-latest"),
            CHAT_MODEL,
            *CHAT_FALLBACK_MODELS,
        ):
            if name and name not in ordered:
                ordered.append(name)
        return ordered[:2]

    models = [CHAT_MODEL]
    for name in CHAT_FALLBACK_MODELS:
        if name not in models:
            models.append(name)
    return models


def _generate_answer(prompt: str) -> str:
    """Call Gemini with retries and model fallbacks for transient 429/503."""
    from google.genai import types
    from google.genai.errors import APIError, ClientError, ServerError

    client = _client()
    config = types.GenerateContentConfig(
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        temperature=0.2,
        max_output_tokens=512 if LEAN_CHAT else 1024,
    )
    last_error: Exception | None = None
    attempts_per_model = 1 if LEAN_CHAT else 3

    for model in _chat_models():
        for attempt in range(attempts_per_model):
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=config,
                )
                text = getattr(response, "text", None) or str(response)
                if model != CHAT_MODEL:
                    logger.info("Answered with fallback model %s", model)
                return text.strip()
            except (ClientError, ServerError, APIError) as exc:
                last_error = exc
                status = getattr(exc, "code", None) or getattr(exc, "status_code", None)
                if status in (429, 503) and attempt < attempts_per_model - 1:
                    delay = 1.0 * (attempt + 1)
                    logger.warning(
                        "Gemini %s on %s (attempt %s); retrying in %.1fs",
                        status,
                        model,
                        attempt + 1,
                        delay,
                    )
                    time.sleep(delay)
                    continue
                if status in (429, 503, 404):
                    logger.warning("Gemini %s on %s; trying next model", status, model)
                    break
                raise
            except Exception as exc:
                # Timeouts / transport errors: fail over quickly on lean hosts.
                last_error = exc
                logger.warning("Gemini transport error on %s: %s", model, exc)
                break

    raise RagUnavailable(
        "Gemini is temporarily overloaded or rate-limited. Please try again in a moment."
    ) from last_error


def _wants_rag_context(message: str, tool_results: list) -> bool:
    """On lean hosts, skip embedding when allowlisted tools already answered."""
    if not LEAN_CHAT:
        return True
    if not tool_results:
        return True
    lower = message.lower()
    faq_tokens = (
        "how do",
        "how to",
        "what is",
        "what's",
        "explain",
        "help",
        "faq",
        "report",
        "pdf",
        "ridesafe",
        "mean",
        "definition",
    )
    return any(token in lower for token in faq_tokens)


def answer_question(message: str) -> dict:
    message = (message or "").strip()
    if not message:
        raise ValueError("Message is required.")
    max_len = 500 if LEAN_CHAT else 1000
    if len(message) > max_len:
        raise ValueError(f"Message must be at most {max_len} characters.")

    if not is_postgres():
        raise RagUnavailable(
            "The chatbot requires PostgreSQL with pgvector. Use Docker Compose or Render."
        )

    begin_tool_trace()
    tool_results = select_and_run_tools(message)

    hits: list[dict] = []
    if _wants_rag_context(message, tool_results):
        try:
            hits = search_chunks(message, k=3 if LEAN_CHAT else 8)
        except Exception as exc:
            logger.warning("RAG search failed; continuing with tools only: %s", exc)
            hits = []

    sources = []
    seen = set()
    context_blocks = []
    chunk_cap = 350 if LEAN_CHAT else 900
    for i, hit in enumerate(hits, start=1):
        label = hit["title"]
        if hit.get("barangay"):
            label = f"{hit['title']} ({hit['barangay']})"
        text = hit["chunk_text"] or ""
        if len(text) > chunk_cap:
            text = text[: chunk_cap - 1] + "…"
        context_blocks.append(f"[{i}] {label}\n{text}")
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

    live_block = format_tool_context(tool_results)
    if live_block:
        context_blocks.append(
            "Live allowlisted tool results (prefer for numbers):\n" + live_block
        )

    for call in get_tool_trace():
        title = f"Live tool: {call['name']}"
        key = (title, None)
        if key not in seen:
            seen.add(key)
            sources.append(
                {
                    "title": title,
                    "barangay": None,
                    "source_type": "tool",
                    "detail": call.get("summary"),
                }
            )

    if not context_blocks:
        return {
            "answer": (
                "I could not find relevant RideSafe data for that question. "
                "Try asking about barangay rankings, offenses, monthly totals, or predicted risk."
            ),
            "sources": [],
        }

    context = "\n\n".join(context_blocks)
    if LEAN_CHAT and len(context) > 6000:
        context = context[:5999] + "…"

    system = (
        "You are RideSafe Assistant for Imus City traffic accident data (2022–Nov 2024). "
        "Answer using the RAG context and any Live allowlisted tool results. "
        "Prefer live tool results for rankings, counts, monthly totals, and hour-specific risk. "
        "Prefer RAG for how-to / FAQ / narrative insights. "
        "Do not invent numbers. Be concise. Distinguish historical incident counts from "
        "predicted risk percentages."
    )
    prompt = f"{system}\n\nContext:\n{context}\n\nUser question: {message}\n\nAnswer:"
    answer = _generate_answer(prompt)
    return {"answer": answer, "sources": sources}
