import os
import json
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import pydeck as pdk
import streamlit as st
import joblib
import gc
import shap

# --- Authentication & Role Check ---
from utils.auth import require_auth
require_auth(['Analyst', 'Commander'])
# -----------------------------------

try:
    from google import genai
except Exception:
    genai = None

from sklearn.preprocessing import LabelEncoder
from sklearn.ensemble import RandomForestClassifier

from utils.data_loader import load_data, query_data
from utils.intelligence import (
    DEFAULT_LIVE_QUERY,
    build_pdf,
    build_situation_report,
    compute_country_risk,
    enrich_live_events_with_country_centroids,
    fetch_gdelt_events,
)
from utils.recommendations import generate_recommendations, priority_color
from utils.tsi import compute_single_tsi, tsi_label
from utils.pdf_export import generate_mission_brief_pdf
from utils.ui_components import st_custom_kpi_card, st_custom_threat_banner

st.set_page_config(
    page_title="Mission Planning & Intelligence",
    page_icon="🎖️",
    layout="wide"
)

def load_css(file_name: str) -> None:
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

load_css("assets/style.css")

st.title("🎖️ | Mission Planning Simulator")
st.markdown("##### Location-based threat assessment, AI predictions, and operational planning.")
st.markdown('<div style="margin-top:0.75rem"></div>', unsafe_allow_html=True)

# -----------------------------------------------
# 1. CACHED FUNCTIONS & LOADERS
# -----------------------------------------------
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

@st.cache_resource
def load_threat_model():
    m_path = "models/threat_prediction_model.pkl"
    enc_path = "models/threat_feature_encoders.pkl"
    t_enc_path = "models/threat_encoder.pkl"
    if os.path.exists(m_path) and os.path.exists(enc_path) and os.path.exists(t_enc_path):
        model = joblib.load(m_path)
        encoders = joblib.load(enc_path)
        target_enc = joblib.load(t_enc_path)
        return model, encoders, target_enc
    import train_models
    train_models.train_all()
    model = joblib.load(m_path)
    encoders = joblib.load(enc_path)
    target_enc = joblib.load(t_enc_path)
    return model, encoders, target_enc

model_tl, encoders_tl, target_enc_tl = load_threat_model()
def get_original_labels(col):
    return list(encoders_tl[col].classes_)

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

@st.cache_resource(show_spinner="Loading ML models...")
def load_attack_models():
    try:
        model = joblib.load("models/attack_prediction_model.pkl")
        target_encoder = joblib.load("models/target_encoder.pkl")
        target_feature_encoder = joblib.load("models/target_feature_encoder.pkl")
        cat_imputer = joblib.load("models/cat_imputer.pkl")
        num_imputer = joblib.load("models/num_imputer.pkl")
    except FileNotFoundError:
        import train_models
        train_models.train_all()
        model = joblib.load("models/attack_prediction_model.pkl")
        target_encoder = joblib.load("models/target_encoder.pkl")
        target_feature_encoder = joblib.load("models/target_feature_encoder.pkl")
        cat_imputer = joblib.load("models/cat_imputer.pkl")
        num_imputer = joblib.load("models/num_imputer.pkl")
    return model, target_encoder, target_feature_encoder, cat_imputer, num_imputer, shap.TreeExplainer(model)

model_ap, target_encoder_ap, target_feature_encoder_ap, cat_imputer_ap, num_imputer_ap, explainer_ap = load_attack_models()
gc.collect()

cat_cols = ["country_txt", "region_txt", "weaptype1_txt", "targtype1_txt", "gname"]
@st.cache_data(show_spinner=False)
def _load_cat_options():
    return pd.read_csv("data/globalterrorism.csv", usecols=cat_cols, encoding="latin1", low_memory=False)

df_cats = _load_cat_options()

@st.cache_data(show_spinner=False)
def _get_country_to_region_map():
    return df_cats.groupby("country_txt")["region_txt"].first().to_dict()

country_to_region = _get_country_to_region_map()

@st.cache_data(show_spinner=False)
def load_military_assets(filepath: str = "data/military_assets.json") -> pd.DataFrame:
    if not os.path.exists(filepath):
        return pd.DataFrame()
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    return pd.DataFrame(data)

