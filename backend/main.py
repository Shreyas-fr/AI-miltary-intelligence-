from pathlib import Path

import duckdb
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from utils.hotspot_utils import cluster_hotspots, compute_tsi

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = PROJECT_ROOT / "data" / "globalterrorism.csv"

app = FastAPI(title="AI Military Intelligence API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _dataset_sql() -> str:
    if not DATASET_PATH.exists():
        raise FileNotFoundError(f"Dataset not found at {DATASET_PATH}")
    escaped = str(DATASET_PATH).replace("'", "''")
    return f"read_csv_auto('{escaped}', header=true, sample_size=-1, all_varchar=false)"


def _summary_query() -> str:
    return f"""
    SELECT
        COUNT(*) AS total_incidents,
        COUNT(DISTINCT country_txt) AS unique_countries,
        COUNT(DISTINCT region_txt) AS unique_regions,
        MIN(iyear) AS first_year,
        MAX(iyear) AS last_year
    FROM {_dataset_sql()}
    """


def _incident_query() -> str:
    return f"""
    SELECT latitude, longitude, nkill, nwound, success, iyear, country_txt, region_txt
    FROM {_dataset_sql()}
    WHERE latitude IS NOT NULL
      AND longitude IS NOT NULL
      AND iyear IS NOT NULL
    """


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/summary")
def summary() -> dict:
    try:
        with duckdb.connect(database=":memory:") as connection:
            row = connection.execute(_summary_query()).fetchone()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {
        "total_incidents": int(row[0] or 0),
        "unique_countries": int(row[1] or 0),
        "unique_regions": int(row[2] or 0),
        "first_year": int(row[3] or 0),
        "last_year": int(row[4] or 0),
    }


@app.get("/api/hotspots")
def hotspots(
    eps_km: float = Query(default=100.0, ge=1.0, le=500.0),
    min_samples: int = Query(default=15, ge=2, le=100),
) -> dict:
    try:
        with duckdb.connect(database=":memory:") as connection:
            incidents = connection.execute(_incident_query()).fetch_df()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    scored = compute_tsi(incidents)
    clustered, hotspot_summary = cluster_hotspots(scored, eps_km=eps_km, min_samples=min_samples)

    hotspots_payload = []
    for row in hotspot_summary.to_dict(orient="records"):
        hotspots_payload.append(
            {
                "cluster": int(row["cluster"]),
                "rank": int(row["rank"]),
                "incidents": int(row["incidents"]),
                "total_tsi": float(row["total_tsi"]),
                "avg_tsi": float(row["avg_tsi"]),
                "centroid_lat": float(row["centroid_lat"]),
                "centroid_lon": float(row["centroid_lon"]),
                "countries": row["countries"],
            }
        )

    noise_incidents = int((clustered["cluster"] == -1).sum()) if "cluster" in clustered.columns else 0

    return {
        "parameters": {"eps_km": eps_km, "min_samples": min_samples},
        "hotspots": hotspots_payload,
        "hotspot_count": len(hotspots_payload),
        "noise_incidents": noise_incidents,
    }
