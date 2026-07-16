"""
Hotspot Detection & Forecasting Utilities
-------------------------------------------------------------------
Core ML logic for the Predictive Tactical Intelligence & Spatial-
Temporal Hotspot Forecasting Framework.

Contains:
  1. Threat Severity Index (TSI)      — non-linear casualty scoring
  2. Geospatial hotspot clustering     — DBSCAN w/ haversine distance
  3. Time-series forecasting           — SARIMA w/ train/test validation
                                          + linear-regression baseline
"""

import warnings

import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error
from statsmodels.tsa.statespace.sarimax import SARIMAX

warnings.filterwarnings("ignore")

EARTH_RADIUS_KM = 6371.0


# ===================================================================
# 1. Threat Severity Index (TSI)
# ===================================================================
def compute_tsi(
    df: pd.DataFrame,
    kill_weight: float = 3.0,
    wound_weight: float = 1.0,
    success_multiplier: float = 1.0,
    fail_multiplier: float = 0.4,
) -> pd.DataFrame:
    """
    Non-linear casualty-weighted severity score per incident.

        TSI = (kill_weight * nkill + wound_weight * nwound) ** 0.85 * success_factor

    Why non-linear (power 0.85, not 1.0): a purely linear sum lets a
    single catastrophic incident dominate an entire hotspot's score.
    Compressing the scale keeps ranking sensitive to *frequency and
    spread* of casualties across a hotspot, not just one outlier event,
    which matches how an intelligence analyst would actually assess
    "is this region a persistent threat corridor."
    """
    df = df.copy()
    nkill = df["nkill"].fillna(0).clip(lower=0)
    nwound = df["nwound"].fillna(0).clip(lower=0)

    raw_impact = kill_weight * nkill + wound_weight * nwound
    success = df["success"].fillna(1) if "success" in df.columns else pd.Series(1, index=df.index)
    success_factor = np.where(success == 1, success_multiplier, fail_multiplier)

    df["tsi"] = np.power(raw_impact, 0.85) * success_factor
    return df


# ===================================================================
# 2. DBSCAN Geospatial Hotspot Clustering
# ===================================================================
def cluster_hotspots(
    df: pd.DataFrame,
    eps_km: float = 100.0,
    min_samples: int = 15,
):
    """
    Clusters incidents into geographic hotspots using DBSCAN with a
    haversine distance metric (great-circle distance on a sphere) —
    far more accurate for lat/long data than naive Euclidean DBSCAN,
    which distorts distances away from the equator.

    Returns:
        df_clustered     — original df + 'cluster' column (-1 = noise)
        hotspot_summary  — one row per hotspot: centroid, incident
                            count, total/avg TSI, and a rank
    """
    df = df.dropna(subset=["latitude", "longitude"]).copy()

    coords_rad = np.radians(df[["latitude", "longitude"]].values)
    eps_rad = eps_km / EARTH_RADIUS_KM  # eps in km -> radians for haversine

    db = DBSCAN(eps=eps_rad, min_samples=min_samples, metric="haversine", algorithm="ball_tree")
    df["cluster"] = db.fit_predict(coords_rad)

    clustered = df[df["cluster"] != -1]

    hotspot_summary = (
        clustered.groupby("cluster")
        .agg(
            incidents=("cluster", "size"),
            total_tsi=("tsi", "sum"),
            avg_tsi=("tsi", "mean"),
            centroid_lat=("latitude", "mean"),
            centroid_lon=("longitude", "mean"),
            countries=("country_txt", lambda x: x.mode().iat[0] if not x.mode().empty else "Unknown"),
        )
        .reset_index()
        .sort_values("total_tsi", ascending=False)
        .reset_index(drop=True)
    )
    hotspot_summary["rank"] = hotspot_summary.index + 1

    return df, hotspot_summary