def haversine_km(lat1: float, lon1: float, lat2_arr: np.ndarray, lon2_arr: np.ndarray) -> np.ndarray:
    R = 6371.0
    phi1 = np.radians(lat1)
    phi2 = np.radians(lat2_arr)
    dphi = np.radians(lat2_arr - lat1)
    dlambda = np.radians(lon2_arr - lon1)
    a = np.sin(dphi / 2.0) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlambda / 2.0) ** 2
    c = 2.0 * np.arctan2(np.sqrt(a), np.sqrt(1.0 - a))
    return R * c

# -----------------------------------------------
# 2. SIDEBAR
# -----------------------------------------------
st.sidebar.header("Mission Parameters")

country_df = get_countries_and_centroids()
countries = country_df["country_txt"].tolist()

if "mission_lat" not in st.session_state:
    st.session_state.mission_lat = 33.3152
if "mission_lon" not in st.session_state:
    st.session_state.mission_lon = 44.3661
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
radius_km = st.sidebar.slider("Mission Radius (km)", min_value=50, max_value=500, value=200, step=10, key="mission_radius_slider", help="Operational radius around the center coordinates.")

# -----------------------------------------------
# DERIVE ML PARAMETERS FROM COUNTRY HISTORY
# -----------------------------------------------
safe_country = selected_country.replace("'", "''")
country_incidents = query_data(
    f"SELECT * FROM 'data/globalterrorism.csv' WHERE latitude IS NOT NULL AND longitude IS NOT NULL AND country_txt = '{safe_country}'"
)

def get_mode(series, default):
    if series is None: return default
    s = series.dropna()
    return s.mode().iloc[0] if not s.empty else default

def get_median(series, default):
    if series is None: return default
    s = series.dropna()
    return int(s.median()) if not s.empty else default

if not country_incidents.empty:
    region = get_mode(country_incidents.get("region_txt"), "Unknown")
    attack = get_mode(country_incidents.get("attacktype1_txt"), "Bombing/Explosion")
    weapon = get_mode(country_incidents.get("weaptype1_txt"), "Explosives")
    target_t = get_mode(country_incidents.get("targtype1_txt"), "Private Citizens & Property")
    nkill = get_median(country_incidents.get("nkill"), 0)
    nwound = get_median(country_incidents.get("nwound"), 0)
    success_val = get_mode(country_incidents.get("success"), 1)
    success = "Yes" if success_val == 1 else "No"
    claimed_val = get_mode(country_incidents.get("claimed"), 0)
    claimed = "Yes" if claimed_val == 1 else "No"
    group_ap = get_mode(country_incidents.get("gname"), "Unknown")
    suicide_ap = get_mode(country_incidents.get("suicide"), 0)
else:
    region = "Unknown"
    attack = "Bombing/Explosion"
    weapon = "Explosives"
    target_t = "Private Citizens & Property"
    nkill = 0
    nwound = 0
    success = "Yes"
    claimed = "No"
    group_ap = "Unknown"
    suicide_ap = 0


st.sidebar.markdown("---")
st.sidebar.header("AI Narrative Settings")
lookback = st.sidebar.selectbox("Live intelligence window", ["15m", "1h", "6h", "1d", "3d", "7d"], index=3, key="ai_lookback")
max_records = st.sidebar.slider("Live records", 25, 250, 100, step=25, key="ai_max_records")
use_live = st.sidebar.checkbox("Include GDELT live feed", value=True, key="ai_use_live")
api_key = os.environ.get("GEMINI_API_KEY") or st.sidebar.text_input("Gemini API Key (optional)", type="password", key="ai_api_key")


# -----------------------------------------------
# 3. TABS
# -----------------------------------------------
tab_mission, tab_threat, tab_attack, tab_ai = st.tabs(['🎯 Mission Planning', '🚨 Threat Level', '🤖 Attack Prediction', '📄 AI Situation Report'])

