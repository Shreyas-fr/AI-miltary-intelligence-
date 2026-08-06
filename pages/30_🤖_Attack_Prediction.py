import streamlit as st
import joblib
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import os
import shap
from utils.ui_components import st_custom_kpi_card

st.set_page_config(
    page_title="Attack Prediction",
    page_icon="🤖",
    layout="wide"
)

def load_css(file_name):
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
load_css("assets/style.css")

st.title("🤖 | Attack Type Prediction")
st.markdown(
    "##### AI-powered classification of likely attack methods based on historical patterns."
)

# -------------------------
# Load Models & Preprocessors
# -------------------------
@st.cache_resource(show_spinner="Loading ML models...")
def load_attack_models():
    try:
        model = joblib.load("models/attack_prediction_model.pkl")
        target_encoder = joblib.load("models/target_encoder.pkl")
        target_feature_encoder = joblib.load("models/target_feature_encoder.pkl")
        cat_imputer = joblib.load("models/cat_imputer.pkl")
        num_imputer = joblib.load("models/num_imputer.pkl")
    except FileNotFoundError:
        import train_models
        train_models.train_all()
        model = joblib.load("models/attack_prediction_model.pkl")
        target_encoder = joblib.load("models/target_encoder.pkl")
        target_feature_encoder = joblib.load("models/target_feature_encoder.pkl")
        cat_imputer = joblib.load("models/cat_imputer.pkl")
        num_imputer = joblib.load("models/num_imputer.pkl")
    return model, target_encoder, target_feature_encoder, cat_imputer, num_imputer, shap.TreeExplainer(model)

model, target_encoder, target_feature_encoder, cat_imputer, num_imputer, explainer = load_attack_models()

import gc
gc.collect()

with st.expander("📊 Global Model Explainability (Feature Importance)", expanded=False):
    importances = model.feature_importances_
    features = ["Country", "Region", "Weapon Type", "Target Type", "Group", "Success", "Suicide", "Fatalities", "Injuries"]
    
    fig_imp = go.Figure(go.Bar(
        x=importances,
        y=features,
        orientation='h',
        marker_color="#FF2D55"
    ))
    fig_imp.update_layout(
        title="Which features matter most overall?",
        xaxis_title="Relative Importance (Mean Decrease Impurity)",
        yaxis={'categoryorder':'total ascending'},
        template="plotly_dark",
        height=350,
        margin=dict(l=10, r=10, t=40, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)"
    )
    st.plotly_chart(fig_imp, use_container_width=True)
    st.caption("Random Forest global feature importance confirms Weapon Type strongly dictates the predicted attack classification.")


# -------------------------
# Load Dataset for Dropdowns
# -------------------------
if not os.path.exists("data/globalterrorism.csv"):
    st.error("Dataset not found. Please add the dataset to the `data` directory.")
    st.stop()

# We only read the categorical columns to populate dropdown options to save memory
cat_cols = ["country_txt", "region_txt", "weaptype1_txt", "targtype1_txt", "gname"]

@st.cache_data(show_spinner=False)
def _load_cat_options():
    return pd.read_csv("data/globalterrorism.csv", usecols=cat_cols, encoding="latin1", low_memory=False)

df_cats = _load_cat_options()

# -------------------------
# Create Input Form
# -------------------------
with st.form("prediction_form"):
    col1, col2 = st.columns(2)

    with col1:
        country = st.selectbox("🌍 Country", sorted(df_cats["country_txt"].dropna().unique()))
        region = st.selectbox("🌎 Region", sorted(df_cats["region_txt"].dropna().unique()))
        weapon = st.selectbox("🔫 Weapon Type", sorted(df_cats["weaptype1_txt"].dropna().unique()))
        target = st.selectbox("🎯 Target Type", sorted(df_cats["targtype1_txt"].dropna().unique()))

    with col2:
        group = st.selectbox("👥 Terrorist Group", sorted(df_cats["gname"].dropna().unique()))
        success = st.selectbox("✅ Attack Successful?", [0, 1], format_func=lambda x: "Yes" if x == 1 else "No")
        suicide = st.selectbox("💣 Suicide Attack?", [0, 1], format_func=lambda x: "Yes" if x == 1 else "No")
        nkill = st.number_input("☠ Number of Fatalities", min_value=0, value=0, step=1)
        nwound = st.number_input("🏥 Number of Injured", min_value=0, value=0, step=1)

    submitted = st.form_submit_button("🚀 Predict Attack Type")

