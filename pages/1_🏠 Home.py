import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from utils.data_loader import query_data
import os

st.set_page_config(
    page_title="Home — AI Military Intelligence",
    page_icon="🏠",
    layout="wide"
)

# Inject custom CSS for premium UI
def load_css(file_name):
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
load_css("assets/style.css")

st.title("🛡️ AI Military Intelligence Dashboard")
st.markdown("##### Global Terrorism Intelligence Powered by Machine Learning & Generative AI")

st.divider()

# -----------------------------------------------
# Load KPI Metrics via DuckDB (fast, aggregated)
# -----------------------------------------------
kpi = query_data("""
    SELECT
        COUNT(*) as incidents,
        SUM(nkill) as fatalities,
        SUM(nwound) as injuries,
        COUNT(DISTINCT country_txt) as countries
    FROM 'data/globalterrorism.csv'
""").iloc[0]

c1, c2, c3, c4 = st.columns(4)
c1.metric("🔺 Total Incidents", f"{int(kpi['incidents']):,}")
c2.metric("💀 Total Fatalities", f"{int(kpi['fatalities'] or 0):,}")
c3.metric("🏥 Total Injuries", f"{int(kpi['injuries'] or 0):,}")
c4.metric("🌍 Countries Affected", f"{int(kpi['countries']):,}")

st.divider()

# -----------------------------------------------
# Chart 1: Attacks Over Years (area chart)
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
    mode="lines",
    name="Attacks",
    fill="tozeroy",
    line=dict(color="#00E5FF", width=2),
    fillcolor="rgba(0,229,255,0.08)"
))
fig.update_layout(
    title="Global Terrorist Attacks Over Time",
    xaxis_title="Year",
    yaxis_title="Number of Attacks",
    template="plotly_dark",
    height=380,
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=20, r=20, t=40, b=20)
)
st.plotly_chart(fig, width="stretch")

st.divider()

# -----------------------------------------------
# Chart 2: Top Regions + Top Attack Types side by side
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
        title="Incidents by Region",
        color="Incidents",
        color_continuous_scale="Blues",
        template="plotly_dark"
    )
    fig2.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=40, b=10)
    )
    st.plotly_chart(fig2, width="stretch")

with col_right:
    attack_types = query_data("""
        SELECT attacktype1_txt as AttackType, COUNT(*) as Count
        FROM 'data/globalterrorism.csv'
        WHERE attacktype1_txt IS NOT NULL
        GROUP BY attacktype1_txt
        ORDER BY Count DESC
    """)
    fig3 = px.pie(
        attack_types, names="AttackType", values="Count",
        title="Attack Type Breakdown",
        template="plotly_dark",
        hole=0.4,
        color_discrete_sequence=px.colors.sequential.Blues_r
    )
    fig3.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=40, b=10)
    )
    st.plotly_chart(fig3, width="stretch")

st.info("👈 Use the sidebar to navigate between intelligence modules.")