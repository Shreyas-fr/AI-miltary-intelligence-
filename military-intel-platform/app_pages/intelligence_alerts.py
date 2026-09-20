import os
import pandas as pd
import streamlit as st


# --- Authentication & Role Check ---
from utils.auth import require_auth
require_auth(['Analyst', 'Commander'])
# -----------------------------------


from utils.data_loader import load_data, query_data
from utils.intelligence import compute_country_risk
from utils.ui_components import st_custom_kpi_card

st.set_page_config(
    page_title="Intelligence Alerts",
    page_icon="🔔",
    layout="wide"
)


def load_css(file_name: str) -> None:
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


load_css("assets/style.css")

st.title("🔔 | Intelligence Alerts")
st.markdown("##### Threshold-based monitoring for critical threat changes.")

# Sidebar: alert configuration
st.sidebar.header("Alert Configuration")

score_threshold = st.sidebar.slider(
    "Threat Score Threshold",
    min_value=50,
    max_value=95,
    value=75,
    step=1,
    help="Trigger an alert if a country's composite threat score reaches or exceeds this threshold."
)

activity_threshold = st.sidebar.slider(
    "Activity Increase % Threshold",
    min_value=20,
    max_value=200,
    value=50,
    step=5,
    help="Trigger an alert if year-over-year incident activity increases by this percentage or more."
)


@st.cache_data(show_spinner=False)
def get_monitored_country_options() -> list[str]:
    df = query_data(
        """
        SELECT country_txt, COUNT(*) AS incident_count
        FROM 'data/globalterrorism.csv'
        WHERE country_txt IS NOT NULL
        GROUP BY country_txt
        ORDER BY incident_count DESC
        """
    )
    return df["country_txt"].tolist()


all_countries = get_monitored_country_options()
top_20_countries = all_countries[:20]

selected_countries = st.sidebar.multiselect(
    "Select Countries to Monitor",
    options=all_countries,
    default=top_20_countries,
    help="Countries selected for automated threshold monitoring."
)

# Load full dataset for country risk computation
try:
    with st.spinner("Loading intelligence records..."):
        historical_df = load_data()
except Exception as e:
    st.error(f"Failed to load GTD dataset: {e}")
    st.stop()

if not selected_countries:
    st.info("Please select at least one country in the sidebar to begin monitoring.")
    st.stop()

alerts = []
summary_rows = []

for country in selected_countries:
    country_hist = historical_df[historical_df["country_txt"] == country]
    if country_hist.empty:
        continue

    # a. Compute risk score
    risk = compute_country_risk(country, historical_df)
    score = risk.score

    # c. Compute year-over-year activity change for recent years
    years = sorted(country_hist["iyear"].dropna().astype(int).unique().tolist())
    if len(years) >= 2:
        latest_yr = years[-1]
        prev_yr = years[-2]
        latest_cnt = int((country_hist["iyear"] == latest_yr).sum())
        prev_cnt = int((country_hist["iyear"] == prev_yr).sum())
        if prev_cnt > 0:
            act_increase_pct = ((latest_cnt - prev_cnt) / prev_cnt) * 100.0
        else:
            act_increase_pct = 0.0
    elif len(years) == 1:
        latest_yr = years[0]
        prev_yr = "N/A"
        latest_cnt = int((country_hist["iyear"] == latest_yr).sum())
        prev_cnt = 0
        act_increase_pct = 0.0
    else:
        latest_yr = "N/A"
        prev_yr = "N/A"
        latest_cnt = 0
        prev_cnt = 0
        act_increase_pct = 0.0

    from utils.alerts import generate_threat_score_alert, generate_activity_surge_alert

    triggered_types = []

    # b. Check if score exceeds threshold
    score_alert = generate_threat_score_alert(country, score, risk.level, score_threshold)
    if score_alert:
        triggered_types.append("Threat Score")
        alerts.append(score_alert)

    # d. Check if activity increase exceeds threshold
    activity_alert = generate_activity_surge_alert(
        country, act_increase_pct, activity_threshold,
        latest_cnt, prev_cnt, latest_yr, prev_yr
    )
    if activity_alert:
        triggered_types.append("Activity Surge")
        alerts.append(activity_alert)

    status_str = ", ".join(triggered_types) if triggered_types else "Normal"
    summary_rows.append({
        "Country": country,
        "Threat Score": score,
        "Risk Level": risk.level,
        "Recent Incidents": latest_cnt,
        "YoY Activity Change (%)": f"{act_increase_pct:+.1f}%" if prev_cnt > 0 else "N/A",
        "Alert Status": status_str
    })

