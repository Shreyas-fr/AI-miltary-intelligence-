import os
import streamlit as st

# --- Authentication & Role Check ---
from utils.auth import require_auth
require_auth(['Viewer', 'Analyst', 'Commander'])
# -----------------------------------

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils.data_loader import query_data
from utils.ui_components import st_custom_kpi_card

# -----------------------------------------------
# 1. Page Configuration
# -----------------------------------------------
st.set_page_config(
    page_title="Threat Timeline",
    page_icon="📅",
    layout="wide"
)

# -----------------------------------------------
# 2. Load Custom CSS
# -----------------------------------------------
def load_css(file_name: str):
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

load_css("assets/style.css")

# -----------------------------------------------
# 3. Header & Subtitle
# -----------------------------------------------
st.title("📅 | Threat Timeline")
st.markdown("##### Interactive temporal analysis of global threat events.")

# -----------------------------------------------
# 4. Sidebar Filters
# -----------------------------------------------
st.sidebar.header("Timeline Filters")

# Fetch available years dynamically from DuckDB
min_max_df = query_data(
    "SELECT MIN(iyear) as min_year, MAX(iyear) as max_year FROM 'data/globalterrorism.csv'"
)
min_year = int(min_max_df.iloc[0]["min_year"])
max_year = int(min_max_df.iloc[0]["max_year"])

# Year range slider
year_range = st.sidebar.slider(
    "Select Year Range",
    min_value=min_year,
    max_value=max_year,
    value=(min_year, max_year),
    step=1,
    help="Filter events within the specified time horizon."
)

# Fetch countries for multiselect
countries_df = query_data(
    "SELECT DISTINCT country_txt FROM 'data/globalterrorism.csv' WHERE country_txt IS NOT NULL ORDER BY country_txt"
)
countries_list = countries_df["country_txt"].tolist()

selected_countries = st.sidebar.multiselect(
    "Filter by Country",
    options=countries_list,
    default=[],
    help="Select one or more countries (leave empty for all)."
)

# Fetch attack types for multiselect
attack_types_df = query_data(
    "SELECT DISTINCT attacktype1_txt FROM 'data/globalterrorism.csv' WHERE attacktype1_txt IS NOT NULL ORDER BY attacktype1_txt"
)
attack_types_list = attack_types_df["attacktype1_txt"].tolist()

selected_attack_types = st.sidebar.multiselect(
    "Filter by Attack Type",
    options=attack_types_list,
    default=[],
    help="Select one or more attack types (leave empty for all)."
)

st.sidebar.markdown("---")
st.sidebar.caption("Use filters above to dynamically adjust temporal scope and event scope.")

# -----------------------------------------------
# 5. Query Data via DuckDB
# -----------------------------------------------
where_conditions = [f"iyear BETWEEN {year_range[0]} AND {year_range[1]}"]

if selected_countries:
    safe_countries = [c.replace("'", "''") for c in selected_countries]
    formatted_countries = ", ".join([f"'{c}'" for c in safe_countries])
    where_conditions.append(f"country_txt IN ({formatted_countries})")

if selected_attack_types:
    safe_attacks = [a.replace("'", "''") for a in selected_attack_types]
    formatted_attacks = ", ".join([f"'{a}'" for a in safe_attacks])
    where_conditions.append(f"attacktype1_txt IN ({formatted_attacks})")

where_clause = " AND ".join(where_conditions)

query_sql = f"""
    SELECT 
        iyear, 
        imonth, 
        iday, 
        country_txt, 
        region_txt, 
        city, 
        attacktype1_txt, 
        weaptype1_txt, 
        targtype1_txt, 
        gname, 
        nkill, 
        nwound, 
        success
    FROM 'data/globalterrorism.csv'
    WHERE {where_clause}
    ORDER BY iyear ASC, imonth ASC, iday ASC
"""

with st.spinner("Loading timeline events..."):
    df = query_data(query_sql)

# Clean numeric columns
df["nkill"] = df["nkill"].fillna(0).astype(int)
df["nwound"] = df["nwound"].fillna(0).astype(int)

