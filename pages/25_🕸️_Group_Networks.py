import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import os
import networkx as nx

from utils.data_loader import query_data
from utils.network_utils import build_group_profiles, compute_similarity_network, generate_network_layout

st.set_page_config(page_title="Group Networks", page_icon="🕸️", layout="wide")

def load_css(file_name):
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
load_css("assets/style.css")

st.title("🕸️ Perpetrator Group Networks")
st.markdown("##### Tactical and Geographic Similarity Graph")
st.info("This module maps relationships between terrorist organizations based on overlapping operational profiles. Two groups are connected if they share highly similar tactical preferences (weapons, targets) and geographic operating areas, indicating potential emulation, competition, or shared resources.")

# -----------------------------------------------
# Sidebar Filters
# -----------------------------------------------
st.sidebar.header("Network Filters")

min_incidents = st.sidebar.slider(
    "Minimum Historical Incidents",
    min_value=20, max_value=500, value=100, step=10,
    help="Filter out minor groups to keep the graph readable."
)

similarity_threshold = st.sidebar.slider(
    "Similarity Threshold",
    min_value=0.5, max_value=0.99, value=0.85, step=0.01,
    help="Higher values require groups to be more identical before an edge is drawn."
)

st.sidebar.markdown("---")
region_df = query_data("SELECT DISTINCT region_txt FROM 'data/globalterrorism.csv' WHERE region_txt IS NOT NULL ORDER BY region_txt")
regions = ["Global"] + region_df["region_txt"].tolist()
selected_region = st.sidebar.selectbox("Constrain to Region", regions)

# -----------------------------------------------
# Data Loading
# -----------------------------------------------
@st.cache_data(show_spinner="Loading operational data...")
def load_network_data(region):
    if region == "Global":
        sql = "SELECT gname, region_txt, attacktype1_txt, weaptype1_txt, targtype1_txt FROM 'data/globalterrorism.csv'"
    else:
        sql = f"SELECT gname, region_txt, attacktype1_txt, weaptype1_txt, targtype1_txt FROM 'data/globalterrorism.csv' WHERE region_txt = '{region}'"
    return query_data(sql)

df = load_network_data(selected_region)

if len(df) == 0:
    st.warning("No data found for the selected region.")
    st.stop()

# -----------------------------------------------
# Network Computation
# -----------------------------------------------
profiles = build_group_profiles(df, min_incidents=min_incidents)

if profiles.empty:
    st.warning(f"No groups found in this region with at least {min_incidents} incidents.")
    st.stop()

G = compute_similarity_network(profiles, threshold=similarity_threshold)

if len(G.nodes) == 0:
    st.warning("No groups met the similarity threshold. Try lowering the threshold or minimum incidents.")
    st.stop()

pos = generate_network_layout(G)

# -----------------------------------------------
# Plotly Visualization
# -----------------------------------------------
# Extract edges
edge_x = []
edge_y = []
edge_weights = []

for edge in G.edges(data=True):
    x0, y0 = pos[edge[0]]
    x1, y1 = pos[edge[1]]
    edge_x.extend([x0, x1, None])
    edge_y.extend([y0, y1, None])
    # For hover or dynamic width, though Plotly standard scatter lines don't support per-segment width easily
    
edge_trace = go.Scatter(
    x=edge_x, y=edge_y,
    line=dict(width=1.5, color='#444'),
    hoverinfo='none',
    mode='lines'
)

# Extract nodes
node_x = []
node_y = []
node_text = []
node_size = []
node_color = []

for node in G.nodes():
    x, y = pos[node]
    node_x.append(x)
    node_y.append(y)
    
    # Sizing by incident count (log scale for visual balance)
    incidents = G.nodes[node]['incidents']
    size = max(10, np.log1p(incidents) * 5)
    node_size.append(size)
    
    # Degree centrality for color
    deg = G.degree(node)
    node_color.append(deg)
    
    # Build a rich hover text using the profile dataframe
    if node in profiles.index:
        prof = profiles.loc[node]
        # Find top weapon and target (excluding incident count)
        features = prof.drop("_incident_count").sort_values(ascending=False)
        top_f = [f.replace('weap_', 'W:').replace('attack_', 'A:').replace('targ_', 'T:').replace('region_', 'R:') 
                 for f in features.head(3).index]
                 
        hover_str = f"<b>{node}</b><br>Incidents: {incidents:,}<br>Connections: {deg}<br><br>Top Tactics:<br>- {top_f[0]}<br>- {top_f[1]}<br>- {top_f[2]}"
    else:
        hover_str = f"<b>{node}</b><br>Connections: {deg}"
        
    node_text.append(hover_str)

node_trace = go.Scatter(
    x=node_x, y=node_y,
    mode='markers',
    hoverinfo='text',
    text=node_text,
    marker=dict(
        showscale=True,
        colorscale='YlOrRd',
        reversescale=False,
        color=node_color,
        size=node_size,
        colorbar=dict(
            thickness=15,
            title=dict(text='Network Connections', side='right'),
            xanchor='left'
        ),
        line_width=2,
        line_color='black'
    )
)

fig = go.Figure(data=[edge_trace, node_trace],
             layout=go.Layout(
                title=dict(text='<br>Tactical Similarity Network', font=dict(size=16)),
                showlegend=False,
                hovermode='closest',
                margin=dict(b=20,l=5,r=5,t=40),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                yaxis=dict(showgrid=False, zeroline=False, showticklabels=False))
                )

st.plotly_chart(fig, use_container_width=True)

# -----------------------------------------------
# Network Summary Stats
# -----------------------------------------------
st.divider()
c1, c2, c3 = st.columns(3)
c1.metric("Groups Displayed", len(G.nodes))
c2.metric("Connections", len(G.edges))

# Most connected group
degrees = dict(G.degree())
if degrees:
    top_group = max(degrees, key=degrees.get)
    top_degree = degrees[top_group]
    c3.metric("Most Influential Node", top_group, f"{top_degree} connections")
