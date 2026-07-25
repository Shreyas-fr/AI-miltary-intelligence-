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


from utils.tsi import compute_tsi as compute_tsi_canonical


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
    Delegates to canonical log-weighted TSI score normalized [0, 100].
    """
    df = df.copy()
    df["tsi"] = compute_tsi_canonical(df)
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

    if df.empty:
        df["cluster"] = pd.Series(dtype=int)
        return df, pd.DataFrame(columns=["cluster", "incidents", "total_tsi", "avg_tsi", "centroid_lat", "centroid_lon", "countries", "rank"])

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
    candidate_orders = [(1, 1, 1), (1, 1, 0), (0, 1, 1), (2, 1, 1), (1, 0, 1), (2, 1, 0), (1, 0, 0), (0, 1, 0), (0, 0, 0)]
    seasonal_order = (0, 0, 0, 0)  # annual data — no sub-cycle seasonality to model
    best_aic, best_order, best_fit = np.inf, (1, 1, 0), None

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
    comparison.
    """
    series = series.astype(float)
    n = len(series)
    test_years = min(test_years, max(1, n // 3))  # guard against tiny series

    train, test = series.iloc[: n - test_years], series.iloc[n - test_years :]

    # --- Linear regression baseline ---
    X_train = np.arange(len(train)).reshape(-1, 1)
    lr = LinearRegression().fit(X_train, train.values)
    X_test = np.arange(len(train), len(train) + test_years).reshape(-1, 1)
    lr_test_pred = np.maximum(lr.predict(X_test), 0)

    # --- SARIMA ---
    model, order = _grid_search_sarima(train)
    if model is not None:
        sarima_test_pred = model.get_forecast(steps=test_years).predicted_mean
        sarima_test_pred.index = test.index
    else:
        order = (0, 1, 0)
        sarima_test_pred = pd.Series(lr_test_pred, index=test.index)


    def _metrics(y_true, y_pred):
        try:
            rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
            mae = float(mean_absolute_error(y_true, y_pred))
        except (ValueError, TypeError):
            rmse, mae = 0.0, 0.0
        return {"RMSE": rmse, "MAE": mae}

    sarima_metrics = _metrics(test.values, sarima_test_pred.values)
    lr_metrics = _metrics(test.values, lr_test_pred)

    # --- Refit SARIMA on the FULL series, forecast forward ---
    try:
        full_model = SARIMAX(
            series, order=order, seasonal_order=(0, 0, 0, 0),
            enforce_stationarity=False, enforce_invertibility=False,
        ).fit(disp=False)
        future = full_model.get_forecast(steps=forecast_years)
        future_mean = np.maximum(future.predicted_mean, 0)
        conf_int = future.conf_int(alpha=0.2).clip(lower=0)
    except Exception:
        X_full = np.arange(len(series)).reshape(-1, 1)
        lr_full = LinearRegression().fit(X_full, series.values)
        X_fut = np.arange(len(series), len(series) + forecast_years).reshape(-1, 1)
        future_mean = pd.Series(np.maximum(lr_full.predict(X_fut), 0))
        conf_int = pd.DataFrame({0: future_mean * 0.8, 1: future_mean * 1.2})


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
