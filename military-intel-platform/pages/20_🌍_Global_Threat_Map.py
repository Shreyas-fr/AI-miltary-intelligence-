import streamlit as st

# --- Authentication & Role Check ---
from utils.auth import require_auth
require_auth(['Viewer', 'Analyst', 'Commander'])
# -----------------------------------

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import os
import gc
from sklearn.cluster import DBSCAN
from scipy.spatial import ConvexHull
import pydeck as pdk

from utils.ui_components import st_custom_kpi_card
from utils.data_loader import query_data, load_data, load_combined
from utils.hotspot_utils import compute_tsi, cluster_hotspots
from utils.migration import (
    compute_window_centroids,
    compute_migration_vectors,
    predict_future_positions,
)

st.set_page_config(page_title="Global Threat Map & Hotspots", page_icon="🌍", layout="wide")

def load_css(file_name):
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown('<style>' + f.read() + '</style>', unsafe_allow_html=True)
load_css("assets/style.css")

st.title("🌍 | Global Threat Map & Hotspots")
st.markdown("##### 3D hexbin map of global terrorist incidents and spatial hotspot detection.")

# -----------------------------------------------
# Sidebar Filters
# -----------------------------------------------
st.sidebar.header("Common Filters")

years_df = query_data("SELECT DISTINCT iyear FROM 'data/globalterrorism.csv' ORDER BY iyear")
years_list = ["All"] + years_df["iyear"].astype(int).tolist()
selected_year = st.sidebar.selectbox("Year", years_list, help="Filter the map to display incidents from a specific year.")

st.sidebar.markdown("---")
st.sidebar.subheader("Clustering Parameters")
eps_km = st.sidebar.slider("Cluster Radius (km)", min_value=25, max_value=500, value=150, step=25,
    help="Maximum distance between two incidents to be in the same cluster (haversine great-circle km)")
min_samples = st.sidebar.slider("Min Incidents per Cluster", min_value=3, max_value=50, value=8,
    help="Minimum points required to form a dense region")

tab1, tab2 = st.tabs(["3D Density Map", "Hotspot Analysis"])

