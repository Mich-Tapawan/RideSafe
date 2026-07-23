"""Allowlisted analytics / ML tools for RideSafe chat (no free-form SQL)."""

from __future__ import annotations

import logging
import re
from contextvars import ContextVar
from typing import Any, Optional

from sqlalchemy import func

from scripts.db import BarangayStat, OffenseStat, get_session
from scripts.repository import get_month_totals
from scripts.summary_report import risk_label

logger = logging.getLogger(__name__)

_tool_calls: ContextVar[list[dict]] = ContextVar("ridesafe_tool_calls", default=None)

_accident_model = None
MAX_LIMIT = 25


def begin_tool_trace() -> None:
    _tool_calls.set([])


def get_tool_trace() -> list[dict]:
    return list(_tool_calls.get() or [])


def _record(name: str, args: dict, summary: str) -> None:
    trace = _tool_calls.get()
    if trace is None:
        return
    trace.append({"name": name, "args": args, "summary": summary})


def _clamp_limit(limit: Any) -> int:
    try:
        value = int(limit)
    except (TypeError, ValueError):
        value = 10
    return max(1, min(value, MAX_LIMIT))


def _optional_year(year: Any) -> Optional[int]:
    if year is None or year == "":
        return None
    try:
        value = int(year)
    except (TypeError, ValueError):
        return None
    if value < 2022 or value > 2024:
        return None
    return value


def _normalize_order(order: Any) -> str:
    text = str(order or "highest").lower()
    return "lowest" if text.startswith("low") else "highest"


def _get_model():
    global _accident_model
    if _accident_model is None:
        from scripts.model import AccidentModel

        model = AccidentModel()
        model.load_model()
        model.precompute_city_hour_averages()
        _accident_model = model
    return _accident_model


def _barangay_list():
    model = _get_model()
    raw = model.barangays
    if raw is None:
        return []
    return [str(b) for b in list(raw)]


def _resolve_barangay(name: str) -> Optional[str]:
    needle = (name or "").strip().upper()
    if not needle:
        return None
    names = _barangay_list()
    for barangay in names:
        if barangay.strip().upper() == needle:
            return barangay
    matches = [b for b in names if needle in b.strip().upper()]
    if len(matches) == 1:
        return matches[0]
    return None


def rank_incident_barangays(
    order: str = "highest",
    limit: int = 10,
    year: Optional[int] = None,
) -> dict[str, Any]:
    """Rank barangays by historical incident counts from the live database."""
    limit = _clamp_limit(limit)
    year = _optional_year(year)
    order = _normalize_order(order)

    session = get_session()
    try:
        query = session.query(
            BarangayStat.barangay_name,
            func.sum(BarangayStat.count).label("total"),
        )
        if year is not None:
            query = query.filter(BarangayStat.year == year)
        rows = query.group_by(BarangayStat.barangay_name).all()
        ranked = [
            {"barangay": r.barangay_name, "incident_count": int(r.total)} for r in rows
        ]
        ranked.sort(
            key=lambda item: item["incident_count"],
            reverse=(order == "highest"),
        )
        ranked = ranked[:limit]
        scope = f"year {year}" if year else "2022–2024 aggregated"
        _record(
            "rank_incident_barangays",
            {"order": order, "limit": limit, "year": year},
            f"{order} {len(ranked)} barangays by incident count ({scope})",
        )
        return {
            "metric": "historical_incident_count",
            "order": order,
            "scope": scope,
            "results": ranked,
        }
    finally:
        session.close()


def get_offense_breakdown(
    year: int = 2024,
    order: str = "highest",
    limit: int = 10,
) -> dict[str, Any]:
    """Return offense-type counts for a year from the live database."""
    year = _optional_year(year)
    if year is None:
        return {"error": "year must be 2022, 2023, or 2024"}
    limit = _clamp_limit(limit)
    order = _normalize_order(order)

    session = get_session()
    try:
        rows = (
            session.query(OffenseStat)
            .filter(OffenseStat.year == year)
            .order_by(
                OffenseStat.count.asc()
                if order == "lowest"
                else OffenseStat.count.desc()
            )
            .limit(limit)
            .all()
        )
        results = [
            {"offense_type": r.offense_type, "count": int(r.count)} for r in rows
        ]
        _record(
            "get_offense_breakdown",
            {"year": year, "order": order, "limit": limit},
            f"{order} {len(results)} offense types for {year}",
        )
        return {"year": year, "order": order, "results": results}
    finally:
        session.close()


