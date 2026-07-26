import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import os
from sklearn.cluster import DBSCAN
from scipy.spatial import ConvexHull
import pydeck as pdk
from utils.data_loader import query_data, load_data

st.set_page_config(page_title="Global Threat Map", page_icon="🌍", layout="wide")

def load_css(file_name):
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
load_css("assets/style.css")

st.title("🌍 Global Threat Map")
st.markdown("##### 3D hexbin map of global terrorist incidents with DBSCAN geospatial cluster analysis.")

# -----------------------------------------------
# Sidebar Filters
# -----------------------------------------------
st.sidebar.header("Filters")

years_df = query_data("SELECT DISTINCT iyear FROM 'data/globalterrorism.csv' ORDER BY iyear")
years_list = ["All"] + years_df["iyear"].astype(int).tolist()
selected_year = st.sidebar.selectbox("Year", years_list)

view_mode = st.sidebar.radio("View Mode", ["Hexbin Density", "DBSCAN Clusters", "Both"], index=2)

st.sidebar.markdown("---")
st.sidebar.subheader("Map Style")
MAP_STYLES = {
    "Dark": "mapbox://styles/mapbox/dark-v11",
    "Street": "mapbox://styles/mapbox/streets-v12",
    "Satellite": "mapbox://styles/mapbox/satellite-streets-v12",
    "Terrain": "mapbox://styles/mapbox/outdoors-v12",
}
selected_style = st.sidebar.selectbox("Map theme", list(MAP_STYLES.keys()))

st.sidebar.markdown("---")
st.sidebar.subheader("DBSCAN Parameters")
eps_km = st.sidebar.slider("Cluster Radius (km)", min_value=50, max_value=500, value=150, step=50,
    help="Maximum distance between two incidents to be in the same cluster (haversine great-circle km)")
min_samples = st.sidebar.slider("Min Incidents per Cluster", min_value=3, max_value=30, value=8,
    help="Minimum points required to form a dense region")

# -----------------------------------------------
# Query Data
# -----------------------------------------------
if selected_year == "All":
    sql = "SELECT latitude, longitude, nkill, country_txt FROM 'data/globalterrorism.csv' WHERE latitude IS NOT NULL AND longitude IS NOT NULL"
else:
    sql = f"SELECT latitude, longitude, nkill, country_txt FROM 'data/globalterrorism.csv' WHERE iyear = {selected_year} AND latitude IS NOT NULL AND longitude IS NOT NULL"

df = query_data(sql)
df["nkill"] = df["nkill"].fillna(0)

st.markdown(f"**Showing {len(df):,} incidents**  |  Year: `{selected_year}`")

if len(df) == 0:
    st.warning("No data available for the selected filters.")
    st.stop()

# -----------------------------------------------
# DBSCAN — Haversine Distance Clustering
# -----------------------------------------------
@st.cache_data(show_spinner="Running DBSCAN clustering...")
def run_dbscan(lat_arr, lon_arr, eps_km_val, min_samp):
    """
    DBSCAN with haversine metric.

    Haversine gives great-circle distance on a sphere:
        d = 2R · arcsin(√[sin²(Δφ/2) + cos(φ₁)cos(φ₂)sin²(Δλ/2)])

    sklearn expects radians when metric='haversine', so we convert:
        eps_radians = eps_km / R_earth   (R_earth = 6371 km)

    Why haversine and NOT Euclidean?
    ----------------------------------
    Latitude and longitude are angular coordinates, not Cartesian.
    Euclidean distance on (lat, lon) tuples distorts at high latitudes
    (e.g. 1° longitude near the poles ≠ 1° longitude at the equator).
    Haversine correctly accounts for Earth's curvature.

    Why DBSCAN and NOT K-Means?
    ----------------------------------
    K-Means requires a pre-specified number of clusters k and assigns
    every point to a cluster, even isolated incidents. DBSCAN:
      • discovers k automatically
      • labels noise/outlier incidents as -1
      • handles arbitrarily shaped hotspots (not just circular)
    """
    R_EARTH = 6371.0
    eps_rad = eps_km_val / R_EARTH

    # 1. Compress to unique coordinates to prevent OOM
    df_coords = pd.DataFrame({'lat': lat_arr, 'lon': lon_arr})
    unique_df = df_coords.groupby(['lat', 'lon']).size().reset_index(name='weight')
    
    unique_coords = np.radians(np.column_stack([unique_df["lat"].values, unique_df["lon"].values]))

    # 2. Run DBSCAN on compressed data
    db = DBSCAN(
        eps=eps_rad,
        min_samples=min_samp,
        algorithm="ball_tree",
        metric="haversine",
        n_jobs=-1
    )
    db.fit(unique_coords, sample_weight=unique_df['weight'].values)
    
    # 3. Map labels back to original dataset
    unique_df['cluster'] = db.labels_
    unique_df.set_index(['lat', 'lon'], inplace=True)
    mapping = unique_df['cluster'].to_dict()
    
    labels = np.array([mapping[(lat, lon)] for lat, lon in zip(lat_arr, lon_arr)])
    return labels

labels = run_dbscan(
    df["latitude"].values,
    df["longitude"].values,
    eps_km,
    min_samples
)

df["cluster"] = labels
n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
n_noise    = (labels == -1).sum()

# -----------------------------------------------
# Cluster Summary
# -----------------------------------------------
kc1, kc2, kc3 = st.columns(3)
kc1.metric("DBSCAN Clusters Found", n_clusters)
kc2.metric("Noise / Isolated Incidents", f"{n_noise:,}")
kc3.metric("Clustered Incidents", f"{(labels != -1).sum():,}")

