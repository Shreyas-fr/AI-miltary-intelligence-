import streamlit as st
import joblib
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import os

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

st.title("🤖 Attack Type Prediction")
st.markdown("##### Enter incident details to predict the most likely attack type using our trained ML model.")


# -------------------------
# Load Models & Preprocessors
# -------------------------
try:
    model = joblib.load("models/attack_prediction_model.pkl")
    target_encoder = joblib.load("models/target_encoder.pkl")
    target_feature_encoder = joblib.load("models/target_feature_encoder.pkl")
    cat_imputer = joblib.load("models/cat_imputer.pkl")
    num_imputer = joblib.load("models/num_imputer.pkl")
except FileNotFoundError:
    st.error("Model files not found. Please run `python train_attack_model.py` first.")
    st.stop()

# -------------------------
# Load Dataset for Dropdowns
# -------------------------
if not os.path.exists("data/globalterrorism.csv"):
    st.error("Dataset not found. Please add the dataset to the `data` directory.")
    st.stop()

# We only read the categorical columns to populate dropdown options to save memory
cat_cols = ["country_txt", "region_txt", "weaptype1_txt", "targtype1_txt", "gname"]
df_cats = pd.read_csv("data/globalterrorism.csv", usecols=cat_cols, encoding="latin1", low_memory=False)

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
    # -------------------------
    # Preprocess Input Data
    # -------------------------
    input_data = pd.DataFrame({
        "country_txt": [country],
        "region_txt": [region],
        "weaptype1_txt": [weapon],
        "targtype1_txt": [target],
        "gname": [group],
        "success": [success],
        "suicide": [suicide],
        "nkill": [nkill],
        "nwound": [nwound]
    })

    # Impute missing values (though dropdowns prevent NaNs, this ensures pipeline consistency)
    input_data[cat_cols] = cat_imputer.transform(input_data[cat_cols])
    
    num_cols = ["success", "suicide", "nkill", "nwound"]
    input_data[num_cols] = num_imputer.transform(input_data[num_cols])

    # Target Encode categorical variables
    cat_encoded = target_feature_encoder.transform(input_data[cat_cols])

    # Combine
    import numpy as np
    input_data_final = np.hstack([cat_encoded, input_data[num_cols].values])

    # -------------------------
    # Prediction
    # -------------------------
    prediction = model.predict(input_data_final)
    attack_type = target_encoder.inverse_transform(prediction)[0]
    
    probabilities = model.predict_proba(input_data_final)[0]
    confidence = probabilities.max() * 100

    st.divider()
    st.subheader("🔍 Prediction Result")

    col_res, col_chart = st.columns(2)

    with col_res:
        st.success(f"### Predicted Attack Type: **{attack_type}**")
        st.metric("Model Confidence", f"{confidence:.1f}%")

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
        st.plotly_chart(fig, width="stretch")
