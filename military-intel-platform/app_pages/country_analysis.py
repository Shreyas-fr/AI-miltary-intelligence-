import streamlit as st

# --- Authentication & Role Check ---
from utils.auth import require_auth
require_auth(['Viewer', 'Analyst', 'Commander'])
# -----------------------------------

import plotly.express as px
import plotly.graph_objects as go
from utils.data_loader import query_data
from utils.ui_components import st_custom_kpi_card
import os

st.set_page_config(
    page_title="Country Analysis",
    page_icon="🌎",
    layout="wide"
)

# Inject custom CSS for premium UI
def load_css(file_name):
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
load_css("assets/style.css")

st.title("🌎 | Country Analysis")
st.markdown("##### Detailed intelligence and historical risk analysis for a specific nation.")

# -----------------------------
# Sidebar
# -----------------------------
# Grab only unique countries for the dropdown to avoid loading full dataset
countries_df = query_data("SELECT DISTINCT country_txt FROM 'data/globalterrorism.csv' WHERE country_txt IS NOT NULL ORDER BY country_txt")
countries = countries_df["country_txt"].tolist()

country = st.sidebar.selectbox("Select Country", countries, help="Select a nation to analyze historical and predictive threat data.")

# Use DuckDB to fetch ONLY the data for the selected country
with st.spinner(f"Loading data for {country}..."):
    safe_country = country.replace("'", "''")
    country_df = query_data(f"SELECT * FROM 'data/globalterrorism.csv' WHERE country_txt = '{safe_country}'")

if country_df.empty:
    st.warning(f"No historical incidents found for {country}.")
    st.stop()

st.header(f"Intelligence Report: {country}")

from utils.data_loader import load_data
from utils.intelligence import compute_country_risk

# Calculate threat score
try:
    with st.spinner("Computing threat score..."):
        historical_all = load_data()
        risk_breakdown = compute_country_risk(country, historical_all)
        threat_score = risk_breakdown.score
        risk_lvl = risk_breakdown.level
        risk_color = risk_breakdown.color
except Exception:
    threat_score = "N/A"
    risk_lvl = "Unknown"
    risk_color = "#94A3B8"

c1, c2, c3, c4, c5 = st.columns(5)

with c1: st_custom_kpi_card("Incidents", f"{len(country_df):,}", "Recorded events", "📉")
with c2: st_custom_kpi_card("Fatalities", f"{int(country_df['nkill'].fillna(0).sum()):,}", "Estimated deaths", "💀")
with c3: st_custom_kpi_card("Injured", f"{int(country_df['nwound'].fillna(0).sum()):,}", "Estimated wounded", "🩹")
with c4: st_custom_kpi_card("Groups", f"{country_df['gname'].nunique():,}", "Known actors", "👥")
with c5: st_custom_kpi_card("Threat Score", f"{threat_score}/100", f"Level: {risk_lvl}", "🛡️")

st.divider()

if 'risk_breakdown' in locals() and risk_breakdown.components:
    with st.expander("🔍 Threat Score Breakdown", expanded=False):
        comp = risk_breakdown.components
        fig_comp = go.Figure(go.Bar(
            x=list(comp.values()),
            y=list(comp.keys()),
            orientation="h",
            marker_color="#00E5FF",
            text=[f"{v:.1f}" for v in comp.values()],
            textposition="auto"
        ))
        fig_comp.update_layout(
            title="How is this score calculated?",
            xaxis_title="Points Contributed",
            yaxis={'categoryorder':'total ascending'},
            template="plotly_dark",
            height=250,
            margin=dict(l=10, r=10, t=30, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)"
        )
        st.plotly_chart(fig_comp, use_container_width=True)

# -----------------------------
# Attacks Over Time
# -----------------------------

left, right = st.columns(2)

with left:
    yearly = country_df.groupby("iyear").size()
    if not yearly.empty:
        full_years = range(int(yearly.index.min()), int(yearly.index.max()) + 1)
        yearly = yearly.reindex(full_years, fill_value=0).reset_index()
        yearly.columns = ["iyear", "Attacks"]
    else:
        yearly = pd.DataFrame(columns=["iyear", "Attacks"])

    fig = px.line(
        yearly, x="iyear", y="Attacks", markers=True,
        title="Attacks Over Years", template="plotly_dark",
        color_discrete_sequence=["#00E5FF"]
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Outfit, sans-serif", color="#CBD5E1"),
        margin=dict(l=10, r=10, t=40, b=10)
    )
    st.plotly_chart(fig, use_container_width=True)

with right:
    attack = country_df.groupby("attacktype1_txt").size().reset_index(name="Count")
    fig = px.pie(
        attack, names="attacktype1_txt", values="Count",
        title="Attack Types Breakdown", template="plotly_dark",
        hole=0.45,
        color_discrete_sequence=["#00E5FF", "#007BFF", "#7000FF", "#FF007A", "#FF6B35", "#FFD60A", "#34C759"]
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Outfit, sans-serif", color="#CBD5E1"),
        margin=dict(l=10, r=10, t=40, b=10)
    )
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# -----------------------------
# Organizations & Weapons
# -----------------------------

left, right = st.columns(2)

with left:
    groups = country_df.groupby("gname").size().reset_index(name="Attacks").sort_values("Attacks", ascending=False).head(10)
    fig = px.bar(groups, x="Attacks", y="gname", orientation="h", title="Top Terrorist Organizations", template="plotly_dark")
    st.plotly_chart(fig, use_container_width=True)

with right:
    weapon = country_df.groupby("weaptype1_txt").size().reset_index(name="Count").sort_values("Count", ascending=False)
    fig = px.bar(weapon, x="weaptype1_txt", y="Count", title="Weapon Types", template="plotly_dark")
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# -----------------------------
# Incident Map
# -----------------------------

st.subheader("Incident Locations")

map_df = country_df.dropna(subset=["latitude", "longitude"])

if not map_df.empty:
    fig = px.scatter_geo(
        map_df,
        lat="latitude",
        lon="longitude",
        hover_name="city",
        hover_data={"country_txt": True, "iyear": True, "attacktype1_txt": True, "gname": True, "nkill": True, "latitude": False, "longitude": False},
        color="attacktype1_txt",
        projection="natural earth",
        title=f"Terrorist Incidents in {country}",
        height=600,
        template="plotly_dark"
    )
    fig.update_layout(margin=dict(l=0, r=0, t=50, b=0))
    st.plotly_chart(fig, use_container_width=True)
else:
    st.warning("No geospatial coordinates available for this country.")

st.divider()

# -----------------------------
# Incident Table
# -----------------------------

st.subheader("Incident Details")

cols = ["iyear", "city", "attacktype1_txt", "targtype1_txt", "weaptype1_txt", "gname", "nkill", "nwound"]
st.dataframe(country_df[cols], use_container_width=True, hide_index=True)

# -----------------------------
# Download
# -----------------------------
csv = country_df.to_csv(index=False).encode()
st.download_button("Download Country Data", csv, file_name=f"{country}.csv", mime="text/csv")