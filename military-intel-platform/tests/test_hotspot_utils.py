import unittest

import numpy as np
import pandas as pd

from utils.hotspot_utils import build_yearly_series, cluster_hotspots, compute_tsi, forecast_hotspot


def sample_incidents():
    rows = []
    for year in range(2000, 2020):
        rows.append({"latitude": 12.0 + (year % 2) * 0.01, "longitude": 77.0,
                     "nkill": year % 4, "nwound": year % 3, "success": 1,
                     "iyear": year, "country_txt": "Example"})
    rows.append({"latitude": 50.0, "longitude": -120.0, "nkill": 1,
                 "nwound": 0, "success": 0, "iyear": 2010,
                 "country_txt": "Noise"})
    return pd.DataFrame(rows)


class HotspotPipelineTests(unittest.TestCase):
    def test_tsi_formula_and_failed_attack_multiplier(self):
        df = pd.DataFrame({"nkill": [1, 1, -2], "nwound": [0, 0, np.nan], "success": [1, 0, 1]})
        scored = compute_tsi(df)
        self.assertTrue(scored.loc[0, "tsi"] > scored.loc[1, "tsi"])
        self.assertTrue((scored["tsi"] >= 0).all() and (scored["tsi"] <= 100).all())

    def test_haversine_clustering_summary_and_noise(self):
        clustered, summary = cluster_hotspots(compute_tsi(sample_incidents()), eps_km=5, min_samples=3)
        self.assertEqual(len(summary), 1)
        self.assertEqual(summary.iloc[0]["incidents"], 20)
        self.assertEqual((clustered["cluster"] == -1).sum(), 1)
        self.assertEqual(summary.iloc[0]["rank"], 1)

    def test_yearly_series_fills_gaps(self):
        df = pd.DataFrame({"cluster": [0, 0], "iyear": [2000, 2002], "tsi": [2.0, 4.0]})
        result = build_yearly_series(df, 0, "tsi")
        self.assertEqual(result.to_dict(), {2000: 2.0, 2001: 0.0, 2002: 4.0})

    def test_forecast_has_validation_and_nonnegative_future(self):
        series = pd.Series([3, 4, 2, 5, 6, 4, 7, 8, 7, 9, 10, 11], index=range(2000, 2012))
        result = forecast_hotspot(series, test_years=3, forecast_years=4)
        self.assertIsNotNone(result["order"])
        self.assertEqual(len(result["future_forecast"]), 4)
        self.assertEqual(len(result["future_conf_int"]), 4)
        self.assertTrue((result["future_forecast"] >= 0).all())
        self.assertEqual(set(result["sarima_metrics"]), {"RMSE", "MAE"})


if __name__ == "__main__":
    unittest.main()