# -----------------------------------------------
# TAB 1: Mission Planning
# -----------------------------------------------
with tab_mission:
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

    historical_df = load_data()
    risk_breakdown = compute_country_risk(selected_country, historical_df)
    threat_score = int(risk_breakdown.score)
    threat_level, threat_color = tsi_label(threat_score)

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    with kpi1: st_custom_kpi_card("Country Risk Score", f"{risk_breakdown.score} / 100", f"{risk_breakdown.level}", "🛡️")
    with kpi2: st_custom_kpi_card("Nearby Incidents (within radius)", f"{len(nearby_df):,}", "Clustered events", "📍")
    with kpi3: st_custom_kpi_card("Estimated Threat Level", threat_level, "Local vicinity", "🚨")
    with kpi4: st_custom_kpi_card("Assets in Range", f"{len(nearby_assets_df):,}", "Allied military", "🏗️")

    st.markdown('<div style="margin-top:1.5rem"></div>', unsafe_allow_html=True)

    st.subheader("📍 Operational Map & Threat Radius")

    mission_center_df = pd.DataFrame([
        {
            "latitude": lat,
            "longitude": lon,
            "radius_m": radius_km * 1000.0,
            "name": "Mission Center",
        }
    ])

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

    st.subheader("🛡️ Mission Risk Assessment")

    badge_color = threat_color
    badge_label = threat_level

    asset_balance_text = ""
    if len(nearby_assets_df) == 0:
        asset_balance_text = "0 assets in range — recommend remote air support or immediate redeployment."
    else:
        asset_balance_text = f"{len(nearby_assets_df)} allied assets in range."

    summary_card_html = (
        f'<div class="module-card">'
        f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:1rem;flex-wrap:wrap;gap:0.5rem;">'
        f'<h3 style="margin:0;">Operational Threat Profile — {selected_country}</h3>'
        f'<span style="background:{badge_color}22;color:{badge_color};border:1px solid {badge_color};padding:6px 16px;border-radius:20px;font-weight:800;font-size:0.95rem;letter-spacing:0.5px;">'
        f'{badge_label} SEVERITY</span>'
        f'</div>'
        f'<p style="color:#CBD5E1;font-size:0.95rem;line-height:1.6;margin-bottom:0.5rem;">'
        f'Target Location: <strong>({lat:.4f}, {lon:.4f})</strong> | Country Risk Score: <strong>{risk_breakdown.score}/100</strong> ({risk_breakdown.level} risk category).'
        f'</p>'
        f'<p style="color:#CBD5E1;font-size:0.95rem;line-height:1.6;margin-bottom:0;">'
        f'Within a radius of <strong>{radius_km} km</strong>, <strong>{len(nearby_df)}</strong> historical conflict incidents were identified. '
        f'<strong>{threat_level.capitalize()} threat zone, {asset_balance_text}</strong> Threat conditions require continuous vigilance and adherence to operational protocols specified below.'
        f'</p>'
        f'</div>'
    )
    st.markdown(summary_card_html, unsafe_allow_html=True)

    st.markdown('<div style="margin-top:1.5rem"></div>', unsafe_allow_html=True)

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
            card_html = (
                f'<div class="module-card" style="border-left:4px solid {p_color};min-height:140px;">'
                f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:0.5rem;">'
                f'<span style="font-size:1.1rem;font-weight:700;color:#F8FAFC;">{rec.icon} {rec.category}</span>'
                f'<span style="background:{p_color}22;color:{p_color};border:1px solid {p_color};padding:3px 10px;border-radius:16px;font-weight:700;font-size:0.75rem;">{rec.priority}</span>'
                f'</div>'
                f'<div style="font-size:1rem;font-weight:600;color:#00E5FF;margin-bottom:0.4rem;">{rec.action}</div>'
                f'<div style="font-size:0.85rem;color:#94A3B8;line-height:1.4;">{rec.rationale}</div>'
                f'</div>'
            )
            col.markdown(card_html, unsafe_allow_html=True)
    else:
        st.info("No specific resource recommendations generated for current threat level.")

    st.markdown('<div style="margin-top:2rem"></div>', unsafe_allow_html=True)

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
        mime="application/pdf",
        key="btn_download_mission_pdf"
    )

