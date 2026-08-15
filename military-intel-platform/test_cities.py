import pandas as pd
from utils.data_loader import query_data

def get_cities(country: str) -> pd.DataFrame:
    safe_country = country.replace("'", "''")
    return query_data(f"""
        SELECT city, 
               MEDIAN(latitude) as med_lat, 
               MEDIAN(longitude) as med_lon
        FROM 'data/globalterrorism.csv'
        WHERE country_txt = '{safe_country}'
          AND city IS NOT NULL 
          AND city != 'Unknown'
          AND latitude IS NOT NULL 
          AND longitude IS NOT NULL
        GROUP BY city
        ORDER BY count(*) DESC
        LIMIT 100
    """)

print(get_cities("Iraq").head())