def get_monthly_totals(year: int = 2024) -> dict[str, Any]:
    """Return monthly offense totals and yearly total for 2022, 2023, or 2024."""
    year = _optional_year(year)
    if year is None:
        return {"error": "year must be 2022, 2023, or 2024"}
    data = get_month_totals(year)
    month_names = [
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
    ]
    monthly = [
        {"month": month_names[m - 1], "month_number": m, "total": total}
        for m, total in sorted((data.get("monthly_totals") or {}).items())
        if 1 <= m <= 12
    ]
    _record("get_monthly_totals", {"year": year}, f"monthly totals for {year}")
    return {
        "year": year,
        "yearly_total": data.get("yearly_total", 0),
        "monthly_totals": monthly,
    }


def get_barangay_incident_summary(
    barangay: str,
    year: Optional[int] = None,
) -> dict[str, Any]:
    """Return historical incident counts for one barangay from the live database."""
    resolved = _resolve_barangay(barangay)
    if not resolved:
        return {"error": f"Unknown barangay: {barangay}"}
    year = _optional_year(year)

    session = get_session()
    try:
        q = session.query(func.sum(BarangayStat.count)).filter(
            func.upper(BarangayStat.barangay_name) == resolved.upper()
        )
        city_q = session.query(func.sum(BarangayStat.count))
        by_year = None
        if year is not None:
            q = q.filter(BarangayStat.year == year)
            city_q = city_q.filter(BarangayStat.year == year)
        else:
            year_rows = (
                session.query(BarangayStat.year, func.sum(BarangayStat.count))
                .filter(func.upper(BarangayStat.barangay_name) == resolved.upper())
                .group_by(BarangayStat.year)
                .order_by(BarangayStat.year)
                .all()
            )
            by_year = [{"year": int(y), "count": int(c)} for y, c in year_rows]

        total = int(q.scalar() or 0)
        city_total = int(city_q.scalar() or 0)
        share = round(100 * total / city_total, 2) if city_total else 0.0
        scope = f"year {year}" if year else "2022–2024 aggregated"
        result = {
            "barangay": resolved,
            "scope": scope,
            "incident_count": total,
            "city_total": city_total,
            "share_percent": share,
        }
        if by_year is not None:
            result["by_year"] = by_year
        _record(
            "get_barangay_incident_summary",
            {"barangay": resolved, "year": year},
            f"{resolved} incidents ({scope})",
        )
        return result
    finally:
        session.close()


def predict_barangay_risk(barangay: str, hour: int) -> dict[str, Any]:
    """Predict relative accident risk percent for a barangay at hour 0–23."""
    resolved = _resolve_barangay(barangay)
    if not resolved:
        return {"error": f"Unknown barangay: {barangay}"}
    try:
        hour_int = int(hour)
    except (TypeError, ValueError):
        return {"error": "hour must be an integer 0–23"}
    if hour_int < 0 or hour_int > 23:
        return {"error": "hour must be between 0 and 23"}

    model = _get_model()
    percent = float(model._predict_probability_value(resolved, hour_int))
    _record(
        "predict_barangay_risk",
        {"barangay": resolved, "hour": hour_int},
        f"{resolved} at {hour_int}:00 → {percent}%",
    )
    return {
        "barangay": resolved,
        "hour": hour_int,
        "predicted_risk_percent": percent,
        "risk_label": risk_label(percent),
    }


def rank_peak_predicted_risk(
    order: str = "highest",
    limit: int = 10,
) -> dict[str, Any]:
    """Rank barangays by peak (worst-hour) predicted risk from the ML model."""
    limit = _clamp_limit(limit)
    order = _normalize_order(order)
    model = _get_model()
    rows = []
    for barangay in _barangay_list():
        name = str(barangay)
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
    rows.sort(
        key=lambda item: item["peak_predicted_risk_percent"],
        reverse=(order == "highest"),
    )
    rows = rows[:limit]
    _record(
        "rank_peak_predicted_risk",
        {"order": order, "limit": limit},
        f"{order} {len(rows)} barangays by peak predicted risk",
    )
    return {
        "metric": "peak_predicted_risk_percent",
        "order": order,
        "results": rows,
    }


TOOL_HANDLERS = {
    "rank_incident_barangays": rank_incident_barangays,
    "get_offense_breakdown": get_offense_breakdown,
    "get_monthly_totals": get_monthly_totals,
    "get_barangay_incident_summary": get_barangay_incident_summary,
    "predict_barangay_risk": predict_barangay_risk,
    "rank_peak_predicted_risk": rank_peak_predicted_risk,
}


def _extract_year(message: str) -> Optional[int]:
    match = re.search(r"\b(2022|2023|2024)\b", message)
    return int(match.group(1)) if match else None