# -----------------------------------------------
# TAB 2: Threat Level
# -----------------------------------------------
with tab_threat:
    tsi_score = compute_single_tsi(
        nkill, nwound,
        1.0 if success == "Yes" else 0.0,
        1.0 if claimed == "Yes" else 0.0
    )
    tsi_lbl, tsi_color = tsi_label(tsi_score)

    st.subheader("📐 Threat Severity Index (TSI)")

    with st.expander("ℹ️ How is TSI calculated?", expanded=False):
        st.markdown("**TSI Non-linear Scoring Formula:**")
        st.latex(r'''
            \text{TSI}_{\text{raw}} =
                w_1 \cdot \ln(1 + n_{\text{kill}}) +
                w_2 \cdot \ln(1 + n_{\text{wound}}) +
                w_3 \cdot \text{success} +
                w_4 \cdot \text{claimed}
        ''')
        st.latex(r'''
            \text{TSI} = 100 \times
            \frac{\text{TSI}_{\text{raw}} - \min}{\max - \min}
            \quad \in [0, 100]
        ''')
        st.markdown("""
        | Weight | Component | Value | Rationale |
        |--------|-----------|-------|-----------|
        | w₁ | Fatalities | **0.50** | Highest operational impact |
        | w₂ | Injuries | **0.30** | Serious but not terminal |
        | w₃ | Success | **0.15** | Signals operational capability |
        | w₄ | Claimed | **0.05** | Signals ideological intent |

        **Why logarithm?** `ln(1 + x)` compresses extreme outliers — a 500-casualty event
        doesn't dominate the index while still ranking far higher than a 5-casualty event.
        """)

    tsi_col1, tsi_col2, tsi_col3 = st.columns(3)
    with tsi_col1: st_custom_kpi_card("TSI Score", f"{tsi_score:.1f} / 100", "", "🔢")
    with tsi_col2: st_custom_kpi_card("Severity Label", tsi_lbl, "", "🚨")
    tsi_col3.markdown(
        f"<div style='padding:14px;border-radius:8px;background:{tsi_color}22;"
        f"border:2px solid {tsi_color};text-align:center;"
        f"font-size:1.4rem;font-weight:700;color:{tsi_color}'>{tsi_lbl}</div>",
        unsafe_allow_html=True
    )

    gauge_fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=tsi_score,
        domain={"x": [0, 1], "y": [0, 1]},
        title={"text": "Threat Severity Index", "font": {"size": 16}},
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": tsi_color},
            "steps": [
                {"range": [0, 25],  "color": "#1a1a2e"},
                {"range": [25, 50], "color": "#16213e"},
                {"range": [50, 75], "color": "#0f3460"},
                {"range": [75, 100],"color": "#2d0a0a"},
            ],
            "threshold": {
                "line": {"color": "white", "width": 3},
                "thickness": 0.8,
                "value": tsi_score
            }
        }
    ))
    gauge_fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        height=250,
        margin=dict(l=20, r=20, t=40, b=10)
    )
    st.plotly_chart(gauge_fig, use_container_width=True)

    st.divider()

    if st.button("🚨 Predict Threat Level (ML Classifier)", key="btn_predict_threat"):
        try:
            input_enc = np.array([[
                encoders_tl["country_txt"].transform([selected_country])[0],
                encoders_tl["region_txt"].transform([region])[0],
                encoders_tl["attacktype1_txt"].transform([attack])[0],
                encoders_tl["weaptype1_txt"].transform([weapon])[0],
                encoders_tl["targtype1_txt"].transform([target_t])[0],
                nkill,
                nwound
            ]])

            prediction    = model_tl.predict(input_enc)
            probabilities = model_tl.predict_proba(input_enc)[0]
            result        = target_enc_tl.inverse_transform(prediction)[0]
            confidence    = np.max(probabilities) * 100
        except (ValueError, KeyError) as enc_err:
            st.error(f"Prediction failed: {enc_err}")
            st.info("A selected category may not have been present during model training. Try different inputs.")
            st.stop()

        st.subheader("🔍 ML Classifier Result")

        col1, col2 = st.columns(2)

        with col1:
            if result == "LOW":
                st.success(f"### 🟢 Threat Level: {result}")
                st.markdown("Incident is classified as **low severity**. Minimal casualties expected.")
            elif result == "MEDIUM":
                st.warning(f"### 🟡 Threat Level: {result}")
                st.markdown("Incident is classified as **medium severity**. Moderate casualties expected. Elevated vigilance recommended.")
            else:
                st.error(f"### 🔴 Threat Level: {result}")
                st.markdown("Incident is classified as **HIGH SEVERITY**. Significant casualties expected. Immediate response required.")

            st.markdown("#### Evidence & Context")
            c1, c2 = st.columns(2)
            with c1: st_custom_kpi_card("Model Confidence", f"{confidence:.1f}%", "", "🧠")
            with c2: st_custom_kpi_card("TSI Score (corroborating)", f"{tsi_score:.1f}/100", tsi_lbl, "📊")

        with col2:
            labels = target_enc_tl.classes_
            colors = ["#2ECC71", "#F39C12", "#E74C3C"]

            fig = go.Figure(go.Bar(
                x=labels,
                y=probabilities * 100,
                marker_color=colors,
                text=[f"{p*100:.1f}%" for p in probabilities],
                textposition="outside"
            ))
            fig.update_layout(
                title="Probability Distribution",
                yaxis_title="Probability (%)",
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=300,
                margin=dict(l=20, r=20, t=40, b=20)
            )
            st.plotly_chart(fig, use_container_width=True)

        st.divider()

        st.subheader("📊 Feature Importance")
        feat_names = ["Country", "Region", "Attack Type", "Weapon Type", "Target Type", "Killed", "Wounded"]
        importances = model_tl.feature_importances_

        fig2 = go.Figure(go.Bar(
            x=importances,
            y=feat_names,
            orientation="h",
            marker_color="#00E5FF"
        ))
        fig2.update_layout(
            title="What drives the prediction?",
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            height=300,
            margin=dict(l=20, r=20, t=40, b=20)
        )
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("👈 Configure the incident parameters in the sidebar and click **Predict Threat Level**.")

