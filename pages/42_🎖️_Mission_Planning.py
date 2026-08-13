import os
import json
import numpy as np
import pandas as pd
import plotly.express as px
import pydeck as pdk
import streamlit as st

# --- Authentication & Role Check ---
from utils.auth import require_auth
require_auth(['Analyst', 'Commander'])
# -----------------------------------


from utils.data_loader import load_data, query_data
from utils.intelligence import compute_country_risk
from utils.recommendations import generate_recommendations, priority_color
from utils.tsi import tsi_label
from utils.pdf_export import generate_mission_brief_pdf
from utils.ui_components import st_custom_kpi_card

st.set_page_config(
    page_title="Mission Planning",
    page_icon="🎖️",
    layout="wide"
)


# Load CSS
def load_css(file_name: str) -> None:
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


load_css("assets/style.css")

# Title & Subtitle
st.title("🎖️ | Mission Planning Simulator")
st.markdown("##### Location-based threat assessment for operational planning.")

st.markdown('<div style="margin-top:0.75rem"></div>', unsafe_allow_html=True)

# -----------------------------------------------
# Sidebar Inputs
# -----------------------------------------------
st.sidebar.header("Mission Parameters")


@st.cache_data(show_spinner=False)
def get_countries_and_centroids() -> pd.DataFrame:
    df_c = query_data(
        """
        SELECT country_txt, 
               MEDIAN(latitude) as med_lat, 
               MEDIAN(longitude) as med_lon,
               COUNT(*) as incident_count
        FROM 'data/globalterrorism.csv' 
        WHERE country_txt IS NOT NULL 
          AND latitude IS NOT NULL 
          AND longitude IS NOT NULL
        GROUP BY country_txt
        ORDER BY country_txt
        """
    )
    return df_c

country_df = get_countries_and_centroids()
countries = country_df["country_txt"].tolist()

# Handle initial state
if "mission_lat" not in st.session_state:
    st.session_state.mission_lat = 33.3152 # Baghdad default
if "mission_lon" not in st.session_state:
    st.session_state.mission_lon = 44.3661 # Baghdad default
if "selected_country" not in st.session_state:
    default_idx = countries.index("Iraq") if "Iraq" in countries else 0
    st.session_state.selected_country = countries[default_idx]

def on_country_change():
    chosen = st.session_state.selected_country
    row = country_df[country_df["country_txt"] == chosen]
    if not row.empty:
        st.session_state.mission_lat = float(row.iloc[0]["med_lat"])
        st.session_state.mission_lon = float(row.iloc[0]["med_lon"])

selected_country = st.sidebar.selectbox(
    "Country", 
    countries, 
    key="selected_country",
    on_change=on_country_change,
    help="Set the initial map view to a country."
)

row = country_df[country_df["country_txt"] == selected_country]
incident_count = int(row.iloc[0]["incident_count"]) if not row.empty else 0
if incident_count < 10:
    st.sidebar.caption("⚠️ *Approximate centroid based on limited historical data.*")

lat = st.sidebar.number_input("Latitude", key="mission_lat", format="%.4f", help="Operation center latitude.")
lon = st.sidebar.number_input("Longitude", key="mission_lon", format="%.4f", help="Operation center longitude.")
radius_km = st.sidebar.slider("Mission Radius (km)", min_value=50, max_value=500, value=200, step=10, help="Operational radius around the center coordinates.")


# -----------------------------------------------
# Haversine Distance Calculation
# -----------------------------------------------
def haversine_km(lat1: float, lon1: float, lat2_arr: np.ndarray, lon2_arr: np.ndarray) -> np.ndarray:
    """Calculate Haversine great-circle distance between point (lat1, lon1) and arrays of coordinates."""
    R = 6371.0  # Earth radius in km
    phi1 = np.radians(lat1)
    phi2 = np.radians(lat2_arr)
    dphi = np.radians(lat2_arr - lat1)
    dlambda = np.radians(lon2_arr - lon1)

    a = np.sin(dphi / 2.0) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlambda / 2.0) ** 2
    c = 2.0 * np.arctan2(np.sqrt(a), np.sqrt(1.0 - a))
    return R * c


