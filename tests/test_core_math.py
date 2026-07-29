import unittest
import pandas as pd
import numpy as np

from utils.tsi import compute_single_tsi
from utils.migration import haversine_km
from utils.intelligence import compute_country_risk
from utils.network_utils import compute_similarity_network

class TestCoreMath(unittest.TestCase):
    
    def test_tsi_non_linear_formula(self):
        # Test Case 1: Zero casualties
        score_zero = compute_single_tsi(nkill=0, nwound=0, success=0, claimed=0)
        self.assertEqual(score_zero, 0.0)
        
        # Test Case 2: High casualties (bounds check)
        score_high = compute_single_tsi(nkill=1000, nwound=1000, success=1, claimed=1)
        self.assertTrue(0.0 <= score_high <= 100.0)

        # Test Case 3: Verify positive components
        score_success = compute_single_tsi(nkill=0, nwound=0, success=1, claimed=0)
        self.assertTrue(score_success > 0.0)

    def test_haversine_distance(self):
        # Baghdad: 33.3152, 44.3661 to Kabul: 34.5553, 69.2075 is ~2270 km
        dist = haversine_km(33.3152, 44.3661, 34.5553, 69.2075)
        self.assertAlmostEqual(dist, 2273, delta=50)
        
        # London (51.5074, -0.1278) to Paris (48.8566, 2.3522) is ~344 km
        dist2 = haversine_km(51.5074, -0.1278, 48.8566, 2.3522)
        self.assertAlmostEqual(dist2, 344, delta=20)
        
    def test_macro_score_clamping(self):
        # Create global df with 10000 rows
        countries = ["Iraq"] * 1000 + ["Other"] * 9000
        lats = [33.3] * 500 + [33.4] * 500 + [0.0] * 9000
        lons = [44.3] * 500 + [44.4] * 500 + [0.0] * 9000
        nkill = [0] * 10000
        
        df = pd.DataFrame({
            "country_txt": countries,
            "latitude": lats,
            "longitude": lons,
            "nkill": nkill
        })
        
        # Iraq has 1000 incidents (10% of global, > 8% cap)
        # It also has grid cells with 500 incidents (> 250 cap)
        risk = compute_country_risk("Iraq", historical=df, live_events=None)
        
        # historical_activity should be 100 * 0.35 = 35.0
        # cluster_density should be 100 * 0.10 = 10.0
        self.assertAlmostEqual(risk.components["Historical Activity"], 35.0)
        self.assertAlmostEqual(risk.components["Cluster Density"], 10.0)
        
    def test_cosine_similarity_threshold(self):
        df = pd.DataFrame({
            "Group A": [1.0, 0.0, 0.0],
            "Group B": [0.9, 0.1, 0.0],
            "Group C": [0.0, 0.0, 1.0],
        }).T
        df.index.name = "gname"
        df.columns = ["feature1", "feature2", "feature3"]
        df["_incident_count"] = [100, 100, 100]
        
        graph = compute_similarity_network(df, threshold=0.85)
        
        self.assertTrue(graph.has_edge("Group A", "Group B"))
        self.assertFalse(graph.has_edge("Group A", "Group C"))
        self.assertFalse(graph.has_edge("Group B", "Group C"))

if __name__ == '__main__':
    unittest.main()
