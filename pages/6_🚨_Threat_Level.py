import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import os
from sklearn.preprocessing import LabelEncoder
from sklearn.ensemble import RandomForestClassifier
from utils.data_loader import load_data
from utils.tsi import compute_tsi, tsi_label

# -----------------------------------------------
# Page Config
# -----------------------------------------------
st.set_page_config(
    page_title="Threat Level Prediction",
    page_icon="🚨",
    layout="wide"
)

def load_css(file_name):
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
load_css("assets/style.css")

st.title("🚨 AI Threat Level Prediction")
st.markdown("##### Estimate the threat severity of a potential terrorist incident using a machine learning classifier.")

# -----------------------------------------------
import joblib
from utils.tsi import compute_single_tsi, tsi_label

# -----------------------------------------------
# Load Pre-trained Model (Cached)
# -----------------------------------------------
@st.cache_resource
def load_threat_model():
    """Load pre-trained threat level model and encoders."""
    m_path = "models/threat_prediction_model.pkl"
    enc_path = "models/threat_feature_encoders.pkl"
    t_enc_path = "models/threat_encoder.pkl"

    if os.path.exists(m_path) and os.path.exists(enc_path) and os.path.exists(t_enc_path):
        model = joblib.load(m_path)
        encoders = joblib.load(enc_path)
        target_enc = joblib.load(t_enc_path)
        return model, encoders, target_enc

    # Fallback to train_models if not built
    import train_models
    train_models.train_all()
    model = joblib.load(m_path)
    encoders = joblib.load(enc_path)
    target_enc = joblib.load(t_enc_path)
    return model, encoders, target_enc

model, encoders, target_enc = load_threat_model()

# -----------------------------------------------
# Sidebar Inputs
# -----------------------------------------------
st.sidebar.header("Incident Parameters")

def get_original_labels(col):
    return list(encoders[col].classes_)

country  = st.sidebar.selectbox("Country",     get_original_labels("country_txt"))
region   = st.sidebar.selectbox("Region",      get_original_labels("region_txt"))
attack   = st.sidebar.selectbox("Attack Type", get_original_labels("attacktype1_txt"))
weapon   = st.sidebar.selectbox("Weapon Type", get_original_labels("weaptype1_txt"))
target_t = st.sidebar.selectbox("Target Type", get_original_labels("targtype1_txt"))
nkill    = st.sidebar.number_input("Estimated Killed",   min_value=0, max_value=5000, value=2)
nwound   = st.sidebar.number_input("Estimated Wounded",  min_value=0, max_value=5000, value=5)
success  = st.sidebar.selectbox("Attack Successful?", ["Yes", "No"])
claimed  = st.sidebar.selectbox("Responsibility Claimed?", ["Yes", "No"])

# -----------------------------------------------
# TSI Score — computed live in O(1) time
# -----------------------------------------------
tsi_score = compute_single_tsi(
    nkill, nwound,
    1.0 if success == "Yes" else 0.0,
    1.0 if claimed == "Yes" else 0.0
)
tsi_lbl, tsi_color = tsi_label(tsi_score)


# -----------------------------------------------
# TSI Display (always visible — no button needed)
# -----------------------------------------------
st.subheader("📐 Threat Severity Index (TSI)")

with st.expander("ℹ️ How is TSI calculated?", expanded=False):
    st.markdown("**TSI Non-linear Scoring Formula:**")
    st.latex(r"""
        \text{TSI}_{\text{raw}} =
            w_1 \cdot \ln(1 + n_{\text{kill}}) +
            w_2 \cdot \ln(1 + n_{\text{wound}}) +
            w_3 \cdot \text{success} +
            w_4 \cdot \text{claimed}
    """)
    st.latex(r"""
        \text{TSI} = 100 \times
        \frac{\text{TSI}_{\text{raw}} - \min}{\max - \min}
        \quad \in [0, 100]
    """)
    st.markdown("""
    | Weight | Component | Value | Rationale |
    |--------|-----------|-------|-----------|
    | w₁ | Fatalities | **0.50** | Highest operational impact |
    | w₂ | Injuries | **0.30** | Serious but not terminal |
    | w₃ | Success | **0.15** | Signals operational capability |
    | w₄ | Claimed | **0.05** | Signals ideological intent |

    **Why logarithm?** `ln(1 + x)` compresses extreme outliers — a 500-casualty event
    doesn't dominate the index while still ranking far higher than a 5-casualty event.
    """)

