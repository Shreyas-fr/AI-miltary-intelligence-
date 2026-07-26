import streamlit as st
import os
import pandas as pd
import pydeck as pdk
from utils.data_loader import query_data
from utils.intelligence import (
    DEFAULT_LIVE_QUERY,
    enrich_live_events_with_country_centroids,
    fetch_gdelt_events,
)
from database.intelligence_db import ingest_live_events, get_live_count, init_db

st.set_page_config(page_title="Live Intelligence Feed", page_icon="🛰️", layout="wide")


def load_css(file_name):
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


load_css("assets/style.css")

# Ensure DB exists on page load
init_db()

st.title("🛰️ Live Intelligence Feed")
st.markdown("##### Public-source conflict monitoring from GDELT, refreshed on analyst demand.")

st.sidebar.header("Live Feed Controls")
timespan = st.sidebar.selectbox("Lookback window", ["15m", "1h", "6h", "1d", "3d", "7d"], index=3)
max_records = st.sidebar.slider("Maximum records", 25, 250, 100, step=25)
query = st.sidebar.text_area("GDELT query", DEFAULT_LIVE_QUERY, height=110)

auto_ingest = st.sidebar.checkbox(
    "💾 Auto-save to Intelligence DB",
    value=True,
    help="Automatically store fetched events into the persistent database for use in predictions."
)

st.sidebar.markdown("---")
st.sidebar.metric("📦 Events in DB", f"{get_live_count():,}")


@st.cache_data(ttl=900, show_spinner=False)
def load_live_feed(query_text: str, window: str, records: int) -> pd.DataFrame:
    live = fetch_gdelt_events(query=query_text, timespan=window, max_records=records)
    historical_geo = query_data(
        """
        SELECT country_txt, latitude, longitude
        FROM 'data/globalterrorism.csv'
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
        """
    )
    return enrich_live_events_with_country_centroids(live, historical_geo)


if st.sidebar.button("🔄 Refresh Live Feed"):
    load_live_feed.clear()

try:
    with st.spinner("Fetching public-source conflict intelligence from GDELT..."):
        live_events = load_live_feed(query, timespan, max_records)
except Exception as exc:
    st.error(f"Unable to fetch GDELT feed: {exc}")
    st.info("Check your internet connection, then use the Refresh Live Feed button.")
    st.stop()

# Auto-ingest into persistent intelligence DB
if auto_ingest and not live_events.empty:
    try:
        new_rows = ingest_live_events(live_events)
        if new_rows > 0:
            st.success(f"💾 **{new_rows} new event(s)** saved to Intelligence Database for predictions.")
        else:
            st.info("ℹ️ All fetched events were already in the Intelligence Database (no duplicates).")
    except Exception as ingest_err:
        st.warning(f"Live ingestion skipped: {ingest_err}")

if live_events.empty:
    st.warning("No matching public-source events were returned for the selected query and window.")
    st.stop()

live_events["date"] = pd.to_datetime(live_events["date"], errors="coerce", utc=True)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Live Items", f"{len(live_events):,}")
c2.metric("Countries / Sources", f"{live_events['country'].nunique():,}")
c3.metric("High+ Severity", f"{live_events['severity'].isin(['High', 'Critical']).sum():,}")
c4.metric("Event Types", f"{live_events['event'].nunique():,}")

st.divider()

map_df = live_events.dropna(subset=["latitude", "longitude"]).copy()
if map_df.empty:
    st.info("No events could be mapped to country-level coordinates.")
else:
    map_df["severity_value"] = map_df["severity"].map(
        {"Low": 25, "Medium": 45, "High": 70, "Critical": 90}
    ).fillna(20)
    map_df["color"] = map_df["severity"].map(
        {
            "Low": [52, 199, 89, 170],
            "Medium": [255, 214, 10, 180],
            "High": [255, 107, 53, 190],
            "Critical": [255, 45, 85, 210],
        }
    )

    layer = pdk.Layer(
        "ScatterplotLayer",
        data=map_df,
        get_position=["longitude", "latitude"],
        get_radius="severity_value * 2200",
        get_fill_color="color",
        pickable=True,
        opacity=0.75,
        stroked=True,
        filled=True,
        line_width_min_pixels=1,
    )
    view_state = pdk.ViewState(longitude=0, latitude=20, zoom=1.35, pitch=0, bearing=0)
    deck = pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        tooltip={
            "html": "<b>{country}</b><br/>{event}<br/>{severity}<br/>{title}",
            "style": {"backgroundColor": "#101827", "color": "white"},
        },
    )
    st.pydeck_chart(deck)
    st.caption("Map points use GTD-derived country centroids when GDELT articles do not provide precise coordinates.")

st.divider()

st.subheader("Recent Events")
severity_filter = st.multiselect(
    "Severity",
    ["Low", "Medium", "High", "Critical"],
    default=["Low", "Medium", "High", "Critical"],
)
filtered = live_events[live_events["severity"].isin(severity_filter)].copy()
filtered["date"] = filtered["date"].dt.strftime("%Y-%m-%d %H:%M UTC")

table = filtered[
    ["country", "location", "event", "date", "source", "latitude", "longitude", "severity", "url", "title"]
].rename(
    columns={
        "country": "Country",
        "location": "Location",
        "event": "Event",
        "date": "Date",
        "source": "Source",
        "latitude": "Latitude",
        "longitude": "Longitude",
        "severity": "Severity",
        "url": "URL",
        "title": "Headline",
    }
)

st.dataframe(
    table,
    width="stretch",
    hide_index=True,
    column_config={
        "URL": st.column_config.LinkColumn("Source Link"),
        "Latitude": st.column_config.NumberColumn(format="%.3f"),
        "Longitude": st.column_config.NumberColumn(format="%.3f"),
    },
)

csv = table.to_csv(index=False)
st.download_button(
    "📥 Download Live Feed CSV",
    csv,
    file_name="live_intelligence_feed.csv",
    mime="text/csv",
)

st.info(
    "Severity is keyword-based and intended for triage. Analysts should corroborate events before drawing conclusions."
)
