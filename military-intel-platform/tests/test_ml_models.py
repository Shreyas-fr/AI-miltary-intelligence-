import os
import unittest
import joblib
import numpy as np
import pandas as pd

from utils.tsi import compute_single_tsi, compute_tsi, tsi_label, get_tsi_bounds
from utils.hotspot_utils import forecast_hotspot


class MLModelsAndPipelineTests(unittest.TestCase):
    def test_model_artifacts_exist(self):
        artifacts = [
            "models/attack_prediction_model.pkl",
            "models/threat_prediction_model.pkl",
            "models/target_encoder.pkl",
            "models/target_feature_encoder.pkl",
            "models/cat_imputer.pkl",
            "models/num_imputer.pkl",
            "models/threat_feature_encoders.pkl",
            "models/threat_encoder.pkl",
            "models/tsi_bounds.json",
            "models/metrics.json",
        ]
        for path in artifacts:
            self.assertTrue(os.path.exists(path), f"Artifact missing: {path}")

    def test_tsi_computation_and_labels(self):
        score_zero = compute_single_tsi(nkill=0, nwound=0, success=0, claimed=0)
        self.assertGreaterEqual(score_zero, 0.0)

        score_high = compute_single_tsi(nkill=50, nwound=100, success=1, claimed=1)
        self.assertGreater(score_high, score_zero)

        label_low, _ = tsi_label(10.0)
        self.assertEqual(label_low, "LOW")

        label_critical, _ = tsi_label(85.0)
        self.assertEqual(label_critical, "CRITICAL")

    def test_threat_level_model_prediction(self):
        model = joblib.load("models/threat_prediction_model.pkl")
        encoders = joblib.load("models/threat_feature_encoders.pkl")
        target_enc = joblib.load("models/threat_encoder.pkl")

        country_idx = 0
        region_idx = 0
        attack_idx = 0
        weapon_idx = 0
        target_idx = 0

        input_arr = np.array([[country_idx, region_idx, attack_idx, weapon_idx, target_idx, 5, 10]])
        pred = model.predict(input_arr)
        result_label = target_enc.inverse_transform(pred)[0]
        self.assertIn(result_label, ["LOW", "MEDIUM", "HIGH"])

    def test_attack_prediction_model_inference(self):
        model = joblib.load("models/attack_prediction_model.pkl")
        target_enc = joblib.load("models/target_encoder.pkl")
        target_feat_enc = joblib.load("models/target_feature_encoder.pkl")
        cat_imp = joblib.load("models/cat_imputer.pkl")
        num_imp = joblib.load("models/num_imputer.pkl")

        input_df = pd.DataFrame([{
            "country_txt": "India",
            "region_txt": "South Asia",
            "weaptype1_txt": "Explosives",
            "targtype1_txt": "Police",
            "gname": "Unknown",
            "success": 1,
            "suicide": 0,
            "nkill": 2,
            "nwound": 5,
            "claimed": 0,
            "iyear": 2020
        }])

        cat_cols = ["country_txt", "region_txt", "weaptype1_txt", "targtype1_txt", "gname"]
        num_cols = ["iyear", "success", "suicide", "nkill", "nwound", "claimed"]

        input_df[cat_cols] = cat_imp.transform(input_df[cat_cols])
        input_df[num_cols] = num_imp.transform(input_df[num_cols])

        cat_enc = target_feat_enc.transform(input_df[cat_cols])
        final_features = np.hstack([cat_enc, input_df[num_cols].values])
        
        pred = model.predict(final_features)
        pred_label = target_enc.inverse_transform(pred)[0]
        self.assertTrue(isinstance(pred_label, str))

    def test_forecasting_resilience(self):
        series = pd.Series([2, 5, 3, 6, 8, 7, 9, 12, 10, 15], index=range(2010, 2020))
        result = forecast_hotspot(series, test_years=2, forecast_years=3)
        self.assertEqual(len(result["future_forecast"]), 3)
        self.assertTrue((result["future_forecast"] >= 0).all())


if __name__ == "__main__":
    unittest.main()
