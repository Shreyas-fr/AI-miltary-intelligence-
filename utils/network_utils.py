"""
Utilities for computing and laying out perpetrator group similarity networks.
"""

import pandas as pd
import numpy as np
import networkx as nx
from sklearn.metrics.pairwise import cosine_similarity
import streamlit as st

@st.cache_data(max_entries=10, show_spinner=False)
def build_group_profiles(df: pd.DataFrame, min_incidents: int = 50) -> pd.DataFrame:
    """
    Builds a tactical/geographic feature vector for each group based on percentage 
    breakdowns of their historical attacks.
    """
    # Filter out Unknown and small groups
    df = df[df["gname"].notna() & (df["gname"] != "Unknown")].copy()
    
    group_counts = df["gname"].value_counts()
    valid_groups = group_counts[group_counts >= min_incidents].index
    
    df = df[df["gname"].isin(valid_groups)]
    
    if df.empty:
        return pd.DataFrame()

    features = []
    
    # We want to dummify categorical columns to create a tactical footprint
    cat_cols = ["region_txt", "attacktype1_txt", "weaptype1_txt", "targtype1_txt"]
    for col in cat_cols:
        if col in df.columns:
            dummies = pd.get_dummies(df[col], prefix=col.split("_")[0])
            dummies["gname"] = df["gname"]
            
            # Average the dummies per group (yields the % of attacks that used this category)
            grouped = dummies.groupby("gname").mean()
            features.append(grouped)
            
    # Combine all feature sets
    profiles = pd.concat(features, axis=1).fillna(0)
    
    # Add incident counts for node sizing
    profiles["_incident_count"] = group_counts[profiles.index]
    
    return profiles


@st.cache_data(max_entries=10, show_spinner=False)
def compute_similarity_network(profiles: pd.DataFrame, threshold: float = 0.8) -> nx.Graph:
    """
    Computes pairwise cosine similarity between group profiles and returns an undirected
    NetworkX graph where edges represent similarity > threshold.
    """
    if profiles.empty or len(profiles) < 2:
        return nx.Graph()
        
    # Extract just the feature columns (drop incident count)
    feature_cols = [c for c in profiles.columns if c != "_incident_count"]
    X = profiles[feature_cols].values
    
    # Compute similarity matrix
    sim_matrix = cosine_similarity(X)
    
    G = nx.Graph()
    
    # Add nodes
    group_names = profiles.index.tolist()
    for i, gname in enumerate(group_names):
        G.add_node(gname, incidents=int(profiles.iloc[i]["_incident_count"]))
        
    # Add edges based on threshold
    for i in range(len(group_names)):
        for j in range(i + 1, len(group_names)):
            sim = sim_matrix[i, j]
            if sim >= threshold:
                G.add_edge(group_names[i], group_names[j], weight=float(sim))
                
    # Remove isolated nodes to keep the graph clean
    isolated = list(nx.isolates(G))
    G.remove_nodes_from(isolated)
    
    return G

@st.cache_data(max_entries=10, show_spinner=False)
def generate_network_layout(_G: nx.Graph):
    """
    Generates a 2D spring layout for the graph to be plotted in Plotly.
    """
    if len(_G.nodes) == 0:
        return {}
        
    # Using spring layout (Fruchterman-Reingold force-directed algorithm)
    # k controls distance between nodes; higher means more spread out
    pos = nx.spring_layout(_G, k=0.5, iterations=50, seed=42)
    return pos
