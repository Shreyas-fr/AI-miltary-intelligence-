import os
import sys
import pandas as pd
import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.data_loader import load_data
from utils.hotspot_utils import compute_tsi, cluster_hotspots, build_yearly_series, forecast_hotspot

def main():
    df = load_data()
    df = df.dropna(subset=["latitude", "longitude"])
    df = compute_tsi(df)
    df_clustered, hotspots = cluster_hotspots(df, eps_km=100.0, min_samples=15)
    
    top_3 = hotspots.head(3)
    
    for row in top_3.itertuples():
        cluster_id = row.cluster
        countries = row.countries
        series = build_yearly_series(df_clustered, cluster_id, value_col="tsi")
        
        result = forecast_hotspot(series, test_years=3, forecast_years=5)
        
        mean_80 = (result['future_conf_int'].iloc[:, 1] - result['future_conf_int'].iloc[:, 0]).mean()
        mean_95 = (result['future_conf_int_95'].iloc[:, 1] - result['future_conf_int_95'].iloc[:, 0]).mean()
        
        print(f"\n--- {countries} ---")
        print(f"Mean 80% CI Width: {mean_80:.2f}")
        print(f"Mean 95% CI Width: {mean_95:.2f}")

if __name__ == "__main__":
    main()
