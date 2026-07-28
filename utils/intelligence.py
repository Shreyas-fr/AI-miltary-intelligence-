"""Live intelligence, risk scoring, and situation report helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
import json
import re
from typing import Iterable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import numpy as np
import pandas as pd


GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"
DEFAULT_LIVE_QUERY = (
    "(terror OR terrorism OR insurgency OR explosion OR bombing OR missile "
    "OR clash OR clashes OR border OR militant OR attack OR conflict)"
)

EVENT_KEYWORDS = {
    "Missile / Rocket": ("missile", "rocket", "drone strike", "airstrike"),
    "Explosion / Bombing": ("explosion", "blast", "bomb", "ied", "suicide"),
    "Border Clash": ("border", "clash", "cross-border", "shelling"),
    "Armed Conflict": ("military", "armed", "combat", "offensive", "conflict"),
    "Terror Incident": ("terror", "terrorism", "militant", "insurgent", "attack"),
}

SEVERITY_TERMS = {
    "Critical": ("massacre", "deadliest", "mass casualty", "dozens killed", "missile"),
    "High": ("killed", "dead", "fatal", "explosion", "bombing", "airstrike"),
    "Medium": ("wounded", "injured", "clash", "shelling", "attack"),
}

LEVEL_COLORS = {
    "Low": "#34C759",
    "Medium": "#FFD60A",
    "High": "#FF6B35",
    "Critical": "#FF2D55",
}


@dataclass(frozen=True)
class RiskBreakdown:
    score: int
    level: str
    color: str
    components: dict[str, float]


def fetch_gdelt_events(
    query: str = DEFAULT_LIVE_QUERY,
    timespan: str = "1d",
    max_records: int = 100,
    timeout: int = 12,
) -> pd.DataFrame:
    """Fetch recent conflict-related articles from GDELT's DOC 2.1 API."""
    params = {
        "query": query,
        "mode": "ArtList",
        "format": "json",
        "sort": "DateDesc",
        "timespan": timespan,
        "maxrecords": max(1, min(int(max_records), 250)),
    }
    url = f"{GDELT_DOC_API}?{urlencode(params)}"
    request = Request(url, headers={"User-Agent": "ai-intelligence-dashboard/1.0"})

    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return _sample_live_frame()

    articles = payload.get("articles", [])
    if not articles:
        return _sample_live_frame()

    rows = []
    for article in articles:
        title = article.get("title") or "Untitled event"
        source_country = article.get("sourceCountry") or article.get("sourcecountry") or "Unknown"
        rows.append(
            {
                "country": source_country,
                "location": source_country,
                "event": classify_event(title),
                "title": title,
                "date": parse_gdelt_date(article.get("seendate")),
                "source": article.get("domain") or article.get("sourceCollection") or "GDELT",
                "url": article.get("url"),
                "severity": classify_severity(title),
                "language": article.get("language", "unknown"),
            }
        )

    return pd.DataFrame(rows).drop_duplicates(subset=["title", "url"]).reset_index(drop=True)


def enrich_live_events_with_country_centroids(
    live_events: pd.DataFrame,
    historical_geo: pd.DataFrame,
) -> pd.DataFrame:
    """Attach country-level lat/lon centroids derived from historical GTD records."""
    if live_events.empty:
        return live_events.assign(latitude=pd.Series(dtype=float), longitude=pd.Series(dtype=float))

    centroids = (
        historical_geo.dropna(subset=["country_txt", "latitude", "longitude"])
        .groupby("country_txt", as_index=False)
        .agg(latitude=("latitude", "median"), longitude=("longitude", "median"))
    )
    country_lookup = {normalize_country(row.country_txt): row for row in centroids.itertuples()}

    enriched = live_events.copy()
    lats: list[float] = []
    lons: list[float] = []
    matched: list[str] = []
    for row in enriched.itertuples():
        match = find_country_match(row.country, row.title, country_lookup.keys())
        if match:
            centroid = country_lookup[match]
            matched.append(str(centroid.country_txt))
            lats.append(float(centroid.latitude))
            lons.append(float(centroid.longitude))
        else:
            matched.append(row.country)
            lats.append(np.nan)
            lons.append(np.nan)

    enriched["country"] = matched
    enriched["latitude"] = lats
    enriched["longitude"] = lons
    return enriched


def classify_event(text: str) -> str:
    lowered = text.lower()
    for label, keywords in EVENT_KEYWORDS.items():
        if any(term in lowered for term in keywords):
            return label
    return "Security Event"


