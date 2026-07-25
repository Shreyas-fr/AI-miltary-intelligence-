"""FastAPI backend for the AI military intelligence platform."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.error import HTTPError

import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sklearn.cluster import DBSCAN
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder

from backend.database import PROJECT_ROOT, load_data, query_data
from utils.intelligence import (
    DEFAULT_LIVE_QUERY,
    build_pdf,
    build_situation_report,
    compute_country_risk,
    enrich_live_events_with_country_centroids,
    fetch_gdelt_events,
)
from utils.tsi import compute_tsi, tsi_label

app = FastAPI(title="AI Military Intelligence API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

LIVE_CACHE: dict[str, Any] = {"key": None, "data": None, "fetched_at": None, "status": "empty", "message": None}
CACHE_TTL = timedelta(minutes=15)


class ReportRequest(BaseModel):
    country: str
    timespan: str = "1d"
    query: str = DEFAULT_LIVE_QUERY
    max_records: int = 100


class AttackPredictionRequest(BaseModel):
    country_txt: str
    region_txt: str
    weaptype1_txt: str
    targtype1_txt: str
    gname: str
    success: int = 1
    suicide: int = 0
    nkill: int = 0
    nwound: int = 0


class ThreatPredictionRequest(BaseModel):
    country_txt: str
    region_txt: str
    attacktype1_txt: str
    weaptype1_txt: str
    targtype1_txt: str
    nkill: int = 2
    nwound: int = 5
    success: int = 1
    claimed: int = 0


@app.get("/")
@app.get("/api")
@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "ai-military-intelligence-api", "version": "1.0.0"}


@app.get("/api/overview")
def overview() -> dict[str, Any]:
    kpi = query_data(
        """
        SELECT
            COUNT(*) AS incidents,
            SUM(nkill) AS fatalities,
            SUM(nwound) AS injuries,
            COUNT(DISTINCT country_txt) AS countries
        FROM 'data/globalterrorism.csv'
        """
    ).iloc[0]
    return {
        "incidents": int(kpi["incidents"]),
        "fatalities": int(kpi["fatalities"] or 0),
        "injuries": int(kpi["injuries"] or 0),
        "countries": int(kpi["countries"]),
    }


@app.get("/api/yearly-trends")
def yearly_trends() -> list[dict[str, Any]]:
    return dataframe_records(
        query_data(
            """
            SELECT iyear AS year, COUNT(*) AS attacks
            FROM 'data/globalterrorism.csv'
            GROUP BY iyear
            ORDER BY iyear
            """
        )
    )


@app.get("/api/top-regions")
def top_regions(limit: int = Query(10, ge=1, le=25)) -> list[dict[str, Any]]:
    return dataframe_records(
        query_data(
            f"""
            SELECT region_txt AS region, COUNT(*) AS incidents
            FROM 'data/globalterrorism.csv'
            WHERE region_txt IS NOT NULL
            GROUP BY region_txt
            ORDER BY incidents DESC
            LIMIT {limit}
            """
        )
    )


@app.get("/api/attack-types")
def attack_types() -> list[dict[str, Any]]:
    return dataframe_records(
        query_data(
            """
            SELECT attacktype1_txt AS attack_type, COUNT(*) AS count
            FROM 'data/globalterrorism.csv'
            WHERE attacktype1_txt IS NOT NULL
            GROUP BY attacktype1_txt
            ORDER BY count DESC
            """
        )
    )


@app.get("/api/settings")
def settings() -> dict[str, Any]:
    stats = query_data(
        """
        SELECT
            COUNT(*) AS rows,
            COUNT(DISTINCT country_txt) AS countries,
            MIN(iyear) AS from_year,
            MAX(iyear) AS to_year
        FROM 'data/globalterrorism.csv'
        """
    ).iloc[0]
    columns = query_data("DESCRIBE SELECT * FROM 'data/globalterrorism.csv'")
    return {
        "dataset": {
            "rows": int(stats["rows"]),
            "countries": int(stats["countries"]),
            "from_year": int(stats["from_year"]),
            "to_year": int(stats["to_year"]),
            "columns": columns["column_name"].tolist(),
        },
        "theme": {
            "base": "dark",
            "primaryColor": "#00E5FF",
            "backgroundColor": "#0A0E17",
            "secondaryBackgroundColor": "#141C2B",
            "textColor": "#E0E6ED",
        },
        "about": {
            "app": "AI Military Intelligence Dashboard",
            "data_source": "Global Terrorism Database (GTD)",
            "ml_framework": "scikit-learn",
            "ai_engine": "Google Gemini 2.5 Flash",
            "data_engine": "DuckDB in-memory SQL",
            "framework": "FastAPI + React, mirrored from Streamlit",
        },
    }


@app.get("/api/global-threat-map")
def global_threat_map(
    year: str = "All",
    eps_km: int = Query(150, ge=50, le=500),
    min_samples: int = Query(8, ge=3, le=30),
) -> dict[str, Any]:
    where_year = "" if year == "All" else f"AND iyear = {int(year)}"
    df = query_data(
        f"""
        SELECT latitude, longitude, nkill, country_txt
        FROM 'data/globalterrorism.csv'
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL {where_year}
        """
    )
    if df.empty:
        return {"summary": {"incidents": 0, "clusters": 0, "noise": 0, "clustered": 0}, "points": [], "clusters": []}
    df["nkill"] = pd.to_numeric(df["nkill"], errors="coerce").fillna(0)
    labels = dbscan_labels(df, eps_km, min_samples)
    df["cluster"] = labels
    clusters = cluster_summary(df, value_column="nkill")
    return {
        "summary": {
            "incidents": int(len(df)),
            "clusters": int(len(clusters)),
            "noise": int((labels == -1).sum()),
            "clustered": int((labels != -1).sum()),
        },
        "points": dataframe_records(df),
        "clusters": clusters,
    }


@app.get("/api/hotspots")
def hotspots(
    eps_km: int = Query(100, ge=25, le=500),
    min_samples: int = Query(15, ge=5, le=50),
) -> dict[str, Any]:
    df = query_data(
        """
        SELECT latitude, longitude, nkill, nwound, success, iyear, country_txt, region_txt
        FROM 'data/globalterrorism.csv'
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
        """
    )
    if df.empty:
        return {"summary": {"hotspots": 0, "clustered": 0, "noise": 0}, "points": [], "hotspots": []}
    df["tsi"] = hotspot_tsi(df)
    labels = dbscan_labels(df, eps_km, min_samples)
    df["cluster"] = labels
    summaries = cluster_summary(df, value_column="tsi", country_column="country_txt")
    return {
        "summary": {
            "hotspots": int(len(summaries)),
            "clustered": int((labels != -1).sum()),
            "noise": int((labels == -1).sum()),
        },
        "points": dataframe_records(df[df["cluster"] != -1]),
        "hotspots": summaries,
    }


@app.get("/api/data-explorer/facets")
def data_explorer_facets() -> dict[str, list[Any]]:
    facets = {}
    for key, column in {
        "years": "iyear",
        "countries": "country_txt",
        "regions": "region_txt",
        "attack_types": "attacktype1_txt",
        "weapons": "weaptype1_txt",
        "groups": "gname",
    }.items():
        values = query_data(
            f"""
            SELECT DISTINCT {column} AS value
            FROM 'data/globalterrorism.csv'
            WHERE {column} IS NOT NULL
            ORDER BY value
            """
        )["value"].tolist()
        facets[key] = values
    return facets


@app.get("/api/data-explorer")
def data_explorer(
    years: str = "",
    countries_filter: str = "",
    regions_filter: str = "",
    attacks_filter: str = "",
    weapons_filter: str = "",
    groups_filter: str = "",
    search: str = "",
    limit: int = Query(500, ge=1, le=2000),
) -> dict[str, Any]:
    where = build_filter_where(
        {
            "iyear": years,
            "country_txt": countries_filter,
            "region_txt": regions_filter,
            "attacktype1_txt": attacks_filter,
            "weaptype1_txt": weapons_filter,
            "gname": groups_filter,
        },
        search,
    )
    summary = query_data(
        f"""
        SELECT
            COUNT(*) AS incidents,
            COUNT(DISTINCT country_txt) AS countries,
            SUM(nkill) AS fatalities,
            SUM(nwound) AS injuries
        FROM 'data/globalterrorism.csv'
        {where}
        """
    ).iloc[0]
    rows = query_data(f"SELECT * FROM 'data/globalterrorism.csv' {where} LIMIT {limit}")
    return {
        "summary": {
            "incidents": int(summary["incidents"] or 0),
            "countries": int(summary["countries"] or 0),
            "fatalities": int(summary["fatalities"] or 0),
            "injuries": int(summary["injuries"] or 0),
            "columns": rows.columns.tolist(),
        },
        "by_country": grouped_records_where(where, "country_txt", "country", 10),
        "attack_types": grouped_records_where(where, "attacktype1_txt", "attack_type", 20),
        "weapon_types": grouped_records_where(where, "weaptype1_txt", "weapon", 20),
        "rows": dataframe_records(rows),
    }


@app.get("/api/prediction/options")
def prediction_options() -> dict[str, list[Any]]:
    cols = ["country_txt", "region_txt", "attacktype1_txt", "weaptype1_txt", "targtype1_txt", "gname"]
    return {col: distinct_values(col) for col in cols}


@lru_cache(maxsize=1)
def _load_attack_models():
    model = joblib.load(PROJECT_ROOT / "models" / "attack_prediction_model.pkl")
    target_encoder = joblib.load(PROJECT_ROOT / "models" / "target_encoder.pkl")
    target_feature_encoder = joblib.load(PROJECT_ROOT / "models" / "target_feature_encoder.pkl")
    cat_imputer = joblib.load(PROJECT_ROOT / "models" / "cat_imputer.pkl")
    num_imputer = joblib.load(PROJECT_ROOT / "models" / "num_imputer.pkl")
    return model, target_encoder, target_feature_encoder, cat_imputer, num_imputer


@app.post("/api/predict-attack")
def predict_attack(payload: AttackPredictionRequest) -> dict[str, Any]:
    try:
        model, target_encoder, target_feature_encoder, cat_imputer, num_imputer = _load_attack_models()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Model loading failed: {exc}") from exc

    cat_cols = ["country_txt", "region_txt", "weaptype1_txt", "targtype1_txt", "gname"]
    num_cols = ["success", "suicide", "nkill", "nwound"]
    input_data = pd.DataFrame([payload.model_dump()])
    input_data[cat_cols] = cat_imputer.transform(input_data[cat_cols])
    input_data[num_cols] = num_imputer.transform(input_data[num_cols])
    cat_encoded = target_feature_encoder.transform(input_data[cat_cols])
    final = np.hstack([cat_encoded, input_data[num_cols].values])
    probabilities = model.predict_proba(final)[0]
    labels = target_encoder.classes_
    sorted_idx = probabilities.argsort()[::-1][:8]
    prediction = labels[int(sorted_idx[0])]
    return {
        "prediction": prediction,
        "confidence": float(probabilities[sorted_idx[0]] * 100),
        "probabilities": [
            {"label": str(labels[i]), "probability": float(probabilities[i] * 100)}
            for i in sorted_idx
        ],
    }


@app.post("/api/predict-threat")
def predict_threat(payload: ThreatPredictionRequest) -> dict[str, Any]:
    model, encoders, target_enc, feature_importance = build_threat_model()
    input_enc = np.array(
        [[
            safe_transform(encoders["country_txt"], payload.country_txt),
            safe_transform(encoders["region_txt"], payload.region_txt),
            safe_transform(encoders["attacktype1_txt"], payload.attacktype1_txt),
            safe_transform(encoders["weaptype1_txt"], payload.weaptype1_txt),
            safe_transform(encoders["targtype1_txt"], payload.targtype1_txt),
            payload.nkill,
            payload.nwound,
        ]]
    )
    probabilities = model.predict_proba(input_enc)[0]
    prediction = model.predict(input_enc)
    result = target_enc.inverse_transform(prediction)[0]
    tsi_score = single_tsi(payload.nkill, payload.nwound, payload.success, payload.claimed)
    return {
        "level": str(result),
        "confidence": float(probabilities.max() * 100),
        "tsi_score": tsi_score,
        "tsi_label": tsi_label_for_score(tsi_score),
        "probabilities": [
            {"label": str(label), "probability": float(prob * 100)}
            for label, prob in zip(target_enc.classes_, probabilities)
        ],
        "feature_importance": feature_importance,
    }

@app.get("/api/countries")
def countries(sort: str = Query("incidents", pattern="^(incidents|name)$")) -> list[dict[str, Any]]:
    order_by = "country_txt ASC" if sort == "name" else "incidents DESC"
    return dataframe_records(
        query_data(
            f"""
            SELECT country_txt AS country, COUNT(*) AS incidents
            FROM 'data/globalterrorism.csv'
            WHERE country_txt IS NOT NULL
            GROUP BY country_txt
            ORDER BY {order_by}
            """
        )
    )


@app.get("/api/country-analysis/{country}")
def country_analysis(country: str) -> dict[str, Any]:
    escaped_country = sql_literal(country)
    area_column = first_existing_column(["provstate", "city", "region_txt"])
    location_expr = "COALESCE(" + ", ".join(existing_columns(["provstate", "city", "region_txt"])) + ", 'Unknown')"
    summary = query_data(
        f"""
        SELECT
            COUNT(*) AS incidents,
            SUM(nkill) AS fatalities,
            SUM(nwound) AS injuries,
            COUNT(DISTINCT gname) AS groups,
            MIN(iyear) AS first_year,
            MAX(iyear) AS latest_year
        FROM 'data/globalterrorism.csv'
        WHERE country_txt = {escaped_country}
        """
    ).iloc[0]
    if int(summary["incidents"] or 0) == 0:
        raise HTTPException(status_code=404, detail=f"No records found for {country}")

    return {
        "country": country,
        "summary": {
            "incidents": int(summary["incidents"] or 0),
            "fatalities": int(summary["fatalities"] or 0),
            "injuries": int(summary["injuries"] or 0),
            "groups": int(summary["groups"] or 0),
            "first_year": int(summary["first_year"] or 0),
            "latest_year": int(summary["latest_year"] or 0),
        },
        "yearly": dataframe_records(
            query_data(
                f"""
                SELECT iyear AS year, COUNT(*) AS attacks, SUM(nkill) AS fatalities, SUM(nwound) AS injuries
                FROM 'data/globalterrorism.csv'
                WHERE country_txt = {escaped_country}
                GROUP BY iyear
                ORDER BY iyear
                """
            )
        ),
        "attack_types": grouped_country_records(country, "attacktype1_txt", "attack_type"),
        "weapon_types": grouped_country_records(country, "weaptype1_txt", "weapon_type"),
        "target_types": grouped_country_records(country, "targtype1_txt", "target_type"),
        "regions": grouped_country_records(country, "region_txt", "region"),
        "areas": grouped_country_records(country, area_column, "area", limit=12),
        "groups": grouped_country_records(country, "gname", "group", limit=12, exclude_unknown=True),
        "incident_locations": dataframe_records(
            query_data(
                f"""
                SELECT
                    iyear AS year,
                    {location_expr} AS location,
                    attacktype1_txt AS attack_type,
                    weaptype1_txt AS weapon_type,
                    targtype1_txt AS target_type,
                    gname AS group_name,
                    nkill AS fatalities,
                    nwound AS injuries,
                    latitude,
                    longitude
                FROM 'data/globalterrorism.csv'
                WHERE country_txt = {escaped_country}
                  AND latitude IS NOT NULL
                  AND longitude IS NOT NULL
                ORDER BY iyear DESC
                """
            )
        ),
        "incident_details": dataframe_records(
            query_data(
                f"""
                SELECT
                    iyear AS year,
                    {location_expr} AS location,
                    attacktype1_txt AS attack_type,
                    weaptype1_txt AS weapon_type,
                    targtype1_txt AS target_type,
                    gname AS group_name,
                    nkill AS fatalities,
                    nwound AS injuries,
                    latitude,
                    longitude
                FROM 'data/globalterrorism.csv'
                WHERE country_txt = {escaped_country}
                ORDER BY iyear DESC, COALESCE(nkill, 0) DESC, COALESCE(nwound, 0) DESC
                """
            )
        ),
    }


@app.get("/api/country-analysis/{country}/csv")
def country_analysis_csv(country: str) -> Response:
    escaped_country = sql_literal(country)
    df = query_data(f"SELECT * FROM 'data/globalterrorism.csv' WHERE country_txt = {escaped_country}")
    if df.empty:
        raise HTTPException(status_code=404, detail=f"No records found for {country}")
    filename = country.replace(" ", "_")
    return Response(
        df.to_csv(index=False),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}_country_data.csv"'},
    )


@app.get("/api/live-feed")
def live_feed(
    timespan: str = Query("1d", pattern="^(15m|1h|6h|1d|3d|7d)$"),
    max_records: int = Query(100, ge=1, le=250),
    query: str = DEFAULT_LIVE_QUERY,
) -> dict[str, Any]:
    events, status, message, fetched_at = get_live_events(query, timespan, max_records)
    return {
        "status": status,
        "message": message,
        "fetched_at": fetched_at.isoformat() if fetched_at else None,
        "events": dataframe_records(events),
    }


@app.get("/api/risk/{country}")
def risk(country: str, timespan: str = "1d") -> dict[str, Any]:
    historical = load_risk_history()
    events, status, message, _ = get_live_events(DEFAULT_LIVE_QUERY, timespan, 100)
    risk_breakdown = compute_country_risk(country, historical, events)
    country_live = events[events["country"].str.lower() == country.lower()] if not events.empty else events
    return {
        "country": country,
        "score": risk_breakdown.score,
        "level": risk_breakdown.level,
        "color": risk_breakdown.color,
        "components": risk_breakdown.components,
        "live_status": status,
        "live_message": message,
        "live_count": int(len(country_live)),
    }


@app.post("/api/situation-report")
def situation_report(payload: ReportRequest) -> dict[str, Any]:
    report, risk_payload, country_live = build_country_report(payload)
    return {"report": report, "risk": risk_payload, "recent_events": dataframe_records(country_live)}


@app.post("/api/situation-report/pdf")
def situation_report_pdf(payload: ReportRequest) -> Response:
    report, _, _ = build_country_report(payload)
    filename = payload.country.replace(" ", "_")
    return Response(
        build_pdf(report),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}_situation_report.pdf"'},
    )


def build_country_report(payload: ReportRequest):
    historical = load_risk_history()
    country_hist = historical[historical["country_txt"] == payload.country].copy()
    if country_hist.empty:
        raise HTTPException(status_code=404, detail=f"No historical records found for {payload.country}")

    events, status, message, _ = get_live_events(payload.query, payload.timespan, payload.max_records)
    country_live = events[events["country"].str.lower() == payload.country.lower()] if not events.empty else events
    risk_breakdown = compute_country_risk(payload.country, historical, events)
    stats = country_stats(country_hist)
    report = build_situation_report(
        payload.country,
        f"Live window: {payload.timespan}",
        stats,
        risk_breakdown,
        country_live,
    )
    risk_payload = {
        "score": risk_breakdown.score,
        "level": risk_breakdown.level,
        "color": risk_breakdown.color,
        "components": risk_breakdown.components,
        "live_status": status,
        "live_message": message,
    }
    return report, risk_payload, country_live


def get_live_events(query: str, timespan: str, max_records: int) -> tuple[pd.DataFrame, str, str | None, datetime | None]:
    now = datetime.now(timezone.utc)
    cache_key = f"{query}|{timespan}|{max_records}"
    cached_at = LIVE_CACHE.get("fetched_at")
    if LIVE_CACHE.get("key") == cache_key and LIVE_CACHE.get("data") is not None and cached_at:
        if now - cached_at < CACHE_TTL:
            return LIVE_CACHE["data"].copy(), LIVE_CACHE["status"], LIVE_CACHE["message"], cached_at

    try:
        live = fetch_gdelt_events(query=query, timespan=timespan, max_records=max_records)
        historical_geo = load_data(["country_txt", "latitude", "longitude"])
        events = enrich_live_events_with_country_centroids(live, historical_geo)
        update_live_cache(cache_key, events, "live", None, now)
        return events.copy(), "live", None, now
    except HTTPError as exc:
        if exc.code == 429:
            message = "Live GDELT quota is temporarily rate-limited. Showing cached or GTD historical fallback data."
        else:
            message = f"GDELT returned HTTP {exc.code}. Showing cached or GTD historical fallback data."
    except Exception as exc:
        message = f"Live GDELT fetch failed: {exc}. Showing cached or GTD historical fallback data."

    if LIVE_CACHE.get("data") is not None:
        return LIVE_CACHE["data"].copy(), "stale-cache", message, LIVE_CACHE["fetched_at"]

    fallback = historical_live_fallback(max_records)
    update_live_cache(cache_key, fallback, "historical-fallback", message, now)
    return fallback.copy(), "historical-fallback", message, now


def update_live_cache(key: str, data: pd.DataFrame, status: str, message: str | None, fetched_at: datetime) -> None:
    LIVE_CACHE.update({"key": key, "data": data.copy(), "status": status, "message": message, "fetched_at": fetched_at})


def historical_live_fallback(max_records: int) -> pd.DataFrame:
    rows = query_data(
        f"""
        SELECT
            country_txt AS country,
            country_txt AS location,
            attacktype1_txt AS event,
            iyear,
            nkill,
            nwound,
            latitude,
            longitude,
            gname
        FROM 'data/globalterrorism.csv'
        WHERE country_txt IS NOT NULL
        ORDER BY iyear DESC, COALESCE(nkill, 0) DESC, COALESCE(nwound, 0) DESC
        LIMIT {max_records}
        """
    )
    if rows.empty:
        return pd.DataFrame(columns=["country", "location", "event", "title", "date", "source", "url", "severity", "language"])

    fallback = rows.copy()
    fallback["title"] = fallback.apply(
        lambda row: f"Historical fallback: {row['event']} in {row['country']} ({int(row['iyear'])})",
        axis=1,
    )
    fallback["date"] = pd.to_datetime(fallback["iyear"].astype(int).astype(str) + "-12-31", utc=True)
    fallback["source"] = "GTD historical fallback"
    fallback["url"] = None
    fallback["language"] = "n/a"
    fallback["severity"] = fallback.apply(lambda row: severity_from_impact(row.get("nkill"), row.get("nwound")), axis=1)
    return fallback[["country", "location", "event", "title", "date", "source", "url", "severity", "language", "latitude", "longitude"]]


def severity_from_impact(nkill: Any, nwound: Any) -> str:
    killed = float(nkill or 0)
    wounded = float(nwound or 0)
    impact = killed * 2 + wounded
    if impact >= 50:
        return "Critical"
    if impact >= 15:
        return "High"
    if impact >= 3:
        return "Medium"
    return "Low"


def load_risk_history() -> pd.DataFrame:
    return load_data(existing_columns(["country_txt", "region_txt", "provstate", "city", "iyear", "nkill", "nwound", "latitude", "longitude"]))


def country_stats(country_hist: pd.DataFrame) -> dict[str, Any]:
    years = sorted(country_hist["iyear"].dropna().astype(int).unique().tolist())
    latest_year = years[-1] if years else None
    previous_year = years[-2] if len(years) > 1 else None
    latest_count = int((country_hist["iyear"] == latest_year).sum()) if latest_year else 0
    previous_count = int((country_hist["iyear"] == previous_year).sum()) if previous_year else 0
    activity_delta = ((latest_count - previous_count) / previous_count) * 100 if previous_count else None

    if "provstate" in country_hist.columns and not country_hist["provstate"].dropna().empty:
        top_area = country_hist["provstate"].value_counts().index[0]
    elif "city" in country_hist.columns and not country_hist["city"].dropna().empty:
        top_area = country_hist["city"].value_counts().index[0]
    elif "region_txt" in country_hist.columns and not country_hist["region_txt"].dropna().empty:
        top_area = country_hist["region_txt"].value_counts().index[0]
    else:
        top_area = None

    fatalities = pd.to_numeric(country_hist.get("nkill", 0), errors="coerce").fillna(0).sum()
    return {
        "historical_incidents": len(country_hist),
        "historical_fatalities": fatalities,
        "activity_delta_pct": activity_delta,
        "top_area": top_area,
    }


def dbscan_labels(df: pd.DataFrame, eps_km: int, min_samples: int) -> np.ndarray:
    coords = np.radians(df[["latitude", "longitude"]].values)
    eps_rad = eps_km / 6371.0
    return DBSCAN(eps=eps_rad, min_samples=min_samples, algorithm="ball_tree", metric="haversine").fit_predict(coords)


def cluster_summary(df: pd.DataFrame, value_column: str, country_column: str | None = None) -> list[dict[str, Any]]:
    clustered = df[df["cluster"] != -1]
    if clustered.empty:
        return []
    aggregations = {
        "incidents": ("cluster", "size"),
        "value": (value_column, "sum"),
        "lat": ("latitude", "mean"),
        "lon": ("longitude", "mean"),
    }
    if country_column:
        aggregations["country"] = (country_column, lambda x: x.mode().iat[0] if not x.mode().empty else "Unknown")
    summary = clustered.groupby("cluster").agg(**aggregations).reset_index()
    summary = summary.sort_values(["value", "incidents"], ascending=False).reset_index(drop=True)
    summary["rank"] = summary.index + 1
    return dataframe_records(summary.round({"value": 2, "lat": 4, "lon": 4}))


def hotspot_tsi(df: pd.DataFrame) -> pd.Series:
    return compute_tsi(df)


def distinct_values(column: str) -> list[Any]:
    return query_data(
        f"""
        SELECT DISTINCT {column} AS value
        FROM 'data/globalterrorism.csv'
        WHERE {column} IS NOT NULL
        ORDER BY value
        """
    )["value"].tolist()


def build_filter_where(filters: dict[str, str], search: str) -> str:
    conditions = []
    for column, raw_values in filters.items():
        if not raw_values:
            continue
        values = [value for value in raw_values.split("|") if value != ""]
        if values:
            conditions.append(f"{column} IN ({', '.join(sql_literal(str(value)) for value in values)})")
    if search:
        escaped = search.replace("'", "''")
        conditions.append(f"(city ILIKE '%{escaped}%' OR country_txt ILIKE '%{escaped}%')")
    return "WHERE " + " AND ".join(conditions) if conditions else ""


def grouped_records_where(where: str, column: str, alias: str, limit: int) -> list[dict[str, Any]]:
    return dataframe_records(
        query_data(
            f"""
            SELECT {column} AS {alias}, COUNT(*) AS incidents
            FROM 'data/globalterrorism.csv'
            {where}
            GROUP BY {column}
            ORDER BY incidents DESC
            LIMIT {limit}
            """
        )
    )


from utils.tsi import compute_single_tsi, tsi_label as canonical_tsi_label

@lru_cache(maxsize=1)
def build_threat_model():
    model_path = PROJECT_ROOT / "models" / "threat_prediction_model.pkl"
    encoders_path = PROJECT_ROOT / "models" / "threat_feature_encoders.pkl"
    target_enc_path = PROJECT_ROOT / "models" / "threat_encoder.pkl"
    feat_imp_path = PROJECT_ROOT / "models" / "threat_feature_importance.pkl"

    if model_path.exists() and encoders_path.exists() and target_enc_path.exists():
        model = joblib.load(model_path)
        encoders = joblib.load(encoders_path)
        target_enc = joblib.load(target_enc_path)
        if feat_imp_path.exists():
            feature_importance = joblib.load(feat_imp_path)
        else:
            names = ["Country", "Region", "Attack Type", "Weapon Type", "Target Type", "Killed", "Wounded"]
            feature_importance = [{"feature": name, "importance": float(value)} for name, value in zip(names, model.feature_importances_)]
        return model, encoders, target_enc, feature_importance

    # Fallback fit if model artifact is not pre-built
    df = load_data(["country_txt", "region_txt", "attacktype1_txt", "weaptype1_txt", "targtype1_txt", "nkill", "nwound", "success"])
    df = df.dropna(subset=["country_txt", "region_txt", "attacktype1_txt", "weaptype1_txt", "targtype1_txt"]).copy()
    df["nkill"] = pd.to_numeric(df["nkill"], errors="coerce").fillna(0)
    df["nwound"] = pd.to_numeric(df["nwound"], errors="coerce").fillna(0)
    df["impact"] = df["nkill"] + df["nwound"]
    df["threat_level"] = pd.cut(df["impact"], bins=[-1, 2, 10, np.inf], labels=["LOW", "MEDIUM", "HIGH"])
    cat_cols = ["country_txt", "region_txt", "attacktype1_txt", "weaptype1_txt", "targtype1_txt"]
    encoders = {}
    for col in cat_cols:
        encoder = LabelEncoder()
        df[col] = encoder.fit_transform(df[col].astype(str))
        encoders[col] = encoder
    target_enc = LabelEncoder()
    y = target_enc.fit_transform(df["threat_level"])
    X = df.drop(columns=["threat_level", "impact", "success"])
    model = RandomForestClassifier(n_estimators=100, class_weight="balanced", random_state=42, n_jobs=-1)
    model.fit(X, y)
    names = ["Country", "Region", "Attack Type", "Weapon Type", "Target Type", "Killed", "Wounded"]
    feature_importance = [{"feature": name, "importance": float(value)} for name, value in zip(names, model.feature_importances_)]
    return model, encoders, target_enc, feature_importance


def safe_transform(encoder: LabelEncoder, value: str) -> int:
    if value in encoder.classes_:
        return int(encoder.transform([value])[0])
    return 0


def single_tsi(nkill: int, nwound: int, success: int = 1, claimed: int = 0) -> float:
    return compute_single_tsi(nkill, nwound, success, claimed)


def tsi_label_for_score(score: float) -> str:
    lbl, _ = canonical_tsi_label(score)
    return lbl



def dataframe_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty:
        return []
    normalized = df.replace({pd.NA: None}).where(pd.notnull(df), None).copy()
    for column in normalized.columns:
        if pd.api.types.is_datetime64_any_dtype(normalized[column]):
            normalized[column] = normalized[column].apply(lambda value: value.isoformat() if value is not None else None)
    return normalized.to_dict(orient="records")


def dataset_columns() -> set[str]:
    columns = query_data("DESCRIBE SELECT * FROM 'data/globalterrorism.csv'")
    return set(columns["column_name"].tolist())


def existing_columns(candidates: list[str]) -> list[str]:
    available = dataset_columns()
    return [column for column in candidates if column in available]


def first_existing_column(candidates: list[str]) -> str:
    columns = existing_columns(candidates)
    if not columns:
        raise HTTPException(status_code=500, detail=f"Dataset missing expected columns: {', '.join(candidates)}")
    return columns[0]


def grouped_country_records(
    country: str,
    source_column: str,
    output_column: str,
    limit: int = 10,
    exclude_unknown: bool = False,
) -> list[dict[str, Any]]:
    escaped_country = sql_literal(country)
    extra_filter = ""
    if exclude_unknown:
        extra_filter = f"AND {source_column} NOT IN ('Unknown', 'Unknown/Other')"
    return dataframe_records(
        query_data(
            f"""
            SELECT {source_column} AS {output_column}, COUNT(*) AS incidents
            FROM 'data/globalterrorism.csv'
            WHERE country_txt = {escaped_country}
              AND {source_column} IS NOT NULL
              {extra_filter}
            GROUP BY {source_column}
            ORDER BY incidents DESC
            LIMIT {limit}
            """
        )
    )


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


frontend_dist = PROJECT_ROOT / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
