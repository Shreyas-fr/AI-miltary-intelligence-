"""
44_🏗️_Military_Assets.py

Military Asset Overlay + Redeployment Simulation (What-If Analysis).

New in this version:
  - Simulation & Redeployment Command panel
  - Haversine ETA calculator with per-asset-type speed heuristics
  - Threat vs. Asset Balance: GTD incident counts within threat radius
    at origin vs. simulated destination
  - Force Allocation Score (% of regional threat events covered)
  - Urgency Recommendation (Airlift vs. Standard Transit)
  - PyDeck ArcLayer trajectory from origin → destination
  - Status-based map color overrides
"""

import json
import math
import os

import pandas as pd
import pydeck as pdk
import streamlit as st

from utils.auth import require_auth
from utils.ui_components import st_custom_kpi_card

require_auth(['Analyst', 'Commander'])

st.set_page_config(page_title="Military Assets & Redeployment Sim", page_icon="🏗️", layout="wide")


def load_css(file_name):
    if os.path.exists(file_name):
        with open(file_name, encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


load_css("assets/style.css")

# ---------------------------------------------------------------------------
# Asset speed heuristics (km/h) for ETA — used in simulation
# ---------------------------------------------------------------------------
ASSET_SPEEDS_KMH = {
    "Airbase":       800,   # tactical airlift / escort
    "Naval Base":     55,   # carrier group cruise speed
    "Army Base":      80,   # mechanised column (road)
    "Radar Station": 120,   # helicopter / light transport
    "Port":           40,   # harbour tug / barge convoy
}

# ---------------------------------------------------------------------------
# Simulated status color overrides for the map
# ---------------------------------------------------------------------------
STATUS_COLOR_OVERRIDE = {
    "Active":      None,          # use asset-type colour
    "Dispatched":  [255, 165, 0, 230],   # amber
    "Maintenance": [100, 100, 100, 180], # grey
    "Destroyed":   [220, 50, 50, 160],   # red
}

# Base color map (used when status is Active)
COLOR_MAP = {
    "Airbase":        [0, 229, 255, 220],
    "Naval Base":     [0, 123, 255, 220],
    "Army Base":      [52, 199, 89,  220],
    "Radar Station":  [255, 214, 10, 220],
    "Port":           [255, 107, 53, 220],
}

THREAT_COLOR_MAP = {
    "Airbase":        [0, 229, 255, 35],
    "Naval Base":     [0, 123, 255, 35],
    "Army Base":      [52, 199, 89,  35],
    "Radar Station":  [255, 214, 10, 35],
    "Port":           [255, 107, 53, 35],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance between two points in kilometres."""
    R = 6371.0
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    Δφ = math.radians(lat2 - lat1)
    Δλ = math.radians(lon2 - lon1)
    a = math.sin(Δφ / 2) ** 2 + math.cos(φ1) * math.cos(φ2) * math.sin(Δλ / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def format_eta(hours: float) -> str:
    """Format hours as a human-readable ETA string."""
    if hours < 1:
        return f"{int(hours * 60)} min"
    d, h = divmod(int(hours), 24)
    parts = []
    if d:
        parts.append(f"{d}d")
    if h or not d:
        parts.append(f"{h}h")
    return " ".join(parts)


@st.cache_data(ttl=300)
def load_gtd_geo() -> pd.DataFrame:
    """Load a lightweight lat/lon subset of GTD for threat coverage queries."""
    try:
        from utils.data_loader import query_data
        return query_data(
            "SELECT latitude, longitude FROM 'data/globalterrorism.csv' "
            "WHERE latitude IS NOT NULL AND longitude IS NOT NULL"
        )
    except Exception:
        return pd.DataFrame(columns=["latitude", "longitude"])


def count_threats_within_radius(
    center_lat: float, center_lon: float, radius_km: float, gtd_df: pd.DataFrame
) -> int:
    """Count GTD incidents within radius_km of the given point."""
    if gtd_df.empty:
        return 0
    # Haversine vectorised via math approximation for speed
    lat_r, lon_r = math.radians(center_lat), math.radians(center_lon)
    lats = gtd_df["latitude"].astype(float).values
    lons = gtd_df["longitude"].astype(float).values
    dlat = [math.radians(la - center_lat) for la in lats]
    dlon = [math.radians(lo - center_lon) for lo in lons]
    dists = []
    for i in range(len(lats)):
        a = (math.sin(dlat[i] / 2) ** 2
             + math.cos(lat_r) * math.cos(math.radians(lats[i]))
             * math.sin(dlon[i] / 2) ** 2)
        dists.append(6371 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))
    return sum(1 for d in dists if d <= radius_km)


@st.cache_data
def load_military_assets(filepath: str = "data/military_assets.json") -> pd.DataFrame:
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    return pd.DataFrame(data)


# ---------------------------------------------------------------------------
# Page Header
# ---------------------------------------------------------------------------
st.title("🏗️ | Military Asset Overlay & Redeployment Simulator")
st.markdown("##### Simulated military installations with threat radius analysis and What-If redeployment simulation.")

# ---------------------------------------------------------------------------
# Sidebar Filters
# ---------------------------------------------------------------------------
st.sidebar.header("Filters")

asset_types = ["Airbase", "Naval Base", "Army Base", "Radar Station", "Port"]
selected_types = st.sidebar.multiselect("Asset Type", options=asset_types, default=asset_types)

threat_radius_km = st.sidebar.slider("Threat Radius (km)", min_value=50, max_value=500, value=200, step=10)
show_threat_overlay = st.sidebar.checkbox("Show Threat Overlay", value=True)

df = load_military_assets()

owners = sorted(df["owner"].dropna().unique())
selected_owners = st.sidebar.multiselect("Asset Owner", options=owners, default=owners)

# Apply filters
filtered_df = df.copy()
if selected_owners:
    filtered_df = filtered_df[filtered_df["owner"].isin(selected_owners)]
else:
    filtered_df = filtered_df.iloc[0:0]
if selected_types:
    filtered_df = filtered_df[filtered_df["type"].isin(selected_types)]
else:
    filtered_df = filtered_df.iloc[0:0]

# ---------------------------------------------------------------------------
# KPI Metrics
# ---------------------------------------------------------------------------
st.markdown("### Asset Metrics")
type_counts = filtered_df["type"].value_counts().to_dict()
kpi_cols = st.columns(6)
with kpi_cols[0]: st_custom_kpi_card("Total Assets", str(len(filtered_df)), "Visible", "📦")
for i, atype in enumerate(asset_types, start=1):
    with kpi_cols[i]: st_custom_kpi_card(atype, str(type_counts.get(atype, 0)), "", "🛡️")

st.markdown("---")

# ---------------------------------------------------------------------------
# Simulation State initialisation
# ---------------------------------------------------------------------------
if "sim_active" not in st.session_state:
    st.session_state["sim_active"] = False
if "sim_asset_name" not in st.session_state:
    st.session_state["sim_asset_name"] = None
if "sim_lat" not in st.session_state:
    st.session_state["sim_lat"] = None
if "sim_lon" not in st.session_state:
    st.session_state["sim_lon"] = None
if "sim_status" not in st.session_state:
    st.session_state["sim_status"] = "Active"

# Build the working dataframe for the map (may include simulation overrides)
map_df = filtered_df.copy()

sim_asset_row = None  # the row being simulated
if st.session_state["sim_active"] and st.session_state["sim_asset_name"]:
    mask = map_df["name"] == st.session_state["sim_asset_name"]
    if mask.any():
        sim_asset_row = map_df[mask].iloc[0].to_dict()
        map_df.loc[mask, "lat"]    = st.session_state["sim_lat"]
        map_df.loc[mask, "lon"]    = st.session_state["sim_lon"]
        map_df.loc[mask, "status"] = st.session_state["sim_status"]

# Assign colors (status can override)
def resolve_color(row):
    override = STATUS_COLOR_OVERRIDE.get(row["status"])
    return override if override else (COLOR_MAP.get(row["type"], [200, 200, 200, 200]))

map_df["color"]        = map_df.apply(resolve_color, axis=1)
map_df["threat_color"] = map_df["type"].map(THREAT_COLOR_MAP)
map_df["radius_m"]     = threat_radius_km * 1000

# ---------------------------------------------------------------------------
# Map
# ---------------------------------------------------------------------------
if not map_df.empty:
    layers = []

    if show_threat_overlay:
        layers.append(pdk.Layer(
            "ScatterplotLayer",
            data=map_df,
            get_position=["lon", "lat"],
            get_radius="radius_m",
            get_fill_color="threat_color",
            get_line_color="color",
            line_width_min_pixels=1,
            stroked=True, filled=True, pickable=False,
        ))

    layers.append(pdk.Layer(
        "ScatterplotLayer",
        data=map_df,
        get_position=["lon", "lat"],
        get_fill_color="color",
        get_radius=22000,
        radius_min_pixels=6, radius_max_pixels=16,
        pickable=True,
    ))

    # Arc trajectory layer for simulation
    if st.session_state["sim_active"] and sim_asset_row:
        arc_data = pd.DataFrame([{
            "from_lat": sim_asset_row["lat"],
            "from_lon": sim_asset_row["lon"],
            "to_lat":   st.session_state["sim_lat"],
            "to_lon":   st.session_state["sim_lon"],
        }])
        layers.append(pdk.Layer(
            "ArcLayer",
            data=arc_data,
            get_source_position=["from_lon", "from_lat"],
            get_target_position=["to_lon", "to_lat"],
            get_source_color=[255, 165, 0, 200],
            get_target_color=[0, 229, 255, 200],
            auto_highlight=True,
            width_min_pixels=3,
            pickable=False,
        ))

    view_state = pdk.ViewState(
        latitude=map_df["lat"].mean(),
        longitude=map_df["lon"].mean(),
        zoom=2, pitch=30, bearing=0,
    )

    tooltip_html = {
        "html": (
            "<b>Asset Name:</b> {name}<br/>"
            "<b>Type:</b> {type}<br/>"
            "<b>Owner:</b> {owner}<br/>"
            "<b>Host Country:</b> {country}<br/>"
            "<b>Status:</b> {status}"
        ),
        "style": {"backgroundColor": "#1A1A2E", "color": "white", "fontFamily": "Outfit, sans-serif", "padding": "8px"},
    }

    with st.spinner("Rendering asset overlay map..."):
        st.pydeck_chart(pdk.Deck(
            map_style=pdk.map_styles.CARTO_DARK,
            layers=layers,
            initial_view_state=view_state,
            tooltip=tooltip_html,
        ), use_container_width=True)
else:
    st.warning("No military assets match the selected filters.")

st.markdown("---")

# ---------------------------------------------------------------------------
# 🔀 Redeployment Simulation Panel
# ---------------------------------------------------------------------------
st.markdown("## 🔀 Redeployment Simulation — What-If Analysis")
st.markdown(
    "Simulate moving an asset to a new position or changing its operational status. "
    "The map, ETA, and Threat Balance update automatically."
)

sim_col, results_col = st.columns([1, 1], gap="large")

with sim_col:
    st.markdown("#### ⚙️ Simulation Command")

    asset_names = filtered_df["name"].tolist()
    selected_asset = st.selectbox(
        "Select Asset to Redeploy",
        options=asset_names,
        key="sim_select_asset",
    )

    asset_row = filtered_df[filtered_df["name"] == selected_asset].iloc[0]
    orig_lat, orig_lon = float(asset_row["lat"]), float(asset_row["lon"])
    asset_type = asset_row["type"]

    # Quick-fill hotspot destinations
    HOTSPOTS = {
        "— Custom —":              (None, None),
        "🇺🇦 Kyiv, Ukraine":       (50.45, 30.52),
        "🇸🇾 Damascus, Syria":     (33.51, 36.29),
        "🇾🇪 Aden, Yemen":         (12.78, 45.04),
        "🇵🇰 Islamabad, Pakistan": (33.72, 73.06),
        "🇳🇬 Maiduguri, Nigeria":  (11.85, 13.16),
        "🇸🇴 Mogadishu, Somalia":  (2.05,  45.34),
        "🇮🇶 Baghdad, Iraq":       (33.34, 44.40),
        "🇲🇱 Timbuktu, Mali":      (16.77, -3.00),
        "🌊 South China Sea":      (12.00, 114.00),
        "🇵🇭 Manila, Philippines": (14.60, 120.98),
    }

    hotspot = st.selectbox("Quick-Fill Destination", options=list(HOTSPOTS.keys()), key="sim_hotspot")
    if HOTSPOTS[hotspot][0] is not None:
        default_lat, default_lon = HOTSPOTS[hotspot]
    else:
        default_lat, default_lon = orig_lat, orig_lon

    dest_lat = st.number_input(
        "Destination Latitude", min_value=-90.0, max_value=90.0,
        value=float(default_lat), step=0.1, format="%.3f", key="sim_lat_input"
    )
    dest_lon = st.number_input(
        "Destination Longitude", min_value=-180.0, max_value=180.0,
        value=float(default_lon), step=0.1, format="%.3f", key="sim_lon_input"
    )

    sim_status = st.selectbox(
        "Operational Status",
        options=["Active", "Dispatched", "Maintenance", "Destroyed"],
        index=0, key="sim_status_select"
    )

    col_run, col_reset = st.columns(2)
    with col_run:
        if st.button("▶ Run Simulation", use_container_width=True, type="primary"):
            st.session_state["sim_active"]     = True
            st.session_state["sim_asset_name"] = selected_asset
            st.session_state["sim_lat"]        = dest_lat
            st.session_state["sim_lon"]        = dest_lon
            st.session_state["sim_status"]     = sim_status
            st.rerun()
    with col_reset:
        if st.button("↺ Reset", use_container_width=True):
            st.session_state["sim_active"]     = False
            st.session_state["sim_asset_name"] = None
            st.session_state["sim_lat"]        = None
            st.session_state["sim_lon"]        = None
            st.session_state["sim_status"]     = "Active"
            st.rerun()

with results_col:
    st.markdown("#### 📊 Simulation Results")

    if not st.session_state["sim_active"] or st.session_state["sim_asset_name"] != selected_asset:
        st.info("Configure the controls on the left and click **▶ Run Simulation** to see results.")
    else:
        sim_dest_lat = st.session_state["sim_lat"]
        sim_dest_lon = st.session_state["sim_lon"]
        sim_speed    = ASSET_SPEEDS_KMH.get(asset_type, 200)

        # Distance & ETA
        dist_km = haversine_km(orig_lat, orig_lon, sim_dest_lat, sim_dest_lon)
        eta_h   = dist_km / sim_speed

        # Threat Balance (GTD incidents within radius at origin vs. destination)
        gtd_geo = load_gtd_geo()
        threats_origin = count_threats_within_radius(orig_lat, orig_lon, threat_radius_km, gtd_geo)
        threats_dest   = count_threats_within_radius(sim_dest_lat, sim_dest_lon, threat_radius_km, gtd_geo)
        total_threats  = max(1, threats_origin + threats_dest)  # avoid div-by-zero
        force_alloc    = (threats_dest / max(1, threats_origin + threats_dest)) * 100

        # Urgency recommendation
        if threats_dest > threats_origin * 1.5:
            urgency = ("🔴 **CRITICAL** — Destination zone is significantly hotter than origin. "
                       "Consider **airlift** to minimise exposure window.")
        elif threats_dest > threats_origin:
            urgency = "🟠 **ELEVATED** — Destination has higher threat density. Standard transit acceptable."
        elif threats_dest == 0:
            urgency = "🟢 **LOW** — Destination zone has no recorded historical incidents."
        else:
            urgency = "🟢 **STABLE** — Destination threat level is equal to or lower than origin."

        # KPI cards
        k1, k2 = st.columns(2)
        with k1:
            st_custom_kpi_card("Distance", f"{dist_km:,.0f} km", f"Speed: {sim_speed} km/h", "🛣️")
        with k2:
            st_custom_kpi_card("Est. ETA", format_eta(eta_h), asset_type, "⏱️")

        k3, k4 = st.columns(2)
        with k3:
            st_custom_kpi_card("Threats at Origin", f"{threats_origin:,}", f"Within {threat_radius_km} km", "📍")
        with k4:
            st_custom_kpi_card("Threats at Dest.", f"{threats_dest:,}", f"Within {threat_radius_km} km", "🎯")

        # Force allocation bar
        st.markdown("**Force Allocation Score** — % of combined regional threat exposure at destination")
        st.progress(min(100, int(force_alloc)) / 100, text=f"{force_alloc:.1f}% of regional threat covered")

        # Urgency
        st.markdown(f"**Tactical Urgency:** {urgency}")

        # Status indicator
        status_color = {
            "Active":      "🟢",
            "Dispatched":  "🟠",
            "Maintenance": "⚫",
            "Destroyed":   "🔴",
        }.get(sim_status, "⚪")
        st.markdown(f"**Simulated Status:** {status_color} `{sim_status}`")

        # Summary card
        st.success(
            f"**{selected_asset}** redeployed from "
            f"`{orig_lat:.3f}, {orig_lon:.3f}` → "
            f"`{sim_dest_lat:.3f}, {sim_dest_lon:.3f}` — "
            f"ETA **{format_eta(eta_h)}** at {sim_speed} km/h"
        )

st.markdown("---")

# ---------------------------------------------------------------------------
# Asset Table
# ---------------------------------------------------------------------------
st.subheader("Filtered Military Assets")
if not filtered_df.empty:
    display_df = filtered_df[["name", "type", "owner", "country", "status", "lat", "lon"]]
    st.dataframe(
        display_df,
        column_config={
            "name":    st.column_config.TextColumn("Asset Name", width="large"),
            "type":    st.column_config.TextColumn("Facility Type", width="medium"),
            "owner":   st.column_config.TextColumn("Operating Nation", width="medium"),
            "country": st.column_config.TextColumn("Host Country", width="medium"),
            "status":  st.column_config.TextColumn("Status"),
            "lat":     st.column_config.NumberColumn("Latitude", format="%.4f"),
            "lon":     st.column_config.NumberColumn("Longitude", format="%.4f"),
        },
        use_container_width=True,
        hide_index=True,
    )
else:
    st.dataframe(pd.DataFrame(), use_container_width=True)

st.caption(
    "⚠️ **Data Disclaimer:** This is a simulated demonstration layer. "
    "Actual military installation coordinates are classified. "
    "ETA calculations use heuristic speed values for illustrative purposes only."
)
