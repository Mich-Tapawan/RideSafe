"""Build insight documents from analytics tables and embed into pgvector."""

import logging
import os
import sys

from scripts.db import (
    RagChunk,
    RagDocument,
    get_session,
    init_db,
    is_postgres,
    rag_chunk_count,
)
from scripts.model import AccidentModel
from scripts.rag import RagUnavailable, chunk_text, embed_texts
from scripts.repository import (
    get_barangay_stats_df,
    get_daily_offense_df,
    get_offense_stats_df,
)
from scripts.summary_report import generate_summary_report

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

FAQ_DOCS = [
    {
        "title": "How to use RideSafe",
        "source_type": "faq",
        "barangay": None,
        "body_text": (
            "RideSafe is a traffic accident analysis and prediction app for Imus City. "
            "On the dashboard, toggle between the bar chart and heat map to explore historical "
            "accidents by offense type and barangay. Enter a barangay name and hour, then run "
            "a prediction to see the estimated chance of an accident. After a prediction, you "
            "can download a PDF summary report for that barangay. The Ask RideSafe chat page "
            "answers questions about trends and barangay risk using curated insights from the data."
        ),
    },
    {
        "title": "Data coverage",
        "source_type": "faq",
        "barangay": None,
        "body_text": (
            "RideSafe uses historical traffic incident records for Imus City covering January 2022 "
            "through November 18, 2024. Charts and predictions are based on this range. "
            "The 2024 data does not include the full calendar year."
        ),
    },
    {
        "title": "What the prediction percentage means",
        "source_type": "faq",
        "barangay": None,
        "body_text": (
            "The prediction percentage is the model's estimated relative chance of an accident "
            "for a selected barangay and hour of day. It uses a Random Forest classifier trained "
            "on barangay, hour, and peak-hour features with SMOTE for class imbalance. "
            "Risk labels: Low below 40%, Moderate from 40% to 55%, High above 55%. "
            "It is a decision-support estimate, not a guarantee that an accident will or will not occur."
        ),
    },
    {
        "title": "Peak hours citywide",
        "source_type": "faq",
        "barangay": None,
        "body_text": (
            "The model treats morning (7–9) and evening (17–19) as peak-hour windows when estimating risk. "
            "Actual peak predicted hours vary by barangay; use Ask RideSafe or a barangay prediction "
            "to see local peak and lowest risk hours."
        ),
    },
]


def _barangay_insight_text(report: dict) -> str:
    quarters = ", ".join(
        f"{q['label']}: {q['count']} ({q['percent']}%)"
        for q in (report.get("quarter_breakdown") or [])
    )
    years = ", ".join(
        f"{y['year']}: {y['count']}" for y in (report.get("year_breakdown") or [])
    )
    recs = " ".join(report.get("recommendations") or [])
    return (
        f"Barangay {report['barangay_name']} traffic safety insight for Imus City. "
        f"Data range: {report['data_range']}. "
        f"Total recorded incidents: {report['total_incidents']} "
        f"({report['share_percent']}% of city total {report['city_total']}). "
        f"Peak predicted risk hour: {report['peak_hour']}:00 at {report['peak_percent']}% "
        f"({report['peak_risk']}). "
        f"Lowest predicted risk hour: {report['lowest_hour']}:00 at {report['lowest_percent']}% "
        f"({report['lowest_risk']}). "
        f"Peak historical quarter: {report['peak_quarter']}. "
        f"Lowest historical quarter: {report['lowest_quarter']}. "
        f"Quarterly breakdown: {quarters or 'n/a'}. "
        f"Yearly breakdown: {years or 'n/a'}. "
        f"Recommendations: {recs}"
    )


def _city_offense_doc() -> dict:
    df = get_offense_stats_df()
    if df.empty:
        body = "No offense statistics available."
    else:
        lines = []
        for year in sorted(df["year"].unique()):
            part = df[df["year"] == year].sort_values("Count of offense", ascending=False)
            top = part.head(5)
            desc = "; ".join(
                f"{row['Offense Type']}: {int(row['Count of offense'])}"
                for _, row in top.iterrows()
            )
            lines.append(f"Year {int(year)} top offenses — {desc}.")
        body = (
            "City-wide offense type statistics for Imus traffic incidents. "
            + " ".join(lines)
        )
    return {
        "title": "City offense trends 2022–2024",
        "source_type": "city",
        "barangay": None,
        "body_text": body,
    }


