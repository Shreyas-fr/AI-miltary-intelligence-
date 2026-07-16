import streamlit as st
import os

st.set_page_config(
    page_title="AI Military Intelligence",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inject custom CSS for premium UI
def load_css(file_name):
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

load_css("assets/style.css")

st.title("🛡️ AI Military Intelligence Dashboard")

st.markdown("""
### Welcome

This dashboard provides military intelligence analysis using the
Global Terrorism Database (GTD).

👈 Select a page from the sidebar.
""")

st.info("""
Available Modules

- 🏠 Home
- 🌍 Global Threat Map
- 🌎 Country Analysis
- 🤖 Attack Prediction
- 🚨 Threat Level Prediction
- 📈 Forecasting
- 🧠 AI Intelligence Report
- 📊 Data Explorer
- ⚙ Settings

👈 Use the **left sidebar** to navigate.
""")

st.info("Select a page from the sidebar to begin.")