with tab1:
    st.markdown("### 3D Density Map Options")
    col1, col2, col3 = st.columns(3)
    with col1:
        view_mode = st.radio("View Mode", ["Hexbin Density", "DBSCAN Clusters", "Both"], index=2)
    with col2:
        mobile_fallback = st.toggle("📱 Mobile-Friendly 2D View", value=False)
    with col3:
        MAP_STYLES = {
            "Dark": pdk.map_styles.CARTO_DARK,
            "Light": pdk.map_styles.CARTO_LIGHT,
            "Road": pdk.map_styles.CARTO_ROAD,
        }
        selected_style = st.selectbox("Map theme", list(MAP_STYLES.keys()))

    if selected_year == "All":
        sql = "SELECT latitude, longitude, nkill, country_txt FROM 'data/globalterrorism.csv' WHERE latitude IS NOT NULL AND longitude IS NOT NULL"
    else:
        sql = "SELECT latitude, longitude, nkill, country_txt FROM 'data/globalterrorism.csv' WHERE iyear = " + str(selected_year) + " AND latitude IS NOT NULL AND longitude IS NOT NULL"
    
    with st.spinner("Loading geospatial data..."):
        df = query_data(sql)
        df["nkill"] = df["nkill"].fillna(0)
    
    st.markdown("**Showing " + str(len(df)) + " incidents** | Year: `" + str(selected_year) + "`")
    
    if len(df) == 0:
        st.warning("No data available for the selected filters.")
    else:
        @st.cache_data(show_spinner="Running DBSCAN clustering...")
        def run_dbscan(lat_arr, lon_arr, eps_km_val, min_samp):
            R_EARTH = 6371.0
            eps_rad = eps_km_val / R_EARTH
            
            df_coords = pd.DataFrame({'lat': lat_arr, 'lon': lon_arr})
            unique_df = df_coords.groupby(['lat', 'lon']).size().reset_index(name='weight')
            
            unique_coords = np.radians(np.column_stack([unique_df["lat"].values, unique_df["lon"].values]))
            
            db = DBSCAN(eps=eps_rad, min_samples=min_samp, algorithm="ball_tree", metric="haversine", n_jobs=-1)
            db.fit(unique_coords, sample_weight=unique_df['weight'].values)
            
            unique_df['cluster'] = db.labels_
            unique_df.set_index(['lat', 'lon'], inplace=True)
            mapping = unique_df['cluster'].to_dict()
            
            labels = np.array([mapping[(lat, lon)] for lat, lon in zip(lat_arr, lon_arr)])
            return labels
        
        labels = run_dbscan(df["latitude"].values, df["longitude"].values, eps_km, min_samples)
        df["cluster"] = labels
        gc.collect()
        
        n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
        n_noise    = (labels == -1).sum()
        
        kc1, kc2, kc3 = st.columns(3)
        with kc1: st_custom_kpi_card("DBSCAN Clusters Found", str(n_clusters), "", "🧩")
        with kc2: st_custom_kpi_card("Noise / Isolated Incidents", str(n_noise), "", "📉")
        with kc3: st_custom_kpi_card("Clustered Incidents", str((labels != -1).sum()), "", "🔗")
        
        with st.expander("ℹ️ Why DBSCAN with haversine distance?", expanded=False):
            st.markdown("**Haversine great-circle distance:**")
            st.latex(r'''
                d = 2R \cdot \arcsin\!\left(\sqrt{
                    \sin^2\!\!\left(\frac{\Delta\varphi}{2}\right) +
                    \cos\varphi_1 \cos\varphi_2 \sin^2\!\!\left(\frac{\Delta\lambda}{2}\right)
                }\right)
            ''')
            st.markdown("| Decision | Reason |\n|----------|--------|\n| **DBSCAN** vs K-Means | No need to specify k; finds arbitrary-shaped hotspots; marks isolated incidents as noise |\n| **Haversine** vs Euclidean | Lat/lon are angular — Euclidean distorts near poles; haversine gives real km distance |\n| `algorithm='ball_tree'` | Efficient spatial indexing for large n; required when metric='haversine' |")
        
        st.divider()
        
        def cluster_polygons(df_in):
            polys = []
            for cid in sorted(df_in[df_in["cluster"] != -1]["cluster"].unique()):
                pts = df_in[df_in["cluster"] == cid][["longitude", "latitude"]].values
                if len(pts) < 3:
                    cx, cy = pts[:, 0].mean(), pts[:, 1].mean()
                    angles = np.linspace(0, 2 * np.pi, 12, endpoint=False)
                    r = 0.5
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
                            coords.append(coords[0])
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
        
        if mobile_fallback:
            st.info("📱 Mobile view enabled: Rendering 2D map with a maximum of 10,000 incidents to preserve mobile GPU memory.")
            df_mobile = df.sample(n=min(10000, len(df)), random_state=42)
            fallback_style = "carto-darkmatter" if "dark" in selected_style.lower() else "carto-positron"
            
            fig = px.scatter_mapbox(
                df_mobile, lat="latitude", lon="longitude", color="nkill", size="nkill",
                color_continuous_scale="Reds", size_max=15, zoom=1, mapbox_style=fallback_style,
                hover_data={"latitude": False, "longitude": False, "nkill": True}
            )
            fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)
        else:
            layers = []
            if view_mode in ["Hexbin Density", "Both"]:
                hex_layer = pdk.Layer(
                    'HexagonLayer', data=df, get_position=['longitude', 'latitude'], radius=20000,
                    elevation_scale=50, elevation_range=[0, 3000], pickable=True, extruded=True,
                    get_weight="nkill", color_range=[[255, 255, 178], [254, 204, 92], [253, 141, 60], [240, 59, 32], [189, 0, 38]],
                )
                layers.append(hex_layer)
            if view_mode in ["DBSCAN Clusters", "Both"] and polygon_data:
                poly_layer = pdk.Layer(
                    "PolygonLayer", data=polygon_data, get_polygon="polygon",
                    get_fill_color=[0, 255, 255, 140], get_line_color=[0, 255, 255, 255],
                    line_width_min_pixels=2, pickable=True, extruded=False,
                )
                layers.append(poly_layer)
            
            view_state = pdk.ViewState(longitude=0, latitude=20, zoom=1.2, min_zoom=1, max_zoom=15, pitch=45, bearing=0)
            r = pdk.Deck(
                layers=layers, initial_view_state=view_state, map_style=MAP_STYLES[selected_style],
                tooltip={"html": "<b>Incidents / Weight:</b> {nkill}<br/><b>Cluster ID:</b> {cluster_id}<br/><b>Total Deaths in Cluster:</b> {nkill_sum}", "style": {"backgroundColor": "steelblue", "color": "white"}}
            )
            with st.spinner("Rendering 3D map..."):
                st.pydeck_chart(r, use_container_width=True)
        
        if n_clusters > 0:
            st.divider()
            st.subheader("🔥 Top Hotspot Clusters — " + str(n_clusters) + " clusters detected")
            cluster_df = df[df["cluster"] != -1].groupby("cluster").agg(
                Incidents=("latitude", "count"), Fatalities=("nkill", "sum"),
                Lat_Center=("latitude", "mean"), Lon_Center=("longitude", "mean"),
            ).reset_index().rename(columns={"cluster": "Cluster ID"})
            cluster_df = cluster_df.sort_values("Incidents", ascending=False).head(15)
            cluster_df["Lat_Center"] = cluster_df["Lat_Center"].round(3)
            cluster_df["Lon_Center"] = cluster_df["Lon_Center"].round(3)
            cluster_df["Fatalities"] = cluster_df["Fatalities"].astype(int)
            st.dataframe(cluster_df, use_container_width=True, hide_index=True)


