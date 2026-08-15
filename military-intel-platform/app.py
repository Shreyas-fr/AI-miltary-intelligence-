import os
# Fix for PyArrow mimalloc memory crashes on Apple Silicon (M-series Macs)
os.environ["ARROW_DEFAULT_MEMORY_POOL"] = "system"

import streamlit as st

st.set_page_config(
    page_title="AI Military Intelligence",
    page_icon=":material/shield:",
    layout="wide",
    initial_sidebar_state="expanded"
)

import yaml
from yaml.loader import SafeLoader
import streamlit_authenticator as stauth

# Load CSS
def load_css(file_name):
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

load_css("assets/style.css")

# --- Authentication Setup ---
# --- Authentication Setup ---
import logging

render_secret_path = '/etc/secrets/credentials.yaml'
local_path = 'credentials.yaml'

credentials_path = None
if os.path.exists(render_secret_path):
    credentials_path = render_secret_path
elif os.path.exists(local_path):
    credentials_path = local_path

if not credentials_path:
    st.error("🔒 **Configuration Error:** `credentials.yaml` not found in `/etc/secrets/` or local directory.")
    st.warning("Ensure credentials are provided via Render Secret Files or local file.")
    st.stop()

print(f"✅ Successfully loaded credentials from: {credentials_path}")

try:
    with open(credentials_path) as file:
        config = yaml.load(file, Loader=SafeLoader)
except Exception as e:
    st.error(f"🔒 **Failed to parse credentials file:** {str(e)}")
    st.stop()

authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days']
)

# Render login widget
authenticator.login(location="main")

auth_status = st.session_state.get("authentication_status")

if auth_status:
    authenticator.logout(location="sidebar")
    st.sidebar.markdown(f"**User:** {st.session_state.get('name', 'Unknown')}")
    
    roles = st.session_state.get("roles")
    role_display = roles[0] if roles and isinstance(roles, list) else "Viewer"
    st.sidebar.markdown(f"**Role:** {role_display}")
    
elif auth_status is False:
    st.error('Username/password is incorrect')
    st.stop()
elif auth_status is None:
    st.warning('Please enter your username and password')
    st.stop()
    
# --- Main Application (Only visible if authenticated) ---

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

st.markdown('<div style="margin-top:1.5rem"></div>', unsafe_allow_html=True)
st.caption("👈 Use the left sidebar navigation menu to select a module and begin analysis.")