# 8a. Display KPI metrics
active_alerts_count = len(alerts)
critical_alerts_count = sum(1 for a in alerts if a["severity"] == "Critical")
countries_monitored_count = len(selected_countries)

c1, c2, c3 = st.columns(3)
with c1: st_custom_kpi_card("Active Alerts", f"{active_alerts_count}", "", "🔔")
with c2: st_custom_kpi_card("Critical Alerts", f"{critical_alerts_count}", "", "🚨")
with c3: st_custom_kpi_card("Countries Monitored", f"{countries_monitored_count}", "", "🌎")

st.divider()

# 8b & 8c. Alert cards display
st.subheader("Triggered Intelligence Alerts")

if not alerts:
    st.success("✅ No active intelligence alerts triggered based on current threshold settings.")
else:
    for alert in alerts:
        card_html = (
            f'<div style="background:rgba(18,26,42,0.7);backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);'
            f'border:1px solid rgba(255,255,255,0.08);border-left:5px solid {alert["border_color"]};border-radius:12px;'
            f'padding:1.25rem 1.5rem;margin-bottom:1rem;box-shadow:0 6px 20px rgba(0,0,0,0.3);">'
            # Header row: country name + alert type badge + severity badge
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.75rem;">'
            f'<div style="display:flex;align-items:center;gap:0.75rem;">'
            f'<span style="color:#F8FAFC;font-size:1.25rem;font-weight:700;">{alert["country"]}</span>'
            f'<span style="background:rgba(255,255,255,0.08);color:#94A3B8;padding:3px 10px;border-radius:6px;font-size:0.82rem;font-weight:600;">{alert["alert_type"]}</span>'
            f'</div>'
            f'<span class="{alert["badge_class"]}">{alert["severity"].upper()}</span>'
            f'</div>'
            # Metrics row: alert type, current value, threshold
            f'<div style="display:flex;flex-wrap:wrap;gap:2.5rem;margin:0.75rem 0;background:rgba(0,0,0,0.25);padding:0.85rem 1.25rem;border-radius:8px;border:1px solid rgba(255,255,255,0.04);">'
            f'<div>'
            f'<div style="color:#94A3B8;font-size:0.75rem;text-transform:uppercase;font-weight:600;letter-spacing:0.5px;">Alert Type</div>'
            f'<div style="color:#F8FAFC;font-weight:700;font-size:1rem;margin-top:2px;">{alert["title"]}</div>'
            f'</div>'
            f'<div>'
            f'<div style="color:#94A3B8;font-size:0.75rem;text-transform:uppercase;font-weight:600;letter-spacing:0.5px;">Current Value</div>'
            f'<div style="color:#00E5FF;font-weight:700;font-size:1.05rem;margin-top:2px;">{alert["current"]}</div>'
            f'</div>'
            f'<div>'
            f'<div style="color:#94A3B8;font-size:0.75rem;text-transform:uppercase;font-weight:600;letter-spacing:0.5px;">Threshold Limit</div>'
            f'<div style="color:#CBD5E1;font-weight:600;font-size:1.05rem;margin-top:2px;">{alert["threshold"]}</div>'
            f'</div>'
            f'</div>'
            # Detail text
            f'<div style="font-size:0.9rem;color:#CBD5E1;line-height:1.4;">{alert["detail"]}</div>'
            f'</div>'
        )
        st.markdown(card_html, unsafe_allow_html=True)

# 8d & 9. Monitored countries summary table with width='stretch'
st.divider()
st.subheader("Monitored Countries Risk Summary")

if summary_rows:
    summary_df = pd.DataFrame(summary_rows)
    st.dataframe(summary_df, use_container_width=True, hide_index=True)
