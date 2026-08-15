"""
utils/geo_utils.py — Geolocation Utilities
==========================================
Provides reverse geocoding functionality using Nominatim (OpenStreetMap).
"""

import json
import time
from urllib.error import URLError
from urllib.request import Request, urlopen

import streamlit as st

@st.cache_data(ttl=86400)
def reverse_geocode(lat: float, lon: float) -> str:
    """Reverse geocode a lat/lon to a human-readable place name using Nominatim.
    
    Includes caching to prevent redundant lookups.
    Respects Nominatim's 1 request/sec rate limit for non-cached calls.
    Returns 'Unknown' if the request fails.
    """
    url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json"
    request = Request(url, headers={"User-Agent": "weather-app-v1 (contact@gmail.com)"})
    
    # Rate limit: Wait 1.1s before making the API call
    time.sleep(1.1)

    try:
        with urlopen(request, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (URLError, json.JSONDecodeError, Exception):
        return "Unknown"
    
    # Extract the best possible name
    address = data.get("address", {})
    if not address:
        name = data.get("display_name", "")
        if name:
            # display_name is often very long, take the first two parts
            parts = name.split(",")
            return ", ".join(parts[:2]).strip()
        return "Unknown"
    
    city = address.get("city") or address.get("town") or address.get("village") or address.get("county")
    country = address.get("country")
    
    if city and country:
        return f"{city}, {country}"
    elif country:
        return country
    elif city:
        return city
    
    return "Unknown"