def _city_barangay_doc() -> dict:
    df = get_barangay_stats_df()
    if df.empty:
        body = "No barangay statistics available."
    else:
        top = df.sort_values("Count of barangay", ascending=False).head(15)
        desc = "; ".join(
            f"{row['Barangay Name']}: {int(row['Count of barangay'])}"
            for _, row in top.iterrows()
        )
        body = (
            "Barangays with the highest aggregated incident counts across 2022–2024 "
            f"(from barangay yearly stats): {desc}."
        )
    return {
        "title": "Highest-incident barangays",
        "source_type": "city",
        "barangay": None,
        "body_text": body,
    }


def _city_year_docs() -> list[dict]:
    docs = []
    for year in (2022, 2023, 2024):
        df = get_daily_offense_df(year)
        if df.empty:
            continue
        total = int(df["Count of offense"].sum())
        docs.append(
            {
                "title": f"City daily offense totals {year}",
                "source_type": "city",
                "barangay": None,
                "body_text": (
                    f"In {year}, Imus recorded approximately {total} offense counts "
                    f"across daily tallies in the RideSafe dataset "
                    f"({'partial year through mid-November' if year == 2024 else 'full year coverage'})."
                ),
            }
        )
    return docs


def _clear_corpus(session):
    session.query(RagChunk).delete()
    session.query(RagDocument).delete()
    session.commit()


def build_rag_corpus(force: bool = False) -> bool:
    """Build and embed RAG corpus. Returns True if built, False if skipped."""
    init_db()
    if not is_postgres():
        logger.warning("Skipping RAG corpus: PostgreSQL with pgvector is required.")
        return False

    if not os.environ.get("GOOGLE_API_KEY", "").strip():
        logger.warning(
            "Skipping RAG corpus: GOOGLE_API_KEY is not set. "
            "Dashboard will still run; chat will be unavailable until the corpus is built."
        )
        return False

    session = get_session()
    try:
        existing = rag_chunk_count(session)
        if existing > 0 and not force:
            logger.info("RAG corpus already has %s chunks; skipping.", existing)
            return False

        if force and existing > 0:
            logger.info("Force rebuild: clearing existing RAG corpus.")
            _clear_corpus(session)

        model = AccidentModel()
        model.load_model()
        model.precompute_city_hour_averages()

        documents: list[dict] = []
        documents.extend(FAQ_DOCS)
        documents.append(_city_offense_doc())
        documents.append(_city_barangay_doc())
        documents.extend(_city_year_docs())

        for barangay in model.barangays:
            try:
                report = generate_summary_report(str(barangay), model, selected_hour=None)
                documents.append(
                    {
                        "title": f"Barangay insight: {report['barangay_name']}",
                        "source_type": "barangay",
                        "barangay": report["barangay_name"],
                        "body_text": _barangay_insight_text(report),
                    }
                )
            except Exception as exc:
                logger.warning("Skipping barangay %s: %s", barangay, exc)

        logger.info("Embedding %s documents...", len(documents))
        total_chunks = 0
        for doc in documents:
            pieces = chunk_text(doc["body_text"])
            if not pieces:
                continue
            rag_doc = RagDocument(
                title=doc["title"],
                source_type=doc["source_type"],
                barangay=doc.get("barangay"),
                body_text=doc["body_text"],
            )
            session.add(rag_doc)
            session.flush()
            vectors = embed_texts(pieces)
            for piece, vector in zip(pieces, vectors):
                session.add(
                    RagChunk(
                        document_id=rag_doc.id,
                        chunk_text=piece,
                        embedding=vector,
                    )
                )
                total_chunks += 1
            session.commit()

        logger.info(
            "RAG corpus ready: %s documents, %s chunks.", len(documents), total_chunks
        )
        return True
    except RagUnavailable as exc:
        session.rollback()
        logger.warning("RAG corpus skipped: %s", exc)
        return False
    except Exception:
        session.rollback()
        logger.exception("Failed to build RAG corpus")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    force = "--force" in sys.argv
    build_rag_corpus(force=force)