# -----------------------------------------------
# Data Fetching & Distance Filtering
# -----------------------------------------------
safe_country = selected_country.replace("'", "''")
country_incidents = query_data(
    f"SELECT * FROM 'data/globalterrorism.csv' WHERE latitude IS NOT NULL AND longitude IS NOT NULL AND country_txt = '{safe_country}'"
)

@st.cache_data(show_spinner=False)
def load_military_assets(filepath: str = "data/military_assets.json") -> pd.DataFrame:
    if not os.path.exists(filepath):
        return pd.DataFrame()
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    return pd.DataFrame(data)

assets_df = load_military_assets()

if not country_incidents.empty:
    distances = haversine_km(
        lat, lon, country_incidents["latitude"].values, country_incidents["longitude"].values
    )
    country_incidents["distance_km"] = distances
    nearby_df = country_incidents[country_incidents["distance_km"] <= radius_km].sort_values("distance_km").reset_index(drop=True)
    nearby_df["tooltip_title"] = nearby_df["country_txt"] + " Incident"
    city_col = nearby_df["city"].fillna("Unknown") if "city" in nearby_df.columns else "Unknown"
    target_col = nearby_df["target1"].fillna("Unknown") if "target1" in nearby_df.columns else "Unknown"
    nkill_col = nearby_df["nkill"].fillna(0).astype(str) if "nkill" in nearby_df.columns else "0"
    
    nearby_df["tooltip_loc"] = "City: " + city_col
    nearby_df["tooltip_det"] = "Target: " + target_col + "<br/>Fatalities: " + nkill_col
else:
    country_incidents["distance_km"] = pd.Series(dtype=float)
    nearby_df = country_incidents.copy()

if not assets_df.empty and "lat" in assets_df.columns and "lon" in assets_df.columns:
    asset_dists = haversine_km(lat, lon, assets_df["lat"].values, assets_df["lon"].values)
    assets_df["distance_km"] = asset_dists
    nearby_assets_df = assets_df[assets_df["distance_km"] <= radius_km].sort_values("distance_km").reset_index(drop=True)
    
    nearby_assets_df["color"] = nearby_assets_df["type"].apply(
        lambda t: [52, 199, 89, 220] if t == "Airbase" 
        else ([10, 132, 255, 220] if t in ["Naval Base", "Port"] 
        else ([255, 159, 10, 220] if t == "Army Base" 
        else [191, 90, 242, 220]))
    )
    
    def get_eta(row):
        t = row["type"]
        d = row["distance_km"]
        if t == "Airbase": s = 800
        elif t in ["Naval Base", "Port"]: s = 60
        elif t == "Army Base": s = 80
        else: return "N/A"
        hrs = d / s
        if hrs < 1: return f"{int(hrs*60)} min"
        return f"{hrs:.1f} hrs"
        
    nearby_assets_df["eta"] = nearby_assets_df.apply(get_eta, axis=1)

    nearby_assets_df["tooltip_title"] = nearby_assets_df["name"] + " (Allied Asset)"
    nearby_assets_df["tooltip_loc"] = "Host: " + nearby_assets_df["country"].fillna("Unknown").astype(str) + " | ETA: " + nearby_assets_df["eta"].astype(str)
    nearby_assets_df["tooltip_det"] = "Owner: " + nearby_assets_df["owner"].fillna("Unknown").astype(str)

    nearest_asset = assets_df.sort_values("distance_km").iloc[0].to_dict() if not assets_df.empty else None
    if nearest_asset:
        nearest_asset["eta"] = get_eta(nearest_asset)
else:
    nearby_assets_df = pd.DataFrame()
    nearest_asset = None

# Country risk computation
historical_df = load_data()
risk_breakdown = compute_country_risk(selected_country, historical_df)
threat_score = int(risk_breakdown.score)
threat_level, threat_color = tsi_label(threat_score)

# -----------------------------------------------
# 7a. KPI Row
# -----------------------------------------------
kpi1, kpi2, kpi3, kpi4 = st.columns(4)
with kpi1: st_custom_kpi_card("Country Risk Score", f"{risk_breakdown.score} / 100", f"{risk_breakdown.level}", "🛡️")
with kpi2: st_custom_kpi_card("Nearby Incidents (within radius)", f"{len(nearby_df):,}", "Clustered events", "📍")
with kpi3: st_custom_kpi_card("Estimated Threat Level", threat_level, "Local vicinity", "🚨")
with kpi4: st_custom_kpi_card("Assets in Range", f"{len(nearby_assets_df):,}", "Allied military", "🏗️")