# Check for empty data
if df.empty:
    st.warning("⚠️ No threat events match the selected filters. Please adjust your sidebar settings.")
    st.stop()

# -----------------------------------------------
# 6. KPI Metrics at Top
# -----------------------------------------------
total_incidents = len(df)
total_fatalities = int(df["nkill"].sum())
total_injured = int(df["nwound"].sum())

# Peak year calculation
year_counts = df["iyear"].value_counts()
peak_year = int(year_counts.idxmax())
peak_year_count = int(year_counts.max())

# Most affected country calculation
country_counts = df["country_txt"].value_counts()
top_country = country_counts.idxmax()
top_country_count = int(country_counts.max())

c1, c2, c3, c4 = st.columns(4)

with c1: st_custom_kpi_card("Total Incidents", f"{total_incidents:,}", f"{year_range[0]} - {year_range[1]}", "📉")
with c2: st_custom_kpi_card("Peak Threat Year", f"{peak_year}", f"{peak_year_count:,} incidents", "🔥")
with c3: st_custom_kpi_card("Most Affected Country", top_country, f"{top_country_count:,} incidents", "📍")
with c4: st_custom_kpi_card("Total Casualties", f"{(total_fatalities + total_injured):,}", f"{total_fatalities:,} k | {total_injured:,} i", "💀")

st.markdown("---")

# -----------------------------------------------
# 7. Timeline Scatter Plot Chart
# -----------------------------------------------
st.subheader("📍 Interactive Threat Event Timeline")

timeline_df = df.copy()

# Add severity classification column
def classify_severity(fatalities: int) -> str:
    if fatalities >= 20:
        return "Critical (>20 Fatalities)"
    elif fatalities >= 6:
        return "High (6-20 Fatalities)"
    elif fatalities >= 1:
        return "Medium (1-5 Fatalities)"
    else:
        return "Low (0 Fatalities)"

timeline_df["Severity"] = timeline_df["nkill"].apply(classify_severity)
timeline_df["Marker_Size"] = timeline_df["nkill"].clip(lower=0) + 6

# Color mapping matching theme (#00E5FF, #007BFF, #FF2D55, etc.)
color_palette = [
    "#00E5FF", "#007BFF", "#FF2D55", "#7000FF", 
    "#FFD60A", "#34C759", "#FF007A", "#FF6B35", "#A855F7"
]

fig_timeline = px.scatter(
    timeline_df,
    x="iyear",
    y="country_txt",
    color="attacktype1_txt",
    size="Marker_Size",
    size_max=28,
    hover_name="country_txt",
    hover_data={
        "iyear": True,
        "country_txt": True,
        "city": True,
        "attacktype1_txt": True,
        "gname": True,
        "nkill": True,
        "nwound": True,
        "Severity": True,
        "Marker_Size": False
    },
    labels={
        "iyear": "Year",
        "country_txt": "Country",
        "attacktype1_txt": "Attack Type",
        "nkill": "Fatalities",
        "nwound": "Injured",
        "gname": "Group",
        "city": "City"
    },
    title=f"Event Timeline Matrix ({year_range[0]} - {year_range[1]})",
    template="plotly_dark",
    color_discrete_sequence=color_palette
)

fig_timeline.update_layout(
    height=550,
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(10,14,23,0.7)",
    xaxis=dict(
        showgrid=True,
        gridcolor="rgba(255,255,255,0.08)",
        dtick=1,
        title="Year"
    ),
    yaxis=dict(
        showgrid=True,
        gridcolor="rgba(255,255,255,0.08)",
        title="Country"
    ),
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="right",
        x=1,
        title=None
    ),
    font=dict(family="Outfit, Inter, sans-serif")
)

with st.spinner("Rendering timeline scatter matrix..."):
    st.plotly_chart(fig_timeline, use_container_width=True)

# -----------------------------------------------
# 8. Yearly Trend Line Chart
# -----------------------------------------------
st.subheader("📈 Yearly Incident & Casualty Dynamics")