if submitted:
    try:
        # -------------------------
        # Preprocess Input Data
        # -------------------------
        input_data = pd.DataFrame({
            "country_txt": [country],
            "region_txt": [region],
            "weaptype1_txt": [weapon],
            "targtype1_txt": [target],
            "gname": [group],
            "iyear": [2017], # Model expects iyear
            "success": [success],
            "suicide": [suicide],
            "nkill": [nkill],
            "nwound": [nwound]
        })

        # Impute missing values (though dropdowns prevent NaNs, this ensures pipeline consistency)
        input_data[cat_cols] = cat_imputer.transform(input_data[cat_cols])
        
        num_cols = ["iyear", "success", "suicide", "nkill", "nwound"]
        input_data[num_cols] = num_imputer.transform(input_data[num_cols])

        # Target Encode categorical variables
        cat_encoded = target_feature_encoder.transform(input_data[cat_cols])

        # Combine
        input_data_final = np.hstack([cat_encoded, input_data[num_cols].values])

        # -------------------------
        # Prediction
        # -------------------------
        prediction = model.predict(input_data_final)
        attack_type = target_encoder.inverse_transform(prediction)[0]
        
        probabilities = model.predict_proba(input_data_final)[0]
        confidence = probabilities.max() * 100
        
        # SHAP Explainability
        shap_vals = explainer.shap_values(input_data_final)
        # For multi-class RF, shap_vals is a list of arrays. Get the array for the predicted class.
        pred_class_idx = int(prediction[0])
        if isinstance(shap_vals, list):
            local_shap = shap_vals[pred_class_idx][0]
        else:
            # shap >= 0.45 might return an array of shape (1, features, classes)
            if len(shap_vals.shape) == 3:
                local_shap = shap_vals[0, :, pred_class_idx]
            else:
                local_shap = shap_vals[0]
                
    except Exception as pred_err:
        st.error(f"Prediction failed: {pred_err}")
        st.info("The selected combination may contain values unseen during training. Try different inputs.")
        st.stop()

    st.divider()
    st.subheader("🔍 Prediction Result")

    col_res, col_chart = st.columns(2)

    with col_res:
        st.success(f"### Predicted Attack Type: **{attack_type}**")
        st_custom_kpi_card("Model Confidence", f"{confidence:.1f}%", "", "🧠")

        if attack_type in ["Hijacking", "Unarmed Assault"]:
            st.warning(
                f"⚠️ **Low Historical Support Notice:** '{attack_type}' represents <1% of historical GTD incidents. "
                "Predictions for rare attack types carry higher uncertainty due to extreme class imbalance in real-world data."
            )
            
        st.markdown("##### Why this prediction?")
        feature_names = ["Country", "Region", "Weapon Type", "Target Type", "Group", "Success", "Suicide", "Fatalities", "Injuries"]
        # Pair features with their SHAP values and sort by absolute impact
        impacts = sorted(zip(feature_names, local_shap), key=lambda x: abs(x[1]), reverse=True)
        
        top_positive = [f for f, v in impacts if v > 0][:2]
        top_negative = [f for f, v in impacts if v < 0][:1]
        
        if top_positive:
            st.write(f"**{', '.join(top_positive)}** contributed most to this prediction.")
        if top_negative:
            st.write(f"*(Conversely, {top_negative[0]} slightly reduced the likelihood).*")

    with col_chart:
        attack_labels = target_encoder.classes_
        top_n = min(8, len(attack_labels))
        sorted_idx = probabilities.argsort()[::-1][:top_n]

        fig = go.Figure(go.Bar(
            x=[attack_labels[i] for i in sorted_idx],
            y=[probabilities[i] * 100 for i in sorted_idx],
            marker_color="#00E5FF",
            text=[f"{probabilities[i]*100:.1f}%" for i in sorted_idx],
            textposition="outside"
        ))
        fig.update_layout(
            title="Top Predicted Attack Types",
            yaxis_title="Probability (%)",
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            height=320,
            margin=dict(l=10, r=10, t=40, b=10)
        )
        st.plotly_chart(fig, use_container_width=True)
