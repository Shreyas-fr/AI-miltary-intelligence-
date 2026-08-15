import os
import sys
import pandas as pd
import numpy as np
from statsmodels.tsa.statespace.sarimax import SARIMAX

# Ensure imports work from scripts/
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.data_loader import load_data
from utils.hotspot_utils import compute_tsi, cluster_hotspots, build_yearly_series, _grid_search_sarima

def main():
    print("Loading data...")
    df = load_data()
    df = df.dropna(subset=["latitude", "longitude"])
    df = compute_tsi(df)
    
    print("Clustering hotspots...")
    df_clustered, hotspots = cluster_hotspots(df, eps_km=100.0, min_samples=15)
    
    # Pick top 3 hotspots
    top_3 = hotspots.head(3)
    
    for row in top_3.itertuples():
        cluster_id = row.cluster
        countries = row.countries
        
        # Build series
        series = build_yearly_series(df_clustered, cluster_id, value_col="tsi")
        series = series.astype(float)
        
        # We want to train up to 2014, and test on 2015, 2016, 2017
        train = series[series.index <= 2014]
        test = series[(series.index >= 2015) & (series.index <= 2017)]
        
        if len(train) < 5 or len(test) < 3:
            print(f"Hotspot {countries} doesn't have enough data.")
            continue
            
        print(f"\n--- Backtesting Hotspot: {countries} ---")
        print(f"Training on {len(train)} years (up to 2014). Testing on 2015, 2016, 2017.")
        
        # Fit SARIMA
        model, order = _grid_search_sarima(train)
        if model is None:
            order = (0, 1, 0)
            print("Fallback to simple model")
            # Fallback fit
            model = SARIMAX(train, order=order, enforce_stationarity=False, enforce_invertibility=False).fit(disp=False)
            
        forecast_res = model.get_forecast(steps=3)
        forecast_mean = np.maximum(forecast_res.predicted_mean.values, 0)
        
        actuals = test.values
        
        print("Actuals:  ", np.round(actuals, 2))
        print("Forecasts:", np.round(forecast_mean, 2))
        
        mae = np.mean(np.abs(actuals - forecast_mean))
        mape = np.mean(np.abs(actuals - forecast_mean) / np.maximum(actuals, 1)) * 100
        
        print(f"MAE:  {mae:.2f}")
        print(f"MAPE: {mape:.2f}%")

if __name__ == "__main__":
    main()