col_left, col_right = st.columns([2, 1])

yearly_summary = df.groupby("iyear").agg(
    Incidents=("iyear", "count"),
    Fatalities=("nkill", "sum"),
    Injured=("nwound", "sum")
).reset_index()

with col_left:
    fig_trend = go.Figure()

    fig_trend.add_trace(go.Scatter(
        x=yearly_summary["iyear"],
        y=yearly_summary["Incidents"],
        mode="lines+markers",
        name="Incidents",
        line=dict(color="#00E5FF", width=3),
        marker=dict(size=8, color="#00E5FF"),
        fill="tozeroy",
        fillcolor="rgba(0, 229, 255, 0.12)"
    ))

    fig_trend.add_trace(go.Scatter(
        x=yearly_summary["iyear"],
        y=yearly_summary["Fatalities"],
        mode="lines+markers",
        name="Fatalities",
        line=dict(color="#FF2D55", width=2, dash="dot"),
        marker=dict(size=6, color="#FF2D55")
    ))

    fig_trend.update_layout(
        title="<b>Incident Count & Fatalities Over Time</b>",
        template="plotly_dark",
        height=380,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(10,14,23,0.7)",
        xaxis=dict(title="Year", showgrid=True, gridcolor="rgba(255,255,255,0.08)", dtick=1),
        yaxis=dict(title="Count", showgrid=True, gridcolor="rgba(255,255,255,0.08)"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        font=dict(family="Outfit, Inter, sans-serif")
    )

    st.plotly_chart(fig_trend, use_container_width=True)

with col_right:
    attack_counts = df["attacktype1_txt"].value_counts().reset_index()
    attack_counts.columns = ["Attack Type", "Count"]

    fig_donut = px.pie(
        attack_counts,
        names="Attack Type",
        values="Count",
        title="<b>Attack Type Share</b>",
        template="plotly_dark",
        hole=0.45,
        color_discrete_sequence=color_palette
    )
    fig_donut.update_layout(
        height=380,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.02),
        font=dict(family="Outfit, Inter, sans-serif")
    )
    st.plotly_chart(fig_donut, use_container_width=True)

# -----------------------------------------------
# 9. Expandable Detail Section
# -----------------------------------------------
st.markdown("---")
with st.expander(f"🔍 Detailed Threat Event Records ({year_range[0]} - {year_range[1]})", expanded=False):
    st.markdown(f"Displaying **{len(df):,}** individual threat records for the selected filters.")
    
    # Optional sub-filter inside expander
    years_in_range = sorted(df["iyear"].unique().tolist())
    selected_detail_year = st.selectbox(
        "Focus on specific year (or select All):",
        options=["All Years"] + [str(y) for y in years_in_range]
    )

    if selected_detail_year == "All Years":
        detail_df = df.copy()
    else:
        detail_df = df[df["iyear"] == int(selected_detail_year)].copy()

    # Format table columns for display
    display_df = detail_df[[
        "iyear", "imonth", "iday", "country_txt", "city", 
        "attacktype1_txt", "targtype1_txt", "gname", "nkill", "nwound"
    ]].rename(columns={
        "iyear": "Year",
        "imonth": "Month",
        "iday": "Day",
        "country_txt": "Country",
        "city": "City",
        "attacktype1_txt": "Attack Type",
        "targtype1_txt": "Target Type",
        "gname": "Group Name",
        "nkill": "Fatalities",
        "nwound": "Injured"
    })

    st.dataframe(
        display_df,
        column_config={
            "Fatalities": st.column_config.NumberColumn("Fatalities", format="%d"),
            "Injured": st.column_config.NumberColumn("Injured", format="%d"),
        },
        height=350,
        use_container_width=True,
        hide_index=True
    )

    # Download CSV button
    csv_data = display_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Export Detailed Log CSV",
        data=csv_data,
        file_name=f"threat_timeline_{year_range[0]}_{year_range[1]}.csv",
        mime="text/csv"
    )
