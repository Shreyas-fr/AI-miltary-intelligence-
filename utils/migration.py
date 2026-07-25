"""
utils/migration.py — Predictive Hotspot Migration Analysis
============================================================
Computes how DBSCAN hotspot centroids shift over time and predicts
future migration directions using linear extrapolation.

Algorithm
---------
1. Split the incident data into temporal windows (e.g., 5-year bins).
2. Run DBSCAN within each window to find hotspot centroids.
3. Match hotspots across windows using nearest-centroid linking.
4. Compute drift vectors (direction + magnitude in km) using haversine.
5. Extrapolate next-period centroid position using linear projection.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points in km."""
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(a))


def compute_window_centroids(
    df: pd.DataFrame,
    window_years: int = 5,
    eps_km: float = 150.0,
    min_samples: int = 10,
) -> pd.DataFrame:
    """Compute DBSCAN cluster centroids for each temporal window.

    Returns a DataFrame with columns:
        window_start, window_end, cluster, centroid_lat, centroid_lon, incidents
    """
    df = df.dropna(subset=["latitude", "longitude", "iyear"]).copy()
    if df.empty:
        return pd.DataFrame(columns=[
            "window_start", "window_end", "cluster",
            "centroid_lat", "centroid_lon", "incidents",
        ])

    min_year = int(df["iyear"].min())
    max_year = int(df["iyear"].max())
    eps_rad = eps_km / EARTH_RADIUS_KM

    records = []
    for start in range(min_year, max_year + 1, window_years):
        end = min(start + window_years - 1, max_year)
        window_df = df[(df["iyear"] >= start) & (df["iyear"] <= end)]
        if len(window_df) < min_samples:
            continue

        coords_rad = np.radians(window_df[["latitude", "longitude"]].values)
        labels = DBSCAN(
            eps=eps_rad, min_samples=min_samples,
            metric="haversine", algorithm="ball_tree",
        ).fit_predict(coords_rad)

        window_df = window_df.copy()
        window_df["_cluster"] = labels

        for cid in sorted(set(labels) - {-1}):
            cluster_pts = window_df[window_df["_cluster"] == cid]
            records.append({
                "window_start": start,
                "window_end": end,
                "cluster": cid,
                "centroid_lat": float(cluster_pts["latitude"].mean()),
                "centroid_lon": float(cluster_pts["longitude"].mean()),
                "incidents": len(cluster_pts),
            })

    return pd.DataFrame(records)


def compute_migration_vectors(
    centroids_df: pd.DataFrame,
    max_link_km: float = 500.0,
) -> list[dict]:
    """Link centroids across time windows and compute drift vectors.

    Returns a list of migration records:
        from_lat, from_lon, to_lat, to_lon, drift_km, window_from, window_to
    """
    if centroids_df.empty:
        return []

    windows = sorted(centroids_df["window_start"].unique())
    migrations = []

    for i in range(len(windows) - 1):
        current = centroids_df[centroids_df["window_start"] == windows[i]]
        next_w = centroids_df[centroids_df["window_start"] == windows[i + 1]]

        for _, cur_row in current.iterrows():
            best_dist = max_link_km
            best_next = None

            for _, nxt_row in next_w.iterrows():
                dist = haversine_km(
                    cur_row["centroid_lat"], cur_row["centroid_lon"],
                    nxt_row["centroid_lat"], nxt_row["centroid_lon"],
                )
                if dist < best_dist:
                    best_dist = dist
                    best_next = nxt_row

            if best_next is not None:
                migrations.append({
                    "from_lat": float(cur_row["centroid_lat"]),
                    "from_lon": float(cur_row["centroid_lon"]),
                    "to_lat": float(best_next["centroid_lat"]),
                    "to_lon": float(best_next["centroid_lon"]),
                    "drift_km": round(best_dist, 1),
                    "from_incidents": int(cur_row["incidents"]),
                    "to_incidents": int(best_next["incidents"]),
                    "window_from": f"{int(cur_row['window_start'])}-{int(cur_row['window_end'])}",
                    "window_to": f"{int(best_next['window_start'])}-{int(best_next['window_end'])}",
                })

    return migrations


def predict_future_positions(
    migrations: list[dict],
) -> list[dict]:
    """Extrapolate future centroid positions from the last observed migration.

    Returns a list of predicted positions with arrows from current → predicted.
    """
    if not migrations:
        return []

    # Group by destination (latest window) and extrapolate
    predictions = []
    for mig in migrations:
        dlat = mig["to_lat"] - mig["from_lat"]
        dlon = mig["to_lon"] - mig["from_lon"]

        predicted_lat = mig["to_lat"] + dlat
        predicted_lon = mig["to_lon"] + dlon

        # Clamp to valid ranges
        predicted_lat = max(-85, min(85, predicted_lat))
        predicted_lon = max(-180, min(180, predicted_lon))

        predictions.append({
            "from_lat": mig["to_lat"],
            "from_lon": mig["to_lon"],
            "to_lat": predicted_lat,
            "to_lon": predicted_lon,
            "drift_km": mig["drift_km"],
            "window_from": mig["window_to"],
            "window_to": "Predicted",
            "source": "extrapolation",
        })

    return predictions
