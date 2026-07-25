import os
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from utils.data_loader import query_data

st.set_page_config(
    page_title="Home — AI Military Intelligence",
    page_icon=":material/dashboard:",
    layout="wide"
)

# Load CSS
def load_css(file_name):
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

load_css("assets/style.css")

# Title & Subtitle
st.markdown("<h1>🛡️ Global Tactical Intelligence Overview</h1>", unsafe_allow_html=True)
st.markdown("##### Spatial-temporal threat analytics · Predictive hotspot scoring · AI situation reporting")

st.markdown('<div style="margin-top:0.75rem"></div>', unsafe_allow_html=True)

# -----------------------------------------------
# Load KPI Metrics via DuckDB
# -----------------------------------------------
kpi = query_data("""
    SELECT
        COUNT(*) as incidents,
        SUM(nkill) as fatalities,
        SUM(nwound) as injuries,
        COUNT(DISTINCT country_txt) as countries,
        MAX(iyear) as latest_year,
        MIN(iyear) as earliest_year
    FROM 'data/globalterrorism.csv'
""").iloc[0]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Incidents", f"{int(kpi['incidents']):,}")
c2.metric("Total Fatalities", f"{int(kpi['fatalities'] or 0):,}")
c3.metric("Total Injuries", f"{int(kpi['injuries'] or 0):,}")
c4.metric("Countries Affected", f"{int(kpi['countries']):,}")

# Second KPI row — platform-level
peak = query_data("""
    SELECT iyear, COUNT(*) as cnt
    FROM 'data/globalterrorism.csv'
    GROUP BY iyear ORDER BY cnt DESC LIMIT 1
""").iloc[0]
top_region = query_data("""
    SELECT region_txt, COUNT(*) as cnt
    FROM 'data/globalterrorism.csv'
    GROUP BY region_txt ORDER BY cnt DESC LIMIT 1
""").iloc[0]

c5, c6, c7, c8 = st.columns(4)
c5.metric("GTD Coverage", f"{int(kpi['earliest_year'])}–{int(kpi['latest_year'])}")
c6.metric("Peak Year", f"{int(peak['iyear'])} ({int(peak['cnt']):,} attacks)")
c7.metric("Most Affected Region", str(top_region['region_txt']))
c8.metric("Avg Fatalities/Incident", f"{(kpi['fatalities'] or 0) / max(kpi['incidents'], 1):.1f}")

# Data provenance banner
from datetime import date as _date
st.info(
    f"📂 **Data sources:** "
    f"Historical baseline: **Global Terrorism Database (GTD)** — "
    f"**{int(kpi['earliest_year'])}–{int(kpi['latest_year'])}** "
    f"({int(kpi['incidents']):,} verified incidents, {int(kpi['countries']):,} countries).  "
    f"Live extension: **GDELT public news feed** — present to **{_date.today().strftime('%d %b %Y')}**. "
    f"KPIs above reflect GTD historical data only."
)


# -----------------------------------------------
# Chart 1: Incident Velocity Over Time
# -----------------------------------------------
yearly = query_data("""
    SELECT iyear, COUNT(*) as Attacks
    FROM 'data/globalterrorism.csv'
    GROUP BY iyear
    ORDER BY iyear
""")

fig = go.Figure()
fig.add_trace(go.Scatter(
    x=yearly["iyear"],
    y=yearly["Attacks"],
    mode="lines+markers",
    name="Attacks",
    fill="tozeroy",
    line=dict(color="#00E5FF", width=3),
    marker=dict(size=5, color="#007BFF"),
    fillcolor="rgba(0,229,255,0.12)"
))

fig.update_layout(
    title="Global Incident Frequency Over Time",
    xaxis_title="Year",
    yaxis_title="Incident Count",
    template="plotly_dark",
    height=400,
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Outfit, sans-serif", color="#CBD5E1"),
    margin=dict(l=20, r=20, t=50, b=20),
    xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)"),
    yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)")
)

st.plotly_chart(fig, width="stretch")

st.markdown('<div style="margin-top:1.5rem"></div>', unsafe_allow_html=True)

# -----------------------------------------------
# Chart 2: Regional Distribution & Attack Type Mix
# -----------------------------------------------
col_left, col_right = st.columns(2)

with col_left:
    top_regions = query_data("""
        SELECT region_txt as Region, COUNT(*) as Incidents
        FROM 'data/globalterrorism.csv'
        GROUP BY region_txt
        ORDER BY Incidents DESC
        LIMIT 10
    """)
    fig2 = px.bar(
        top_regions, x="Incidents", y="Region", orientation="h",
        title="Top Regional Concentrations",
        color="Incidents",
        color_continuous_scale=["#007BFF", "#00E5FF"],
        template="plotly_dark"
    )
    fig2.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Outfit, sans-serif", color="#CBD5E1"),
        margin=dict(l=10, r=10, t=50, b=10),
        coloraxis_showscale=False
    )
    st.plotly_chart(fig2, width="stretch")

with col_right:
    attack_types = query_data("""
        SELECT attacktype1_txt as AttackType, COUNT(*) as Count
        FROM 'data/globalterrorism.csv'
        WHERE attacktype1_txt IS NOT NULL
        GROUP BY attacktype1_txt
        ORDER BY Count DESC
        LIMIT 7
    """)
    fig3 = px.pie(
        attack_types, names="AttackType", values="Count",
        title="Incident Tactics Breakdown",
        template="plotly_dark",
        hole=0.45,
        color_discrete_sequence=["#00E5FF", "#007BFF", "#7000FF", "#FF007A", "#FF6B35", "#FFD60A", "#34C759"]
    )
    fig3.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Outfit, sans-serif", color="#CBD5E1"),
        margin=dict(l=10, r=10, t=50, b=10)
    )
    st.plotly_chart(fig3, width="stretch")

st.markdown('<div style="margin-top:1rem"></div>', unsafe_allow_html=True)
st.caption("💡 Select any module from the left sidebar to dive into specific threat analysis.")
