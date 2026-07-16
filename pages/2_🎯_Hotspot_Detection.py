import streamlit as st
import pydeck as pdk
import os
from utils.data_loader import query_data
from utils.hotspot_utils import compute_tsi, cluster_hotspots

st.set_page_config(page_title="Hotspot Detection", page_icon="🎯", layout="wide")


def load_css(file_name):
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


load_css("assets/style.css")

st.title("🎯 Spatial Hotspot Detection")
st.markdown(
    "##### DBSCAN clustering (haversine distance) over incident geometry, "
    "ranked by a non-linear Threat Severity Index (TSI)."
)

st.sidebar.header("Clustering Parameters")
eps_km = st.sidebar.slider(
    "Cluster radius (km)", 25, 500, 100, step=25,
    help="Max distance between two incidents to be grouped into the same hotspot.",
)
min_samples = st.sidebar.slider("Minimum incidents per hotspot", 5, 50, 15, step=5)

# -----------------------------------------------
# Load only what's needed, filtered to valid coords
# -----------------------------------------------
df = query_data(
    """
    SELECT latitude, longitude, nkill, nwound, success, iyear, country_txt, region_txt
    FROM 'data/globalterrorism.csv'
    WHERE latitude IS NOT NULL AND longitude IS NOT NULL
    """
)

df = compute_tsi(df)

with st.spinner("Running DBSCAN over incident geometry..."):
    df_clustered, hotspots = cluster_hotspots(df, eps_km=eps_km, min_samples=min_samples)

# Persist for the Forecasting page
st.session_state["hotspot_df"] = df_clustered
st.session_state["hotspot_summary"] = hotspots

c1, c2, c3 = st.columns(3)
c1.metric("Hotspots Detected", f"{len(hotspots):,}")
c2.metric("Incidents in Hotspots", f"{len(df_clustered[df_clustered['cluster'] != -1]):,}")
c3.metric("Noise (isolated incidents)", f"{(df_clustered['cluster'] == -1).sum():,}")

st.divider()

# -----------------------------------------------
# Map — hexbin height/color driven by aggregated TSI
# -----------------------------------------------
plot_df = df_clustered[df_clustered["cluster"] != -1]

if plot_df.empty:
    st.warning("No hotspots found with these parameters — try a larger radius or lower minimum incidents.")
else:
    layer = pdk.Layer(
        "HexagonLayer",
        data=plot_df,
        get_position=["longitude", "latitude"],
        radius=int(eps_km * 300),
        elevation_scale=40,
        elevation_range=[0, 3000],
        pickable=True,
        extruded=True,
        get_weight="tsi",
        color_range=[
            [255, 255, 178], [254, 204, 92], [253, 141, 60],
            [240, 59, 32], [189, 0, 38],
        ],
    )
    view_state = pdk.ViewState(longitude=0, latitude=20, zoom=1.5, pitch=40.5, bearing=-27.36)
    r = pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        tooltip={"text": "Elevation/color = aggregated Threat Severity Index (TSI)"},
    )
    st.pydeck_chart(r)

st.divider()

# -----------------------------------------------
# Ranked hotspot table
# -----------------------------------------------
st.subheader("Top Threat Hotspots (ranked by total TSI)")

if hotspots.empty:
    st.info("No hotspots to display yet — adjust the clustering parameters in the sidebar.")
else:
    display_cols = ["rank", "countries", "incidents", "total_tsi", "avg_tsi", "centroid_lat", "centroid_lon"]
    st.dataframe(
        hotspots[display_cols]
        .head(20)
        .rename(
            columns={
                "rank": "Rank", "countries": "Dominant Country", "incidents": "Incidents",
                "total_tsi": "Total TSI", "avg_tsi": "Avg TSI",
                "centroid_lat": "Lat", "centroid_lon": "Lon",
            }
        ),
        width="stretch",
    )

st.info("👉 Go to **Hotspot Forecasting** to project attack trends for any hotspot above.")
