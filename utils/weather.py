"""
utils/weather.py — Weather Intelligence Integration
=====================================================
Fetches current weather conditions from OpenWeather API for operational
planning. Degrades gracefully without an API key.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from urllib.parse import urlencode
from urllib.request import Request, urlopen


OPENWEATHER_API = "https://api.openweathermap.org/data/2.5/weather"


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


def fetch_weather(
    lat: float,
    lon: float,
    api_key: str | None = None,
    timeout: int = 10,
) -> WeatherData | None:
    """Fetch current weather for a lat/lon coordinate.

    Returns None if the API key is missing or the request fails.
    """
    key = api_key or os.environ.get("OPENWEATHER_API_KEY")
    if not key:
        return None

    params = {
        "lat": lat,
        "lon": lon,
        "appid": key,
        "units": "metric",
    }
    url = f"{OPENWEATHER_API}?{urlencode(params)}"
    request = Request(url, headers={"User-Agent": "ai-intelligence-platform/1.0"})

    try:
        with urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception:
        return None

    weather_desc = data.get("weather", [{}])[0]
    main = data.get("main", {})
    wind = data.get("wind", {})
    rain = data.get("rain", {})

    return WeatherData(
        temperature_c=main.get("temp", 0),
        feels_like_c=main.get("feels_like", 0),
        humidity=main.get("humidity", 0),
        wind_speed_ms=wind.get("speed", 0),
        wind_direction=wind.get("deg", 0),
        visibility_km=data.get("visibility", 10000) / 1000,
        description=weather_desc.get("description", "unknown"),
        icon=weather_desc.get("icon", "01d"),
        pressure_hpa=main.get("pressure", 0),
        clouds_pct=data.get("clouds", {}).get("all", 0),
        rain_mm=rain.get("1h", 0),
        city=data.get("name", "Unknown"),
        country=data.get("sys", {}).get("country", ""),
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
