import streamlit as st
import numpy as np
from utils.ui_components import st_custom_kpi_card
import pydeck as pdk
import pandas as pd
import os
from utils.data_loader import query_data, load_combined
from utils.hotspot_utils import compute_tsi, cluster_hotspots

st.set_page_config(page_title="Hotspot Detection", page_icon="🎯", layout="wide")


def load_css(file_name):
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


load_css("assets/style.css")

st.title("🎯 | Spatial Hotspot Detection")
st.markdown(
    "##### DBSCAN clustering (haversine distance) over incident geometry, "
    "ranked by a non-linear Threat Severity Index (TSI)."
)

st.sidebar.header("Clustering Parameters")
eps_km = st.sidebar.slider(
    "Cluster radius (km)", 25, 500, 100, step=25,
    help="Max distance between two incidents to be grouped into the same hotspot.",
)
min_samples = st.sidebar.slider("Minimum incidents per hotspot", 5, 50, 15, step=5, help="Minimum incidents needed to define a hotspot.")

st.sidebar.markdown("---")
st.sidebar.subheader("Data Source")
use_combined = st.sidebar.checkbox(
    "Include Live Intelligence Events",
    value=False,
    help="Augment GTD historical data with events stored in the Intelligence Database."
)

# -----------------------------------------------
# Load only what's needed, filtered to valid coords
# -----------------------------------------------
if use_combined:
    with st.spinner("Loading GTD + Live Intelligence data..."):
        df = load_combined()
        df = df.dropna(subset=["latitude", "longitude"]).copy()
    live_tag = " (GTD + Live)"
else:
    df = query_data(
        """
        SELECT latitude, longitude, nkill, nwound, success, iyear, country_txt, region_txt
        FROM 'data/globalterrorism.csv'
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
        """
    )
    live_tag = " (GTD only)"

df = compute_tsi(df)

with st.spinner("Running DBSCAN over incident geometry..."):
    df_clustered, hotspots = cluster_hotspots(df, eps_km=eps_km, min_samples=min_samples)

# Persist for the Forecasting page
st.session_state["hotspot_df"] = df_clustered
st.session_state["hotspot_summary"] = hotspots

import gc
gc.collect()

c1, c2, c3 = st.columns(3)
with c1: st_custom_kpi_card("Hotspots Detected", f"{len(hotspots):,}", "Identified via DBSCAN", "🎯")
with c2: st_custom_kpi_card("Incidents in Hotspots", f"{len(df_clustered[df_clustered['cluster'] != -1]):,}", "Clustered events", "🔗")
with c3: st_custom_kpi_card("Noise (isolated incidents)", f"{(df_clustered['cluster'] == -1).sum():,}", "Too isolated for hotspot", "📉")

st.divider()

from utils.migration import (
    compute_window_centroids,
    compute_migration_vectors,
    predict_future_positions,
)

st.sidebar.markdown("---")
st.sidebar.subheader("Predictive Migration Analysis")
show_migration = st.sidebar.checkbox("Show Hotspot Migration Vectors", value=False)
window_years = st.sidebar.slider("Migration Window (Years)", 3, 10, 5, step=1, help="Time window to calculate hotspot centroid migrations.")

# -----------------------------------------------
# Map — hexbin height/color driven by aggregated TSI
# -----------------------------------------------
plot_df = df_clustered[df_clustered["cluster"] != -1]

if plot_df.empty:
    st.warning("No hotspots found with these parameters — try a larger radius or lower minimum incidents.")
else:
    layers = []

    hex_layer = pdk.Layer(
        "HexagonLayer",
        data=plot_df,
        get_position=["longitude", "latitude"],
        radius=int(eps_km * 300),
        elevation_scale=40,
        elevation_range=[0, 3000],
        pickable=True,
        extruded=True,
        get_weight="tsi",
        color_range=[
            [255, 255, 178], [254, 204, 92], [253, 141, 60],
            [240, 59, 32], [189, 0, 38],
        ],
    )
    layers.append(hex_layer)

    migration_data = []
    if show_migration:
        centroids_df = compute_window_centroids(df, window_years=window_years, eps_km=eps_km, min_samples=min_samples)
        m_vectors = compute_migration_vectors(centroids_df)
        p_vectors = predict_future_positions(m_vectors)

        all_vectors = m_vectors + p_vectors
        if all_vectors:
            arc_layer = pdk.Layer(
                "ArcLayer",
                data=all_vectors,
                get_source_position=["from_lon", "from_lat"],
                get_target_position=["to_lon", "to_lat"],
                get_source_color=[0, 229, 255, 200],
                get_target_color=[255, 45, 85, 255],
                get_width=4,
                pickable=True,
            )
            layers.append(arc_layer)
            migration_data = all_vectors

    view_state = pdk.ViewState(longitude=0, latitude=20, zoom=1.5, pitch=0, bearing=0)
    r = pdk.Deck(
        layers=layers,
        initial_view_state=view_state,
        tooltip={"html": "<b>Hotspot Data / Migration Vector</b>"},
    )
    with st.spinner("Rendering predictive map..."):
        st.pydeck_chart(r, use_container_width=True)

    if show_migration and migration_data:
        st.subheader("🔮 Predictive Hotspot Migration Vectors")
        mig_df = pd.DataFrame(migration_data)
        st.dataframe(
            mig_df[[
                "window_from", "window_to", "from_lat", "from_lon",
                "to_lat", "to_lon", "drift_km"
            ]].rename(columns={
                "window_from": "From Period", "window_to": "To Period",
                "from_lat": "Origin Lat", "from_lon": "Origin Lon",
                "to_lat": "Target Lat", "to_lon": "Target Lon",
                "drift_km": "Drift Distance (km)"
            }),
            use_container_width=True,
            hide_index=True
        )

st.divider()

# -----------------------------------------------
# Ranked hotspot table
# -----------------------------------------------
st.subheader("Top Threat Hotspots (ranked by total TSI)")

if hotspots.empty:
    st.info("No hotspots to display yet — adjust the clustering parameters in the sidebar.")
else:
    display_cols = ["rank", "countries", "incidents", "total_tsi", "avg_tsi", "centroid_lat", "centroid_lon"]
    st.dataframe(
        hotspots[display_cols]
        .head(20)
        .rename(
            columns={
                "rank": "Rank", "countries": "Dominant Country", "incidents": "Incidents",
                "total_tsi": "Total TSI", "avg_tsi": "Avg TSI",
                "centroid_lat": "Lat", "centroid_lon": "Lon",
            }
        ),
        use_container_width=True,
        hide_index=True
    )

st.info("👉 Go to **Hotspot Forecasting** to project attack trends for any hotspot above.")