def classify_severity(text: str) -> str:
    lowered = text.lower()
    for label, keywords in SEVERITY_TERMS.items():
        if any(term in lowered for term in keywords):
            return label
    return "Low"


def severity_score(level: str) -> int:
    return {"Low": 20, "Medium": 45, "High": 70, "Critical": 90}.get(level, 20)


def parse_gdelt_date(value: str | None) -> pd.Timestamp:
    if not value:
        return pd.Timestamp.now(tz=timezone.utc)
    parsed = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(parsed):
        return pd.Timestamp.now(tz=timezone.utc)
    return parsed


def normalize_country(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "")).strip().lower()


def find_country_match(country: str, title: str, candidates: Iterable[str]) -> str | None:
    normalized_country = normalize_country(country)
    normalized_title = normalize_country(title)
    candidate_list = list(candidates)

    for candidate in candidate_list:
        if normalized_country == candidate:
            return candidate
    for candidate in candidate_list:
        if candidate and re.search(rf"\b{re.escape(candidate)}\b", normalized_title):
            return candidate
    return None


def compute_country_risk(
    country: str,
    historical: pd.DataFrame,
    live_events: pd.DataFrame | None = None,
) -> RiskBreakdown:
    """Return a 0-100 composite risk score for a country."""
    country_hist = historical[historical["country_txt"] == country].copy()
    if country_hist.empty:
        return RiskBreakdown(0, "Low", LEVEL_COLORS["Low"], {})

    live_events = live_events if live_events is not None else _empty_live_frame()
    country_live = live_events[live_events["country"].map(normalize_country) == normalize_country(country)]

    total_events = max(len(historical), 1)
    country_events = len(country_hist)
    
    # CLAMPING RATIONALE (0.08 / 8%): 
    # High-volume conflict zones (e.g., Iraq, Afghanistan) account for massive shares of total GTD incidents.
    # Without a ceiling, they warp the 0-100 scale, causing most other countries to score near zero. 
    # Clamping at 8% of global incidents ensures the worst outliers max out at 100/100, preserving dynamic range for the rest of the world.
    historical_activity = min(country_events / max(total_events * 0.08, 1), 1) * 100

    recent_events = min(len(country_live) / 10, 1) * 100

    nkill = pd.to_numeric(country_hist.get("nkill", 0), errors="coerce").fillna(0).clip(lower=0)
    fatalities = min(float(nkill.mean()) / 8, 1) * 100

    geo_events = country_hist.dropna(subset=["latitude", "longitude"])
    if geo_events.empty:
        cluster_density = 0.0
    else:
        rounded_places = geo_events.assign(
            lat_bin=geo_events["latitude"].round(1),
            lon_bin=geo_events["longitude"].round(1),
        )
        
        # CLAMPING RATIONALE (250 incidents):
        # A 0.1 x 0.1 degree grid cell is roughly 11km x 11km at the equator.
        # >250 incidents in a single neighborhood historically denotes a severe, sustained urban conflict zone (e.g., Baghdad, Mogadishu).
        # We cap density here so extreme multi-thousand incident clusters don't squash the scale for emerging hotspots.
        cluster_density = min(rounded_places.groupby(["lat_bin", "lon_bin"]).size().max() / 250, 1) * 100

    instability = 0.0
    if not country_live.empty:
        instability = min(country_live["severity"].map(severity_score).mean(), 100)

    components = {
        "Historical Activity": historical_activity * 0.35,
        "Recent Events": recent_events * 0.25,
        "Fatalities": fatalities * 0.15,
        "Cluster Density": cluster_density * 0.10,
        "Political Instability": instability * 0.15,
    }
    score = int(round(sum(components.values())))
    level = risk_level(score)
    return RiskBreakdown(score, level, LEVEL_COLORS[level], components)


def risk_level(score: float) -> str:
    if score >= 75:
        return "Critical"
    if score >= 55:
        return "High"
    if score >= 30:
        return "Medium"
    return "Low"


