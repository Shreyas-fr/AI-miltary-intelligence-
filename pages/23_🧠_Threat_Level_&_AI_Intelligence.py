import os
import joblib
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import streamlit as st

# --- Authentication & Role Check ---
from utils.auth import require_auth
require_auth(['Analyst', 'Commander'])
# -----------------------------------


try:
    from google import genai
except Exception:
    genai = None

from sklearn.preprocessing import LabelEncoder
from sklearn.ensemble import RandomForestClassifier

from utils.data_loader import load_data, query_data
from utils.tsi import compute_single_tsi, tsi_label
from utils.ui_components import st_custom_kpi_card, st_custom_threat_banner
from utils.intelligence import (
    DEFAULT_LIVE_QUERY,
    build_pdf,
    build_situation_report,
    compute_country_risk,
    enrich_live_events_with_country_centroids,
    fetch_gdelt_events,
)

# -----------------------------------------------
# Page Config
# -----------------------------------------------
st.set_page_config(
    page_title="Threat Level & AI Intelligence",
    page_icon="🧠",
    layout="wide"
)

def load_css(file_name):
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
load_css("assets/style.css")

st.title("🧠 | Threat Level & AI Intelligence")
st.markdown("##### Quantitative threat scoring and AI narrative generation in a unified view.")

# -----------------------------------------------
# Load ML Model
# -----------------------------------------------
@st.cache_resource
def load_threat_model():
    m_path = "models/threat_prediction_model.pkl"
    enc_path = "models/threat_feature_encoders.pkl"
    t_enc_path = "models/threat_encoder.pkl"
    if os.path.exists(m_path) and os.path.exists(enc_path) and os.path.exists(t_enc_path):
        model = joblib.load(m_path)
        encoders = joblib.load(enc_path)
        target_enc = joblib.load(t_enc_path)
        return model, encoders, target_enc
    import train_models
    train_models.train_all()
    model = joblib.load(m_path)
    encoders = joblib.load(enc_path)
    target_enc = joblib.load(t_enc_path)
    return model, encoders, target_enc

model, encoders, target_enc = load_threat_model()
def get_original_labels(col):
    return list(encoders[col].classes_)

# -----------------------------------------------
# Load Data & AI Config
# -----------------------------------------------
@st.cache_data(ttl=900, show_spinner=False)
def load_recent_events(query_text: str, window: str, records: int) -> pd.DataFrame:
    live = fetch_gdelt_events(query=query_text, timespan=window, max_records=records)
    historical_geo = query_data(
        """
        SELECT country_txt, latitude, longitude
        FROM 'data/globalterrorism.csv'
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
        """
    )
    return enrich_live_events_with_country_centroids(live, historical_geo)

@st.cache_data(show_spinner=False)
def country_options() -> list[str]:
    countries = query_data(
        """
        SELECT country_txt, COUNT(*) AS incidents
        FROM 'data/globalterrorism.csv'
        WHERE country_txt IS NOT NULL
        GROUP BY country_txt
        ORDER BY incidents DESC
        """
    )
    return countries["country_txt"].tolist()

# -----------------------------------------------
# Sidebar Inputs
# -----------------------------------------------
st.sidebar.header("Geography Filter")
country_list = country_options()
selected_country = st.sidebar.selectbox("Select Sovereign Nation", country_list, help="Choose the country to analyze.")

st.sidebar.markdown("---")
st.sidebar.header("ML Incident Parameters")
region   = st.sidebar.selectbox("Region", get_original_labels("region_txt"), help="Filter the incident history by region.")
attack   = st.sidebar.selectbox("Attack Type", get_original_labels("attacktype1_txt"), help="Specify the type of attack to simulate.")
weapon   = st.sidebar.selectbox("Weapon Type", get_original_labels("weaptype1_txt"), help="Specify the weapon used in the simulated attack.")
target_t = st.sidebar.selectbox("Target Type", get_original_labels("targtype1_txt"), help="Identify the target of the simulated attack.")
nkill    = st.sidebar.number_input("Estimated Killed", min_value=0, max_value=5000, value=2, help="Number of fatalities.")
nwound   = st.sidebar.number_input("Estimated Wounded", min_value=0, max_value=5000, value=5, help="Number of non-fatal injuries.")
success  = st.sidebar.selectbox("Attack Successful?", ["Yes", "No"], help="Whether the attack achieved its goal.")
claimed  = st.sidebar.selectbox("Responsibility Claimed?", ["Yes", "No"], help="Whether a group claimed responsibility.")

