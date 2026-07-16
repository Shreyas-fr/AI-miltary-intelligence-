import streamlit as st
import pandas as pd
from utils.data_loader import query_data
import os
from google import genai

st.set_page_config(
    page_title="AI Intelligence Report",
    page_icon="🧠",
    layout="wide"
)

def load_css(file_name):
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
load_css("assets/style.css")

st.title("🧠 AI Intelligence Report")

st.markdown("""
Generate an AI-assisted intelligence summary from the Global Terrorism Database (GTD) 
using Google's Gemini Large Language Model.
""")


# -------------------------------------------------
# API Key Input
# -------------------------------------------------
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    api_key = st.sidebar.text_input("Enter Gemini API Key", type="password")
    if not api_key:
        st.warning("Please provide a Gemini API Key in the sidebar to generate AI reports.")
        st.stop()

# -------------------------------------------------
# Sidebar Filters
# -------------------------------------------------
st.sidebar.header("Report Filters")
years_df = query_data("SELECT DISTINCT iyear FROM 'data/globalterrorism.csv' ORDER BY iyear")
years = ["All"] + years_df["iyear"].astype(int).tolist()
selected_year = st.sidebar.selectbox("Select Year", years)

# -------------------------------------------------
# Query Data Statistics using DuckDB
# -------------------------------------------------
where_clause = f"WHERE iyear = {selected_year}" if selected_year != "All" else ""

stats_query = f"""
    SELECT 
        COUNT(*) as total_incidents,
        SUM(nkill) as total_killed,
        SUM(nwound) as total_wounded,
        COUNT(DISTINCT country_txt) as countries,
        COUNT(DISTINCT gname) as groups
    FROM 'data/globalterrorism.csv' {where_clause}
"""
stats = query_data(stats_query).iloc[0]

top_countries = query_data(f"""
    SELECT country_txt, COUNT(*) as c 
    FROM 'data/globalterrorism.csv' {where_clause} 
    GROUP BY country_txt ORDER BY c DESC LIMIT 5
""")

top_groups = query_data(f"""
    SELECT gname, COUNT(*) as c 
    FROM 'data/globalterrorism.csv' {where_clause} 
    GROUP BY gname ORDER BY c DESC LIMIT 5
""")

top_weapons = query_data(f"""
    SELECT weaptype1_txt, COUNT(*) as c 
    FROM 'data/globalterrorism.csv' {where_clause} 
    GROUP BY weaptype1_txt ORDER BY c DESC LIMIT 3
""")

# -------------------------------------------------
# Dashboard Metrics
# -------------------------------------------------
st.subheader("Key Intelligence Indicators")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Incidents", f"{int(stats['total_incidents']):,}")
col2.metric("Fatalities", f"{int(stats['total_killed'] or 0):,}")
col3.metric("Injuries", f"{int(stats['total_wounded'] or 0):,}")

avg_killed = (stats['total_killed'] or 0) / (stats['total_incidents'] or 1)
threat = "HIGH 🔴" if avg_killed >= 5 else "MEDIUM 🟡" if avg_killed >= 2 else "LOW 🟢"
col4.metric("Threat Level", threat)

# -------------------------------------------------
# AI Generation
# -------------------------------------------------
st.subheader("Generate Executive Brief")

if st.button("🚀 Generate AI Brief"):
    with st.spinner("Generating intelligence brief using Gemini..."):
        try:
            client = genai.Client(api_key=api_key)
            
            prompt = f"""
            You are a senior intelligence analyst. Write a concise, professional executive brief 
            based on the following terrorism statistics for the year(s): {selected_year}.
            
            Data Summary:
            - Total Incidents: {int(stats['total_incidents'])}
            - Total Fatalities: {int(stats['total_killed'] or 0)}
            - Total Injuries: {int(stats['total_wounded'] or 0)}
            
            Top 5 Targeted Countries:
            {top_countries.to_dict('records')}
            
            Top 5 Active Terrorist Groups:
            {top_groups.to_dict('records')}
            
            Top 3 Weapon Types Used:
            {top_weapons.to_dict('records')}
            
            Please provide:
            1. An Executive Summary paragraph.
            2. Key threat vectors and patterns identified.
            3. Actionable strategic recommendations for counter-terrorism units.
            
            Use markdown formatting. Keep it professional and analytical.
            """
            
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
            )
            
            st.success("Brief generated successfully.")
            st.markdown(response.text)
            
            st.download_button(
                "📄 Download Intelligence Report",
                response.text,
                file_name="AI_Intelligence_Report.md"
            )
        except Exception as e:
            st.error(f"Failed to generate report: {str(e)}")