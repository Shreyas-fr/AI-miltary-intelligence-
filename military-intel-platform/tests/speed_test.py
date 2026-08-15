import time
import os
import psutil
from streamlit.testing.v1 import AppTest
import logging

logging.getLogger("streamlit").setLevel(logging.ERROR)

def time_page(name, path):
    print(f"\n--- Testing {name} ---")
    at = AppTest.from_file(path, default_timeout=60)
    at.session_state["authentication_status"] = True
    at.session_state["user_role"] = "Commander"
    
    start = time.time()
    at.run()
    duration = time.time() - start
    print(f"{name} initial load time: {duration:.2f} seconds")
    
    # Run it again to simulate an interaction (e.g. changing a slider)
    start = time.time()
    at.run()
    duration2 = time.time() - start
    print(f"{name} rerun time: {duration2:.2f} seconds")
    return duration, duration2

time_page("Global Threat Map", "pages/20_🌍_Global_Threat_Map.py")
time_page("Intelligence Database", "pages/50_🗄️_Intelligence_Database.py")
time_page("Forecasting", "pages/31_📈_Forecasting.py")
