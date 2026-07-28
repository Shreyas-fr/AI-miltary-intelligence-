import concurrent.futures
import os

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.data_loader import load_data, query_data
from utils.intelligence import compute_country_risk, fetch_gdelt_events
from utils.recommendations import generate_recommendations, priority_color

# -----------------------------------------------------------------------------
# 1. Page Configuration
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Resource Recommendation",
    page_icon="📋",
    layout="wide"
)

# -----------------------------------------------------------------------------
# 2. Load CSS
# -----------------------------------------------------------------------------
def load_css(file_name: str) -> None:
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_css("assets/style.css")

# -----------------------------------------------------------------------------
# 3 & 4. Title and Subtitle
# -----------------------------------------------------------------------------
st.title("📋 AI Resource Recommendation")
st.markdown("##### AI-driven operational response suggestions based on threat assessment")

# -----------------------------------------------------------------------------
# 6. Sidebar Controls
# -----------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def get_country_options() -> list[str]:
    """Fetch distinct countries ordered by incident count descending."""
    sql = """
        SELECT country_txt, COUNT(*) AS incidents
        FROM 'data/globalterrorism.csv'
        WHERE country_txt IS NOT NULL
        GROUP BY country_txt
        ORDER BY incidents DESC
    """
    df = query_data(sql)
    return df["country_txt"].tolist()

st.sidebar.header("Filter Options")
country_list = get_country_options()
selected_country = st.sidebar.selectbox("Select Country", country_list)
use_live_feed = st.sidebar.checkbox("Include Live GDELT Signals", value=True)

# -----------------------------------------------------------------------------
# 7. Helper Functions for Main Flow
# -----------------------------------------------------------------------------
def get_dominant_attack_type(country: str) -> str | None:
    """Query DuckDB for the dominant attack type in the selected country."""
    safe_country = country.replace("'", "''")
    sql = f"""
        SELECT attacktype1_txt, COUNT(*) AS cnt
        FROM 'data/globalterrorism.csv'
        WHERE country_txt = '{safe_country}'
          AND attacktype1_txt IS NOT NULL
          AND attacktype1_txt != 'Unknown'
        GROUP BY attacktype1_txt
        ORDER BY cnt DESC
        LIMIT 1
    """
    df = query_data(sql)
    if not df.empty:
        return str(df.iloc[0]["attacktype1_txt"])
    return None

def get_recent_trend(country: str) -> str:
    """Determine recent threat trend by comparing the last 2 available years."""
    safe_country = country.replace("'", "''")
    sql = f"""
        SELECT iyear, COUNT(*) AS cnt
        FROM 'data/globalterrorism.csv'
        WHERE country_txt = '{safe_country}' AND iyear IS NOT NULL
        GROUP BY iyear
        ORDER BY iyear ASC
    """
    df_years = query_data(sql)
    if len(df_years) >= 2:
        latest_count = int(df_years.iloc[-1]["cnt"])
        previous_count = int(df_years.iloc[-2]["cnt"])
        if latest_count > previous_count:
            return "increasing"
        elif latest_count < previous_count:
            return "decreasing"
        else:
            return "stable"
    return "stable"

# -----------------------------------------------------------------------------
# Main Data Processing
# -----------------------------------------------------------------------------
historical = load_data()

live_events = pd.DataFrame()
live_count = 0
live_error_msg = None
if use_live_feed:
    try:
        with st.spinner("Fetching public-source conflict intelligence from GDELT..."):
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(fetch_gdelt_events, timespan="1d", max_records=50)
                live_df = future.result(timeout=5)
                
            if not live_df.empty and "country" in live_df.columns:
                country_live = live_df[
                    live_df["country"].astype(str).str.lower() == selected_country.lower()
                ]
                live_count = len(country_live)
    except concurrent.futures.TimeoutError:
        live_count = 0
        live_error_msg = "Live feed timeout (exceeded 5s). Falling back to historical data."
    except Exception as e:
        live_count = 0
        live_error_msg = f"Live feed error ({e}). Falling back to historical data."

