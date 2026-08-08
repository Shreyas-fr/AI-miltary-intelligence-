import streamlit as st

# --- Authentication & Role Check ---
from utils.auth import require_auth
require_auth(['Commander'])
# -----------------------------------

import os

st.set_page_config(
    page_title="Settings",
    page_icon="⚙️",
    layout="wide"
)

def load_css(file_name):
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
load_css("assets/style.css")

st.title("⚙️ | Dashboard Settings")
st.markdown("##### Configure your AI Military Intelligence Dashboard preferences.")

st.divider()

# -----------------------------------------------
# Dataset Info
# -----------------------------------------------
st.subheader("📊 Dataset Status")
from utils.data_loader import query_data
try:
    stats = query_data("SELECT COUNT(*) as rows, COUNT(DISTINCT country_txt) as countries, MIN(iyear) as from_year, MAX(iyear) as to_year FROM 'data/globalterrorism.csv'").iloc[0]
    st.success("✅ Dataset loaded and connected successfully.")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Incidents", f"{int(stats['rows']):,}")
    c2.metric("Countries",       f"{int(stats['countries']):,}")
    c3.metric("Data From",       f"{int(stats['from_year'])}")
    c4.metric("Data To",         f"{int(stats['to_year'])}")
except Exception as e:
    st.error(f"❌ Dataset not found or error: {e}")

st.divider()

# -----------------------------------------------
# General Settings (informational — config via .streamlit/config.toml)
# -----------------------------------------------
st.subheader("🎨 Appearance")
st.info("The dashboard is using a **Premium Dark Mode** theme configured via `.streamlit/config.toml`. To switch themes, edit the config file directly.")

with st.expander("View current theme config"):
    st.code("""
[theme]
base="dark"
primaryColor="#00E5FF"
backgroundColor="#0A0E17"
secondaryBackgroundColor="#141C2B"
textColor="#E0E6ED"
""", language="toml")

st.divider()

# -----------------------------------------------
# Gemini API Key
# -----------------------------------------------
st.subheader("🔑 Gemini API Key")
st.markdown("The **AI Intelligence Report** page requires a Google Gemini API Key. You can provide it inline on the page, or set it as an environment variable for persistence:")
st.code("export GEMINI_API_KEY=your_key_here", language="bash")

st.divider()

# -----------------------------------------------
# About
# -----------------------------------------------
st.subheader("ℹ️ About")
st.markdown("""
| Item | Detail |
|------|--------|
| **App** | AI Military Intelligence Dashboard |
| **Data Source** | Global Terrorism Database (GTD) |
| **ML Framework** | scikit-learn (Random Forest, Target Encoding) |
| **AI Engine** | Google Gemini 2.5 Flash |
| **Data Engine** | DuckDB in-memory SQL |
| **Visualization** | Plotly, PyDeck |
| **Framework** | Streamlit |
""")