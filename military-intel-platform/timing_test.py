import time
from utils.data_loader import query_data

def time_query(name, sql):
    start = time.time()
    df = query_data(sql)
    duration = (time.time() - start) * 1000
    print(f"{name}: {len(df)} rows | Time: {duration:.2f} ms")

print("--- Query Timing Test ---")
time_query("Data Explorer Main Load", "SELECT * FROM 'data/globalterrorism.csv' LIMIT 500")
time_query("Threat Map Coordinates", "SELECT latitude, longitude, nkill, country_txt FROM 'data/globalterrorism.csv' WHERE latitude IS NOT NULL AND longitude IS NOT NULL AND iyear = 2015")
time_query("Country Analysis Aggregation", "SELECT iyear AS year, COUNT(*) AS attacks, SUM(nkill) AS fatalities, SUM(nwound) AS injuries FROM 'data/globalterrorism.csv' WHERE country_txt = 'Iraq' GROUP BY iyear ORDER BY iyear")

