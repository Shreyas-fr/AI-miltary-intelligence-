import os
import pandas as pd
import plotly.express as px
import streamlit as st

from utils.similarity import SimilarityEngine
from utils.data_loader import query_data
from utils.ui_components import st_custom_kpi_card

# -----------------------------------------------
# Page Configuration
# -----------------------------------------------
st.set_page_config(
    page_title="Event Similarity",
    page_icon="🔍",
    layout="wide"
)

# -----------------------------------------------
# Load Custom CSS
# -----------------------------------------------
def load_css(file_name):
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_css("assets/style.css")

# -----------------------------------------------
# Header
# -----------------------------------------------
st.title("🔍 | Event Similarity Engine")
st.markdown("##### Find historically similar incidents using AI-powered pattern matching.")

# -----------------------------------------------
# Cache SimilarityEngine Initialization
# -----------------------------------------------
@st.cache_resource(show_spinner="Building similarity index...")
def get_engine():
    df = query_data(
        "SELECT iyear, country_txt, region_txt, attacktype1_txt, weaptype1_txt, targtype1_txt, gname, nkill, nwound, success, city FROM 'data/globalterrorism.csv'"
    )
    return SimilarityEngine(df), df

engine, df = get_engine()

# -----------------------------------------------
# Dropdown Options
# -----------------------------------------------
countries = sorted([c for c in df["country_txt"].dropna().unique() if str(c).strip() and str(c).lower() not in ("unknown", "nan")])
attack_types = sorted([a for a in df["attacktype1_txt"].dropna().unique() if str(a).strip() and str(a).lower() not in ("unknown", "nan")])
weapon_types = sorted([w for w in df["weaptype1_txt"].dropna().unique() if str(w).strip() and str(w).lower() not in ("unknown", "nan")])
target_types = sorted([t for t in df["targtype1_txt"].dropna().unique() if str(t).strip() and str(t).lower() not in ("unknown", "nan")])

# -----------------------------------------------
# Input Form
# -----------------------------------------------
with st.form(key="similarity_query_form"):
    st.subheader("🎯 Target Incident Specifications")
    
    col1, col2 = st.columns(2)
    
    with col1:
        country = st.selectbox("Country", options=countries, index=0 if countries else None)
        attack_type = st.selectbox("Attack Type", options=attack_types, index=0 if attack_types else None)
        weapon_type = st.selectbox("Weapon Type", options=weapon_types, index=0 if weapon_types else None)
        target_type = st.selectbox("Target Type", options=target_types, index=0 if target_types else None)
        
    with col2:
        group = st.text_input("Perpetrator Group / Name", value="Unknown")
        nkill = st.number_input("Fatalities (nkill)", min_value=0, max_value=10000, value=0, step=1)
        nwound = st.number_input("Injuries (nwound)", min_value=0, max_value=10000, value=0, step=1)
        success = st.toggle("Attack Successful", value=True)
        
    submitted = st.form_submit_button("🔍 Find Similar Events", use_container_width=True)

