"""Offense-type glossary and live count insights for the Offense Analytics view."""

from __future__ import annotations

from typing import Any

from scripts.repository import get_offense_stats_df

# Keys use the same title-case normalization as bar_graph.py
OFFENSE_DEFINITIONS: dict[str, dict[str, str]] = {
    "Imprudence And Negligence (Reckless Imprudence) - Rpc Art. 365": {
        "short_label": "General reckless imprudence",
        "legal_basis": "Revised Penal Code Art. 365",
        "meaning": (
            "A catch-all reckless imprudence / negligence filing under Art. 365 when "
            "the record does not further classify the outcome as property damage, "
            "physical injury, or homicide."
        ),
        "insight": (
            "Often appears when the blotter uses a generic Art. 365 label. Compare "
            "volume against the more specific “resulting to …” categories to see how "
            "detailed coding is in each year."
        ),
    },
    "Reckless Imprudence Resulting To Damage To Property - Rpc Art 365": {
        "short_label": "Damage to property",
        "legal_basis": "Revised Penal Code Art. 365",
        "meaning": (
            "Reckless driving or negligence that damaged property (vehicles, roadside "
            "assets, structures) without a recorded physical injury or death in this "
            "offense label."
        ),
        "insight": (
            "Usually among the largest volume categories in traffic datasets—useful "
            "for spotting property-loss hotspots even when injuries are not coded."
        ),
    },
    "Reckless Imprudence Resulting To Multiple Damage To Property - Rpc Art 365": {
        "short_label": "Multiple property damage",
        "legal_basis": "Revised Penal Code Art. 365",
        "meaning": (
            "Reckless imprudence involving damage to more than one property interest "
            "or multiple damaged assets in the same incident coding."
        ),
        "insight": (
            "Signals more complex collisions (multi-vehicle / multi-asset). Spikes "
            "may align with congestion corridors or multi-party crash patterns."
        ),
    },
    "Reckless Imprudence Resulting To Physical Injury - Rpc Art 365": {
        "short_label": "Physical injury",
        "legal_basis": "Revised Penal Code Art. 365",
        "meaning": (
            "Reckless imprudence that resulted in physical injury to a person "
            "(non-fatal), as coded under Art. 365."
        ),
        "insight": (
            "A key severity indicator below homicide. Rising shares relative to "
            "property-only cases suggest more harmful crash outcomes."
        ),
    },
    "Reckless Imprudence Resulting To Multiple Physical Injury - Rpc Art 365": {
        "short_label": "Multiple physical injury",
        "legal_basis": "Revised Penal Code Art. 365",
        "meaning": (
            "Reckless imprudence resulting in physical injuries to more than one "
            "person in the coded incident."
        ),
        "insight": (
            "Often associated with multi-passenger or multi-party crashes. Monitor "
            "alongside peak-hour risk for enforcement and emergency planning."
        ),
    },
    "Reckless Imprudence Resulting To Homicide - Rpc Art 365": {
        "short_label": "Homicide",
        "legal_basis": "Revised Penal Code Art. 365",
        "meaning": (
            "Reckless imprudence resulting in the death of a person (homicide under "
            "the Art. 365 reckless-imprudence framework), as recorded in the dataset."
        ),
        "insight": (
            "Lowest volume but highest severity. Even small counts warrant attention "
            "in barangay and hour analyses for road-safety priority setting."
        ),
    },
    "Reckless Imprudence Resulting To Multiple Homicide - Rpc Art 365": {
        "short_label": "Multiple homicide",
        "legal_basis": "Revised Penal Code Art. 365",
        "meaning": (
            "Reckless imprudence resulting in more than one fatality in the coded "
            "incident under Art. 365."
        ),
        "insight": (
            "Rare but critical events. Pair with geospatial hotspots when these "
            "appear to identify high-consequence locations."
        ),
    },
}


def _normalize_offense_name(name: str) -> str:
    return str(name).strip().lower().title()


def offense_chart_mapping(offense_names: list[str]) -> dict[str, str]:
    """Stable Offense N labels shared by the bar chart and glossary."""
    unique = sorted({_normalize_offense_name(n) for n in offense_names if n})
    return {name: f"Offense {i + 1}" for i, name in enumerate(unique)}


def build_offense_guide() -> dict[str, Any]:
    """Chart labels (Offense N), definitions, and yearly counts for the UI."""
    df = get_offense_stats_df()
    if df.empty:
        return {
            "intro": "No offense statistics are available.",
            "legal_context": (
                "Most RideSafe offense labels refer to reckless imprudence under "
                "Revised Penal Code Article 365."
            ),
            "items": [],
        }

    working = df.copy()
    working["Offense Type"] = working["Offense Type"].map(_normalize_offense_name)

    mapping = offense_chart_mapping(working["Offense Type"].tolist())
    unique = list(mapping.keys())

    items: list[dict[str, Any]] = []
    for name in unique:
        part = working[working["Offense Type"] == name]
        by_year = {
            int(year): int(group["Count of offense"].sum())
            for year, group in part.groupby("year")
        }
        total = int(part["Count of offense"].sum())
        definition = OFFENSE_DEFINITIONS.get(name, {})
        items.append(
            {
                "chart_label": mapping[name],
                "offense_type": name,
                "short_label": definition.get("short_label", name),
                "legal_basis": definition.get(
                    "legal_basis", "Revised Penal Code Art. 365"
                ),
                "meaning": definition.get(
                    "meaning",
                    "Traffic-related reckless imprudence / negligence offense "
                    "recorded in the Imus incident dataset.",
                ),
                "insight": definition.get(
                    "insight",
                    "Compare yearly bars in the chart to see whether this category "
                    "is rising, falling, or stable.",
                ),
                "total_count": total,
                "by_year": {
                    "2022": by_year.get(2022, 0),
                    "2023": by_year.get(2023, 0),
                    "2024": by_year.get(2024, 0),
                },
            }
        )

    items.sort(key=lambda row: row["total_count"], reverse=True)
    top = items[0] if items else None

    return {
        "intro": (
            "Bars are labeled Offense 1, Offense 2, … for readability. Hover a bar "
            "or use the glossary below to see the full Revised Penal Code Art. 365 "
            "offense name, meaning, and RideSafe insight."
        ),
        "legal_context": (
            "Article 365 of the Revised Penal Code covers imprudence and negligence "
            "(including reckless imprudence). RideSafe groups Imus traffic incidents "
            "by the specific Art. 365 outcome coded in the source records—property "
            "damage, physical injury, homicide, or a general reckless-imprudence label."
        ),
        "top_offense": (
            {
                "chart_label": top["chart_label"],
                "short_label": top["short_label"],
                "total_count": top["total_count"],
            }
            if top
            else None
        ),
        "items": items,
    }