with st.expander("ℹ️ Why DBSCAN with haversine distance?", expanded=False):
    st.markdown("""
    **Haversine great-circle distance:**
    """)
    st.latex(r"""
        d = 2R \cdot \arcsin\!\left(\sqrt{
            \sin^2\!\!\left(\frac{\Delta\varphi}{2}\right) +
            \cos\varphi_1 \cos\varphi_2 \sin^2\!\!\left(\frac{\Delta\lambda}{2}\right)
        }\right)
    """)
    st.markdown("""
    | Decision | Reason |
    |----------|--------|
    | **DBSCAN** vs K-Means | No need to specify k; finds arbitrary-shaped hotspots; marks isolated incidents as noise |
    | **Haversine** vs Euclidean | Lat/lon are angular — Euclidean distorts near poles; haversine gives real km distance |
    | `algorithm='ball_tree'` | Efficient spatial indexing for large n; required when metric='haversine' |
    """)

st.divider()

# -----------------------------------------------
# Build Cluster Polygon Data for Pydeck PolygonLayer
# -----------------------------------------------
def cluster_polygons(df_in):
    polys = []
    for cid in sorted(df_in[df_in["cluster"] != -1]["cluster"].unique()):
        pts = df_in[df_in["cluster"] == cid][["longitude", "latitude"]].values
        if len(pts) < 3:
            # fallback: small circle approximation
            cx, cy = pts[:, 0].mean(), pts[:, 1].mean()
            angles = np.linspace(0, 2 * np.pi, 12, endpoint=False)
            r = 0.5  # ~0.5 degree ≈ 55 km
            coords = [[cx + r * np.cos(a), cy + r * np.sin(a)] for a in angles]
        else:
            unique_pts = np.unique(pts, axis=0)
            if len(unique_pts) < 3:
                cx, cy = pts[:, 0].mean(), pts[:, 1].mean()
                angles = np.linspace(0, 2 * np.pi, 12, endpoint=False)
                r = 0.5
                coords = [[cx + r * np.cos(a), cy + r * np.sin(a)] for a in angles]
            else:
                try:
                    hull = ConvexHull(unique_pts)
                    coords = unique_pts[hull.vertices].tolist()
                    coords.append(coords[0])  # close polygon
                except Exception:
                    cx, cy = pts[:, 0].mean(), pts[:, 1].mean()
                    angles = np.linspace(0, 2 * np.pi, 12, endpoint=False)
                    r = max(0.3, (pts[:, 0].max() - pts[:, 0].min()) / 2)
                    coords = [[cx + r * np.cos(a), cy + r * np.sin(a)] for a in angles]

        count = len(pts)
        nkill_sum = df_in[df_in["cluster"] == cid]["nkill"].sum()
        polys.append({
            "cluster_id": int(cid),
            "polygon": coords,
            "count": int(count),
            "nkill_sum": int(nkill_sum),
        })
    return polys

polygon_data = cluster_polygons(df)

# -----------------------------------------------
# PyDeck Map
# -----------------------------------------------
layers = []

if view_mode in ["Hexbin Density", "Both"]:
    hex_layer = pdk.Layer(
        'HexagonLayer',
        data=df,
        get_position=['longitude', 'latitude'],
        radius=20000,
        elevation_scale=50,
        elevation_range=[0, 3000],
        pickable=True,
        extruded=True,
        get_weight="nkill",
        color_range=[
            [255, 255, 178],
            [254, 204, 92],
            [253, 141, 60],
            [240, 59, 32],
            [189, 0, 38]
        ]
    )
    layers.append(hex_layer)

if view_mode in ["DBSCAN Clusters", "Both"] and polygon_data:
    poly_layer = pdk.Layer(
        "PolygonLayer",
        data=polygon_data,
        get_polygon="polygon",
        get_fill_color=[0, 229, 255, 40],
        get_line_color=[0, 229, 255, 200],
        get_line_width=5000,
        pickable=True,
        stroked=True,
        filled=True,
    )
    layers.append(poly_layer)

view_state = pdk.ViewState(
    longitude=0, latitude=20, zoom=1.5,
    min_zoom=1, max_zoom=15, pitch=0, bearing=0
)

r = pdk.Deck(
    layers=layers,
    initial_view_state=view_state,
    tooltip=True,
    map_style=MAP_STYLES[selected_style],
)
st.pydeck_chart(r, use_container_width=True)

# -----------------------------------------------
# Cluster Hotspot Table
# -----------------------------------------------
if n_clusters > 0:
    st.divider()
    st.subheader(f"🔥 Top Hotspot Clusters — {n_clusters} clusters detected")

    cluster_df = df[df["cluster"] != -1].groupby("cluster").agg(
        Incidents=("latitude", "count"),
        Fatalities=("nkill", "sum"),
        Lat_Center=("latitude", "mean"),
        Lon_Center=("longitude", "mean"),
    ).reset_index().rename(columns={"cluster": "Cluster ID"})
    cluster_df = cluster_df.sort_values("Incidents", ascending=False).head(15)
    cluster_df["Lat_Center"] = cluster_df["Lat_Center"].round(3)
    cluster_df["Lon_Center"] = cluster_df["Lon_Center"].round(3)
    cluster_df["Fatalities"] = cluster_df["Fatalities"].astype(int)

    st.dataframe(cluster_df.reset_index(drop=True), width="stretch")

st.info("👈 Change filters from the sidebar. Toggle between Hexbin, DBSCAN clusters, or both.")