def _extract_limit(message: str, default: int = 10) -> int:
    match = re.search(r"\btop\s+(\d{1,2})\b", message, re.I)
    if not match:
        match = re.search(r"\b(\d{1,2})\s+(barangays|areas|places)\b", message, re.I)
    if match:
        return _clamp_limit(match.group(1))
    return default


def _extract_hour(message: str) -> Optional[int]:
    match = re.search(r"\b([01]?\d|2[0-3])\s*:?\s*00\b", message)
    if match:
        return int(match.group(1))
    match = re.search(r"\bat\s+([01]?\d|2[0-3])\b", message, re.I)
    if match:
        return int(match.group(1))
    match = re.search(r"\bhour\s+([01]?\d|2[0-3])\b", message, re.I)
    if match:
        return int(match.group(1))
    return None


def _find_barangay_in_message(message: str) -> Optional[str]:
    upper = message.upper()
    names = sorted(_barangay_list(), key=len, reverse=True)
    for name in names:
        if name.upper() in upper:
            return name
    return None


def _wants_lowest(message: str) -> bool:
    lower = message.lower()
    return any(
        token in lower
        for token in (
            "lowest",
            "least",
            "fewest",
            "safest",
            "minimal",
            "bottom",
            "least dangerous",
        )
    )


def select_and_run_tools(message: str) -> list[dict[str, Any]]:
    """Deterministic allowlisted tool router (safe live queries, no free-form SQL)."""
    lower = message.lower()
    year = _extract_year(message)
    limit = _extract_limit(message, default=10)
    order = "lowest" if _wants_lowest(message) else "highest"
    results: list[dict[str, Any]] = []

    ranking_intent = any(
        token in lower
        for token in (
            "highest",
            "lowest",
            "most",
            "least",
            "fewest",
            "safest",
            "dangerous",
            "hotspot",
            "top ",
            "rank",
            "ranking",
            "which barangay",
            "what barangay",
        )
    )
    risk_intent = any(
        token in lower
        for token in ("risk", "predict", "probability", "chance", "ml ", "model")
    )
    offense_intent = any(
        token in lower
        for token in ("offense", "violation", "accident type", "incident type")
    )
    month_intent = any(
        token in lower for token in ("month", "monthly", "seasonal", "by month")
    )

    barangay = _find_barangay_in_message(message)
    hour = _extract_hour(message)

    if barangay and hour is not None:
        results.append(
            {
                "tool": "predict_barangay_risk",
                "data": predict_barangay_risk(barangay, hour),
            }
        )

    if barangay and not ranking_intent and (
        "how many" in lower
        or "incident" in lower
        or "summary" in lower
        or "share" in lower
        or hour is None
    ):
        results.append(
            {
                "tool": "get_barangay_incident_summary",
                "data": get_barangay_incident_summary(barangay, year),
            }
        )

    if ranking_intent and risk_intent:
        results.append(
            {
                "tool": "rank_peak_predicted_risk",
                "data": rank_peak_predicted_risk(order=order, limit=limit),
            }
        )
    elif ranking_intent:
        results.append(
            {
                "tool": "rank_incident_barangays",
                "data": rank_incident_barangays(
                    order=order, limit=limit, year=year
                ),
            }
        )

    if offense_intent:
        results.append(
            {
                "tool": "get_offense_breakdown",
                "data": get_offense_breakdown(
                    year=year or 2024, order=order, limit=limit
                ),
            }
        )

    if month_intent:
        results.append(
            {
                "tool": "get_monthly_totals",
                "data": get_monthly_totals(year=year or 2024),
            }
        )

    # If user named a barangay + asked about risk without hour, give peak/low from model
    if barangay and risk_intent and hour is None and not ranking_intent:
        preds = _get_model().predict_all_hours(barangay)
        peak_hour = max(preds, key=preds.get)
        low_hour = min(preds, key=preds.get)
        results.append(
            {
                "tool": "predict_barangay_risk",
                "data": {
                    "barangay": barangay,
                    "peak": predict_barangay_risk(barangay, int(peak_hour)),
                    "lowest": predict_barangay_risk(barangay, int(low_hour)),
                },
            }
        )

    return results


def format_tool_context(tool_results: list[dict[str, Any]]) -> str:
    if not tool_results:
        return ""
    import json

    blocks = []
    for item in tool_results:
        blocks.append(
            f"Tool `{item['tool']}` result:\n"
            + json.dumps(item["data"], indent=2, default=str)
        )
    return "\n\n".join(blocks)
