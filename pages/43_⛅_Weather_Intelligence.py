import os
import pandas as pd
import pydeck as pdk
import streamlit as st

# --- Authentication & Role Check ---
from utils.auth import require_auth
require_auth(['Viewer', 'Analyst', 'Commander'])
# -----------------------------------

import numpy as np

from utils.weather_utils import fetch_weather_by_coords, compute_weather_impact
from utils.ui_components import st_custom_kpi_card, fetch_weather

# 1. Page config
st.set_page_config(page_title="Weather Intelligence", page_icon="⛅", layout="wide")

# 2. Load CSS
def load_css(file_name: str) -> None:
    if os.path.exists(file_name):
        with open(file_name, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_css("assets/style.css")

# 3. Title & 4. Subtitle
st.title("🌦️ | Weather Intelligence")
st.markdown("##### Operational weather conditions for mission planning.")

# 6. Sidebar configuration
st.sidebar.header("⚙️ Weather Settings")

# API key input (password field, with os.environ.get fallback)
env_api_key = os.environ.get("OPENWEATHER_API_KEY", "")
api_key = st.sidebar.text_input(
    "OpenWeather API Key",
    value=env_api_key,
    type="password",
    help="Enter an OpenWeather API key or set the OPENWEATHER_API_KEY environment variable.",
)

# Preset locations
PRESETS = {
    "Baghdad, Iraq": (33.3, 44.4),
    "Kabul, Afghanistan": (34.5, 69.2),
    "Damascus, Syria": (33.5, 36.3),
    "Mogadishu, Somalia": (2.0, 45.3),
    "Sana'a, Yemen": (15.4, 44.2),
    "Tripoli, Libya": (32.9, 13.2),
}

preset_choice = st.sidebar.selectbox(
    "Preset Location",
    options=["Custom Location"] + list(PRESETS.keys()),
    index=0,
)

if preset_choice in PRESETS:
    default_lat, default_lon = PRESETS[preset_choice]
else:
    default_lat, default_lon = 33.0, 44.0

lat = st.sidebar.number_input(
    "Latitude",
    value=default_lat,
    min_value=-90.0,
    max_value=90.0,
    step=0.1,
    format="%.4f",
)
lon = st.sidebar.number_input(
    "Longitude",
    value=default_lon,
    min_value=-180.0,
    max_value=180.0,
    step=0.1,
    format="%.4f",
)


def render_map(latitude: float, longitude: float, loc_name: str, status_desc: str):
    """Renders a PyDeck map with a location marker centered at (latitude, longitude)."""
    map_data = pd.DataFrame(
        [
            {
                "lat": latitude,
                "lon": longitude,
                "name": loc_name,
                "status": status_desc,
            }
        ]
    )

    layer_outer = pdk.Layer(
        "ScatterplotLayer",
        data=map_data,
        get_position=["lon", "lat"],
        get_color=[255, 75, 75, 50],
        get_radius=20000,
        pickable=False,
    )

    layer_marker = pdk.Layer(
        "ScatterplotLayer",
        data=map_data,
        get_position=["lon", "lat"],
        get_color=[255, 45, 85, 240],
        get_radius=5000,
        radius_min_pixels=10,
        radius_max_pixels=25,
        pickable=True,
    )

    view_state = pdk.ViewState(
        latitude=latitude,
        longitude=longitude,
        zoom=7,
        pitch=0,
        bearing=0,
    )

    tooltip = {
        "html": "<b>{name}</b><br/>{status}",
        "style": {
            "background": "#1e293b",
            "color": "white",
            "font-family": "sans-serif",
            "border-radius": "6px",
            "padding": "8px 12px",
        },
    }

    deck = pdk.Deck(
        layers=[layer_outer, layer_marker],
        initial_view_state=view_state,
        tooltip=tooltip,
        map_style=None,
    )

    with st.spinner("Rendering operational map..."):
        st.pydeck_chart(deck, use_container_width=True)


# Determine whether weather data can be fetched
effective_key = api_key.strip() if api_key and api_key.strip() else None
weather: WeatherData | None = None

if effective_key:
    weather = fetch_weather(lat, lon, effective_key)

# 7. When API key is available and weather is successfully fetched
if weather:
    # b. Display KPI metrics: Temperature, Wind Speed, Visibility, Humidity
    st.subheader("📊 Weather Metrics")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st_custom_kpi_card("Temperature", f"{weather.temperature_c:.1f} °C", f"Feels like {weather.feels_like_c:.1f} °C", "🌡️")
    with col2:
        st_custom_kpi_card("Wind Speed", f"{weather.wind_speed_ms:.1f} m/s", f"Direction: {weather.wind_direction}°", "💨")
    with col3:
        st_custom_kpi_card("Visibility", f"{weather.visibility_km:.1f} km", "", "👁️")
    with col4:
        st_custom_kpi_card("Humidity", f"{weather.humidity}%", f"Pressure: {weather.pressure_hpa} hPa", "💧")

    # c. Display weather description and icon
    st.markdown("---")
    col_desc, col_icon = st.columns([4, 1])

    city_country = weather.city
    if weather.country:
        city_country += f", {weather.country}"

    with col_desc:
        st.markdown(f"### 📍 Location: {city_country}")
        st.markdown(
            f"**Condition:** {weather.description.capitalize()}  \n"
            f"**Cloud Cover:** {weather.clouds_pct}% | **Precipitation (1h):** {weather.rain_mm:.1f} mm"
        )
    with col_icon:
        if weather.icon:
            icon_url = f"https://openweathermap.org/img/wn/{weather.icon}@2x.png"
            st.image(icon_url, width=90)

    # d & e. Assess operational impact and display impact cards
    st.markdown("---")
    st.subheader("🛡️ Operational Impact Assessment")
    impacts = assess_operational_impact(weather)

    impact_cols = st.columns(len(impacts))
    for idx, impact in enumerate(impacts):
        factor = impact["factor"]
        status = impact["status"]
        color = impact["color"]
        detail = impact["detail"]
        bg_color = f"{color}1F"  # soft background tint matching status color

        with impact_cols[idx]:
            st.markdown(
                f"""
                <div style="
                    background-color: {bg_color};
                    border: 1px solid {color};
                    border-radius: 8px;
                    padding: 16px;
                    height: 100%;
                    margin-bottom: 16px;
                ">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                        <strong style="font-size: 1.05rem;">{factor}</strong>
                        <span style="
                            background-color: {color};
                            color: #ffffff;
                            padding: 3px 10px;
                            border-radius: 12px;
                            font-weight: 700;
                            font-size: 0.8rem;
                            text-transform: uppercase;
                        ">{status}</span>
                    </div>
                    <div style="font-size: 0.9rem; line-height: 1.4;">
                        {detail}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # f. Display a pydeck map with the location marker
    st.markdown("---")
    st.subheader("🗺️ Operational Location Map")
    loc_title = preset_choice if preset_choice != "Custom Location" else f"Location ({lat:.2f}, {lon:.2f})"
    render_map(lat, lon, loc_title, f"Condition: {weather.description.capitalize()}")

# 8. When API key is NOT available or fetch returns None
else:
    st.info("An OpenWeather API key is needed to retrieve live weather conditions and operational impact assessment.")
    st.markdown("Get a free API key at openweathermap.org")

    st.markdown("---")
    st.subheader("🗺️ Target Location Map")
    loc_title = preset_choice if preset_choice != "Custom Location" else f"Target Coordinates ({lat:.2f}, {lon:.2f})"
    render_map(lat, lon, loc_title, f"Target Coordinates: ({lat:.4f}, {lon:.4f})")