# ===================================================================
# 3. Time-Series Forecasting (SARIMA) with validation
# ===================================================================
def build_yearly_series(df: pd.DataFrame, cluster_id: int, value_col: str = "tsi") -> pd.Series:
    """Aggregate one hotspot's incidents into a yearly series (TSI sum or attack count)."""
    sub = df[df["cluster"] == cluster_id]
    yearly = sub.groupby("iyear").size() if value_col == "count" else sub.groupby("iyear")[value_col].sum()

    full_years = range(int(yearly.index.min()), int(yearly.index.max()) + 1)
    yearly = yearly.reindex(full_years, fill_value=0)
    yearly.index.name = "iyear"
    return yearly


def _grid_search_sarima(train: pd.Series):
    """
    Lightweight AIC-based order search over a small candidate set.
    Keeps the project self-contained (no pmdarima dependency) while
    still selecting the model by an objective criterion rather than
    guessing a fixed (p,d,q).
    """
    candidate_orders = [(1, 1, 1), (1, 1, 0), (0, 1, 1), (2, 1, 1), (1, 0, 1), (2, 1, 0)]
    seasonal_order = (0, 0, 0, 0)  # annual data — no sub-cycle seasonality to model
    best_aic, best_order, best_fit = np.inf, None, None

    for order in candidate_orders:
        try:
            fit = SARIMAX(
                train, order=order, seasonal_order=seasonal_order,
                enforce_stationarity=False, enforce_invertibility=False,
            ).fit(disp=False)
            if fit.aic < best_aic:
                best_aic, best_order, best_fit = fit.aic, order, fit
        except Exception:
            continue

    return best_fit, best_order


def forecast_hotspot(series: pd.Series, test_years: int = 3, forecast_years: int = 5) -> dict:
    """
    Train/test-splits a hotspot's yearly series, fits the best SARIMA
    model (by AIC), validates against held-out years, and forecasts
    forward. A linear-regression baseline is fit alongside for
    comparison — a single model with no baseline is weak evidence of
    model quality, and reviewers will ask for one anyway.
    """
    series = series.astype(float)
    n = len(series)
    test_years = min(test_years, max(1, n // 3))  # guard against tiny series

    train, test = series.iloc[: n - test_years], series.iloc[n - test_years :]

    # --- SARIMA ---
    model, order = _grid_search_sarima(train)
    if model is None:
        raise ValueError("SARIMA fitting failed for this hotspot — try one with more yearly history.")

    sarima_test_pred = model.get_forecast(steps=test_years).predicted_mean
    sarima_test_pred.index = test.index

    # --- Linear regression baseline ---
    X_train = np.arange(len(train)).reshape(-1, 1)
    lr = LinearRegression().fit(X_train, train.values)
    X_test = np.arange(len(train), len(train) + test_years).reshape(-1, 1)
    lr_test_pred = np.maximum(lr.predict(X_test), 0)

    def _metrics(y_true, y_pred):
        return {
            "RMSE": float(np.sqrt(mean_squared_error(y_true, y_pred))),
            "MAE": float(mean_absolute_error(y_true, y_pred)),
        }

    sarima_metrics = _metrics(test.values, sarima_test_pred.values)
    lr_metrics = _metrics(test.values, lr_test_pred)

    # --- Refit SARIMA on the FULL series, forecast forward ---
    full_model = SARIMAX(
        series, order=order, seasonal_order=(0, 0, 0, 0),
        enforce_stationarity=False, enforce_invertibility=False,
    ).fit(disp=False)
    future = full_model.get_forecast(steps=forecast_years)
    future_mean = np.maximum(future.predicted_mean, 0)
    conf_int = future.conf_int(alpha=0.2).clip(lower=0)

    last_year = int(series.index.max())
    future_years = list(range(last_year + 1, last_year + forecast_years + 1))

    return {
        "order": order,
        "train": train,
        "test": test,
        "sarima_test_pred": sarima_test_pred,
        "lr_test_pred": pd.Series(lr_test_pred, index=test.index),
        "sarima_metrics": sarima_metrics,
        "lr_metrics": lr_metrics,
        "future_years": future_years,
        "future_forecast": pd.Series(future_mean.values, index=future_years),
        "future_conf_int": conf_int.set_axis(future_years),
    }