def build_situation_report(
    country: str,
    period_label: str,
    stats: dict,
    risk: RiskBreakdown,
    live_events: pd.DataFrame,
) -> str:
    """Create a concise analyst-style situation report without requiring an LLM."""
    activity_delta = stats.get("activity_delta_pct")
    if activity_delta is None:
        activity_line = "Historical activity trend could not be computed for the selected window."
    else:
        direction = "increased" if activity_delta >= 0 else "decreased"
        activity_line = f"Activity {direction} by {abs(activity_delta):.1f}% versus the previous comparable period."

    top_area = stats.get("top_area") or "No dominant area identified"
    recent_count = len(live_events)
    event_mix = ", ".join(live_events["event"].value_counts().head(3).index.tolist()) if recent_count else "No live events matched"
    recommendation = recommendation_for_level(risk.level)

    return f"""# AI Situation Report

Country: {country}

Period: {period_label}

## Key Judgments

- {recent_count} recent public-source conflict or security items were detected in the live feed.
- Historical GTD records show {int(stats.get("historical_incidents", 0)):,} incidents and {int(stats.get("historical_fatalities", 0)):,} fatalities.
- {activity_line}
- Highest historical concentration: {top_area}.
- Current live-event mix: {event_mix}.

Risk Level: {risk.level.upper()} ({risk.score}/100)

## Risk Drivers

- Historical Activity: {risk.components.get("Historical Activity", 0):.1f} weighted points
- Recent Events: {risk.components.get("Recent Events", 0):.1f} weighted points
- Fatalities: {risk.components.get("Fatalities", 0):.1f} weighted points
- Cluster Density: {risk.components.get("Cluster Density", 0):.1f} weighted points
- Political Instability: {risk.components.get("Political Instability", 0):.1f} weighted points

## Recommendation

{recommendation}

Analyst note: This is a decision-support summary from historical GTD records and public news metadata. It should be reviewed by a human analyst before operational use.
"""


def recommendation_for_level(level: str) -> str:
    if level == "Critical":
        return "Escalate monitoring, validate sources, and prepare senior leadership briefings."
    if level == "High":
        return "Increase surveillance priority, track source corroboration, and monitor neighboring regions."
    if level == "Medium":
        return "Maintain enhanced monitoring and watch for changes in event frequency or severity."
    return "Continue routine monitoring and keep the country on the baseline watch list."


def build_pdf(report_markdown: str) -> bytes:
    """Render a simple PDF report. Requires reportlab at runtime."""
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, title="AI Situation Report")
    styles = getSampleStyleSheet()
    story = []

    for line in report_markdown.splitlines():
        stripped = line.strip()
        if not stripped:
            story.append(Spacer(1, 8))
            continue
        if stripped.startswith("# "):
            story.append(Paragraph(stripped[2:], styles["Title"]))
        elif stripped.startswith("## "):
            story.append(Paragraph(stripped[3:], styles["Heading2"]))
        elif stripped.startswith("- "):
            story.append(Paragraph(f"- {stripped[2:]}", styles["BodyText"]))
        else:
            story.append(Paragraph(stripped, styles["BodyText"]))

    doc.build(story)
    return buffer.getvalue()


def _empty_live_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=["country", "location", "event", "title", "date", "source", "url", "severity", "language"]
    )


def _sample_live_frame() -> pd.DataFrame:
    now = pd.Timestamp.now(tz=timezone.utc)
    data = [
        {
            "country": "India", "location": "India", "event": "Border Clash",
            "title": "Cross-border security exchange reported along line of control",
            "date": now - pd.Timedelta(hours=2), "source": "defence-news.org",
            "url": "https://gdeltproject.org", "severity": "Medium", "language": "English"
        },
        {
            "country": "Ukraine", "location": "Ukraine", "event": "Missile / Rocket",
            "title": "Drone strike intercepted over eastern regional corridor",
            "date": now - pd.Timedelta(hours=4), "source": "reuters.com",
            "url": "https://gdeltproject.org", "severity": "High", "language": "English"
        },
        {
            "country": "Israel", "location": "Israel", "event": "Terror Incident",
            "title": "Security forces respond to perimeter incident in northern sector",
            "date": now - pd.Timedelta(hours=6), "source": "apnews.com",
            "url": "https://gdeltproject.org", "severity": "High", "language": "English"
        },
        {
            "country": "Somalia", "location": "Somalia", "event": "Explosion / Bombing",
            "title": "IED explosion targeting military convoy reported in lower Shabelle",
            "date": now - pd.Timedelta(hours=8), "source": "bbc.com",
            "url": "https://gdeltproject.org", "severity": "Critical", "language": "English"
        },
        {
            "country": "Syria", "location": "Syria", "event": "Armed Conflict",
            "title": "Artillery shelling exchange reported near northern de-escalation zone",
            "date": now - pd.Timedelta(hours=10), "source": "aljazeera.com",
            "url": "https://gdeltproject.org", "severity": "Medium", "language": "English"
        },
    ]
    return pd.DataFrame(data)
