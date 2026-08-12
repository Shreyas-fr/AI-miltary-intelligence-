import os
import json
import streamlit as st

# --- Authentication & Role Check ---
from utils.auth import require_auth
require_auth(['Commander'])
# -----------------------------------

import pandas as pd
import plotly.express as px
from database.intelligence_db import (
    init_db,
    ingest_live_events,
    get_live_df,
    get_event_log,
    get_db_stats,
    get_live_count,
)
from utils.intelligence import (
    fetch_gdelt_events,
    enrich_live_events_with_country_centroids,
    DEFAULT_LIVE_QUERY,
)
from utils.data_loader import query_data
from utils.ui_components import st_custom_kpi_card

st.set_page_config(
    page_title="Intelligence Database",
    page_icon="🗄️",
    layout="wide",
)


def load_css(file_name: str) -> None:
    if os.path.exists(file_name):
        with open(file_name, encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


load_css("assets/style.css")

# Initialise database on page load
init_db()

st.title("🗄️ | Intelligence Database")
st.markdown("##### Persistent live intelligence storage for AI-enhanced predictions.")

# Section 1 - Database Health KPIs
stats = get_db_stats()
col1, col2, col3, col4, col5 = st.columns(5)
with col1: st_custom_kpi_card("Total Combined Events", f"{stats.get('total_rows', 0):,}", "", "📚")
with col2: st_custom_kpi_card("GTD Historical Events", f"{stats.get('gtd_rows', 0):,}", "", "🏛️")
with col3: st_custom_kpi_card("Live Events Stored", f"{stats.get('live_rows', 0):,}", "", "⚡")
with col4: st_custom_kpi_card("Countries in Live DB", f"{stats.get('live_countries', 0):,}", "", "🌎")
with col5: st_custom_kpi_card("DB Size", f"{stats.get('db_size_kb', 0):,} KB", "", "🗄️")

st.divider()

# Display persistent session message if ingestion was performed
if "ingest_success_msg" in st.session_state:
    st.success(st.session_state.pop("ingest_success_msg"))

# Section 2 - Manual Ingestion Panel
with st.expander("🔄 Manual Ingestion Controls", expanded=True):
    col_q, col_opts = st.columns([2, 1])
    with col_q:
        q = st.text_area("GDELT Query", value=DEFAULT_LIVE_QUERY, height=100)
    with col_opts:
        ts = st.selectbox("Timespan", ["15m", "1h", "6h", "1d", "3d", "7d"], index=3)
        mr = st.slider("Max Records", min_value=25, max_value=250, value=100, step=25)

    if st.button("🔄 Fetch & Ingest Live Events"):
        with st.spinner("Fetching from GDELT..."):
            try:
                live = fetch_gdelt_events(query=q, timespan=ts, max_records=mr)
                if live.empty:
                    st.warning("No live events found matching the query and timespan.")
                else:
                    historical_geo = query_data(
                        "SELECT country_txt, latitude, longitude FROM 'data/globalterrorism.csv' WHERE latitude IS NOT NULL AND longitude IS NOT NULL"
                    )
                    enriched = enrich_live_events_with_country_centroids(live, historical_geo)
                    new_rows = ingest_live_events(enriched)
                    st.session_state["ingest_success_msg"] = f"✅ {new_rows} new events ingested into the database!"
                    st.rerun()
            except Exception as e:
                st.error(f"Failed to fetch live events from GDELT: {e}")

# Section 3 - Live Events Table
live_df = get_live_df()
with st.expander("Live Events in Database", expanded=True):
    if live_df.empty:
        st.info("No live events found in the database. Use the manual ingestion controls above or the Live Feed page to ingest live events.")
    else:
        target_cols = [
            "iyear",
            "imonth",
            "country_txt",
            "region_txt",
            "city",
            "attacktype1_txt",
            "nkill",
            "nwound",
            "severity",
            "original_title",
        ]
        avail_cols = [c for c in target_cols if c in live_df.columns]
        display_df = live_df[avail_cols].rename(
            columns={
                "iyear": "Year",
                "imonth": "Month",
                "country_txt": "Country",
                "region_txt": "Region",
                "city": "City",
                "attacktype1_txt": "Attack Type",
                "nkill": "Fatalities",
                "nwound": "Injuries",
                "severity": "Severity",
                "original_title": "Original Title / Headline",
            }
        )
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        st.download_button(
            "Download Live Events CSV",
            data=live_df.to_csv(index=False),
            file_name="live_events_db.csv",
            mime="text/csv",
        )

# Section 4 - Ingestion History
with st.expander("Ingestion History", expanded=True):
    event_log_df = get_event_log()
    if event_log_df.empty:
        st.info("No ingestion history recorded yet.")
    else:
        target_log_cols = ["run_at", "source", "rows_added"]
        avail_log_cols = [c for c in target_log_cols if c in event_log_df.columns]
        display_log = event_log_df[avail_log_cols].rename(
            columns={
                "run_at": "Ingestion Time",
                "source": "Source",
                "rows_added": "Rows Added",
            }
        )
        st.dataframe(display_log, use_container_width=True, hide_index=True)

# Section 5 - Export Combined Dataset
with st.expander("📥 Export Combined Dataset", expanded=True):
    st.info(
        "The combined dataset merges historical Global Terrorism Database (GTD) records with live persistent events stored in DuckDB."
    )
    col_exp1, col_exp2 = st.columns(2)
    with col_exp1:
        if st.button("Generate Combined CSV Export"):
            with st.spinner("Generating combined dataset export..."):
                from utils.data_loader import load_combined

                comb_df = load_combined()
                csv_comb = comb_df.to_csv(index=False)
                st.download_button(
                    label="📥 Download Combined CSV",
                    data=csv_comb,
                    file_name="combined_intelligence_dataset.csv",
                    mime="text/csv",
                )
    with col_exp2:
        if st.button("🔁 Retrain Models on Combined Data"):
            st.warning(
                "To retrain ML models on the combined dataset, run the following command from the project root in your terminal:\n\n`./venv/bin/python train_models.py`"
            )

# Section 6 - Live Events Distribution Charts
st.subheader("📊 Live Events Distribution")
if live_df.empty:
    st.info("No live events available in the database to generate distribution charts.")
else:
    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        top_countries = (
            live_df["country_txt"]
            .value_counts()
            .head(10)
            .reset_index()
        )
        top_countries.columns = ["Country", "Event Count"]
        fig_bar = px.bar(
            top_countries,
            x="Event Count",
            y="Country",
            orientation="h",
            title="Top 10 Countries in Live DB",
            template="plotly_dark",
            color="Event Count",
            color_continuous_scale="Reds",
        )
        fig_bar.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            yaxis={"categoryorder": "total ascending"},
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    with chart_col2:
        attack_types = (
            live_df["attacktype1_txt"]
            .value_counts()
            .reset_index()
        )
        attack_types.columns = ["Attack Type", "Count"]
        fig_pie = px.pie(
            attack_types,
            names="Attack Type",
            values="Count",
            title="Live Events by Attack Type",
            template="plotly_dark",
            hole=0.4,
        )
        fig_pie.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_pie, use_container_width=True)
