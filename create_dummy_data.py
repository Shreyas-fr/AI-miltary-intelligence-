import pandas as pd
import numpy as np
import os

os.makedirs('data', exist_ok=True)

data = {
    'iyear': [2020, 2021, 2022, 2023],
    'imonth': [1, 2, 3, 4],
    'iday': [1, 15, 20, 25],
    'latitude': [34.0, 35.0, 36.0, 37.0],
    'longitude': [69.0, 70.0, 71.0, 72.0],
    'country_txt': ['Afghanistan', 'Iraq', 'Pakistan', 'India'],
    'region_txt': ['South Asia', 'Middle East', 'South Asia', 'South Asia'],
    'city': ['Kabul', 'Baghdad', 'Islamabad', 'Delhi'],
    'attacktype1_txt': ['Bombing/Explosion', 'Armed Assault', 'Assassination', 'Facility/Infrastructure Attack'],
    'weaptype1_txt': ['Explosives', 'Firearms', 'Melee', 'Incendiary'],
    'targtype1_txt': ['Military', 'Police', 'Government', 'Private Citizens & Property'],
    'gname': ['Taliban', 'ISIS', 'Unknown', 'Unknown'],
    'success': [1, 0, 1, 1],
    'suicide': [0, 1, 0, 0],
    'nkill': [5, 10, 1, 0],
    'nwound': [10, 5, 0, 2]
}

# Duplicate some rows to make the dataset slightly larger for random forest
df = pd.DataFrame(data)
df = pd.concat([df]*25, ignore_index=True)

df.to_csv('data/globalterrorism.csv', index=False)
print("Dummy data generated in data/globalterrorism.csv")
