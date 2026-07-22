import pandas as pd
import plotly.graph_objects as go

from scripts.repository import get_offense_stats_df


def generate_bar_graph():
    df_combined = get_offense_stats_df()

    if df_combined.empty:
        return "<p>No offense data available.</p>"

    df_combined["Offense Type"] = (
        df_combined["Offense Type"].str.strip().str.lower().str.title()
    )

    unique_offenses = df_combined["Offense Type"].unique()
    offense_mapping = {
        original: f"Offense {i + 1}" for i, original in enumerate(unique_offenses)
    }

    df_combined["Simplified Offense Type"] = df_combined["Offense Type"].map(offense_mapping)

    accidents_by_offense = (
        df_combined.groupby(["year", "Simplified Offense Type", "Offense Type"])
        .agg(accident_count=("Count of offense", "sum"))
        .reset_index()
    )

    years = [2022, 2023, 2024]
    colors = ["#CCFF33", "#34A0A4", "#38B000"]
    fig = go.Figure()

    for year, color in zip(years, colors):
        year_data = accidents_by_offense[accidents_by_offense["year"] == year]
        fig.add_trace(
            go.Bar(
                x=year_data["Simplified Offense Type"],
                y=year_data["accident_count"],
                name=str(year),
                marker_color=color,
                hovertext=year_data["Offense Type"],
                hoverinfo="text+y+name",
            )
        )

    fig.update_layout(
        xaxis=dict(
            title="Offense Type",
            title_font=dict(size=14),
            tickmode="array",
            tickvals=list(offense_mapping.values()),
            ticktext=list(offense_mapping.values()),
        ),
        yaxis=dict(title="Number of Accidents", title_font=dict(size=14)),
        barmode="group",
        plot_bgcolor="#0B2C40",
        paper_bgcolor="#001D3D",
        font=dict(color="white"),
        legend=dict(title="Years", font=dict(size=12)),
        height=600,
    )

    fig.update_traces(hovertemplate="%{hovertext}<br>Accidents: %{y}")

    return fig.to_html(full_html=False)
