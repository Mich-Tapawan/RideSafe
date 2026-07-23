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
    get_month_totals,
    get_offense_stats_df,
)
from scripts.summary_report import generate_summary_report, risk_label

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
        "title": "Incident count vs predicted risk",
        "source_type": "faq",
        "barangay": None,
        "body_text": (
            "Incident count is how many historical traffic incidents were recorded for a barangay "
            "in the 2022–2024 dataset. Predicted risk percentage is the ML model's estimated relative "
            "chance of an accident for a barangay at a specific hour. Highest-incident barangays are "
            "not always the same as highest peak predicted risk barangays. Lowest-incident or safest "
            "barangays by count may still have elevated predicted risk at certain hours. When users ask "
            "about most accidents, highest volume, or hotspots by history, use incident rankings. "
            "When they ask about highest or lowest risk, safest hours, or model probability, use "
            "predicted peak-risk rankings."
        ),
    },
    {
        "title": "Peak hours citywide",
        "source_type": "faq",
        "barangay": None,
        "body_text": (
            "The model treats morning (7–9) and evening (17–19) as peak-hour windows when estimating risk. "
            "Actual peak predicted hours vary by barangay; use Ask RideSafe or a barangay prediction "
            "to see local peak and lowest risk hours. Citywide average predicted risk by hour is also "
            "available in the city hour-risk insight document."
        ),
    },
]


def _format_ranked_lines(rows: list[tuple[str, str]]) -> str:
    return "\n".join(f"{i}. {label} — {detail}" for i, (label, detail) in enumerate(rows, start=1))


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
            part = df[df["year"] == year].sort_values(
                "Count of offense", ascending=False
            )
            top = part.head(10)
            top_desc = "; ".join(
                f"{row['Offense Type']}: {int(row['Count of offense'])}"
                for _, row in top.iterrows()
            )
            bottom = part.tail(5).sort_values("Count of offense", ascending=True)
            bottom_desc = "; ".join(
                f"{row['Offense Type']}: {int(row['Count of offense'])}"
                for _, row in bottom.iterrows()
            )
            lines.append(
                f"Year {int(year)} top offenses (highest counts) — {top_desc}. "
                f"Year {int(year)} lowest-count offenses among recorded types — {bottom_desc}."
            )
        body = (
            "City-wide offense type statistics for Imus traffic incidents (highest and lowest counts). "
            + " ".join(lines)
        )
    return {
        "title": "City offense trends 2022–2024",
        "source_type": "city",
        "barangay": None,
        "body_text": body,
    }


def _incident_rank_docs() -> list[dict]:
    df = get_barangay_stats_df()
    if df.empty:
        return [
            {
                "title": "Highest-incident barangays",
                "source_type": "city",
                "barangay": None,
                "body_text": "No barangay statistics available.",
            }
        ]

    ranked = df.sort_values("Count of barangay", ascending=False)
    top = ranked.head(15)
    bottom = ranked.sort_values("Count of barangay", ascending=True).head(15)

    top_rows = [
        (
            str(row["Barangay Name"]),
            f"{int(row['Count of barangay'])} aggregated incidents",
        )
        for _, row in top.iterrows()
    ]
    bottom_rows = [
        (
            str(row["Barangay Name"]),
            f"{int(row['Count of barangay'])} aggregated incidents",
        )
        for _, row in bottom.iterrows()
    ]

    return [
        {
            "title": "Highest-incident barangays",
            "source_type": "city",
            "barangay": None,
            "body_text": (
                "Barangays with the highest aggregated historical incident counts across 2022–2024 "
                "(most accidents / hotspots by recorded volume). Synonyms: highest, most incidents, "
                "most accidents, dangerous by history, top hotspots.\n"
                + _format_ranked_lines(top_rows)
            ),
        },
        {
            "title": "Lowest-incident barangays",
            "source_type": "city",
            "barangay": None,
            "body_text": (
                "Barangays with the lowest aggregated historical incident counts across 2022–2024 "
                "(fewest accidents / safest by recorded volume). Synonyms: lowest, least accidents, "
                "fewest incidents, safest by history, minimal incident count.\n"
                + _format_ranked_lines(bottom_rows)
            ),
        },
    ]


