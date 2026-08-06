import os
import re

updates = {
    "20_🌍_Global_Threat_Map.py": [
        (r'st\.sidebar\.selectbox\("Year", years_list\)', r'st.sidebar.selectbox("Year", years_list, help="Filter the map to display incidents from a specific year.")'),
        (r'st\.sidebar\.selectbox\("Map theme", list\(MAP_STYLES\.keys\(\)\)\)', r'st.sidebar.selectbox("Map theme", list(MAP_STYLES.keys()), help="Choose the visual style for the base map.")'),
        (r'eps_km = st\.sidebar\.slider\("Cluster Radius \(km\)", min_value=50, max_value=500, value=150, step=50,\n\s*\)', r'eps_km = st.sidebar.slider("Cluster Radius (km)", min_value=50, max_value=500, value=150, step=50, help="Maximum distance between points to form a spatial cluster.")'),
        (r'min_samples = st\.sidebar\.slider\("Min Incidents per Cluster", min_value=3, max_value=30, value=8,\n\s*\)', r'min_samples = st.sidebar.slider("Min Incidents per Cluster", min_value=3, max_value=30, value=8, help="Minimum number of incidents required to form a spatial cluster hotspot.")')
    ],
    "21_🎯_Hotspot_Detection.py": [
        (r'eps_km = st\.sidebar\.slider\(\n\s*"Cluster radius \(km\)", 25, 500, 100, step=25,\n\s*\)', r'eps_km = st.sidebar.slider("Cluster radius (km)", 25, 500, 100, step=25, help="Radius around each point to search for neighboring incidents.")'),
        (r'min_samples = st\.sidebar\.slider\("Minimum incidents per hotspot", 5, 50, 15, step=5\)', r'min_samples = st.sidebar.slider("Minimum incidents per hotspot", 5, 50, 15, step=5, help="Minimum incidents needed to define a hotspot.")'),
        (r'window_years = st\.sidebar\.slider\("Migration Window \(Years\)", 3, 10, 5, step=1\)', r'window_years = st.sidebar.slider("Migration Window (Years)", 3, 10, 5, step=1, help="Time window to calculate hotspot centroid migrations.")')
    ],
    "22_🌎_Country_Analysis.py": [
        (r'country = st\.sidebar\.selectbox\("Select Country", countries\)', r'country = st.sidebar.selectbox("Select Country", countries, help="Select a nation to analyze historical and predictive threat data.")')
    ],
    "23_🧠_Threat_Level_&_AI_Intelligence.py": [
        (r'selected_country = st\.sidebar\.selectbox\("Select Sovereign Nation", country_list\)', r'selected_country = st.sidebar.selectbox("Select Sovereign Nation", country_list, help="Choose the country to analyze.")'),
        (r'region   = st\.sidebar\.selectbox\("Region",      get_original_labels\("region_txt"\)\)', r'region   = st.sidebar.selectbox("Region", get_original_labels("region_txt"), help="Filter the incident history by region.")'),
        (r'attack   = st\.sidebar\.selectbox\("Attack Type", get_original_labels\("attacktype1_txt"\)\)', r'attack   = st.sidebar.selectbox("Attack Type", get_original_labels("attacktype1_txt"), help="Specify the type of attack to simulate.")'),
        (r'weapon   = st\.sidebar\.selectbox\("Weapon Type", get_original_labels\("weaptype1_txt"\)\)', r'weapon   = st.sidebar.selectbox("Weapon Type", get_original_labels("weaptype1_txt"), help="Specify the weapon used in the simulated attack.")'),
        (r'target_t = st\.sidebar\.selectbox\("Target Type", get_original_labels\("targtype1_txt"\)\)', r'target_t = st.sidebar.selectbox("Target Type", get_original_labels("targtype1_txt"), help="Identify the target of the simulated attack.")'),
        (r'nkill    = st\.sidebar\.number_input\("Estimated Killed",   min_value=0, max_value=5000, value=2\)', r'nkill    = st.sidebar.number_input("Estimated Killed", min_value=0, max_value=5000, value=2, help="Number of fatalities.")'),
        (r'nwound   = st\.sidebar\.number_input\("Estimated Wounded",  min_value=0, max_value=5000, value=5\)', r'nwound   = st.sidebar.number_input("Estimated Wounded", min_value=0, max_value=5000, value=5, help="Number of non-fatal injuries.")'),
        (r'success  = st\.sidebar\.selectbox\("Attack Successful\?", \["Yes", "No"\]\)', r'success  = st.sidebar.selectbox("Attack Successful?", ["Yes", "No"], help="Whether the attack achieved its goal.")'),
        (r'claimed  = st\.sidebar\.selectbox\("Responsibility Claimed\?", \["Yes", "No"\]\)', r'claimed  = st.sidebar.selectbox("Responsibility Claimed?", ["Yes", "No"], help="Whether a group claimed responsibility.")'),
        (r'lookback = st\.sidebar\.selectbox\("Live intelligence window", \["15m", "1h", "6h", "1d", "3d", "7d"\], index=3\)', r'lookback = st.sidebar.selectbox("Live intelligence window", ["15m", "1h", "6h", "1d", "3d", "7d"], index=3, help="Timeframe to fetch recent events from the live intelligence database.")'),
        (r'max_records = st\.sidebar\.slider\("Live records", 25, 250, 100, step=25\)', r'max_records = st.sidebar.slider("Live records", 25, 250, 100, step=25, help="Maximum number of live intelligence records to retrieve.")')
    ],
    "24_📅_Threat_Timeline.py": [
        (r'year_range = st\.sidebar\.slider\(\n\s*"Select Year Range",\n\s*min_value=min_year,\n\s*max_value=max_year,\n\s*value=\(min_year, max_year\),\n\s*step=1\n\s*\)', r'year_range = st.sidebar.slider("Select Year Range", min_value=min_year, max_value=max_year, value=(min_year, max_year), step=1, help="Filter the timeline analysis to a specific period.")')
    ],
    "25_🕸️_Group_Networks.py": [
        (r'min_incidents = st\.sidebar\.slider\(\n\s*"Minimum incidents per group",\n\s*10, 500, 50\n\s*\)', r'min_incidents = st.sidebar.slider("Minimum incidents per group", 10, 500, 50, help="Filter out smaller groups to focus on major actors.")'),
        (r'similarity_threshold = st\.sidebar\.slider\(\n\s*"Network edge threshold",\n\s*0\.0, 1\.0, 0\.4, 0\.05\n\s*\)', r'similarity_threshold = st.sidebar.slider("Network edge threshold", 0.0, 1.0, 0.4, 0.05, help="Higher values create stricter connections between groups.")'),
        (r'selected_region = st\.sidebar\.selectbox\("Constrain to Region", regions\)', r'selected_region = st.sidebar.selectbox("Constrain to Region", regions, help="Analyze group networks operating in a specific area.")')
    ],
    "31_📈_Forecasting.py": [
        (r'selected_label = st\.sidebar\.selectbox\("Select Hotspot", list\(hotspot_options\.keys\(\)\)\)', r'selected_label = st.sidebar.selectbox("Select Hotspot", list(hotspot_options.keys()), help="Choose a hotspot cluster to forecast.")'),
        (r'test_years = st\.sidebar\.slider\("Validation window \(years held out\)", 1, 5, 3\)', r'test_years = st.sidebar.slider("Validation window (years held out)", 1, 5, 3, help="Years of data to hold out for model backtesting.")'),
        (r'forecast_years = st\.sidebar\.slider\("Forecast horizon \(years\)", 1, 10, 5\)', r'forecast_years = st.sidebar.slider("Forecast horizon (years)", 1, 10, 5, help="Number of years into the future to project.")')
    ],
    "40_🛰️_Live_Intelligence_Feed.py": [
        (r'timespan = st\.sidebar\.selectbox\("Lookback window", \["15m", "1h", "6h", "1d", "3d", "7d"\], index=3\)', r'timespan = st.sidebar.selectbox("Lookback window", ["15m", "1h", "6h", "1d", "3d", "7d"], index=3, help="Timeframe to fetch incoming intelligence data.")'),
        (r'max_records = st\.sidebar\.slider\("Maximum records", 25, 250, 100, step=25\)', r'max_records = st.sidebar.slider("Maximum records", 25, 250, 100, step=25, help="Limit the number of results rendered.")')
    ],
    "41_🔔_Intelligence_Alerts.py": [
        (r'score_threshold = st\.sidebar\.slider\(\n\s*"Minimum Threat Score", 0, 100, 60, step=5\n\s*\)', r'score_threshold = st.sidebar.slider("Minimum Threat Score", 0, 100, 60, step=5, help="Filter alerts to only show events exceeding this threat score.")'),
        (r'activity_threshold = st\.sidebar\.slider\(\n\s*"Minimum Historical Activity", 0, 1000, 50, step=50\n\s*\)', r'activity_threshold = st.sidebar.slider("Minimum Historical Activity", 0, 1000, 50, step=50, help="Filter to regions with established historical incident volume.")')
    ],
    "42_🎖️_Mission_Planning.py": [
        (r'selected_country = st\.sidebar\.selectbox\("Country", countries, index=default_country_idx\)', r'selected_country = st.sidebar.selectbox("Country", countries, index=default_country_idx, help="Set the initial map view to a country.")'),
        (r'lat = st\.sidebar\.number_input\("Latitude", value=33\.0, format="%\.4f"\)', r'lat = st.sidebar.number_input("Latitude", value=33.0, format="%.4f", help="Operation center latitude.")'),
        (r'lon = st\.sidebar\.number_input\("Longitude", value=44\.0, format="%\.4f"\)', r'lon = st.sidebar.number_input("Longitude", value=44.0, format="%.4f", help="Operation center longitude.")'),
        (r'radius_km = st\.sidebar\.slider\("Mission Radius \(km\)", min_value=50, max_value=500, value=200, step=10\)', r'radius_km = st.sidebar.slider("Mission Radius (km)", min_value=50, max_value=500, value=200, step=10, help="Operational radius around the center coordinates.")')
    ],
    "43_⛅_Weather_Intelligence.py": [
        (r'preset_choice = st\.sidebar\.selectbox\(\n\s*"Quick Locations", list\(_PRESETS\.keys\(\)\), index=0\n\s*\)', r'preset_choice = st.sidebar.selectbox("Quick Locations", list(_PRESETS.keys()), index=0, help="Select a predefined high-interest location.")'),
        (r'lat = st\.sidebar\.number_input\(\n\s*"Latitude", value=_PRESETS\[preset_choice\]\["lat"\], format="%\.4f"\n\s*\)', r'lat = st.sidebar.number_input("Latitude", value=_PRESETS[preset_choice]["lat"], format="%.4f", help="Target latitude for weather analysis.")'),
        (r'lon = st\.sidebar\.number_input\(\n\s*"Longitude", value=_PRESETS\[preset_choice\]\["lon"\], format="%\.4f"\n\s*\)', r'lon = st.sidebar.number_input("Longitude", value=_PRESETS[preset_choice]["lon"], format="%.4f", help="Target longitude for weather analysis.")')
    ],
    "44_🏗️_Military_Assets.py": [
        (r'threat_radius_km = st\.sidebar\.slider\(\n\s*"Threat Radius \(km\)", 50, 500, 150, step=50\n\s*\)', r'threat_radius_km = st.sidebar.slider("Threat Radius (km)", 50, 500, 150, step=50, help="Calculate risk to assets within this radius of historical hotspots.")')
    ],
    "52_📋_Resource_Recommendation.py": [
        (r'selected_country = st\.sidebar\.selectbox\("Select Country", country_list\)', r'selected_country = st.sidebar.selectbox("Select Country", country_list, help="Target country for resource allocation analysis.")')
    ]
}

directory = "pages/"
for filename, replacements in updates.items():
    filepath = os.path.join(directory, filename)
    if os.path.exists(filepath):
        with open(filepath, 'r') as file:
            content = file.read()
        
        for pattern, replacement in replacements:
            content = re.sub(pattern, replacement, content)
            
        with open(filepath, 'w') as file:
            file.write(content)
        print(f"Updated {filename}")
    else:
        print(f"File not found: {filename}")