# 7a. Compute risk for selected country
risk = compute_country_risk(selected_country, historical, live_events if not live_events.empty else None)

# 7b. Get dominant attack type
dominant_attack = get_dominant_attack_type(selected_country)

# 7c. Determine recent trend
trend = get_recent_trend(selected_country)

# 7d. Generate recommendations
recommendations = generate_recommendations(
    threat_score=risk.score,
    dominant_attack_type=dominant_attack,
    recent_trend=trend,
    live_event_count=live_count
)

# -----------------------------------------------------------------------------
# 8. Display UI
# -----------------------------------------------------------------------------

# Context Expander
with st.expander("ℹ️ Operational Context & Assessment Factors", expanded=False):
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Selected Country", selected_country)
    c2.metric("Dominant Attack Type", dominant_attack or "N/A")
    c3.metric("Activity Trend", trend.capitalize())
    c4.metric("Live 24h Conflict Events", live_count)

if live_error_msg:
    st.warning(live_error_msg)

# 8a. KPI Row
kpi_col1, kpi_col2, kpi_col3 = st.columns(3)
kpi_col1.metric("Threat Score", f"{risk.score} / 100")
kpi_col2.metric("Risk Level", risk.level)
kpi_col3.metric("Total Recommendations", len(recommendations))

st.divider()

# 8b. Risk Gauge Chart (Plotly indicator, same style as page 6)
gauge_fig = go.Figure(go.Indicator(
    mode="gauge+number",
    value=risk.score,
    domain={"x": [0, 1], "y": [0, 1]},
    title={"text": f"Threat Risk Score ({risk.level} Risk)", "font": {"size": 16}},
    gauge={
        "axis": {"range": [0, 100]},
        "bar": {"color": risk.color},
        "steps": [
            {"range": [0, 25],  "color": "#1a1a2e"},
            {"range": [25, 50], "color": "#16213e"},
            {"range": [50, 75], "color": "#0f3460"},
            {"range": [75, 100],"color": "#2d0a0a"},
        ],
        "threshold": {
            "line": {"color": "white", "width": 3},
            "thickness": 0.8,
            "value": risk.score
        }
    }
))

gauge_fig.update_layout(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    height=260,
    margin=dict(l=20, r=20, t=40, b=10)
)

st.plotly_chart(gauge_fig, width="stretch")

st.divider()

# 8c, 8d, 8e. Recommendation Cards Grouped by Priority
st.subheader("🛡️ Operational Response Recommendations")

priority_order = ["Critical", "High", "Elevated", "Routine"]

for priority in priority_order:
    priority_recs = [r for r in recommendations if r.priority == priority]
    if not priority_recs:
        continue

    st.markdown(f"#### {priority} Priority ({len(priority_recs)})")
    
    for rec in priority_recs:
        badge_bg = priority_color(rec.priority)
        badge_text_color = "#000000" if rec.priority == "Elevated" else "#FFFFFF"
        
        with st.container(border=True):
            col_head, col_badge = st.columns([3, 1])
            with col_head:
                st.markdown(f"##### {rec.icon} {rec.category}")
            with col_badge:
                st.markdown(
                    f"<div style='background-color: {badge_bg}; color: {badge_text_color}; "
                    f"padding: 4px 12px; border-radius: 12px; text-align: center; "
                    f"font-weight: bold; font-size: 0.85rem; float: right; margin-top: 4px;'>"
                    f"{rec.priority} Priority</div>",
                    unsafe_allow_html=True,
                )
            st.markdown(f"**Action:** {rec.action}")
            st.markdown(
                f"<p style='font-size: 0.88rem; color: #94A3B8; margin-top: 4px; margin-bottom: 0px;'>Rationale: {rec.rationale}</p>",
                unsafe_allow_html=True,
            )