st.markdown('<div style="margin-top:1.5rem"></div>', unsafe_allow_html=True)

# -----------------------------------------------
# 7b. Pydeck Map with Mission Location & Radius
# -----------------------------------------------
st.subheader("📍 Operational Map & Threat Radius")

mission_center_df = pd.DataFrame([
    {
        "latitude": lat,
        "longitude": lon,
        "radius_m": radius_km * 1000.0,
        "name": "Mission Center",
    }
])

# Threat Radius Circle Layer (Translucent Red Circle)
circle_layer = pdk.Layer(
    "ScatterplotLayer",
    data=mission_center_df,
    get_position=["longitude", "latitude"],
    get_fill_color=[255, 45, 85, 35],
    get_line_color=[255, 45, 85, 200],
    get_radius="radius_m",
    stroked=True,
    filled=True,
    line_width_min_pixels=2,
    pickable=False,
)

# Mission Center Marker Layer (Solid Red Marker)
center_marker_layer = pdk.Layer(
    "ScatterplotLayer",
    data=mission_center_df,
    get_position=["longitude", "latitude"],
    get_fill_color=[255, 45, 85, 255],
    get_line_color=[255, 255, 255, 255],
    get_radius=2500,
    radius_min_pixels=8,
    radius_max_pixels=16,
    stroked=True,
    line_width_min_pixels=2,
    pickable=True,
)

map_layers = [circle_layer]

# Nearby Historical Incidents Layer (Amber dots)
if not nearby_df.empty:
    incidents_layer = pdk.Layer(
        "ScatterplotLayer",
        data=nearby_df,
        get_position=["longitude", "latitude"],
        get_fill_color=[255, 214, 10, 180],
        get_radius=1500,
        radius_min_pixels=4,
        radius_max_pixels=8,
        pickable=True,
    )
    map_layers.append(incidents_layer)

if not nearby_assets_df.empty:
    assets_layer = pdk.Layer(
        "ScatterplotLayer",
        data=nearby_assets_df,
        get_position=["lon", "lat"],
        get_fill_color="color",
        get_line_color=[255, 255, 255, 255],
        get_radius=2000,
        radius_min_pixels=6,
        radius_max_pixels=12,
        stroked=True,
        line_width_min_pixels=2,
        pickable=True,
    )
    map_layers.append(assets_layer)

map_layers.append(center_marker_layer)

view_state = pdk.ViewState(
    latitude=lat,
    longitude=lon,
    zoom=7,
    pitch=0,
    bearing=0,
)

deck = pdk.Deck(
    layers=map_layers,
    initial_view_state=view_state,
    tooltip={
        "html": "<b>{tooltip_title}</b><br/>{tooltip_loc}<br/>{tooltip_det}",
        "style": {"background": "#0f3460", "color": "white", "font-family": "Outfit, sans-serif"},
    },
)

st.pydeck_chart(deck, use_container_width=True)

st.markdown('<div style="margin-top:1.5rem"></div>', unsafe_allow_html=True)

# -----------------------------------------------
# 7c. Nearby Historical Incidents Table & Charts
# -----------------------------------------------
st.subheader(f"📊 Historical Incidents within {radius_km} km Radius")

