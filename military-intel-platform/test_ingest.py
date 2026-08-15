import pandas as pd
from database.intelligence_db import init_db, ingest_live_events, get_live_count

# Initialize DB
init_db()

# Create dummy overlapping events
data1 = {
    'source_id': ['G1', 'G2'],
    'source': ['GDELT', 'GDELT'],
    'url': ['http://g1.com', 'http://g2.com'],
    'title': ['Event 1', 'Event 2'],
    'language': ['eng', 'eng'],
    'date': ['2026-07-26', '2026-07-26'],
    'country': ['Iraq', 'Syria'],
    'location': ['Baghdad', 'Damascus'],
    'latitude': [33.3, 33.5],
    'longitude': [44.4, 36.3],
    'event': ['Bombing', 'Armed Assault'],
    'severity': ['High', 'Critical']
}

data2 = {
    'source_id': ['G2', 'G3'], # G2 overlaps
    'source': ['GDELT', 'GDELT'],
    'url': ['http://g2.com', 'http://g3.com'],
    'title': ['Event 2', 'Event 3'],
    'language': ['eng', 'eng'],
    'date': ['2026-07-26', '2026-07-26'],
    'country': ['Syria', 'Yemen'],
    'location': ['Damascus', 'Sanaa'],
    'latitude': [33.5, 15.3],
    'longitude': [36.3, 44.2],
    'event': ['Armed Assault', 'Drone Strike'],
    'severity': ['Critical', 'High']
}

df1 = pd.DataFrame(data1)
df2 = pd.DataFrame(data2)

print(f"Row count before ingest 1: {get_live_count()}")
ingest_live_events(df1)
print(f"Row count after ingest 1 (added G1, G2): {get_live_count()}")
ingest_live_events(df2)
print(f"Row count after ingest 2 (added G2, G3 - G2 is duplicate): {get_live_count()}")
