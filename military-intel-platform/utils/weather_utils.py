"""
utils/weather_utils.py — Weather Intelligence Integration (Open-Meteo)
======================================================================
Fetches current weather conditions from Open-Meteo API.
No API key required.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.error import URLError
from urllib.request import Request, urlopen

OPEN_METEO_API = "https://api.open-meteo.com/v1/forecast"

@dataclass
class WeatherData:
    """Current weather conditions for a location."""
    temperature_c: float
    feels_like_c: float
    humidity: int
    wind_speed_ms: float
    wind_direction: int
    visibility_km: float
    description: str
    icon: str
    pressure_hpa: int
    clouds_pct: int
    rain_mm: float
    city: str
    country: str


def get_wmo_description(code: int) -> tuple[str, str]:
    """Map WMO code to a description and generic emoji icon."""
    mapping = {
        0: ("Clear sky", "01d"),
        1: ("Mainly clear", "02d"),
        2: ("Partly cloudy", "03d"),
        3: ("Overcast", "04d"),
        45: ("Fog", "50d"),
        48: ("Depositing rime fog", "50d"),
        51: ("Light drizzle", "09d"),
        53: ("Moderate drizzle", "09d"),
        55: ("Dense drizzle", "09d"),
        61: ("Slight rain", "10d"),
        63: ("Moderate rain", "10d"),
        65: ("Heavy rain", "10d"),
        71: ("Slight snow fall", "13d"),
        73: ("Moderate snow fall", "13d"),
        75: ("Heavy snow fall", "13d"),
        80: ("Slight rain showers", "09d"),
        81: ("Moderate rain showers", "09d"),
        82: ("Violent rain showers", "09d"),
        95: ("Thunderstorm", "11d"),
        96: ("Thunderstorm with slight hail", "11d"),
        99: ("Thunderstorm with heavy hail", "11d"),
    }
    desc, icon = mapping.get(code, ("Unknown", "01d"))
    return desc, icon


def fetch_weather_by_coords(
    lat: float,
    lon: float,
    timeout: int = 10,
) -> WeatherData | None:
    """Fetch current weather for a lat/lon coordinate using Open-Meteo.
    Returns None if the request fails or times out.
    """
    url = (
        f"{OPEN_METEO_API}?latitude={lat}&longitude={lon}"
        "&current=temperature_2m,wind_speed_10m,relative_humidity_2m,"
        "weather_code,precipitation,visibility"
    )
    request = Request(url, headers={"User-Agent": "ai-intelligence-platform/1.0"})

    try:
        with urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (URLError, json.JSONDecodeError, Exception):
        return None

    current = data.get("current", {})
    
    # Defaults and conversions
    temp_c = current.get("temperature_2m", 0.0)
    wind_kmh = current.get("wind_speed_10m", 0.0)
    wind_ms = wind_kmh / 3.6  # convert km/h to m/s
    humidity = current.get("relative_humidity_2m", 0)
    precip_mm = current.get("precipitation", 0.0)
    vis_m = current.get("visibility", 10000)
    vis_km = vis_m / 1000.0
    wmo_code = current.get("weather_code", 0)
    
    desc, icon = get_wmo_description(wmo_code)

    return WeatherData(
        temperature_c=temp_c,
        feels_like_c=temp_c,  # not provided by this minimal call
        humidity=humidity,
        wind_speed_ms=wind_ms,
        wind_direction=0,     # not requested to save bandwidth
        visibility_km=vis_km,
        description=desc,
        icon=icon,
        pressure_hpa=1013,    # generic
        clouds_pct=0,         # not requested
        rain_mm=precip_mm,
        city="Unknown",       # Reverse geocoding not included
        country="",
    )


def assess_operational_impact(weather: WeatherData) -> list[dict]:
    """Assess weather impact on military operations."""
    impacts = []

    if weather.visibility_km < 1:
        impacts.append({
            "factor": "Visibility",
            "status": "Critical",
            "color": "#FF2D55",
            "detail": f"Visibility {weather.visibility_km:.1f} km — severely limits aerial reconnaissance and ground observation.",
        })
    elif weather.visibility_km < 5:
        impacts.append({
            "factor": "Visibility",
            "status": "Degraded",
            "color": "#FF6B35",
            "detail": f"Visibility {weather.visibility_km:.1f} km — reduced effectiveness of visual surveillance.",
        })
    else:
        impacts.append({
            "factor": "Visibility",
            "status": "Good",
            "color": "#34C759",
            "detail": f"Visibility {weather.visibility_km:.1f} km — no operational impact.",
        })

    if weather.wind_speed_ms > 15:
        impacts.append({
            "factor": "Wind",
            "status": "Critical",
            "color": "#FF2D55",
            "detail": f"Wind {weather.wind_speed_ms:.0f} m/s — UAV operations grounded, helicopter ops restricted.",
        })
    elif weather.wind_speed_ms > 8:
        impacts.append({
            "factor": "Wind",
            "status": "Degraded",
            "color": "#FF6B35",
            "detail": f"Wind {weather.wind_speed_ms:.0f} m/s — small UAV operations affected.",
        })
    else:
        impacts.append({
            "factor": "Wind",
            "status": "Good",
            "color": "#34C759",
            "detail": f"Wind {weather.wind_speed_ms:.0f} m/s — all aerial operations clear.",
        })

    if weather.rain_mm > 10:
        impacts.append({
            "factor": "Precipitation",
            "status": "Critical",
            "color": "#FF2D55",
            "detail": f"Heavy rain ({weather.rain_mm:.0f} mm/h) — ground mobility severely impacted.",
        })
    elif weather.rain_mm > 2:
        impacts.append({
            "factor": "Precipitation",
            "status": "Degraded",
            "color": "#FF6B35",
            "detail": f"Moderate rain ({weather.rain_mm:.1f} mm/h) — unpaved road conditions degraded.",
        })
    else:
        impacts.append({
            "factor": "Precipitation",
            "status": "Good",
            "color": "#34C759",
            "detail": "No significant precipitation — normal ground operations.",
        })

    if weather.temperature_c > 45:
        impacts.append({
            "factor": "Temperature",
            "status": "Critical",
            "color": "#FF2D55",
            "detail": f"Extreme heat ({weather.temperature_c:.0f}°C) — heat casualty risk, equipment stress.",
        })
    elif weather.temperature_c < -15:
        impacts.append({
            "factor": "Temperature",
            "status": "Critical",
            "color": "#FF2D55",
            "detail": f"Extreme cold ({weather.temperature_c:.0f}°C) — cold weather injuries, equipment failures.",
        })
    else:
        impacts.append({
            "factor": "Temperature",
            "status": "Good",
            "color": "#34C759",
            "detail": f"Temperature {weather.temperature_c:.0f}°C — within operational limits.",
        })

    return impacts
