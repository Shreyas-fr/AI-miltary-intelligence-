import streamlit as st
import pandas as pd
import time
from utils.data_loader import query_data

st.write("Starting stress test...")
start = time.time()

for i in range(2): # Twice each
    st.write(f"Iteration {i+1}")
    
    # 1. Country Analysis
    df1 = query_data("SELECT * FROM 'data/globalterrorism.csv' WHERE country_txt = 'Iraq'")
    st.dataframe(df1)
    
    # 2. Data Explorer
    df2 = query_data("SELECT * FROM 'data/globalterrorism.csv' LIMIT 1000")
    st.dataframe(df2)
    
    # 3. Global Threat Map (Heavy geospatial query)
    df3 = query_data("SELECT latitude, longitude, nkill, country_txt FROM 'data/globalterrorism.csv' WHERE latitude IS NOT NULL")
    st.dataframe(df3)
    
    # 4. Hotspot Detection
    df4 = query_data("SELECT latitude, longitude, nkill, nwound, success, iyear, country_txt, region_txt FROM 'data/globalterrorism.csv'")
    st.dataframe(df4)
    
st.write(f"Stress test completed in {time.time() - start:.2f} seconds.")