# -----------------------------------------------
# TAB 3: Attack Prediction
# -----------------------------------------------
with tab_attack:
    with st.expander("📊 Global Model Explainability (Feature Importance)", expanded=False):
        importances_ap = model_ap.feature_importances_
        features_ap = ["Country", "Region", "Weapon Type", "Target Type", "Group", "Success", "Suicide", "Fatalities", "Injuries"]
        
        fig_imp = go.Figure(go.Bar(
            x=importances_ap,
            y=features_ap,
            orientation='h',
            marker_color="#FF2D55"
        ))
        fig_imp.update_layout(
            title="Which features matter most overall?",
            xaxis_title="Relative Importance (Mean Decrease Impurity)",
            yaxis={'categoryorder':'total ascending'},
            template="plotly_dark",
            height=350,
            margin=dict(l=10, r=10, t=40, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)"
        )
        st.plotly_chart(fig_imp, use_container_width=True)
        st.caption("Random Forest global feature importance confirms Weapon Type strongly dictates the predicted attack classification.")
    
    st.info(f"Using historically derived parameters for **{selected_country}**: Weapon: **{weapon}**, Target: **{target_t}**, Group: **{group_ap}**")
    submitted_ap = st.button("🚀 Predict Attack Type", key="btn_ap_predict")

    if submitted_ap:
        try:
            try:
                derived_region = country_to_region.get(selected_country, "Unknown")
            except Exception:
                derived_region = "Unknown"
            
            input_data = pd.DataFrame({
                "country_txt": [selected_country],
                "region_txt": [derived_region],
                "weaptype1_txt": [weapon],
                "targtype1_txt": [target_t],
                "gname": [group_ap],
                "iyear": [2017],
                "success": [1 if success == "Yes" else 0],
                "suicide": [suicide_ap],
                "nkill": [nkill],
                "nwound": [nwound]
            })

            input_data[cat_cols] = cat_imputer_ap.transform(input_data[cat_cols])
            
            num_cols = ["iyear", "success", "suicide", "nkill", "nwound"]
            input_data[num_cols] = num_imputer_ap.transform(input_data[num_cols])

            cat_encoded = target_feature_encoder_ap.transform(input_data[cat_cols])

            input_data_final = np.hstack([cat_encoded, input_data[num_cols].values])

            prediction = model_ap.predict(input_data_final)
            attack_type = target_encoder_ap.inverse_transform(prediction)[0]
            
            probabilities = model_ap.predict_proba(input_data_final)[0]
            confidence = probabilities.max() * 100
            
            shap_vals = explainer_ap.shap_values(input_data_final)
            pred_class_idx = int(prediction[0])
            if isinstance(shap_vals, list):
                local_shap = shap_vals[pred_class_idx][0]
            else:
                if len(shap_vals.shape) == 3:
                    local_shap = shap_vals[0, :, pred_class_idx]
                else:
                    local_shap = shap_vals[0]
                    
        except Exception as pred_err:
            st.error(f"Prediction failed: {pred_err}")
            st.info("The selected combination may contain values unseen during training. Try different inputs.")
            st.stop()

        st.divider()
        st.subheader("🔍 Prediction Result")

        col_res, col_chart = st.columns(2)

        with col_res:
            st.success(f"### Predicted Attack Type: **{attack_type}**")
            st_custom_kpi_card("Model Confidence", f"{confidence:.1f}%", "", "🧠")

            if attack_type in ["Hijacking", "Unarmed Assault"]:
                st.warning(
                    f"⚠️ **Low Historical Support Notice:** '{attack_type}' represents <1% of historical GTD incidents. "
                    "Predictions for rare attack types carry higher uncertainty due to extreme class imbalance in real-world data."
                )
                
            st.markdown("##### Why this prediction?")
            feature_names = ["Country", "Region", "Weapon Type", "Target Type", "Group", "Success", "Suicide", "Fatalities", "Injuries"]
            impacts = sorted(zip(feature_names, local_shap), key=lambda x: abs(x[1]), reverse=True)
            
            top_positive = [f for f, v in impacts if v > 0][:2]
            top_negative = [f for f, v in impacts if v < 0][:1]
            
            if top_positive:
                st.write(f"**{', '.join(top_positive)}** contributed most to this prediction.")
            if top_negative:
                st.write(f"*(Conversely, {top_negative[0]} slightly reduced the likelihood).*")

        with col_chart:
            attack_labels = target_encoder_ap.classes_
            top_n = min(8, len(attack_labels))
            sorted_idx = probabilities.argsort()[::-1][:top_n]

            fig = go.Figure(go.Bar(
                x=[attack_labels[i] for i in sorted_idx],
                y=[probabilities[i] * 100 for i in sorted_idx],
                marker_color="#00E5FF",
                text=[f"{probabilities[i]*100:.1f}%" for i in sorted_idx],
                textposition="outside"
            ))
            fig.update_layout(
                title="Top Predicted Attack Types",
                yaxis_title="Probability (%)",
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=320,
                margin=dict(l=10, r=10, t=40, b=10)
            )
            st.plotly_chart(fig, use_container_width=True)

