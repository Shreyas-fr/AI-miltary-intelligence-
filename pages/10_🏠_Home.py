import os
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from utils.data_loader import query_data
from utils.ui_components import st_custom_kpi_card
from datetime import date as _date

st.set_page_config(
    page_title="Home — AI Military Intelligence",
    page_icon="🏠",
    layout="wide"
)

def load_css(file_name):
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
load_css("assets/style.css")

st.title("🏠 | Global Tactical Intelligence Overview")
st.markdown("##### Spatial-temporal threat analytics, predictive hotspot scoring, and AI situation reporting.")

st.markdown('<div style="margin-top:0.75rem"></div>', unsafe_allow_html=True)

with st.spinner("Loading global metrics..."):
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

c1, c2, c3, c4 = st.columns(4)
with c1: st_custom_kpi_card("Total Incidents", f"{int(kpi['incidents']):,}", "Global recorded events", "📉")
with c2: st_custom_kpi_card("Total Fatalities", f"{int(kpi['fatalities'] or 0):,}", "Estimated deaths", "💀")
with c3: st_custom_kpi_card("Total Injuries", f"{int(kpi['injuries'] or 0):,}", "Estimated wounded", "🩹")
with c4: st_custom_kpi_card("Countries Affected", f"{int(kpi['countries']):,}", "Sovereign nations", "🌎")

c5, c6, c7, c8 = st.columns(4)
with c5: st_custom_kpi_card("GTD Coverage", f"{int(kpi['earliest_year'])}–{int(kpi['latest_year'])}", "Date range", "📅")
with c6: st_custom_kpi_card("Peak Year", f"{int(peak['iyear'])}", f"{int(peak['cnt']):,} attacks", "🔥")
with c7: st_custom_kpi_card("Most Affected Region", str(top_region['region_txt']), "Highest volume", "📍")
with c8: st_custom_kpi_card("Avg Fatalities/Incident", f"{(kpi['fatalities'] or 0) / max(kpi['incidents'], 1):.1f}", "Lethality ratio", "⚖️")

st.info(
    f"📂 **Data sources:** "
    f"Historical baseline: **Global Terrorism Database (GTD)** — "
    f"**{int(kpi['earliest_year'])}–{int(kpi['latest_year'])}** "
    f"({int(kpi['incidents']):,} verified incidents, {int(kpi['countries']):,} countries).  "
    f"Live extension: **GDELT public news feed** — present to **{_date.today().strftime('%d %b %Y')}**. "
    f"KPIs above reflect GTD historical data only."
)

with st.spinner("Rendering incident frequency..."):
    yearly = query_data("""
        SELECT iyear, COUNT(*) as Attacks
        FROM 'data/globalterrorism.csv'
        GROUP BY iyear
        ORDER BY iyear
    """)

if not yearly.empty:
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
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No yearly data found to render the frequency chart.")

st.markdown('<div style="margin-top:1.5rem"></div>', unsafe_allow_html=True)

col_left, col_right = st.columns(2)

with col_left:
    top_regions = query_data("""
        SELECT region_txt as Region, COUNT(*) as Incidents
        FROM 'data/globalterrorism.csv'
        GROUP BY region_txt
        ORDER BY Incidents DESC
        LIMIT 10
    """)
    if not top_regions.empty:
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
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No regional data found.")

with col_right:
    attack_types = query_data("""
        SELECT attacktype1_txt as AttackType, COUNT(*) as Count
        FROM 'data/globalterrorism.csv'
        WHERE attacktype1_txt IS NOT NULL
        GROUP BY attacktype1_txt
        ORDER BY Count DESC
        LIMIT 7
    """)
    if not attack_types.empty:
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
        st.plotly_chart(fig3, use_container_width=True)
    else:
        st.info("No attack type data found.")

st.markdown('<div style="margin-top:1rem"></div>', unsafe_allow_html=True)
st.caption("💡 Select any module from the left sidebar to dive into specific threat analysis.")
