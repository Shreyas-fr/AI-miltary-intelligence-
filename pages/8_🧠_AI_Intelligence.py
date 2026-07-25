import os

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

try:
    from google import genai
except Exception:
    genai = None

from utils.data_loader import load_data, query_data
from utils.intelligence import (
    DEFAULT_LIVE_QUERY,
    build_pdf,
    build_situation_report,
    compute_country_risk,
    enrich_live_events_with_country_centroids,
    fetch_gdelt_events,
)

st.set_page_config(page_title="AI Situation Report", page_icon="🧠", layout="wide")


def load_css(file_name):
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


load_css("assets/style.css")

st.title("🧠 AI Situation Report Generator")
st.markdown("##### Country-level threat scoring and analyst-ready intelligence briefs.")


@st.cache_data(ttl=900, show_spinner=False)
def load_recent_events(query_text: str, window: str, records: int) -> pd.DataFrame:
    live = fetch_gdelt_events(query=query_text, timespan=window, max_records=records)
    historical_geo = query_data(
        """
        SELECT country_txt, latitude, longitude
        FROM 'data/globalterrorism.csv'
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
        """
    )
    return enrich_live_events_with_country_centroids(live, historical_geo)


@st.cache_data(show_spinner=False)
def country_options() -> list[str]:
    countries = query_data(
        """
        SELECT country_txt, COUNT(*) AS incidents
        FROM 'data/globalterrorism.csv'
        WHERE country_txt IS NOT NULL
        GROUP BY country_txt
        ORDER BY incidents DESC
        """
    )
    return countries["country_txt"].tolist()


st.sidebar.header("Report Controls")
country = st.sidebar.selectbox("Country", country_options())
lookback = st.sidebar.selectbox("Live intelligence window", ["15m", "1h", "6h", "1d", "3d", "7d"], index=3)
max_records = st.sidebar.slider("Live records", 25, 250, 100, step=25)
use_live = st.sidebar.checkbox("Include GDELT live feed", value=True)
api_key = os.environ.get("GEMINI_API_KEY") or st.sidebar.text_input("Gemini API Key (optional)", type="password")

historical = load_data()
country_hist = historical[historical["country_txt"] == country].copy()

live_events = pd.DataFrame()
live_error = None
if use_live:
    try:
        with st.spinner("Collecting recent public-source events..."):
            live_events = load_recent_events(DEFAULT_LIVE_QUERY, lookback, max_records)
    except Exception as exc:
        live_error = str(exc)
        live_events = pd.DataFrame(columns=["country", "event", "severity", "title", "date", "source", "url"])

country_live = live_events[
    live_events.get("country", pd.Series(dtype=str)).map(lambda value: str(value).lower())
    == country.lower()
].copy() if not live_events.empty else live_events

years = sorted(country_hist["iyear"].dropna().astype(int).unique().tolist())
latest_year = years[-1] if years else None
previous_year = years[-2] if len(years) > 1 else None
latest_count = int((country_hist["iyear"] == latest_year).sum()) if latest_year else 0
previous_count = int((country_hist["iyear"] == previous_year).sum()) if previous_year else 0
activity_delta = None
if previous_count and previous_count > 0:
    activity_delta = ((latest_count - previous_count) / previous_count) * 100

top_area = None
if "provstate" in country_hist.columns and not country_hist["provstate"].dropna().empty:
    top_area = country_hist["provstate"].value_counts().index[0]
elif "region_txt" in country_hist.columns and not country_hist["region_txt"].dropna().empty:
    top_area = country_hist["region_txt"].value_counts().index[0]

stats = {
    "historical_incidents": len(country_hist),
    "historical_fatalities": pd.to_numeric(country_hist.get("nkill", 0), errors="coerce").fillna(0).sum(),
    "activity_delta_pct": activity_delta,
    "top_area": top_area,
}
risk = compute_country_risk(country, historical, live_events)
report = build_situation_report(country, f"Live window: {lookback}", stats, risk, country_live)

if live_error:
    st.warning(f"Live feed unavailable, using historical data only: {live_error}")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Threat Score", f"{risk.score}/100")
c2.metric("Risk Level", risk.level)
c3.metric("Historical Incidents", f"{len(country_hist):,}")
c4.metric("Live Items", f"{len(country_live):,}")

fig = go.Figure(
    go.Indicator(
        mode="gauge+number",
        value=risk.score,
        title={"text": "AI Risk Score"},
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": risk.color},
            "steps": [
                {"range": [0, 30], "color": "rgba(52,199,89,0.20)"},
                {"range": [30, 55], "color": "rgba(255,214,10,0.20)"},
                {"range": [55, 75], "color": "rgba(255,107,53,0.20)"},
                {"range": [75, 100], "color": "rgba(255,45,85,0.20)"},
            ],
        },
    )
)
fig.update_layout(template="plotly_dark", height=300, paper_bgcolor="rgba(0,0,0,0)")
st.plotly_chart(fig, width="stretch")

st.subheader("Risk Drivers")
component_df = pd.DataFrame(
    [{"Component": key, "Weighted Points": round(value, 2)} for key, value in risk.components.items()]
)
st.bar_chart(component_df.set_index("Component"))

st.divider()

st.subheader("Situation Report")

generated_report = report
can_use_gemini = bool(api_key and genai is not None)
if st.button("🚀 Generate / Enhance Brief"):
    if can_use_gemini:
        with st.spinner("Enhancing report with Gemini..."):
            try:
                client = genai.Client(api_key=api_key)
                prompt = f"""
You are a senior intelligence analyst. Rewrite the following situation report into a concise,
professional brief. Keep all risk figures unchanged, avoid operational targeting guidance, and
include a short analyst recommendation.

{report}
"""
                response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
                generated_report = response.text
                st.session_state["generated_sitrep"] = generated_report
            except Exception as exc:
                st.error(f"Gemini enhancement failed: {exc}")
                st.session_state["generated_sitrep"] = report
    else:
        if genai is None:
            st.info("google-genai is not installed or importable, so a local report template was used.")
        elif not api_key:
            st.info("No Gemini API key supplied, so a local report template was used.")
        st.session_state["generated_sitrep"] = report

generated_report = st.session_state.get("generated_sitrep", generated_report)
st.markdown(generated_report)

download_col1, download_col2 = st.columns(2)
with download_col1:
    st.download_button(
        "📄 Download Markdown Report",
        generated_report,
        file_name=f"{country}_situation_report.md",
        mime="text/markdown",
    )
with download_col2:
    try:
        pdf_bytes = build_pdf(generated_report)
        st.download_button(
            "📕 Download PDF Report",
            pdf_bytes,
            file_name=f"{country}_situation_report.pdf",
            mime="application/pdf",
        )
    except Exception:
        st.caption("PDF export requires reportlab. Markdown export is available.")

st.divider()

st.subheader("Recent Live Items For Selected Country")
if country_live.empty:
    st.info("No live items matched this country in the selected window.")
else:
    display = country_live[["date", "event", "severity", "source", "title", "url"]].copy()
    display["date"] = pd.to_datetime(display["date"], errors="coerce", utc=True).dt.strftime("%Y-%m-%d %H:%M UTC")
    st.dataframe(
        display.rename(
            columns={
                "date": "Date",
                "event": "Event",
                "severity": "Severity",
                "source": "Source",
                "title": "Headline",
                "url": "URL",
            }
        ),
        width="stretch",
        hide_index=True,
        column_config={"URL": st.column_config.LinkColumn("Source Link")},
    )

st.info("This report is a decision-support artifact from historical GTD data and public news metadata.")
