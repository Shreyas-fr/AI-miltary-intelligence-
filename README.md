# Predictive Tactical Intelligence & Hotspot Forecasting

A Streamlit decision-support dashboard using GTD incident data. It discovers geographic threat hotspots without political-boundary assumptions, ranks them with a casualty-based Threat Severity Index (TSI), and forecasts hotspot trends using AIC-selected SARIMA models validated against linear regression.

## Pipeline

1. **DuckDB ingestion** queries the CSV directly and selects only required columns.
2. **TSI scoring:** `(3 × fatalities + injuries)^0.85 × success factor`, where the factor is 1.0 for a successful event and 0.4 otherwise.
3. **DBSCAN clustering** uses haversine great-circle distance and labels isolated events as noise.
4. **Forecasting** aggregates annual TSI or incident count, selects a SARIMA order by AIC, evaluates held-out years using RMSE/MAE, compares linear regression, then produces an 80% interval.
5. **Streamlit UI** preserves detection results in session state for forecasting.

## Run

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Place a GTD-compatible CSV at `data/globalterrorism.csv`. Required hotspot columns are `latitude`, `longitude`, `nkill`, `nwound`, `success`, `iyear`, `country_txt`, and `region_txt`.

Open **Hotspot Detection** first, adjust DBSCAN parameters, and then open **Forecasting**. Forecast downloads are available as CSV.

## Verify

```bash
python -m unittest discover -s tests -v
python -m compileall app.py pages utils
```

The system is an assisted analytical tool. Forecasts are estimates derived from historical data and should not be treated as autonomous operational recommendations.
