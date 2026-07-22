"""Idempotent seed: traffic-incident.xlsx -> database."""

import os
import sys
from pathlib import Path

import pandas as pd

from scripts.db import (
    BarangayStat,
    DailyOffenseCount,
    Incident,
    OffenseStat,
    get_session,
    incident_count,
    init_db,
)

EXCEL_FILE_PATH = os.environ.get("EXCEL_FILE_PATH", "traffic-incident.xlsx")

INCIDENT_SHEETS = [
    "Jan 1 - Dec 31, 2022",
    "Jan 1 - Dec 31, 2023",
    "Jan 1 - Nov 18, 2024",
]

OFFENSE_YEARS = {2022: "OFFENSE 2022", 2023: "OFFENSE 2023", 2024: "OFFENSE 2024"}
BRGY_YEARS = {2022: "brgy 2022", 2023: "brgy 2023", 2024: "brgy 2024"}
DATE_COM_YEARS = {2022: "date com 2022", 2023: "date com 2023", 2024: "date com 2024"}


def _parse_time(value):
    if pd.isna(value):
        return None
    if hasattr(value, "hour"):
        return value.time() if hasattr(value, "time") else value
    parsed = pd.to_datetime(str(value), format="%H:%M:%S", errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.time()


def seed_incidents(session, file_path: str) -> int:
    count = 0
    for sheet in INCIDENT_SHEETS:
        df = pd.read_excel(file_path, sheet_name=sheet)
        for _, row in df.iterrows():
            barangay = row.get("barangay")
            if pd.isna(barangay):
                continue
            date_val = pd.to_datetime(row.get("dateCommitted"), errors="coerce")
            session.add(
                Incident(
                    date_committed=date_val.date() if pd.notna(date_val) else None,
                    time_committed=_parse_time(row.get("timeCommitted")),
                    barangay=str(barangay).strip().upper(),
                )
            )
            count += 1
    return count


def seed_offense_stats(session, file_path: str) -> int:
    count = 0
    for year, sheet in OFFENSE_YEARS.items():
        df = pd.read_excel(file_path, sheet_name=sheet, header=2)
        df = df[df["Offense Type"].str.lower() != "grand total"]
        for _, row in df.iterrows():
            offense = str(row["Offense Type"]).strip()
            if not offense:
                continue
            session.add(
                OffenseStat(
                    year=year,
                    offense_type=offense,
                    count=int(row["Count of offense"]),
                )
            )
            count += 1
    return count


def seed_barangay_stats(session, file_path: str) -> int:
    count = 0
    for year, sheet in BRGY_YEARS.items():
        df = pd.read_excel(file_path, sheet_name=sheet, header=2)
        df = df[df["Barangay Name"].str.lower() != "grand total"]
        for _, row in df.iterrows():
            name = str(row["Barangay Name"]).strip()
            if not name:
                continue
            session.add(
                BarangayStat(
                    year=year,
                    barangay_name=name,
                    count=int(row["Count of barangay"]),
                )
            )
            count += 1
    return count


def seed_daily_offense_counts(session, file_path: str) -> int:
    count = 0
    for year, sheet in DATE_COM_YEARS.items():
        df = pd.read_excel(file_path, sheet_name=sheet, header=2)
        df = df.dropna(subset=["Date"])
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df[df["Date"].dt.year == year]
        for _, row in df.iterrows():
            session.add(
                DailyOffenseCount(
                    offense_date=row["Date"].date(),
                    count=int(row["Count of offense"]),
                )
            )
            count += 1
    return count


def seed_database(file_path: str | None = None) -> bool:
    """Seed DB from xlsx. Returns True if seeding ran, False if skipped."""
    file_path = file_path or EXCEL_FILE_PATH
    if not Path(file_path).is_file():
        print(f"Seed skipped: {file_path} not found", file=sys.stderr)
        return False

    init_db()
    session = get_session()
    try:
        if incident_count(session) > 0:
            print("Database already seeded; skipping.")
            return False

        print(f"Seeding database from {file_path}...")
        n_incidents = seed_incidents(session, file_path)
        n_offense = seed_offense_stats(session, file_path)
        n_barangay = seed_barangay_stats(session, file_path)
        n_daily = seed_daily_offense_counts(session, file_path)
        session.commit()
        print(
            f"Seeded {n_incidents} incidents, {n_offense} offense stats, "
            f"{n_barangay} barangay stats, {n_daily} daily counts."
        )
        return True
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def force_reseed(file_path: str | None = None):
    """Clear all tables and re-seed (for manual data refresh)."""
    file_path = file_path or EXCEL_FILE_PATH
    init_db()
    session = get_session()
    try:
        session.query(DailyOffenseCount).delete()
        session.query(BarangayStat).delete()
        session.query(OffenseStat).delete()
        session.query(Incident).delete()
        session.commit()
    finally:
        session.close()
    seed_database(file_path)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--force":
        force_reseed()
    else:
        seed_database()
