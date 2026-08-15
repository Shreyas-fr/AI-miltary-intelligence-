import os
import sys
import pandas as pd
import numpy as np

def run_reports():
    print("=== 1. AI Threat Score Breakdown ===")
    from utils.data_loader import load_data
    from utils.intelligence import compute_country_risk
    
    historical = load_data()
    countries = ["Iraq", "Afghanistan", "France"]
    
    for country in countries:
        risk = compute_country_risk(country, historical, None)
        print(f"\nCountry: {country}")
        print(f"Total Score: {risk.score:.1f} / 100 ({risk.level})")
        for k, v in risk.components.items():
            print(f"  - {k}: {v:.1f}")
            
    print("\n=== 2. SARIMA Forecast (Top 3 Hotspots) ===")
    from utils.hotspot_utils import cluster_hotspots, compute_tsi, build_yearly_series, forecast_hotspot
    df = historical.dropna(subset=["latitude", "longitude"])
    df = compute_tsi(df)
    df_clustered, hotspots = cluster_hotspots(df, eps_km=100, min_samples=15)
    
    top_3 = hotspots.head(3)
    for row in top_3.itertuples():
        cluster_id = row.cluster
        print(f"\nHotspot #{row.rank} ({row.countries})")
        series = build_yearly_series(df_clustered, cluster_id, value_col="tsi")
        try:
            res = forecast_hotspot(series, test_years=3, forecast_years=3)
            # MAE/RMSE
            print(f"  SARIMA MAE: {res['sarima_metrics']['MAE']:.2f}")
            print(f"  Baseline MAE: {res['lr_metrics']['MAE']:.2f}")
            
            # Confidence interval width (upper - lower) for the first forecasted year
            width_80 = res['future_conf_int'].iloc[0, 1] - res['future_conf_int'].iloc[0, 0]
            print(f"  80% CI Width (Year 1): {width_80:.2f}")
            
            if 'future_conf_int_95' in res:
                width_95 = res['future_conf_int_95'].iloc[0, 1] - res['future_conf_int_95'].iloc[0, 0]
                print(f"  95% CI Width (Year 1): {width_95:.2f}")
            else:
                print("  95% CI not returned by forecast_hotspot.")
                
        except Exception as e:
            print(f"  Failed: {e}")

    print("\n=== 3. SHAP Sanity Checks ===")
    import joblib
    model = joblib.load("models/attack_prediction_model.pkl")
    target_encoder = joblib.load("models/target_encoder.pkl")
    target_feature_encoder = joblib.load("models/target_feature_encoder.pkl")
    cat_imputer = joblib.load("models/cat_imputer.pkl")
    num_imputer = joblib.load("models/num_imputer.pkl")
    import shap
    explainer = shap.TreeExplainer(model)
    
    cat_cols = ["country_txt", "region_txt", "weaptype1_txt", "targtype1_txt", "gname"]
    num_cols = ["iyear", "success", "suicide", "nkill", "nwound"]
    
    scenarios = [
        {"name": "Scenario 1 (Middle East IED)", "country_txt": "Iraq", "region_txt": "Middle East & North Africa", "weaptype1_txt": "Explosives", "targtype1_txt": "Military", "gname": "Unknown", "success": 1, "suicide": 0, "nkill": 5, "nwound": 10},
        {"name": "Scenario 2 (South Asia Assault)", "country_txt": "Afghanistan", "region_txt": "South Asia", "weaptype1_txt": "Firearms", "targtype1_txt": "Police", "gname": "Taliban", "success": 1, "suicide": 0, "nkill": 3, "nwound": 2},
        {"name": "Scenario 3 (Western Europe Bombing)", "country_txt": "France", "region_txt": "Western Europe", "weaptype1_txt": "Explosives", "targtype1_txt": "Private Citizens & Property", "gname": "Unknown", "success": 1, "suicide": 0, "nkill": 1, "nwound": 15},
        {"name": "Scenario 4 (Africa Hostage)", "country_txt": "Nigeria", "region_txt": "Sub-Saharan Africa", "weaptype1_txt": "Firearms", "targtype1_txt": "Educational Institution", "gname": "Boko Haram", "success": 1, "suicide": 0, "nkill": 0, "nwound": 0},
        {"name": "Scenario 5 (Assassination Attempt)", "country_txt": "Colombia", "region_txt": "South America", "weaptype1_txt": "Firearms", "targtype1_txt": "Government (General)", "gname": "FARC", "success": 0, "suicide": 0, "nkill": 0, "nwound": 0},
    ]
    
    for s in scenarios:
        input_data = pd.DataFrame([{k: v for k, v in s.items() if k != "name"}])
        input_data["iyear"] = 2017
        
        input_data[cat_cols] = cat_imputer.transform(input_data[cat_cols])
        input_data[num_cols] = num_imputer.transform(input_data[num_cols])
        cat_encoded = target_feature_encoder.transform(input_data[cat_cols])
        input_final = np.hstack([cat_encoded, input_data[num_cols].values])
        
        pred = model.predict(input_final)
        pred_label = target_encoder.inverse_transform(pred)[0]
        
        print(f"\n{s['name']}")
        print(f"  -> Predicted: {pred_label}")
        
        # Calculate SHAP values
        shap_vals = explainer.shap_values(input_final)
        pred_class_idx = int(pred[0])
        
        if isinstance(shap_vals, list):
            local_shap = shap_vals[pred_class_idx][0]
        else:
            if len(shap_vals.shape) == 3:
                local_shap = shap_vals[0, :, pred_class_idx]
            else:
                local_shap = shap_vals[0]
                
        feature_names = cat_cols + num_cols
        impacts = sorted(zip(feature_names, local_shap), key=lambda x: abs(x[1]), reverse=True)
        
        print("  -> Top Feature Contributions:")
        for feat, val in impacts[:3]:
            direction = "+" if val > 0 else "-"
            print(f"     * {feat}: {direction}{abs(val):.4f}")
        
if __name__ == "__main__":
    run_reports()
