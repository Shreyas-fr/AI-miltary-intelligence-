import os
import psutil
import time
from streamlit.testing.v1 import AppTest
import gc

def print_mem(step_name):
    process = psutil.Process(os.getpid())
    mem_mb = process.memory_info().rss / 1024 / 1024
    print(f"[{step_name}] Memory Usage: {mem_mb:.2f} MB")
    return mem_mb

# Initialize AppTest
at = AppTest.from_file("app.py", default_timeout=30)
at.session_state["authentication_status"] = True
at.session_state["user_role"] = "Commander"
print_mem("Startup - Before Run")
at.run()
print_mem("Startup - After Initial Run")

def simulate_navigation():
    # Simulate loading Global Threat Map
    at_map = AppTest.from_file("pages/20_🌍_Global_Threat_Map.py", default_timeout=30)
    at_map.session_state["authentication_status"] = True
    at_map.session_state["user_role"] = "Commander"
    at_map.run()
    
    # Simulate loading Mission Planning (formerly Attack Prediction)
    at_pred = AppTest.from_file("pages/42_🎖️_Mission_Planning.py", default_timeout=30)
    at_pred.session_state["authentication_status"] = True
    at_pred.session_state["user_role"] = "Commander"
    at_pred.run()

    # Simulate loading Intelligence Database (formerly Data Explorer)
    at_explore = AppTest.from_file("pages/50_🗄️_Intelligence_Database.py", default_timeout=30)
    at_explore.session_state["authentication_status"] = True
    at_explore.session_state["user_role"] = "Commander"
    at_explore.run()

simulate_navigation()
print_mem("After 1st Pass (3 Heavy Pages)")

for i in range(15):
    simulate_navigation()

print_mem("After 15 Passes (Stress Test)")
gc.collect()
print_mem("After Garbage Collection")

