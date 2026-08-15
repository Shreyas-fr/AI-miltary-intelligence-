import pandas as pd
import streamlit as st
import numpy as np

df = pd.DataFrame(np.random.randn(100000, 5), columns=['a', 'b', 'c', 'd', 'e'])
st.dataframe(df)
