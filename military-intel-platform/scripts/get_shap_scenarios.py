import joblib
import pandas as pd
import numpy as np
import shap

# Load models
model = joblib.load("models/attack_prediction_model.pkl")
target_encoder = joblib.load("models/target_encoder.pkl")
target_feature_encoder = joblib.load("models/target_feature_encoder.pkl")
cat_imputer = joblib.load("models/cat_imputer.pkl")
num_imputer = joblib.load("models/num_imputer.pkl")
explainer = shap.TreeExplainer(model)

scenarios = [
    ("Afghanistan", "South Asia", "Explosives", "Police", "Taliban", 2017, 1, 0, 5.0, 10.0, 0),
    ("Iraq", "Middle East & North Africa", "Explosives", "Private Citizens & Property", "Islamic State of Iraq and the Levant (ISIL)", 2017, 1, 0, 20.0, 30.0, 0),
    ("India", "South Asia", "Firearms", "Military", "Unknown", 2017, 1, 0, 2.0, 0.0, 0),
    ("Pakistan", "South Asia", "Explosives", "Government (General)", "Tehrik-i-Taliban Pakistan (TTP)", 2017, 1, 0, 10.0, 15.0, 0),
    ("Somalia", "Sub-Saharan Africa", "Explosives", "Government (General)", "Al-Shabaab", 2017, 1, 1, 30.0, 50.0, 0),
]

features = ["country_txt", "region_txt", "weaptype1_txt", "targtype1_txt", "gname", "iyear", "success", "suicide", "nkill", "nwound", "claimed"]
cat_cols = ["country_txt", "region_txt", "weaptype1_txt", "targtype1_txt", "gname"]
num_cols = ["iyear", "success", "suicide", "nkill", "nwound", "claimed"]

for s in scenarios:
    df = pd.DataFrame([s], columns=features)
    
    # encode
    df[cat_cols] = cat_imputer.transform(df[cat_cols])
    df[num_cols] = num_imputer.transform(df[num_cols])
    cat_enc = target_feature_encoder.transform(df[cat_cols])
    X = np.hstack([cat_enc, df[num_cols].values])
    
    pred = model.predict(X)[0]
    pred_class = int(pred)
    attack_type = target_encoder.inverse_transform([pred])[0]
    
    shap_vals = explainer.shap_values(X)
    local_shap = shap_vals[pred_class][0] if isinstance(shap_vals, list) else (shap_vals[0, :, pred_class] if len(shap_vals.shape)==3 else shap_vals[0])
    
    impacts = sorted(zip(features, local_shap), key=lambda x: abs(x[1]), reverse=True)
    top_pos = [f for f, v in impacts if v > 0][:2]
    
    print(f"\nScenario: {s[0]} / {s[2]} / {s[4]}")
    print(f"Predicted: {attack_type}")
    print(f"Top positive SHAP features: {top_pos}")
    for f, v in impacts[:3]:
        print(f"  {f}: {v:.3f}")
