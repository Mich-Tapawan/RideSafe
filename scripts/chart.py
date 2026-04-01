import pandas as pd
import plotly.graph_objects as go

def calculate_quarter_totals(quarter_ranges, df_filtered):
    """Divide and Conquer approach to calculate quarterly totals."""
    # Base case: only one quarter
    if len(quarter_ranges) == 1:
        start_month, end_month = quarter_ranges[0]
        quarter_data = df_filtered[
            (df_filtered['Date'].dt.month >= start_month) & 
            (df_filtered['Date'].dt.month <= end_month)
        ]
        return [quarter_data['Count of offense'].sum()]
    
    # Divide the quarters into two halves
    mid = len(quarter_ranges) // 2
    left_totals = calculate_quarter_totals(quarter_ranges[:mid], df_filtered)
    right_totals = calculate_quarter_totals(quarter_ranges[mid:], df_filtered)
    
    return left_totals + right_totals

def generate_chart(FILE_PATH, year):
    sheet_name = f'date com {year}'
    df = pd.read_excel(FILE_PATH, sheet_name=sheet_name, header=2)

    df = df.dropna(subset=['Date'])
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    df_filtered = df[df['Date'].dt.year == year]

    quarters = ["Jan-Mar", "Apr-Jun", "Jul-Sep", "Oct-Dec"]
    quarter_ranges = [(1, 3), (4, 6), (7, 9), (10, 12)]

    # Calculate the total offenses for each quarter using Divide and Conquer
    total_per_quarter = calculate_quarter_totals(quarter_ranges, df_filtered)

    total = sum(total_per_quarter)

    colors = ['#CCFF33', '#55A630', '#EBEB55', '#007F5F']

    fig = go.Figure()
    fig.add_trace(go.Pie(
        labels=quarters,
        values=total_per_quarter,
        hole=0.7,
        hoverinfo="label+value+percent",
        textinfo="label+percent",
        textfont=dict(size=14, color="white"),
        marker=dict(colors=colors),
        hovertemplate="<b>%{label}</b><br>Accidents: %{value}<br><extra></extra>"
    ))

    fig.update_layout(
        annotations=[
            dict(
                x=0.5, y=0.5, text=f"<b>{int(total)}</b><br>Total", 
                font=dict(size=20, color="white"),
                showarrow=False, align="center", 
                xref="paper", yref="paper"
            )
        ],
        paper_bgcolor="#00264d",
        plot_bgcolor="#00264d",
        autosize=True,
        height=280,
        margin=dict(l=24, r=24, t=24, b=24),
        showlegend=False
    )

    graph_html = fig.to_html(
        full_html=False,
        include_plotlyjs="cdn",
        config={"responsive": True},
    )
    return graph_html
