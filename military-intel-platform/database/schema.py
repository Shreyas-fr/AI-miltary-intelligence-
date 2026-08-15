"""
database/schema.py — GDELT → GTD Schema Normalisation
=======================================================
Maps GDELT live event fields to a GTD-compatible row schema
so that live incidents can be merged with historical data for
all prediction models.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Attack type mapping: GDELT event category → GTD attacktype1_txt
# ---------------------------------------------------------------------------
GDELT_TO_ATTACK_TYPE: dict[str, str] = {
    "Missile / Rocket":   "Bombing/Explosion",
    "Explosion / Bombing": "Bombing/Explosion",
    "Border Clash":       "Armed Assault",
    "Armed Conflict":     "Armed Assault",
    "Terror Incident":    "Unknown",
    "Hostage / Kidnap":   "Hostage Taking (Kidnapping)",
    "Assassination":      "Assassination",
    "Cyberattack":        "Facility/Infrastructure Attack",
    "Unknown":            "Unknown",
}


# ---------------------------------------------------------------------------
# Country → GTD region lookup (abbreviated — covers most GDELT countries)
# ---------------------------------------------------------------------------
COUNTRY_TO_REGION: dict[str, str] = {
    # Middle East & North Africa
    "Iraq": "Middle East & North Africa",
    "Syria": "Middle East & North Africa",
    "Israel": "Middle East & North Africa",
    "Lebanon": "Middle East & North Africa",
    "Yemen": "Middle East & North Africa",
    "Libya": "Middle East & North Africa",
    "Egypt": "Middle East & North Africa",
    "Jordan": "Middle East & North Africa",
    "Saudi Arabia": "Middle East & North Africa",
    "Iran": "Middle East & North Africa",
    "Turkey": "Middle East & North Africa",
    # South Asia
    "India": "South Asia",
    "Pakistan": "South Asia",
    "Afghanistan": "South Asia",
    "Bangladesh": "South Asia",
    "Sri Lanka": "South Asia",
    "Nepal": "South Asia",
    # Sub-Saharan Africa
    "Nigeria": "Sub-Saharan Africa",
    "Somalia": "Sub-Saharan Africa",
    "Mali": "Sub-Saharan Africa",
    "Niger": "Sub-Saharan Africa",
    "Sudan": "Sub-Saharan Africa",
    "South Sudan": "Sub-Saharan Africa",
    "Ethiopia": "Sub-Saharan Africa",
    "Kenya": "Sub-Saharan Africa",
    "Mozambique": "Sub-Saharan Africa",
    "Democratic Republic of the Congo": "Sub-Saharan Africa",
    "Cameroon": "Sub-Saharan Africa",
    "Burkina Faso": "Sub-Saharan Africa",
    "Chad": "Sub-Saharan Africa",
    # Eastern Europe
    "Ukraine": "Eastern Europe",
    "Russia": "Eastern Europe",
    "Georgia": "Eastern Europe",
    # Western Europe
    "France": "Western Europe",
    "Germany": "Western Europe",
    "Spain": "Western Europe",
    "United Kingdom": "Western Europe",
    "Italy": "Western Europe",
    "Belgium": "Western Europe",
    # North America
    "United States": "North America",
    "Mexico": "North America",
    "Canada": "North America",
    # South America
    "Colombia": "South America",
    "Brazil": "South America",
    "Venezuela": "South America",
    "Peru": "South America",
    # Southeast Asia
    "Philippines": "Southeast Asia",
    "Myanmar": "Southeast Asia",
    "Indonesia": "Southeast Asia",
    "Thailand": "Southeast Asia",
    # Central Asia
    "Kazakhstan": "Central Asia",
    "Kyrgyzstan": "Central Asia",
}


# ---------------------------------------------------------------------------
# Weapon type inference from attack type
# ---------------------------------------------------------------------------
ATTACK_TO_WEAPON: dict[str, str] = {
    "Bombing/Explosion":               "Explosives",
    "Armed Assault":                   "Firearms",
    "Assassination":                   "Firearms",
    "Hostage Taking (Kidnapping)":     "Unknown",
    "Facility/Infrastructure Attack":  "Unknown",
    "Unknown":                         "Unknown",
}


# ---------------------------------------------------------------------------
# Severity → estimated casualty ranges (median estimate)
# ---------------------------------------------------------------------------
SEVERITY_TO_NKILL: dict[str, int] = {
    "Critical": 5,
    "High":     2,
    "Medium":   0,
    "Low":      0,
}
SEVERITY_TO_NWOUND: dict[str, int] = {
    "Critical": 10,
    "High":     5,
    "Medium":   2,
    "Low":      0,
}


def make_source_id(title: str, date_str: str = "") -> str:
    """Generate a stable SHA-256 deduplication key.

    Uses title only (normalised) to ensure identical articles are detected
    as duplicates even if fetched at different timestamps.
    """
    raw = title.strip().lower()
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:40]


def normalize_live_row(row: dict) -> dict:
    """Convert a single GDELT live event dict to a GTD-compatible dict.

    Parameters
    ----------
    row : dict
        A row from the live events DataFrame with keys:
        country, location, event, title, date, source, url, severity

    Returns
    -------
    dict with GTD-compatible keys plus source_id and ingested_at.
    """
    event_type = row.get("event", "Unknown")
    severity   = row.get("severity", "Low")
    country    = str(row.get("country") or "Unknown").strip()
    title      = str(row.get("title") or "").strip()
    location   = str(row.get("location") or country).strip()
    date_raw   = row.get("date")

    # Parse date to extract year/month/day
    iyear, imonth, iday = None, None, None
    try:
        if isinstance(date_raw, datetime):
            dt = date_raw
        else:
            dt = datetime.fromisoformat(str(date_raw))
        iyear, imonth, iday = dt.year, dt.month, dt.day
    except Exception:
        now = datetime.now(tz=timezone.utc)
        iyear, imonth, iday = now.year, now.month, now.day

    # Normalise mappings
    attack_type = GDELT_TO_ATTACK_TYPE.get(event_type, "Unknown")
    weapon_type = ATTACK_TO_WEAPON.get(attack_type, "Unknown")
    region      = COUNTRY_TO_REGION.get(country, "Unknown")
    nkill       = SEVERITY_TO_NKILL.get(severity, 0)
    nwound      = SEVERITY_TO_NWOUND.get(severity, 0)

    # Latitude/longitude default to None — enriched later from centroid table
    return {
        "source_id":       make_source_id(title, date_raw),
        "ingested_at":     datetime.now(tz=timezone.utc).isoformat(),
        "iyear":           iyear,
        "imonth":          imonth,
        "iday":            iday,
        "country_txt":     country,
        "region_txt":      region,
        "city":            location if location != country else None,
        "attacktype1_txt": attack_type,
        "weaptype1_txt":   weapon_type,
        "targtype1_txt":   "Unknown",
        "gname":           "Unknown Group",
        "latitude":        row.get("latitude"),
        "longitude":       row.get("longitude"),
        "nkill":           nkill,
        "nwound":          nwound,
        "success":         1,
        "suicide":         0,
        "source_label":    "GDELT",
        "original_title":  title,
        "severity":        severity,
    }
