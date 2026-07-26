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
print_mem("Startup - Before Run")
at.run()
print_mem("Startup - After Initial Run")

def simulate_navigation():
    # Simulate loading Global Threat Map
    at_map = AppTest.from_file("pages/2_🌍_Global_Threat_Map.py", default_timeout=30)
    at_map.run()
    
    # Simulate loading Attack Prediction
    at_pred = AppTest.from_file("pages/5_🤖_Attack_Prediction.py", default_timeout=30)
    at_pred.run()

    # Simulate loading Data Explorer
    at_explore = AppTest.from_file("pages/9_📊_Data_Explorer.py", default_timeout=30)
    at_explore.run()

simulate_navigation()
print_mem("After 1st Pass (3 Heavy Pages)")

for i in range(15):
    simulate_navigation()

print_mem("After 15 Passes (Stress Test)")
gc.collect()
print_mem("After Garbage Collection")

