"""City and barangay insight payloads for the dashboard (shared with RAG sources)."""

from __future__ import annotations

import logging
from typing import Any, Optional

from scripts.repository import get_month_totals
from scripts.summary_report import generate_summary_report, risk_label

logger = logging.getLogger(__name__)


def _yearly_totals() -> dict[int, int]:
    return {
        year: int(get_month_totals(year).get("yearly_total") or 0)
        for year in (2022, 2023, 2024)
    }


def _incident_rankings(limit: int = 5) -> tuple[list[dict], list[dict]]:
    from scripts.db import BarangayStat, get_session
    from sqlalchemy import func

    session = get_session()
    try:
        rows = (
            session.query(
                BarangayStat.barangay_name,
                func.sum(BarangayStat.count).label("total"),
            )
            .group_by(BarangayStat.barangay_name)
            .all()
        )
        ranked = [
            {"barangay": r.barangay_name, "incident_count": int(r.total)} for r in rows
        ]
        ranked.sort(key=lambda item: item["incident_count"], reverse=True)
        hottest = ranked[:limit]
        safest = list(reversed(ranked[-limit:])) if ranked else []
        safest.sort(key=lambda item: item["incident_count"])
        return hottest, safest
    finally:
        session.close()


def _peak_risk_rankings(model, limit: int = 5) -> tuple[list[dict], list[dict]]:
    raw = getattr(model, "barangays", None)
    if raw is None:
        barangays: list[str] = []
    else:
        try:
            barangays = [str(b) for b in list(raw)]
        except TypeError:
            barangays = []
    rows: list[dict[str, Any]] = []
    for name in barangays:
        try:
            preds = model.predict_all_hours(name)
        except Exception as exc:
            logger.warning("predict_all_hours failed for %s: %s", name, exc)
            continue
        if not preds:
            continue
        peak_hour = max(preds, key=preds.get)
        peak_percent = float(preds[peak_hour])
        rows.append(
            {
                "barangay": name,
                "peak_hour": int(peak_hour),
                "peak_predicted_risk_percent": peak_percent,
                "risk_label": risk_label(peak_percent),
            }
        )
    rows.sort(key=lambda item: item["peak_predicted_risk_percent"], reverse=True)
    highest = rows[:limit]
    lowest = sorted(rows, key=lambda item: item["peak_predicted_risk_percent"])[:limit]
    return highest, lowest


def build_city_insights(model) -> dict[str, Any]:
    """Aggregate KPIs, rankings, and city hour-risk series for the Overview."""
    yearly = _yearly_totals()
    total = sum(yearly.values())
    yoy_change_percent = None
    if yearly.get(2023):
        yoy_change_percent = round(
            100 * (yearly[2024] - yearly[2023]) / yearly[2023],
            1,
        )

    hotspots, safest = _incident_rankings(5)
    peak_high, peak_low = _peak_risk_rankings(model, 5)

    averages = getattr(model, "city_hour_averages", None) or {}
    hour_risk = [
        {
            "hour": hour,
            "avg_risk_percent": float(averages.get(hour, 0)),
        }
        for hour in range(24)
    ]
    peak_city = max(hour_risk, key=lambda row: row["avg_risk_percent"]) if hour_risk else None
    calm_city = min(hour_risk, key=lambda row: row["avg_risk_percent"]) if hour_risk else None

    from scripts.offense_guide import build_offense_guide

    return {
        "data_range": "January 2022 – November 18, 2024",
        "city_kpis": {
            "total_incidents": total,
            "yearly_totals": {
                "2022": yearly[2022],
                "2023": yearly[2023],
                "2024": yearly[2024],
            },
            "yoy_change_percent": yoy_change_percent,
            "peak_city_hour": peak_city,
            "calm_city_hour": calm_city,
        },
        "hotspots": hotspots,
        "safest_by_volume": safest,
        "highest_peak_risk": peak_high,
        "lowest_peak_risk": peak_low,
        "hour_risk": hour_risk,
        "offense_guide": build_offense_guide(),
    }


def barangay_insight_card(
    barangay: str,
    model,
    selected_hour: Optional[int] = None,
) -> dict[str, Any]:
    """Compact insight for Map & Predictions (no matplotlib chart)."""
    report = generate_summary_report(
        barangay,
        model,
        selected_hour=selected_hour,
        include_chart=False,
    )
    return {
        "barangay_name": report["barangay_name"],
        "total_incidents": report["total_incidents"],
        "city_total": report["city_total"],
        "share_percent": report["share_percent"],
        "peak_hour": report["peak_hour"],
        "lowest_hour": report["lowest_hour"],
        "peak_percent": report["peak_percent"],
        "lowest_percent": report["lowest_percent"],
        "peak_risk": report["peak_risk"],
        "lowest_risk": report["lowest_risk"],
        "peak_quarter": report["peak_quarter"],
        "lowest_quarter": report["lowest_quarter"],
        "selected_hour": report["selected_hour"],
        "selected_percent": report["selected_percent"],
        "selected_risk": report["selected_risk"],
        "city_avg_selected": report["city_avg_selected"],
        "recommendations": report["recommendations"][:4],
        "year_breakdown": report["year_breakdown"],
    }