st.sidebar.markdown("---")
st.sidebar.header("AI Narrative Settings")
lookback = st.sidebar.selectbox("Live intelligence window", ["15m", "1h", "6h", "1d", "3d", "7d"], index=3, help="Timeframe to fetch recent events from the live intelligence database.")
max_records = st.sidebar.slider("Live records", 25, 250, 100, step=25, help="Maximum number of live intelligence records to retrieve.")
use_live = st.sidebar.checkbox("Include GDELT live feed", value=True)
api_key = os.environ.get("GEMINI_API_KEY") or st.sidebar.text_input("Gemini API Key (optional)", type="password")

# -----------------------------------------------
# Main Tabs
# -----------------------------------------------
tab_ml, tab_ai = st.tabs(["🚨 Threat Level Prediction", "🤖 AI Narrative Intelligence"])

with tab_ml:
    # TSI Score
    tsi_score = compute_single_tsi(
        nkill, nwound,
        1.0 if success == "Yes" else 0.0,
        1.0 if claimed == "Yes" else 0.0
    )
    tsi_lbl, tsi_color = tsi_label(tsi_score)

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
    with tsi_col1: st_custom_kpi_card("TSI Score", f"{tsi_score:.1f} / 100", "", "🔢")
    with tsi_col2: st_custom_kpi_card("Severity Label", tsi_lbl, "", "🚨")
    tsi_col3.markdown(
        f"<div style='padding:14px;border-radius:8px;background:{tsi_color}22;"
        f"border:2px solid {tsi_color};text-align:center;"
        f"font-size:1.4rem;font-weight:700;color:{tsi_color}'>{tsi_lbl}</div>",
        unsafe_allow_html=True
    )

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
    st.plotly_chart(gauge_fig, use_container_width=True)

    st.divider()

    if st.button("🚨 Predict Threat Level (ML Classifier)"):
        try:
            input_enc = np.array([[
                encoders["country_txt"].transform([selected_country])[0],
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

            st.markdown("#### Evidence & Context")
            c1, c2 = st.columns(2)
            with c1: st_custom_kpi_card("Model Confidence", f"{confidence:.1f}%", "", "🧠")
            with c2: st_custom_kpi_card("TSI Score (corroborating)", f"{tsi_score:.1f}/100", tsi_lbl, "📊")

        with col2:
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
            st.plotly_chart(fig, use_container_width=True)

        st.divider()

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
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("👈 Configure the incident parameters in the sidebar and click **Predict Threat Level**.")

with tab_ai:
    historical = load_data()
    country_hist = historical[historical["country_txt"] == selected_country].copy()

    live_events = pd.DataFrame()
    live_error = None
    if use_live:
        try:
            with st.spinner("Collecting recent public-source events..."):
                live_events = load_recent_events(DEFAULT_LIVE_QUERY, lookback, max_records)
        except Exception as exc:
            live_error = str(exc)
            live_events = pd.DataFrame(columns=["country", "event", "severity", "title", "date", "source", "url"])

    country_live = live_events[
        live_events.get("country", pd.Series(dtype=str)).map(lambda value: str(value).lower())
        == selected_country.lower()
    ].copy() if not live_events.empty else live_events

    years = sorted(country_hist["iyear"].dropna().astype(int).unique().tolist())
    latest_year = years[-1] if years else None
    previous_year = years[-2] if len(years) > 1 else None
    latest_count = int((country_hist["iyear"] == latest_year).sum()) if latest_year else 0
    previous_count = int((country_hist["iyear"] == previous_year).sum()) if previous_year else 0
    activity_delta = None
    if previous_count and previous_count > 0:
        activity_delta = ((latest_count - previous_count) / previous_count) * 100

    top_area = None
    if "provstate" in country_hist.columns and not country_hist["provstate"].dropna().empty:
        top_area = country_hist["provstate"].value_counts().index[0]
    elif "region_txt" in country_hist.columns and not country_hist["region_txt"].dropna().empty:
        top_area = country_hist["region_txt"].value_counts().index[0]

    stats = {
        "historical_incidents": len(country_hist),
        "historical_fatalities": pd.to_numeric(country_hist.get("nkill", 0), errors="coerce").fillna(0).sum(),
        "activity_delta_pct": activity_delta,
        "top_area": top_area,
    }
    
    risk = compute_country_risk(selected_country, historical, live_events)
    report = build_situation_report(selected_country, f"Live window: {lookback}", stats, risk, country_live)

    if live_error:
        st.info(
            "📡 **Live Feed Status:** External SIGINT stream (GDELT/API) unreachable or degraded. "
            "Automatically failing over to **Cached GTD Tactical Intelligence Database** (Offline Mode).",
            icon="🛡️"
        )

    st_custom_threat_banner(risk.level, f"{risk.score}/100")
    
    c1, c2 = st.columns(2)
    with c1: st_custom_kpi_card("Historical Incidents", f"{len(country_hist):,}", "Recorded events", "📚")
    with c2: st_custom_kpi_card("Live Items", f"{len(country_live):,}", "Recent 24h events", "⚡")

    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=risk.score,
            title={"text": "AI Risk Score"},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": risk.color},
                "steps": [
                    {"range": [0, 30], "color": "rgba(52,199,89,0.20)"},
                    {"range": [30, 55], "color": "rgba(255,214,10,0.20)"},
                    {"range": [55, 75], "color": "rgba(255,107,53,0.20)"},
                    {"range": [75, 100], "color": "rgba(255,45,85,0.20)"},
                ],
            },
        )
    )
    fig.update_layout(template="plotly_dark", height=300, paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("🔍 What drives this score?", expanded=True):
        comp = risk.components
        if comp:
            fig_comp = go.Figure(go.Bar(
                x=list(comp.values()),
                y=list(comp.keys()),
                orientation="h",
                marker_color="#00E5FF",
                text=[f"{v:.1f}" for v in comp.values()],
                textposition="auto"
            ))
            fig_comp.update_layout(
                title="Threat Score Component Breakdown",
                xaxis_title="Contribution to Final Score",
                yaxis={'categoryorder':'total ascending'},
                template="plotly_dark",
                height=250,
                margin=dict(l=10, r=10, t=30, b=10),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)"
            )
            st.plotly_chart(fig_comp, use_container_width=True)
        else:
            st.write("Not enough data to calculate components.")

    st.subheader("Risk Drivers")
    component_df = pd.DataFrame(
        [{"Component": key, "Weighted Points": round(value, 2)} for key, value in risk.components.items()]
    )
    st.bar_chart(component_df.set_index("Component"))

    st.divider()

    st.subheader("Situation Report")

    generated_report = report
    can_use_gemini = bool(api_key and genai is not None)
    if st.button("🚀 Generate / Enhance Brief"):
        if can_use_gemini:
            with st.spinner("Enhancing report with Gemini..."):
                try:
                    client = genai.Client(api_key=api_key)
                    prompt = f"""
You are a senior intelligence analyst. Rewrite the following situation report into a concise,
professional brief. Keep all risk figures unchanged, avoid operational targeting guidance, and
include a short analyst recommendation.

{report}
"""
                    response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
                    generated_report = response.text
                    st.session_state["generated_sitrep"] = generated_report
                except Exception as exc:
                    st.info(
                        "📡 **Live Feed Status:** External SIGINT stream (Gemini/API) unreachable or degraded. "
                        "Automatically failing over to **Local Report Generation** (Offline Mode).",
                        icon="🛡️"
                    )
                    st.session_state["generated_sitrep"] = report
        else:
            if genai is None:
                st.info("google-genai is not installed or importable, so a local report template was used.")
            elif not api_key:
                st.info("No Gemini API key supplied, so a local report template was used.")
            st.session_state["generated_sitrep"] = report

    generated_report = st.session_state.get("generated_sitrep", generated_report)
    st.markdown(generated_report)

    download_col1, download_col2 = st.columns(2)
    with download_col1:
        st.download_button(
            "📄 Download Markdown Report",
            generated_report,
            file_name=f"{selected_country}_situation_report.md",
            mime="text/markdown",
        )
    with download_col2:
        try:
            pdf_bytes = build_pdf(generated_report)
            st.download_button(
                "📕 Download PDF Report",
                pdf_bytes,
                file_name=f"{selected_country}_situation_report.pdf",
                mime="application/pdf",
            )
        except Exception:
            st.caption("PDF export requires reportlab. Markdown export is available.")

    st.divider()

    st.subheader("Recent Live Items For Selected Country")
    if country_live.empty:
        st.info("No live items matched this country in the selected window.")
    else:
        display = country_live[["date", "event", "severity", "source", "title", "url"]].copy()
        display["date"] = pd.to_datetime(display["date"], errors="coerce", utc=True).dt.strftime("%Y-%m-%d %H:%M UTC")
        st.dataframe(
            display.rename(
                columns={
                    "date": "Date",
                    "event": "Event",
                    "severity": "Severity",
                    "source": "Source",
                    "title": "Headline",
                    "url": "URL",
                }
            ),
            use_container_width=True,
            hide_index=True,
            column_config={"URL": st.column_config.LinkColumn("Source Link")},
        )

    st.info("This report is a decision-support artifact from historical GTD data and public news metadata.")