if not nearby_df.empty:
    col_mapping = {
        "iyear": "Year",
        "city": "City",
        "attacktype1_txt": "Attack Type",
        "target1": "Target",
        "gname": "Group",
        "nkill": "Fatalities",
        "nwound": "Injuries",
        "distance_km": "Distance (km)",
    }
    avail_cols = [c for c in col_mapping.keys() if c in nearby_df.columns]
    table_df = nearby_df[avail_cols].rename(columns=col_mapping).copy()

    if "Fatalities" in table_df.columns:
        table_df["Fatalities"] = pd.to_numeric(table_df["Fatalities"], errors="coerce").fillna(0).astype(int)
    if "Injuries" in table_df.columns:
        table_df["Injuries"] = pd.to_numeric(table_df["Injuries"], errors="coerce").fillna(0).astype(int)
    if "Distance (km)" in table_df.columns:
        table_df["Distance (km)"] = table_df["Distance (km)"].round(1)

    st.dataframe(table_df, use_container_width=True, hide_index=True)

    # Additional visual charts for nearby incidents
    c_chart1, c_chart2 = st.columns(2)
    with c_chart1:
        if "attacktype1_txt" in nearby_df.columns:
            atk_counts = nearby_df["attacktype1_txt"].value_counts().reset_index()
            atk_counts.columns = ["Attack Type", "Count"]
            fig_atk = px.bar(
                atk_counts.head(7),
                x="Count",
                y="Attack Type",
                orientation="h",
                title="Nearby Incident Tactics Breakdown",
                color="Count",
                color_continuous_scale=["#007BFF", "#00E5FF"],
                template="plotly_dark",
            )
            fig_atk.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(family="Outfit, sans-serif", color="#CBD5E1"),
                margin=dict(l=10, r=10, t=40, b=10),
                coloraxis_showscale=False,
            )
            st.plotly_chart(fig_atk, use_container_width=True)

    with c_chart2:
        if "iyear" in nearby_df.columns:
            yearly_trend = nearby_df.groupby("iyear").size().reset_index(name="Incidents")
            fig_trend = px.line(
                yearly_trend,
                x="iyear",
                y="Incidents",
                markers=True,
                title="Nearby Incidents Timeline",
                template="plotly_dark",
            )
            fig_trend.update_traces(line_color="#00E5FF", marker=dict(color="#7000FF", size=6))
            fig_trend.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(family="Outfit, sans-serif", color="#CBD5E1"),
                margin=dict(l=10, r=10, t=40, b=10),
                xaxis_title="Year",
                yaxis_title="Incidents",
            )
            st.plotly_chart(fig_trend, use_container_width=True)
else:
    st.info(f"No historical incidents recorded within {radius_km} km of coordinates ({lat:.4f}, {lon:.4f}).")

st.markdown('<div style="margin-top:1.5rem"></div>', unsafe_allow_html=True)

# -----------------------------------------------
# Allied Military Assets Table
# -----------------------------------------------
st.subheader("🏗️ Allied Military Assets")
if not nearby_assets_df.empty:
    assets_display = nearby_assets_df[["name", "type", "eta", "distance_km", "owner", "country"]].copy()
    assets_display["distance_km"] = assets_display["distance_km"].round(1)
    st.dataframe(
        assets_display,
        column_config={
            "name": st.column_config.TextColumn("Asset Name", width="large"),
            "type": st.column_config.TextColumn("Facility Type", width="medium"),
            "eta": st.column_config.TextColumn("ETA (Deploy)", width="small"),
            "distance_km": st.column_config.NumberColumn("Distance (km)", format="%.1f"),
            "owner": st.column_config.TextColumn("Operating Nation", width="medium"),
            "country": st.column_config.TextColumn("Host Country", width="medium"),
        },
        use_container_width=True,
        hide_index=True
    )
    st.caption("⚠️ **Data Disclaimer:** This is a simulated demonstration layer. Actual military installation coordinates are classified. The 'Operating Nation' (Ownership) assignments are illustrative estimates based on general public knowledge for UI demonstration purposes and do not represent verified or official defense intelligence.")
else:
    if nearest_asset:
        st.info(f"No allied assets within {radius_km}km. The nearest asset is **{nearest_asset['name']}** ({nearest_asset['type']}), located **{nearest_asset['distance_km']:.1f}km** away in {nearest_asset['country']} (ETA: {nearest_asset.get('eta', 'N/A')}).")
    else:
        st.info("No allied assets available in the database.")

st.markdown('<div style="margin-top:1.5rem"></div>', unsafe_allow_html=True)

# -----------------------------------------------
# 7d. Risk Assessment Summary with Severity Badge
# -----------------------------------------------
st.subheader("🛡️ Mission Risk Assessment")

badge_color = threat_color
badge_label = threat_level

asset_balance_text = ""
if len(nearby_assets_df) == 0:
    asset_balance_text = "0 assets in range — recommend remote air support or immediate redeployment."
