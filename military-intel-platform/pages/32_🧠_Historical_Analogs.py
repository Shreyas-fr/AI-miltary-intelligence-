import os
import streamlit as st
import pandas as pd

# --- Authentication & Role Check ---
from utils.auth import require_auth
require_auth(['Analyst', 'Commander'])
# -----------------------------------

from utils.analog_utils import find_historical_analog
from utils.ui_components import st_custom_kpi_card

st.set_page_config(page_title="Historical Analog Finder", page_icon="🧠", layout="wide")

def load_css(file_name: str):
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_css("assets/style.css")

st.title("🧠 | Historical Analog Finder")
st.markdown(
    "##### AI-driven tactical signature matching. Finds the closest historical period "
    "matching the selected country's recent tactical footprint (weapons, targets, lethality, tempo)."
)

# 1. Select Country
# Get unique countries from GTD to populate the dropdown
@st.cache_data(ttl=86400)
def get_countries():
    df = pd.read_csv("data/globalterrorism.csv", usecols=["country_txt"])
    return sorted(df["country_txt"].dropna().unique())

countries = get_countries()

query_country = st.selectbox(
    "Select Country for Analog Search", 
    options=countries,
    index=countries.index("Iraq") if "Iraq" in countries else 0,
    help="Select the nation to analyze. The system will use its most recent 6-month data window to find an analog."
)

st.divider()

if st.button("Find Historical Analog", type="primary"):
    with st.spinner(f"Computing tactical vector and searching historical matrix for {query_country}..."):
        analog_result, error = find_historical_analog(query_country)
        
    if error:
        st.error(f"⚠️ {error}")
    else:
        q_win = analog_result['query_window']
        a_win = analog_result['analog_window']
        nxt = analog_result['subsequent_stats']
        
        sim_pct = a_win['similarity'] * 100
        
        # Current Context
        st.subheader(f"Current Context: {query_country}")
        st.markdown(
            f"**Baseline Date Range:** {q_win['start_date'].strftime('%b %Y')} to {q_win['end_date'].strftime('%b %Y')}  \n"
            f"*Analyzed {q_win['incident_count']} incidents to build the tactical signature.*"
        )
        
        st.markdown("<br/>", unsafe_allow_html=True)
        
        # The Match
        st.subheader("Closest Historical Analog")
        
        col1, col2 = st.columns([1, 2])
        with col1:
            st_custom_kpi_card(
                "Similarity Match", 
                f"{sim_pct:.1f}%", 
                f"{a_win['country']}", 
                "🤝"
            )
        with col2:
            st.markdown(
                f"""
                <div style='background-color: #1e293b; padding: 1.5rem; border-radius: 8px; border-left: 5px solid #00E5FF;'>
                    <h4 style='margin-top: 0; color: #00E5FF;'>Analog: {a_win['country']}</h4>
                    <p style='font-size: 1.1rem; margin-bottom: 0;'>
                        <b>Date Range:</b> {a_win['start_date'].strftime('%b %Y')} to {a_win['end_date'].strftime('%b %Y')}<br/>
                        <b>Incidents in Window:</b> {a_win['incident_count']}<br/>
                    </p>
                </div>
                """, unsafe_allow_html=True
            )
            
        st.markdown("<br/>", unsafe_allow_html=True)
        
        # What Happened Next
        st.subheader("What Happened Next?")
        st.markdown(
            f"The subsequent 6-month period for **{a_win['country']}** "
            f"({nxt['next_start'].strftime('%b %Y')} to {nxt['next_end'].strftime('%b %Y')}):"
        )
        
        if nxt.get('out_of_bounds'):
            st.warning("No subsequent data available — outside dataset coverage (post-Dec 2017)")
        else:
            c1, c2, c3, c4 = st.columns(4)
            
            freq_color = "#FF2D55" if nxt['freq_change_pct'] > 0 else "#34C759"
            cas_color = "#FF2D55" if nxt['cas_change_pct'] > 0 else "#34C759"
            
            freq_sign = "+" if nxt['freq_change_pct'] > 0 else ""
            cas_sign = "+" if nxt['cas_change_pct'] > 0 else ""
            
            with c1:
                st.markdown(f"**Attack Frequency:**<br/><span style='color:{freq_color}; font-size:1.5rem; font-weight:bold;'>{freq_sign}{nxt['freq_change_pct']:.1f}%</span>", unsafe_allow_html=True)
                st.caption(f"{nxt['next_incidents']} total attacks")
            with c2:
                st.markdown(f"**Lethality Shift:**<br/><span style='color:{cas_color}; font-size:1.5rem; font-weight:bold;'>{cas_sign}{nxt['cas_change_pct']:.1f}%</span>", unsafe_allow_html=True)
                st.caption("Change in avg casualties")
            with c3:
                st.markdown(f"**Primary Target Shift:**<br/><span style='font-size:1.2rem; font-weight:bold; color:#CBD5E1;'>{nxt['new_target']}</span>", unsafe_allow_html=True)
            with c4:
                st.markdown(f"**Primary Weapon Shift:**<br/><span style='font-size:1.2rem; font-weight:bold; color:#CBD5E1;'>{nxt['new_weapon']}</span>", unsafe_allow_html=True)

        st.markdown("<br/>", unsafe_allow_html=True)
        
        # Honest Caveat
        st.warning(
            "**Tactical Similarity ≠ Geopolitical Destiny**\n\n"
            "This tool identifies historical parallels in insurgent tactics; it does not account for modern countermeasures, regime changes, or foreign intervention. "
            "A high tactical match does not guarantee the same outcome if current defensive assets are vastly superior."
        )