with tab2:
    st.markdown("### Hotspot Analysis Options")
    col1, col2, col3 = st.columns(3)
    with col1:
        use_combined = st.checkbox("Include Live Intelligence Events", value=False)
    with col2:
        show_migration = st.checkbox("Show Hotspot Migration Vectors", value=False)
    with col3:
        window_years = st.slider("Migration Window (Years)", 3, 10, 5, step=1)
    
    if use_combined:
        with st.spinner("Loading GTD + Live Intelligence data..."):
            df2 = load_combined()
            df2 = df2.dropna(subset=["latitude", "longitude"]).copy()
    else:
        df2 = query_data("SELECT latitude, longitude, nkill, nwound, success, iyear, country_txt, region_txt FROM 'data/globalterrorism.csv' WHERE latitude IS NOT NULL AND longitude IS NOT NULL")
    
    df2 = compute_tsi(df2)
    with st.spinner("Running DBSCAN over incident geometry..."):
        df_clustered, hotspots = cluster_hotspots(df2, eps_km=eps_km, min_samples=min_samples)
    
    st.session_state["hotspot_df"] = df_clustered
    st.session_state["hotspot_summary"] = hotspots
    gc.collect()
    
    c1, c2, c3 = st.columns(3)
    with c1: st_custom_kpi_card("Hotspots Detected", str(len(hotspots)), "Identified via DBSCAN", "🎯")
    with c2: st_custom_kpi_card("Incidents in Hotspots", str(len(df_clustered[df_clustered['cluster'] != -1])), "Clustered events", "🔗")
    with c3: st_custom_kpi_card("Noise (isolated incidents)", str((df_clustered['cluster'] == -1).sum()), "Too isolated for hotspot", "📉")
    
    st.divider()
    plot_df = df_clustered[df_clustered["cluster"] != -1]
    
    if plot_df.empty:
        st.warning("No hotspots found with these parameters — try a larger radius or lower minimum incidents.")
    else:
        layers2 = []
        hex_layer2 = pdk.Layer(
            "HexagonLayer", data=plot_df, get_position=["longitude", "latitude"],
            radius=int(eps_km * 300), elevation_scale=40, elevation_range=[0, 3000],
            pickable=True, extruded=True, get_weight="tsi",
            color_range=[[255, 255, 178], [254, 204, 92], [253, 141, 60], [240, 59, 32], [189, 0, 38]],
        )
        layers2.append(hex_layer2)
        
        migration_data = []
        if show_migration:
            centroids_df = compute_window_centroids(df2, window_years=window_years, eps_km=eps_km, min_samples=min_samples)
            m_vectors = compute_migration_vectors(centroids_df)
            p_vectors = predict_future_positions(m_vectors)
            
            all_vectors = m_vectors + p_vectors
            if all_vectors:
                arc_layer = pdk.Layer(
                    "ArcLayer", data=all_vectors, get_source_position=["from_lon", "from_lat"],
                    get_target_position=["to_lon", "to_lat"], get_source_color=[0, 229, 255, 200],
                    get_target_color=[255, 45, 85, 255], get_width=4, pickable=True,
                )
                layers2.append(arc_layer)
                migration_data = all_vectors
        
        view_state2 = pdk.ViewState(longitude=0, latitude=20, zoom=1.5, pitch=0, bearing=0)
        r2 = pdk.Deck(layers=layers2, initial_view_state=view_state2, tooltip={"html": "<b>Hotspot Data / Migration Vector</b>"})
        with st.spinner("Rendering predictive map..."):
            st.pydeck_chart(r2, use_container_width=True)
            
        if show_migration and migration_data:
            st.subheader("🔮 Predictive Hotspot Migration Vectors")
            mig_df = pd.DataFrame(migration_data)
            st.dataframe(
                mig_df[["window_from", "window_to", "from_lat", "from_lon", "to_lat", "to_lon", "drift_km"]].rename(columns={
                    "window_from": "From Period", "window_to": "To Period",
                    "from_lat": "Origin Lat", "from_lon": "Origin Lon",
                    "to_lat": "Target Lat", "to_lon": "Target Lon",
                    "drift_km": "Drift Distance (km)"
                }),
                use_container_width=True, hide_index=True
            )
            
    st.divider()
    st.subheader("Top Threat Hotspots (ranked by total TSI)")
    if hotspots.empty:
        st.info("No hotspots to display yet — adjust the clustering parameters in the sidebar.")
    else:
        display_cols = ["rank", "countries", "incidents", "total_tsi", "avg_tsi", "centroid_lat", "centroid_lon"]
        st.dataframe(
            hotspots[display_cols].head(20).rename(
                columns={"rank": "Rank", "countries": "Dominant Country", "incidents": "Incidents", "total_tsi": "Total TSI", "avg_tsi": "Avg TSI", "centroid_lat": "Lat", "centroid_lon": "Lon"}
            ),
            use_container_width=True, hide_index=True
        )
    st.info("👉 Go to **Hotspot Forecasting** to project attack trends for any hotspot above.")