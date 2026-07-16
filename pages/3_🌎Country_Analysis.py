import streamlit as st
import plotly.express as px
from utils.data_loader import query_data
import os

st.set_page_config(
    page_title="Country Analysis",
    page_icon="🌎",
    layout="wide"
)

# Inject custom CSS for premium UI
def load_css(file_name):
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
load_css("assets/style.css")

st.title("🌎 Country Analysis")

# -----------------------------
# Sidebar
# -----------------------------
# Grab only unique countries for the dropdown to avoid loading full dataset
countries_df = query_data("SELECT DISTINCT country_txt FROM 'data/globalterrorism.csv' WHERE country_txt IS NOT NULL ORDER BY country_txt")
countries = countries_df["country_txt"].tolist()

country = st.sidebar.selectbox("Select Country", countries)

# Use DuckDB to fetch ONLY the data for the selected country
safe_country = country.replace("'", "''")
country_df = query_data(f"SELECT * FROM 'data/globalterrorism.csv' WHERE country_txt = '{safe_country}'")

st.header(f"Intelligence Report : {country}")

# -----------------------------
# KPIs
# -----------------------------

c1, c2, c3, c4 = st.columns(4)

c1.metric("Incidents", f"{len(country_df):,}")
c2.metric("Fatalities", f"{int(country_df['nkill'].fillna(0).sum()):,}")
c3.metric("Injured", f"{int(country_df['nwound'].fillna(0).sum()):,}")
c4.metric("Groups", f"{country_df['gname'].nunique():,}")

st.divider()

# -----------------------------
# Attacks Over Time
# -----------------------------

left, right = st.columns(2)

with left:
    yearly = country_df.groupby("iyear").size().reset_index(name="Attacks")
    fig = px.line(yearly, x="iyear", y="Attacks", markers=True, title="Attacks Over Years", template="plotly_dark")
    st.plotly_chart(fig, width="stretch")

with right:
    attack = country_df.groupby("attacktype1_txt").size().reset_index(name="Count")
    fig = px.pie(attack, names="attacktype1_txt", values="Count", title="Attack Types", template="plotly_dark")
    st.plotly_chart(fig, width="stretch")

st.divider()

# -----------------------------
# Organizations & Weapons
# -----------------------------

left, right = st.columns(2)

with left:
    groups = country_df.groupby("gname").size().reset_index(name="Attacks").sort_values("Attacks", ascending=False).head(10)
    fig = px.bar(groups, x="Attacks", y="gname", orientation="h", title="Top Terrorist Organizations", template="plotly_dark")
    st.plotly_chart(fig, width="stretch")

with right:
    weapon = country_df.groupby("weaptype1_txt").size().reset_index(name="Count").sort_values("Count", ascending=False)
    fig = px.bar(weapon, x="weaptype1_txt", y="Count", title="Weapon Types", template="plotly_dark")
    st.plotly_chart(fig, width="stretch")

st.divider()

# -----------------------------
# Incident Map
# -----------------------------

st.subheader("Incident Locations")

map_df = country_df.dropna(subset=["latitude", "longitude"])

if not map_df.empty:
    fig = px.scatter_geo(
        map_df,
        lat="latitude",
        lon="longitude",
        hover_name="city",
        hover_data={"country_txt": True, "iyear": True, "attacktype1_txt": True, "gname": True, "nkill": True, "latitude": False, "longitude": False},
        color="attacktype1_txt",
        projection="natural earth",
        title=f"Terrorist Incidents in {country}",
        height=600,
        template="plotly_dark"
    )
    fig.update_layout(margin=dict(l=0, r=0, t=50, b=0))
    st.plotly_chart(fig, width="stretch")
else:
    st.warning("No geospatial coordinates available for this country.")

st.divider()

# -----------------------------
# Incident Table
# -----------------------------

st.subheader("Incident Details")

cols = ["iyear", "city", "attacktype1_txt", "targtype1_txt", "weaptype1_txt", "gname", "nkill", "nwound"]
st.dataframe(country_df[cols], width="stretch")

# -----------------------------
# Download
# -----------------------------
csv = country_df.to_csv(index=False).encode()
st.download_button("Download Country Data", csv, file_name=f"{country}.csv", mime="text/csv")