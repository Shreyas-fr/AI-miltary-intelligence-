import os
import psutil
import time
import gc
from utils.data_loader import query_data

def print_mem(step_name):
    process = psutil.Process(os.getpid())
    mem_mb = process.memory_info().rss / 1024 / 1024
    print(f"[{step_name:<20}] Memory Usage: {mem_mb:.2f} MB")
    return mem_mb

print_mem("Startup")

for i in range(1, 21):
    # Simulate slightly different queries so that if caching was still active, it would leak memory for each unique query
    sql1 = f"SELECT * FROM 'data/globalterrorism.csv' LIMIT {1000 + i}"
    sql2 = f"SELECT latitude, longitude, nkill, country_txt FROM 'data/globalterrorism.csv' WHERE latitude IS NOT NULL AND iyear = {2000 + (i%17)}"
    
    df1 = query_data(sql1)
    df2 = query_data(sql2)
    
    if i == 1:
        print_mem("After 1 Pass")
    elif i % 5 == 0:
        print_mem(f"After {i} Passes")

gc.collect()
print_mem("End of test")
