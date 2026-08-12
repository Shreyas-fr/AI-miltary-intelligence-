import json
import os
import streamlit as st

# --- Authentication & Role Check ---
from utils.auth import require_auth
require_auth(['Analyst', 'Commander'])
# -----------------------------------

import pandas as pd
import pydeck as pdk
from utils.ui_components import st_custom_kpi_card

st.set_page_config(page_title="Military Assets", page_icon="🏗️", layout="wide")


def load_css(file_name):
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


load_css("assets/style.css")

st.title("🏗️ | Military Asset Overlay")
st.markdown("##### Simulated military installations with threat radius analysis.")

# Color mapping for asset types
COLOR_MAP = {
    "Airbase": [0, 229, 255, 200],
    "Naval Base": [0, 123, 255, 200],
    "Army Base": [52, 199, 89, 200],
    "Radar Station": [255, 214, 10, 200],
    "Port": [255, 107, 53, 200],
}

THREAT_COLOR_MAP = {
    "Airbase": [0, 229, 255, 40],
    "Naval Base": [0, 123, 255, 40],
    "Army Base": [52, 199, 89, 40],
    "Radar Station": [255, 214, 10, 40],
    "Port": [255, 107, 53, 40],
}


@st.cache_data
def load_military_assets(filepath: str = "data/military_assets.json") -> pd.DataFrame:
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    return pd.DataFrame(data)


# -----------------------------------------------
# Sidebar Filters
# -----------------------------------------------
st.sidebar.header("Filters")

asset_types = ["Airbase", "Naval Base", "Army Base", "Radar Station", "Port"]
selected_types = st.sidebar.multiselect(
    "Asset Type",
    options=asset_types,
    default=asset_types,
)

threat_radius_km = st.sidebar.slider(
    "Threat Radius (km)",
    min_value=50,
    max_value=500,
    value=200,
    step=10,
)

show_threat_overlay = st.sidebar.checkbox(
    "Show Threat Overlay",
    value=True,
)

df = load_military_assets()

# New Owner Filter
owners = sorted(df["owner"].dropna().unique())
selected_owners = st.sidebar.multiselect(
    "Asset Owner (Operator)",
    options=owners,
    default=owners,
)

# Filter dataframe
filtered_df = df.copy()

if selected_owners:
    filtered_df = filtered_df[filtered_df["owner"].isin(selected_owners)]
else:
    filtered_df = filtered_df.iloc[0:0]

if selected_types:
    filtered_df = filtered_df[filtered_df["type"].isin(selected_types)]
else:
    filtered_df = filtered_df.iloc[0:0]

# KPI Metrics
st.markdown("### Asset Metrics")
total_count = len(filtered_df)
type_counts = filtered_df["type"].value_counts().to_dict()

kpi_cols = st.columns(6)
with kpi_cols[0]: st_custom_kpi_card("Total Assets", str(total_count), "Visible", "📦")
for i, atype in enumerate(asset_types, start=1):
    with kpi_cols[i]: st_custom_kpi_card(atype, str(type_counts.get(atype, 0)), "", "🛡️")

st.markdown("---")

# Map visualization
if not filtered_df.empty:
    filtered_df["color"] = filtered_df["type"].map(COLOR_MAP)
    filtered_df["threat_color"] = filtered_df["type"].map(THREAT_COLOR_MAP)
    filtered_df["radius_m"] = threat_radius_km * 1000

    layers = []

    if show_threat_overlay:
        threat_layer = pdk.Layer(
            "ScatterplotLayer",
            data=filtered_df,
            get_position=["lon", "lat"],
            get_radius="radius_m",
            get_fill_color="threat_color",
            get_line_color="color",
            line_width_min_pixels=1,
            stroked=True,
            filled=True,
            pickable=False,
        )
        layers.append(threat_layer)

    asset_layer = pdk.Layer(
        "ScatterplotLayer",
        data=filtered_df,
        get_position=["lon", "lat"],
        get_fill_color="color",
        get_radius=20000,
        radius_min_pixels=6,
        radius_max_pixels=15,
        pickable=True,
    )
    layers.append(asset_layer)

    view_state = pdk.ViewState(
        latitude=filtered_df["lat"].mean(),
        longitude=filtered_df["lon"].mean(),
        zoom=2,
        pitch=0,
        bearing=0,
    )

    tooltip_html = {
        "html": "<b>Asset Name:</b> {name}<br/>"
        "<b>Type:</b> {type}<br/>"
        "<b>Owner:</b> {owner}<br/>"
        "<b>Host Country:</b> {country}<br/>"
        "<b>Status:</b> {status}",
        "style": {"backgroundColor": "#1E1E1E", "color": "white", "fontFamily": "Outfit, sans-serif"},
    }

    r = pdk.Deck(
        map_style=pdk.map_styles.CARTO_DARK,
        layers=layers,
        initial_view_state=view_state,
        tooltip=tooltip_html,
    )

    with st.spinner("Rendering asset overlay map..."):
        st.pydeck_chart(r, use_container_width=True)
else:
    st.warning("No military assets match the selected filters.")

st.markdown("---")

# Asset Table
st.subheader("Filtered Military Assets")
if not filtered_df.empty:
    display_df = filtered_df[["name", "type", "owner", "country", "status", "lat", "lon"]]
    
    st.dataframe(
        display_df,
        column_config={
            "name": st.column_config.TextColumn("Asset Name", width="large"),
            "type": st.column_config.TextColumn("Facility Type", width="medium"),
            "owner": st.column_config.TextColumn("Operating Nation", width="medium"),
            "country": st.column_config.TextColumn("Host Country", width="medium"),
            "status": st.column_config.TextColumn("Status"),
            "lat": st.column_config.NumberColumn("Latitude", format="%.4f"),
            "lon": st.column_config.NumberColumn("Longitude", format="%.4f"),
        },
        use_container_width=True, 
        hide_index=True
    )
else:
    st.dataframe(pd.DataFrame(), use_container_width=True)

st.caption("⚠️ **Data Disclaimer:** This is a simulated demonstration layer. Actual military installation coordinates are classified. The 'Operating Nation' (Ownership) assignments are illustrative estimates based on general public knowledge for UI demonstration purposes and do not represent verified or official defense intelligence.")
