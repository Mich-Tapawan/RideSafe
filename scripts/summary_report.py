import base64
import io
from datetime import datetime

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from scripts.repository import get_incidents_df

QUARTER_LABELS = ["Jan-Mar", "Apr-Jun", "Jul-Sep", "Oct-Dec"]


def risk_label(percent):
    if percent < 40:
        return "Low"
    if percent <= 55:
        return "Moderate"
    return "High"


def _quarter_stats(df_barangay):
    if df_barangay.empty:
        return {}, None, None

    working = df_barangay.copy()
    working["quarter"] = working["month"].apply(
        lambda m: QUARTER_LABELS[(m - 1) // 3] if m else None
    )
    quarter_counts = working.groupby("quarter", observed=False).size().reindex(
        QUARTER_LABELS, fill_value=0
    )
    total = int(quarter_counts.sum())
    quarter_breakdown = [
        {
            "label": label,
            "count": int(quarter_counts[label]),
            "percent": round(100 * quarter_counts[label] / total, 1) if total else 0,
        }
        for label in QUARTER_LABELS
    ]
    peak_quarter = quarter_counts.idxmax()
    lowest_quarter = quarter_counts.idxmin()
    return quarter_breakdown, peak_quarter, lowest_quarter


def _year_stats(df_barangay):
    if df_barangay.empty:
        return []
    counts = df_barangay.groupby("year").size()
    return [
        {"year": int(year), "count": int(count)}
        for year, count in sorted(counts.items())
    ]


def _top_hours(predictions, n=3, highest=True):
    ordered = sorted(predictions.items(), key=lambda item: item[1], reverse=highest)
    return [{"hour": hour, "percent": pct} for hour, pct in ordered[:n]]


def _city_avg_at_hour(accident_model, hour):
    if accident_model.city_hour_averages:
        return accident_model.city_hour_averages.get(hour, 0)
    values = [
        accident_model._predict_probability_value(barangay, hour)
        for barangay in accident_model.barangays
    ]
    return round(sum(values) / len(values), 2) if values else 0


def _build_chart(predictions, peak_hour, lowest_hour, selected_hour):
    hours = [f"{h}:00" for h in range(24)]
    values = [predictions[str(h).zfill(2)] for h in range(24)]

    fig, ax = plt.subplots(figsize=(10, 3.2), dpi=120)
    colors = ["#3347E6"] * 24
    if lowest_hour in predictions:
        colors[int(lowest_hour)] = "#00DBF9"
    if peak_hour in predictions:
        colors[int(peak_hour)] = "#9351E4"
    if selected_hour is not None and selected_hour in predictions:
        colors[int(selected_hour)] = "#E67E22"

    ax.bar(hours, values, color=colors, width=0.72)
    ax.set_ylabel("Probability (%)")
    ax.set_xlabel("Hour of day")
    ax.set_title("Hourly accident probability (ML model)")
    ax.set_ylim(0, max(values) * 1.15 if values else 100)
    ax.tick_params(axis="x", rotation=45, labelsize=7)
    ax.grid(axis="y", linestyle="--", alpha=0.35)
    fig.tight_layout()

    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode("ascii")


def generate_summary_report(barangay, accident_model, selected_hour=None):
    barangay = barangay.strip().upper()
    if barangay not in accident_model.barangays:
        raise ValueError(f"Invalid barangay: {barangay}")

    if selected_hour is not None:
        selected_hour = int(selected_hour)
        if selected_hour < 0 or selected_hour > 23:
            raise ValueError("Hour must be between 0 and 23")

    df = get_incidents_df()
    df_barangay = df[df["barangay"] == barangay]
    total_incidents = len(df_barangay)
    city_total = len(df)
    share_percent = round(100 * total_incidents / city_total, 2) if city_total else 0

    quarter_breakdown, peak_quarter, lowest_quarter = _quarter_stats(df_barangay)
    year_breakdown = _year_stats(df_barangay)

    predictions = accident_model.predict_all_hours(barangay)
    peak_hour = max(predictions, key=predictions.get)
    lowest_hour = min(predictions, key=predictions.get)
    peak_percent = predictions[peak_hour]
    lowest_percent = predictions[lowest_hour]

    selected_hour_key = None
    selected_percent = None
    selected_risk = None
    city_avg_selected = None
    if selected_hour is not None:
        selected_hour_key = str(selected_hour).zfill(2)
        selected_percent = predictions[selected_hour_key]
        selected_risk = risk_label(selected_percent)
        city_avg_selected = _city_avg_at_hour(accident_model, selected_hour)

    hourly_rows = [
        {
            "hour": hour,
            "percent": pct,
            "risk": risk_label(pct),
            "is_peak": hour == peak_hour,
            "is_lowest": hour == lowest_hour,
            "is_selected": hour == selected_hour_key,
        }
        for hour, pct in sorted(predictions.items())
    ]

    recommendations = []
    recommendations.append(
        f"Peak predicted risk is at {peak_hour}:00 ({peak_percent}%, {risk_label(peak_percent)})."
    )
    recommendations.append(
        f"Lowest predicted risk is at {lowest_hour}:00 ({lowest_percent}%)."
    )
    if peak_quarter:
        recommendations.append(
            f"Historically, most incidents in this barangay occurred in {peak_quarter} ({next(q['percent'] for q in quarter_breakdown if q['label'] == peak_quarter)}% of local records)."
        )
    if selected_hour is not None and selected_percent is not None:
        diff = round(selected_percent - city_avg_selected, 2)
        direction = "above" if diff > 0 else "below"
        recommendations.append(
            f"Your selected time ({selected_hour_key}:00) is {abs(diff)}% {direction} the city average at that hour ({city_avg_selected}%)."
        )

    return {
        "barangay_name": barangay,
        "generated_at": datetime.now().strftime("%B %d, %Y at %I:%M %p"),
        "data_range": "January 2022 – November 18, 2024",
        "total_incidents": total_incidents,
        "city_total": city_total,
        "share_percent": share_percent,
        "peak_hour": peak_hour,
        "lowest_hour": lowest_hour,
        "peak_quarter": peak_quarter or "N/A",
        "lowest_quarter": lowest_quarter or "N/A",
        "peak_percent": peak_percent,
        "lowest_percent": lowest_percent,
        "peak_risk": risk_label(peak_percent),
        "lowest_risk": risk_label(lowest_percent),
        "selected_hour": selected_hour_key,
        "selected_percent": selected_percent,
        "selected_risk": selected_risk,
        "city_avg_selected": city_avg_selected,
        "predictions": predictions,
        "hourly_rows": hourly_rows,
        "top_hours": _top_hours(predictions, 3, highest=True),
        "bottom_hours": _top_hours(predictions, 3, highest=False),
        "quarter_breakdown": quarter_breakdown,
        "year_breakdown": year_breakdown,
        "recommendations": recommendations,
        "chart_base64": _build_chart(predictions, peak_hour, lowest_hour, selected_hour_key),
    }
