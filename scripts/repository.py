import pandas as pd
from sqlalchemy import func

from scripts.db import (
    BarangayStat,
    DailyOffenseCount,
    Incident,
    OffenseStat,
    get_session,
)


def get_offense_stats_df(session=None):
    session = session or get_session()
    rows = session.query(OffenseStat).all()
    if not rows:
        return pd.DataFrame(columns=["year", "Offense Type", "Count of offense"])
    return pd.DataFrame(
        [
            {"year": r.year, "Offense Type": r.offense_type, "Count of offense": r.count}
            for r in rows
        ]
    )


def get_barangay_stats_df(session=None):
    session = session or get_session()
    rows = (
        session.query(
            BarangayStat.barangay_name,
            func.sum(BarangayStat.count).label("Count of barangay"),
        )
        .group_by(BarangayStat.barangay_name)
        .all()
    )
    if not rows:
        return pd.DataFrame(columns=["Barangay Name", "Count of barangay"])
    return pd.DataFrame(
        [
            {
                "Barangay Name": r.barangay_name.strip().title(),
                "Count of barangay": int(r[1]),
            }
            for r in rows
        ]
    )


def get_barangay_names(session=None):
    session = session or get_session()
    rows = (
        session.query(BarangayStat.barangay_name)
        .distinct()
        .order_by(BarangayStat.barangay_name)
        .all()
    )
    return [r[0] for r in rows]


def get_daily_offense_df(year, session=None):
    session = session or get_session()
    rows = (
        session.query(DailyOffenseCount)
        .filter(
            func.extract("year", DailyOffenseCount.offense_date) == year,
        )
        .all()
    )
    if not rows:
        return pd.DataFrame(columns=["Date", "Count of offense"])
    return pd.DataFrame(
        [
            {"Date": r.offense_date, "Count of offense": r.count}
            for r in rows
        ]
    )


def get_month_totals(year, session=None):
    session = session or get_session()
    rows = (
        session.query(
            func.extract("month", DailyOffenseCount.offense_date).label("month"),
            func.sum(DailyOffenseCount.count).label("total"),
        )
        .filter(func.extract("year", DailyOffenseCount.offense_date) == year)
        .group_by("month")
        .all()
    )
    monthly_totals = {int(r.month): int(r.total) for r in rows}
    yearly_total = sum(monthly_totals.values())
    return {"monthly_totals": monthly_totals, "yearly_total": yearly_total}


def get_incidents_df(session=None):
    session = session or get_session()
    rows = session.query(Incident).all()
    if not rows:
        return pd.DataFrame(
            columns=["dateCommitted", "timeCommitted", "barangay", "hour", "month", "year"]
        )
    records = []
    for r in rows:
        date_val = pd.Timestamp(r.date_committed) if r.date_committed else pd.NaT
        time_val = r.time_committed
        hour = time_val.hour if time_val else None
        records.append(
            {
                "dateCommitted": date_val,
                "timeCommitted": time_val,
                "barangay": r.barangay,
                "hour": hour,
                "month": date_val.month if pd.notna(date_val) else None,
                "year": date_val.year if pd.notna(date_val) else None,
            }
        )
    return pd.DataFrame(records).dropna(subset=["barangay"])