def _peak_risk_rank_docs(model: AccidentModel) -> list[dict]:
    """Citywide rankings by each barangay's peak and lowest predicted risk hour."""
    rows = []
    for barangay in model.barangays:
        name = str(barangay)
        try:
            preds = model.predict_all_hours(name)
        except Exception as exc:
            logger.warning("Skipping peak-risk rank for %s: %s", name, exc)
            continue
        if not preds:
            continue
        peak_hour = max(preds, key=preds.get)
        lowest_hour = min(preds, key=preds.get)
        rows.append(
            {
                "barangay": name,
                "peak_hour": peak_hour,
                "peak_percent": float(preds[peak_hour]),
                "lowest_hour": lowest_hour,
                "lowest_percent": float(preds[lowest_hour]),
            }
        )

    if not rows:
        return []

    by_peak_high = sorted(rows, key=lambda r: r["peak_percent"], reverse=True)[:15]
    by_peak_low = sorted(rows, key=lambda r: r["peak_percent"])[:15]
    by_lowest_hour = sorted(rows, key=lambda r: r["lowest_percent"])[:15]

    high_lines = _format_ranked_lines(
        [
            (
                r["barangay"],
                f"peak predicted risk {r['peak_percent']}% ({risk_label(r['peak_percent'])}) "
                f"at {r['peak_hour']}:00",
            )
            for r in by_peak_high
        ]
    )
    low_peak_lines = _format_ranked_lines(
        [
            (
                r["barangay"],
                f"peak predicted risk only {r['peak_percent']}% ({risk_label(r['peak_percent'])}) "
                f"at {r['peak_hour']}:00 — among the safest by model peak risk",
            )
            for r in by_peak_low
        ]
    )
    calm_hour_lines = _format_ranked_lines(
        [
            (
                r["barangay"],
                f"lowest predicted hour risk {r['lowest_percent']}% "
                f"({risk_label(r['lowest_percent'])}) at {r['lowest_hour']}:00",
            )
            for r in by_lowest_hour
        ]
    )

    return [
        {
            "title": "Highest peak predicted risk barangays",
            "source_type": "city",
            "barangay": None,
            "body_text": (
                "Barangays ranked by highest peak predicted accident risk percentage from the "
                "Random Forest model (most dangerous by model probability at their worst hour). "
                "Synonyms: highest risk, most dangerous, elevated probability, high peak risk.\n"
                + high_lines
            ),
        },
        {
            "title": "Lowest peak predicted risk barangays",
            "source_type": "city",
            "barangay": None,
            "body_text": (
                "Barangays ranked by lowest peak predicted accident risk percentage from the "
                "Random Forest model (safest overall by model — their worst hour is still relatively low). "
                "Synonyms: lowest risk, safest barangays, least dangerous, minimal peak risk, "
                "safest by prediction.\n"
                + low_peak_lines
            ),
        },
        {
            "title": "Lowest predicted hour risk by barangay",
            "source_type": "city",
            "barangay": None,
            "body_text": (
                "Barangays ranked by their calmest hour (lowest predicted risk percentage at any hour). "
                "Useful for questions about safest hours or lowest risk times across the city.\n"
                + calm_hour_lines
            ),
        },
    ]


def _city_hour_risk_doc(model: AccidentModel) -> dict:
    averages = model.city_hour_averages or {}
    if not averages:
        body = "Citywide average predicted risk by hour is not available."
    else:
        ordered = sorted(averages.items(), key=lambda item: item[1], reverse=True)
        peak_hours = ordered[:5]
        calm_hours = sorted(averages.items(), key=lambda item: item[1])[:5]
        peak_desc = "; ".join(f"{h}:00 → {pct}%" for h, pct in peak_hours)
        calm_desc = "; ".join(f"{h}:00 → {pct}%" for h, pct in calm_hours)
        body = (
            "Citywide average predicted accident risk by hour of day (mean across barangays). "
            f"Highest average risk hours: {peak_desc}. "
            f"Lowest average risk hours: {calm_desc}."
        )
    return {
        "title": "Citywide average risk by hour",
        "source_type": "city",
        "barangay": None,
        "body_text": body,
    }


def _city_month_docs() -> list[dict]:
    month_names = (
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    )
    docs = []
    for year in (2022, 2023, 2024):
        data = get_month_totals(year)
        monthly = data.get("monthly_totals") or {}
        if not monthly:
            continue
        ranked = sorted(monthly.items(), key=lambda item: item[1], reverse=True)
        top = ranked[:3]
        bottom = sorted(monthly.items(), key=lambda item: item[1])[:3]
        top_desc = "; ".join(
            f"{month_names[m - 1]}: {total}" for m, total in top if 1 <= m <= 12
        )
        bottom_desc = "; ".join(
            f"{month_names[m - 1]}: {total}" for m, total in bottom if 1 <= m <= 12
        )
        docs.append(
            {
                "title": f"Monthly offense highlights {year}",
                "source_type": "city",
                "barangay": None,
                "body_text": (
                    f"In {year}, monthly offense totals (highest months: {top_desc}; "
                    f"lowest months: {bottom_desc}). Yearly total approximately "
                    f"{data.get('yearly_total', 0)}."
                ),
            }
        )
    return docs


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
        documents.extend(_incident_rank_docs())
        documents.extend(_peak_risk_rank_docs(model))
        documents.append(_city_hour_risk_doc(model))
        documents.extend(_city_year_docs())
        documents.extend(_city_month_docs())

        for barangay in model.barangays:
            try:
                report = generate_summary_report(
                    str(barangay), model, selected_hour=None
                )
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
            pieces = chunk_text(doc["body_text"], size=900, overlap=100)
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
    try:
        build_rag_corpus(force=force)
    except Exception:
        # Keep Docker/Render bootable; chat returns 503 until corpus succeeds.
        logger.exception(
            "RAG corpus build failed; starting without chat until rebuild succeeds."
        )
        sys.exit(0)
