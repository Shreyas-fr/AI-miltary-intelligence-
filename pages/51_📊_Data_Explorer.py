import streamlit as st

# --- Authentication & Role Check ---
from utils.auth import require_auth
require_auth(['Analyst', 'Commander'])
# -----------------------------------

import pandas as pd
import plotly.express as px
import os
from utils.data_loader import load_data, query_data
from utils.ui_components import st_custom_kpi_card

# -----------------------------------------------
# Page Configuration
# -----------------------------------------------
st.set_page_config(
    page_title="Data Explorer",
    page_icon="📊",
    layout="wide"
)

def load_css(file_name):
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
load_css("assets/style.css")

st.title("📊 | Global Terrorism Data Explorer")
st.markdown("##### Filter, visualize and download the full GTD dataset.")

# -----------------------------------------------
# Load full dataset (cached in memory)
# -----------------------------------------------
df = load_data()

# -----------------------------------------------
# Sidebar Filters
# -----------------------------------------------
st.sidebar.header("🔽 Filter Dataset")

years      = sorted(df["iyear"].dropna().unique())
countries  = sorted(df["country_txt"].dropna().unique())
regions    = sorted(df["region_txt"].dropna().unique())
atk_types  = sorted(df["attacktype1_txt"].dropna().unique())
weapons    = sorted(df["weaptype1_txt"].dropna().unique())
groups     = sorted(df["gname"].dropna().unique())

selected_year    = st.sidebar.multiselect("Year",           years,     default=[])
selected_country = st.sidebar.multiselect("Country",        countries, default=[])
selected_region  = st.sidebar.multiselect("Region",         regions,   default=[])
selected_attack  = st.sidebar.multiselect("Attack Type",    atk_types, default=[])
selected_weapon  = st.sidebar.multiselect("Weapon Type",    weapons,   default=[])
selected_group   = st.sidebar.multiselect("Terrorist Group",groups,    default=[])

# -----------------------------------------------
# Apply Filters
# -----------------------------------------------
filtered_df = df.copy()

if selected_year:    filtered_df = filtered_df[filtered_df["iyear"].isin(selected_year)]
if selected_country: filtered_df = filtered_df[filtered_df["country_txt"].isin(selected_country)]
if selected_region:  filtered_df = filtered_df[filtered_df["region_txt"].isin(selected_region)]
if selected_attack:  filtered_df = filtered_df[filtered_df["attacktype1_txt"].isin(selected_attack)]
if selected_weapon:  filtered_df = filtered_df[filtered_df["weaptype1_txt"].isin(selected_weapon)]
if selected_group:   filtered_df = filtered_df[filtered_df["gname"].isin(selected_group)]

# -----------------------------------------------
# Search Box
# -----------------------------------------------
search = st.text_input("🔍 Search by City or Country", placeholder="e.g., Kabul, Iraq...")

if search:
    filtered_df = filtered_df[
        filtered_df["city"].fillna("").str.contains(search, case=False)
        | filtered_df["country_txt"].fillna("").str.contains(search, case=False)
    ]

# -----------------------------------------------
# KPI Metrics
# -----------------------------------------------
if filtered_df.empty:
    st.warning("No records match the selected filters. Please broaden your search criteria.")
    st.stop()

st.subheader("Dataset Summary")
c1, c2, c3, c4 = st.columns(4)
with c1: st_custom_kpi_card("Incidents",   f"{len(filtered_df):,}", "", "📉")
with c2: st_custom_kpi_card("Countries",   f"{filtered_df['country_txt'].nunique():,}", "", "🌎")
with c3: st_custom_kpi_card("Fatalities",  f"{int(filtered_df['nkill'].fillna(0).sum()):,}", "", "💀")
with c4: st_custom_kpi_card("Injuries",    f"{int(filtered_df['nwound'].fillna(0).sum()):,}", "", "🩹")

st.divider()

# -----------------------------------------------
# Visual Analytics Tabs
# -----------------------------------------------
st.subheader("Visual Analytics")
tab1, tab2, tab3 = st.tabs(["🌐 By Country", "💥 Attack Types", "🔫 Weapon Types"])

with tab1:
    country_chart = filtered_df["country_txt"].value_counts().head(10).reset_index()
    country_chart.columns = ["Country", "Incidents"]
    fig = px.bar(
        country_chart, x="Country", y="Incidents",
        color="Incidents", color_continuous_scale="Blues",
        title="Top 10 Countries by Incidents",
        template="plotly_dark"
    )
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    atk_chart = filtered_df["attacktype1_txt"].value_counts().reset_index()
    atk_chart.columns = ["Attack Type", "Count"]
    fig = px.pie(
        atk_chart, names="Attack Type", values="Count",
        title="Attack Type Distribution",
        template="plotly_dark", hole=0.4,
        color_discrete_sequence=px.colors.sequential.Blues_r
    )
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)

with tab3:
    wpn_chart = filtered_df["weaptype1_txt"].value_counts().reset_index()
    wpn_chart.columns = ["Weapon", "Count"]
    fig = px.bar(
        wpn_chart, x="Weapon", y="Count",
        color="Count", color_continuous_scale="Reds",
        title="Weapon Type Distribution",
        template="plotly_dark"
    )
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# -----------------------------------------------
# Filtered Dataset Table + Download
# -----------------------------------------------
st.subheader("Filtered Dataset")
st.caption(f"Showing {len(filtered_df):,} records")
st.dataframe(filtered_df, height=450, use_container_width=True, hide_index=True)

csv = filtered_df.to_csv(index=False)
st.download_button("📥 Download Filtered Data", csv, file_name="Filtered_GTD_Data.csv", mime="text/csv")

st.divider()

# -----------------------------------------------
# Dataset Info Panel
# -----------------------------------------------
with st.expander("🔎 Dataset Info"):
    col1, col2, col3 = st.columns(3)
    with col1: st_custom_kpi_card("Rows", f"{filtered_df.shape[0]:,}", "", "🔢")
    with col2: st_custom_kpi_card("Columns", f"{filtered_df.shape[1]:,}", "", "📋")
    with col3: st_custom_kpi_card("Memory", f"{round(filtered_df.memory_usage(deep=True).sum() / 1024**2, 2)} MB", "", "💾")

    st.markdown("**Column Names:**")
    st.write(filtered_df.columns.tolist())

    missing = filtered_df.isnull().sum().sort_values(ascending=False).reset_index()
    missing.columns = ["Column", "Missing Values"]
    missing = missing[missing["Missing Values"] > 0]
    if not missing.empty:
        st.markdown("**Missing Values:**")
        st.dataframe(missing, use_container_width=True, hide_index=True)