# -----------------------------------------------
# Compute and Display Results
# -----------------------------------------------
if submitted or "similarity_has_run" not in st.session_state:
    st.session_state["similarity_has_run"] = True
    
    # Infer region_txt for query if possible
    region_series = df[df["country_txt"] == country]["region_txt"].dropna() if country else pd.Series()
    region_txt = region_series.iloc[0] if not region_series.empty else "Unknown"

    query_dict = {
        "country_txt": country,
        "region_txt": region_txt,
        "attacktype1_txt": attack_type,
        "weaptype1_txt": weapon_type,
        "targtype1_txt": target_type,
        "gname": group,
        "nkill": nkill,
        "nwound": nwound,
        "success": 1 if success else 0,
    }

    with st.spinner("Finding similar historical events..."):
        results = engine.find_similar(query_dict, top_k=10)

    st.divider()

    # 1. KPI Metrics
    top_sim = results["similarity_pct"].iloc[0] if not results.empty else 0.0
    avg_sim = results["similarity_pct"].mean() if not results.empty else 0.0
    top_country = results["country_txt"].iloc[0] if not results.empty else "N/A"
    top_year = int(results["iyear"].iloc[0]) if not results.empty and pd.notna(results["iyear"].iloc[0]) else "N/A"

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    with kpi1: st_custom_kpi_card("Top Similarity Score", f"{top_sim:.1f}%", "", "🎯")
    with kpi2: st_custom_kpi_card("Average Similarity", f"{avg_sim:.1f}%", "", "📊")
    with kpi3: st_custom_kpi_card("Top Match Location", f"{top_country}", "", "📍")
    with kpi4: st_custom_kpi_card("Top Match Year", f"{top_year}", "", "📅")

    st.markdown("---")

    # 2. Similarity Score Bar Chart (plotly_dark)
    st.subheader("📊 Top Matches Similarity Distribution")
    chart_df = results.copy()
    chart_df["Match Label"] = [
        f"#{i+1} {row['country_txt']} ({int(row['iyear']) if pd.notna(row['iyear']) else 'N/A'})"
        for i, row in chart_df.iterrows()
    ]
    fig = px.bar(
        chart_df,
        x="similarity_pct",
        y="Match Label",
        orientation="h",
        labels={"similarity_pct": "Similarity (%)", "Match Label": "Historical Event"},
        title="Top 10 Most Similar Historical Incidents",
        color="similarity_pct",
        color_continuous_scale="Blues",
        template="plotly_dark"
    )
    fig.update_layout(yaxis=dict(autorange="reversed"))
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # 3. Results Table
    st.subheader("📄 Historical Match Rankings")
    table_df = pd.DataFrame({
        "Rank": [f"#{i+1}" for i in range(len(results))],
        "Year": results["iyear"].fillna(0).astype(int),
        "Country": results["country_txt"].fillna("Unknown"),
        "City": results["city"].fillna("Unknown"),
        "Attack Type": results["attacktype1_txt"].fillna("Unknown"),
        "Weapon": results["weaptype1_txt"].fillna("Unknown"),
        "Group": results["gname"].fillna("Unknown"),
        "Fatalities": results["nkill"].fillna(0).astype(int),
        "Injuries": results["nwound"].fillna(0).astype(int),
        "Similarity %": results["similarity_pct"].apply(lambda x: f"{x:.1f}%")
    })
    st.dataframe(table_df, use_container_width=True, hide_index=True)

    st.markdown("---")

    # 4. Expandable Details for Each Match
    st.subheader("📋 Expandable Match Details")
    for idx, row in results.iterrows():
        rank = idx + 1
        sim_pct = row["similarity_pct"]
        year = int(row["iyear"]) if pd.notna(row["iyear"]) else "N/A"
        c_name = row.get("country_txt", "Unknown")
        city_name = row.get("city", "Unknown")

        with st.expander(f"Rank #{rank} | {c_name} ({year}) — {sim_pct:.1f}% Similarity"):
            dcol1, dcol2, dcol3 = st.columns(3)
            with dcol1:
                st.markdown(f"**Location:** {city_name}, {c_name}")
                st.markdown(f"**Region:** {row.get('region_txt', 'N/A')}")
                st.markdown(f"**Year:** {year}")
            with dcol2:
                st.markdown(f"**Attack Type:** {row.get('attacktype1_txt', 'N/A')}")
                st.markdown(f"**Weapon Type:** {row.get('weaptype1_txt', 'N/A')}")
                st.markdown(f"**Target Type:** {row.get('targtype1_txt', 'N/A')}")
            with dcol3:
                st.markdown(f"**Group:** {row.get('gname', 'N/A')}")
                st.markdown(f"**Fatalities:** {int(row.get('nkill', 0) or 0)}")
                st.markdown(f"**Injuries:** {int(row.get('nwound', 0) or 0)}")
                st.markdown(f"**Status:** {'Successful' if row.get('success') == 1 else 'Failed'}")