# -----------------------------------------------
# TAB 4: AI Situation Report
# -----------------------------------------------
with tab_ai:
    historical = load_data()
    country_hist = historical[historical["country_txt"] == selected_country].copy()

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
        == selected_country.lower()
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
    
    risk = compute_country_risk(selected_country, historical, live_events)
    report = build_situation_report(selected_country, f"Live window: {lookback}", stats, risk, country_live)

    if live_error:
        st.info(
            "📡 **Live Feed Status:** External SIGINT stream (GDELT/API) unreachable or degraded. "
            "Automatically failing over to **Cached GTD Tactical Intelligence Database** (Offline Mode).",
            icon="🛡️"
        )

    st_custom_threat_banner(risk.level, f"{risk.score}/100")
    
    c1, c2 = st.columns(2)
    with c1: st_custom_kpi_card("Historical Incidents", f"{len(country_hist):,}", "Recorded events", "📚")
    with c2: st_custom_kpi_card("Live Items", f"{len(country_live):,}", "Recent 24h events", "⚡")

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
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("🔍 What drives this score?", expanded=True):
        comp = risk.components
        if comp:
            fig_comp = go.Figure(go.Bar(
                x=list(comp.values()),
                y=list(comp.keys()),
                orientation="h",
                marker_color="#00E5FF",
                text=[f"{v:.1f}" for v in comp.values()],
                textposition="auto"
            ))
            fig_comp.update_layout(
                title="Threat Score Component Breakdown",
                xaxis_title="Contribution to Final Score",
                yaxis={'categoryorder':'total ascending'},
                template="plotly_dark",
                height=250,
                margin=dict(l=10, r=10, t=30, b=10),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)"
            )
            st.plotly_chart(fig_comp, use_container_width=True)
        else:
            st.write("Not enough data to calculate components.")

    st.subheader("Risk Drivers")
    component_df = pd.DataFrame(
        [{"Component": key, "Weighted Points": round(value, 2)} for key, value in risk.components.items()]
    )
    st.bar_chart(component_df.set_index("Component"))

    st.divider()

    st.subheader("Situation Report")

    generated_report = report
    can_use_gemini = bool(api_key and genai is not None)
    if st.button("🚀 Generate / Enhance Brief", key="btn_ai_brief"):
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
                    st.info(
                        "📡 **Live Feed Status:** External SIGINT stream (Gemini/API) unreachable or degraded. "
                        "Automatically failing over to **Local Report Generation** (Offline Mode).",
                        icon="🛡️"
                    )
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
            file_name=f"{selected_country}_situation_report.md",
            mime="text/markdown",
            key="btn_download_md"
        )
    with download_col2:
        try:
            pdf_bytes = build_pdf(generated_report)
            st.download_button(
                "📕 Download PDF Report",
                pdf_bytes,
                file_name=f"{selected_country}_situation_report.pdf",
                mime="application/pdf",
                key="btn_download_pdf"
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
            use_container_width=True,
            hide_index=True,
            column_config={"URL": st.column_config.LinkColumn("Source Link")},
        )

    st.info("This report is a decision-support artifact from historical GTD data and public news metadata.")