else:
    asset_balance_text = f"{len(nearby_assets_df)} allied assets in range."

summary_card_html = f"""
<div class="module-card">
    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1rem; flex-wrap: wrap; gap: 0.5rem;">
        <h3 style="margin: 0;">Operational Threat Profile — {selected_country}</h3>
        <span style="background: {badge_color}22; color: {badge_color}; border: 1px solid {badge_color}; padding: 6px 16px; border-radius: 20px; font-weight: 800; font-size: 0.95rem; letter-spacing: 0.5px;">
            {badge_label} SEVERITY
        </span>
    </div>
    <p style="color: #CBD5E1; font-size: 0.95rem; line-height: 1.6; margin-bottom: 0.5rem;">
        Target Location: <strong>({lat:.4f}, {lon:.4f})</strong> | Country Risk Score: <strong>{risk_breakdown.score}/100</strong> ({risk_breakdown.level} risk category).
    </p>
    <p style="color: #CBD5E1; font-size: 0.95rem; line-height: 1.6; margin-bottom: 0;">
        Within a radius of <strong>{radius_km} km</strong>, <strong>{len(nearby_df)}</strong> historical conflict incidents were identified. 
        <strong>{threat_level.capitalize()} threat zone, {asset_balance_text}</strong> Threat conditions require continuous vigilance and adherence to operational protocols specified below.
    </p>
</div>
"""
st.markdown(summary_card_html, unsafe_allow_html=True)

st.markdown('<div style="margin-top:1.5rem"></div>', unsafe_allow_html=True)

# -----------------------------------------------
# 7e & 7f. Resource Recommendations
# -----------------------------------------------
st.subheader("📋 Recommended Resource Allocations & Tactical Actions")

dominant_attack_type = None
if not nearby_df.empty and "attacktype1_txt" in nearby_df.columns:
    top_atks = nearby_df["attacktype1_txt"].dropna().value_counts()
    if not top_atks.empty:
        dominant_attack_type = top_atks.index[0]

recs = generate_recommendations(threat_score=threat_score, dominant_attack_type=dominant_attack_type)

if recs:
    rec_cols = st.columns(2)
    for idx, rec in enumerate(recs):
        col = rec_cols[idx % 2]
        p_color = priority_color(rec.priority)
        card_html = f"""
        <div class="module-card" style="border-left: 4px solid {p_color}; min-height: 140px;">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.5rem;">
                <span style="font-size: 1.1rem; font-weight: 700; color: #F8FAFC;">
                    {rec.icon} {rec.category}
                </span>
                <span style="background: {p_color}22; color: {p_color}; border: 1px solid {p_color}; padding: 3px 10px; border-radius: 16px; font-weight: 700; font-size: 0.75rem;">
                    {rec.priority}
                </span>
            </div>
            <div style="font-size: 1rem; font-weight: 600; color: #00E5FF; margin-bottom: 0.4rem;">
                {rec.action}
            </div>
            <div style="font-size: 0.85rem; color: #94A3B8; line-height: 1.4;">
                {rec.rationale}
            </div>
        </div>
        """
        col.markdown(card_html, unsafe_allow_html=True)
else:
    st.info("No specific resource recommendations generated for current threat level.")

st.markdown('<div style="margin-top:2rem"></div>', unsafe_allow_html=True)

# -----------------------------------------------
# 8. PDF Export
# -----------------------------------------------
st.subheader("📥 Export Intelligence Brief")

with st.spinner("Preparing PDF export..."):
    pdf_bytes = generate_mission_brief_pdf(
        country=selected_country,
        lat=lat,
        lon=lon,
        radius=radius_km,
        threat_score=threat_score,
        threat_level=threat_level,
        incident_count=len(nearby_df),
        dominant_attack=dominant_attack_type,
        recommendations=recs,
        nearby_assets=nearby_assets_df.to_dict('records') if not nearby_assets_df.empty else ({"nearest": nearest_asset} if nearest_asset else None)
    )

st.download_button(
    label="📄 Download Mission Brief (PDF)",
    data=pdf_bytes,
    file_name=f"Mission_Brief_{selected_country}_{lat}_{lon}.pdf",
    mime="application/pdf"
)