tsi_col1, tsi_col2, tsi_col3 = st.columns(3)
tsi_col1.metric("TSI Score", f"{tsi_score:.1f} / 100")
tsi_col2.metric("Severity Label", tsi_lbl)
tsi_col3.markdown(
    f"<div style='padding:14px;border-radius:8px;background:{tsi_color}22;"
    f"border:2px solid {tsi_color};text-align:center;"
    f"font-size:1.4rem;font-weight:700;color:{tsi_color}'>{tsi_lbl}</div>",
    unsafe_allow_html=True
)

# TSI gauge
gauge_fig = go.Figure(go.Indicator(
    mode="gauge+number",
    value=tsi_score,
    domain={"x": [0, 1], "y": [0, 1]},
    title={"text": "Threat Severity Index", "font": {"size": 16}},
    gauge={
        "axis": {"range": [0, 100]},
        "bar": {"color": tsi_color},
        "steps": [
            {"range": [0, 25],  "color": "#1a1a2e"},
            {"range": [25, 50], "color": "#16213e"},
            {"range": [50, 75], "color": "#0f3460"},
            {"range": [75, 100],"color": "#2d0a0a"},
        ],
        "threshold": {
            "line": {"color": "white", "width": 3},
            "thickness": 0.8,
            "value": tsi_score
        }
    }
))
gauge_fig.update_layout(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    height=250,
    margin=dict(l=20, r=20, t=40, b=10)
)
st.plotly_chart(gauge_fig, width="stretch")

st.divider()

# -----------------------------------------------
# Predict
# -----------------------------------------------
if st.button("🚨 Predict Threat Level (ML Classifier)"):
    try:
        input_enc = np.array([[
            encoders["country_txt"].transform([country])[0],
            encoders["region_txt"].transform([region])[0],
            encoders["attacktype1_txt"].transform([attack])[0],
            encoders["weaptype1_txt"].transform([weapon])[0],
            encoders["targtype1_txt"].transform([target_t])[0],
            nkill,
            nwound
        ]])

        prediction    = model.predict(input_enc)
        probabilities = model.predict_proba(input_enc)[0]
        result        = target_enc.inverse_transform(prediction)[0]
        confidence    = np.max(probabilities) * 100
    except (ValueError, KeyError) as enc_err:
        st.error(f"Prediction failed: {enc_err}")
        st.info("A selected category may not have been present during model training. Try different inputs.")
        st.stop()

    st.subheader("🔍 ML Classifier Result")

    col1, col2 = st.columns(2)

    with col1:
        if result == "LOW":
            st.success(f"### 🟢 Threat Level: {result}")
            st.markdown("Incident is classified as **low severity**. Minimal casualties expected.")
        elif result == "MEDIUM":
            st.warning(f"### 🟡 Threat Level: {result}")
            st.markdown("Incident is classified as **medium severity**. Moderate casualties expected. Elevated vigilance recommended.")
        else:
            st.error(f"### 🔴 Threat Level: {result}")
            st.markdown("Incident is classified as **HIGH SEVERITY**. Significant casualties expected. Immediate response required.")

        st.metric("Model Confidence", f"{confidence:.1f}%")
        st.metric("TSI Score (corroborating)", f"{tsi_score:.1f}/100 — {tsi_lbl}")

    with col2:
        # Probability Gauge Chart
        labels = target_enc.classes_
        colors = ["#2ECC71", "#F39C12", "#E74C3C"]

        fig = go.Figure(go.Bar(
            x=labels,
            y=probabilities * 100,
            marker_color=colors,
            text=[f"{p*100:.1f}%" for p in probabilities],
            textposition="outside"
        ))
        fig.update_layout(
            title="Probability Distribution",
            yaxis_title="Probability (%)",
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            height=300,
            margin=dict(l=20, r=20, t=40, b=20)
        )
        st.plotly_chart(fig, width="stretch")

    st.divider()

    # Feature importance
    st.subheader("📊 Feature Importance")
    feat_names = ["Country", "Region", "Attack Type", "Weapon Type", "Target Type", "Killed", "Wounded"]
    importances = model.feature_importances_

    fig2 = go.Figure(go.Bar(
        x=importances,
        y=feat_names,
        orientation="h",
        marker_color="#00E5FF"
    ))
    fig2.update_layout(
        title="What drives the prediction?",
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=300,
        margin=dict(l=20, r=20, t=40, b=20)
    )
    st.plotly_chart(fig2, width="stretch")
else:
    st.info("👈 Configure the incident parameters in the sidebar and click **Predict Threat Level**.")