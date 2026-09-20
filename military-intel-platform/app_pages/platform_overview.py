import os
import streamlit as st
from utils.auth import require_auth

require_auth(['Viewer', 'Analyst', 'Commander'])

# Hero Section
st.markdown("<h1>🛡️ AI Military Intelligence Command Center</h1>", unsafe_allow_html=True)
st.markdown("##### Advanced tactical risk scoring, spatial hotspot forecasting, and AI situation reporting")

st.markdown("""
<div class="module-card">
    <div style="font-size: 1.1rem; color: #E2E8F0; line-height: 1.6;">
        Welcome to the <strong>Predictive Tactical Intelligence Platform</strong>.
        This system combines historical incident analytics (GTD), spatial DBSCAN clustering,
        SARIMA time-series forecasting, live public-source intelligence monitoring (GDELT),
        and non-linear Threat Severity Index (TSI) scoring for assisted command decisions.
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown('<div style="margin-top:1rem"></div>', unsafe_allow_html=True)

# Module Grid
st.markdown("### Platform modules")

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.markdown("""
    <div class="module-card">
        <div class="module-icon">🌍</div>
        <div class="module-title">Global Threat & Hotspots</div>
        <div class="module-desc">Geospatial incident maps and DBSCAN clustering with Haversine distance and migration vectors.</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="module-card">
        <div class="module-icon">🤖</div>
        <div class="module-title">Predictive ML Models</div>
        <div class="module-desc">Random Forest classifiers to predict tactical attack types and classify threat levels.</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="module-card">
        <div class="module-icon">🔔</div>
        <div class="module-title">Intelligence Alerts</div>
        <div class="module-desc">Threshold-based surveillance rules for real-time risk score and activity surge spikes.</div>
    </div>
    """, unsafe_allow_html=True)

with c2:
    st.markdown("""
    <div class="module-card">
        <div class="module-icon">📈</div>
        <div class="module-title">Time-Series Forecasting</div>
        <div class="module-desc">AIC-optimized SARIMA forecasting with held-out validation against linear baseline models.</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="module-card">
        <div class="module-icon">🛰️</div>
        <div class="module-title">Live Public Signals</div>
        <div class="module-desc">Real-time GDELT news metadata integration for event detection and risk trend tracking.</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="module-card">
        <div class="module-icon">📋</div>
        <div class="module-title">Resource Recommendation</div>
        <div class="module-desc">AI-driven operational response suggestions and tactical force posture guidelines.</div>
    </div>
    """, unsafe_allow_html=True)

with c3:
    st.markdown("""
    <div class="module-card">
        <div class="module-icon">🧠</div>
        <div class="module-title">AI Situation Briefings</div>
        <div class="module-desc">Composite 0–100 risk breakdowns, risk driver metrics, and executive situation reports.</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="module-card">
        <div class="module-icon">📊</div>
        <div class="module-title">Data Explorer</div>
        <div class="module-desc">Interactive DuckDB SQL query engine over multi-year incident data with instant CSV export.</div>
    </div>
    """, unsafe_allow_html=True)



    st.markdown("""
    <div class="module-card">
        <div class="module-icon">⛅</div>
        <div class="module-title">Weather Intelligence</div>
        <div class="module-desc">OpenWeather conditions and operational impact assessment for reconnaissance and flight planning.</div>
    </div>
    """, unsafe_allow_html=True)

with c4:
    st.markdown("""
    <div class="module-card">
        <div class="module-icon">🌎</div>
        <div class="module-title">Country Intelligence</div>
        <div class="module-desc">Deep-dive country profiles combining GTD statistics, live news, and risk breakdown.</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="module-card">
        <div class="module-icon">🚨</div>
        <div class="module-title">AI Threat Scoring</div>
        <div class="module-desc">Non-linear Threat Severity Index (TSI) scoring for real-time incident severity estimation.</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="module-card">
        <div class="module-icon">🎖️</div>
        <div class="module-title">Mission Planning</div>
        <div class="module-desc">Location-based threat radius simulator for tactical operational preparation.</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="module-card">
        <div class="module-icon">🏗️</div>
        <div class="module-title">Military Asset Layer</div>
        <div class="module-desc">Simulated airbase, naval, and radar installation overlays with threat proximity buffers.</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("### Companion Systems")

gods_eye_url = os.environ.get("GODS_EYE_VIEW_URL", "http://localhost:5173")

st.markdown(f"""
<a href="{gods_eye_url}" target="_blank" style="text-decoration: none; color: inherit;">
    <div class="module-card" style="border-left: 4px solid #00E5FF;">
        <div class="module-icon">👁️</div>
        <div class="module-title">God's Eye View (Live 3D OSINT)</div>
        <div class="module-desc">External Companion System: Live 3D geospatial OSINT globe (flights, military traffic, satellites). Opens in a new tab.</div>
    </div>
</a>
""", unsafe_allow_html=True)

st.markdown('<div style="margin-top:1.5rem"></div>', unsafe_allow_html=True)
st.caption("👈 Use the left sidebar navigation menu to select a module and begin analysis.")
