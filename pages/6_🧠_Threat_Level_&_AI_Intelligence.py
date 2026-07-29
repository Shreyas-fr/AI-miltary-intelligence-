import os
import pandas as pd
import plotly.express as px
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

st.set_page_config(page_title="Threat Level & AI Intelligence", page_icon="🧠", layout="wide")

def load_css(file_name):
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_css("assets/style.css")

st.title("🧠 Threat Level & AI Intelligence")
st.markdown("##### View quantitative country threat levels and AI narrative reports side-by-side.")

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

# -----------------------------
# Unified Sidebar
# -----------------------------
st.sidebar.header("Controls")
country = st.sidebar.selectbox("Select Country", country_options())

st.sidebar.markdown("---")
st.sidebar.subheader("AI Narrative Settings")
lookback = st.sidebar.selectbox("Live intelligence window", ["15m", "1h", "6h", "1d", "3d", "7d"], index=3)
max_records = st.sidebar.slider("Live records", 25, 250, 100, step=25)
use_live = st.sidebar.checkbox("Include GDELT live feed", value=True)
api_key = os.environ.get("GEMINI_API_KEY") or st.sidebar.text_input("Gemini API Key (optional)", type="password")

# -----------------------------
# Data Loading
# -----------------------------
historical_all = load_data()
country_hist = historical_all[historical_all["country_txt"] == country].copy()
safe_country = country.replace("'", "''")
country_df = query_data(f"SELECT * FROM 'data/globalterrorism.csv' WHERE country_txt = '{safe_country}'")

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

try:
    risk_breakdown = compute_country_risk(country, historical_all, live_events)
    threat_score = risk_breakdown.score
    risk_lvl = risk_breakdown.level
    risk_color = risk_breakdown.color
except Exception:
    risk_breakdown = None
    threat_score = "N/A"
    risk_lvl = "Unknown"
    risk_color = "#94A3B8"

tab1, tab2 = st.tabs(["📊 Country Threat Metrics", "🤖 AI Narrative Intelligence"])

# -----------------------------
# Tab 1: Country Threat Metrics
# -----------------------------
with tab1:
    st.header(f"Intelligence Report : {country}")
    
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Incidents", f"{len(country_df):,}")
    c2.metric("Fatalities", f"{int(country_df['nkill'].fillna(0).sum()):,}")
    c3.metric("Injured", f"{int(country_df['nwound'].fillna(0).sum()):,}")
    c4.metric("Groups", f"{country_df['gname'].nunique():,}")
    c5.metric("Threat Score", f"{threat_score}/100 ({risk_lvl})")
    
    st.divider()
    
    if risk_breakdown and risk_breakdown.components:
        with st.expander("🔍 Threat Score Breakdown", expanded=True):
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
            st.plotly_chart(fig_comp, width="stretch")
            
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
        st.plotly_chart(fig, width="stretch")

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
        st.plotly_chart(fig, width="stretch")
        
    st.divider()

    left, right = st.columns(2)
    with left:
        groups = country_df.groupby("gname").size().reset_index(name="Attacks").sort_values("Attacks", ascending=False).head(10)
        fig = px.bar(groups, x="Attacks", y="gname", orientation="h", title="Top Terrorist Organizations", template="plotly_dark")
        st.plotly_chart(fig, width="stretch")

    with right:
        weapon = country_df.groupby("weaptype1_txt").size().reset_index(name="Count").sort_values("Count", ascending=False)
        fig = px.bar(weapon, x="weaptype1_txt", y="Count", title="Weapon Types", template="plotly_dark")
        st.plotly_chart(fig, width="stretch")
        
    st.divider()

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
        st.plotly_chart(fig, width="stretch")
    else:
        st.warning("No geospatial coordinates available for this country.")

    st.divider()
    st.subheader("Incident Details")
    cols = ["iyear", "city", "attacktype1_txt", "targtype1_txt", "weaptype1_txt", "gname", "nkill", "nwound"]
    st.dataframe(country_df[cols], width="stretch")
    csv = country_df.to_csv(index=False).encode()
    st.download_button("Download Country Data", csv, file_name=f"{country}.csv", mime="text/csv")


# -----------------------------
# Tab 2: AI Narrative Intelligence
# -----------------------------
with tab2:
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
    
    if risk_breakdown:
        report = build_situation_report(country, f"Live window: {lookback}", stats, risk_breakdown, country_live)
    else:
        report = "Could not generate report due to missing risk breakdown."

    if live_error:
        st.warning(f"Live feed unavailable, using historical data only: {live_error}")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Threat Score", f"{threat_score}/100")
    c2.metric("Risk Level", risk_lvl)
    c3.metric("Historical Incidents", f"{len(country_hist):,}")
    c4.metric("Live Items", f"{len(country_live):,}")
    
    if risk_breakdown:
        fig = go.Figure(
            go.Indicator(
                mode="gauge+number",
                value=risk_breakdown.score,
                title={"text": "AI Risk Score"},
                gauge={
                    "axis": {"range": [0, 100]},
                    "bar": {"color": risk_breakdown.color},
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
