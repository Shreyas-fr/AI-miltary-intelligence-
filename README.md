# AI-Based Military Intelligence & Threat Assessment Platform

A Streamlit decision-support platform using GTD incident data and public-source GDELT signals. It discovers geographic threat hotspots, ranks them with a casualty-based Threat Severity Index (TSI), forecasts hotspot trends, monitors recent conflict reporting, scores country risk, and generates analyst-ready situation reports.

## Pipeline

1. **DuckDB ingestion** queries the CSV directly and selects only required columns.
2. **TSI scoring:** `(3 × fatalities + injuries)^0.85 × success factor`, where the factor is 1.0 for a successful event and 0.4 otherwise.
3. **DBSCAN clustering** uses haversine great-circle distance and labels isolated events as noise.
4. **Forecasting** aggregates annual TSI or incident count, selects a SARIMA order by AIC, evaluates held-out years using RMSE/MAE, compares linear regression, then produces an 80% interval.
5. **Live intelligence feed** queries GDELT for recent conflict, terrorism, explosion, missile, and border-clash reporting, then maps events to GTD-derived country centroids when precise coordinates are unavailable.
6. **AI risk score** blends historical activity, recent events, fatalities, cluster density, and a live-event instability proxy into a 0-100 country score.
7. **Situation report generator** creates a country brief locally and can optionally enhance it with Gemini when `GEMINI_API_KEY` is configured.

## Run the FastAPI + React version

```bash
source venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`. The React frontend calls the FastAPI backend at `http://127.0.0.1:8000` by default. Set `VITE_API_BASE_URL` if you run the backend somewhere else.

The live feed endpoint caches GDELT responses for 15 minutes. If GDELT returns HTTP 429 or another fetch error, the backend returns stale cached data when available, otherwise a clearly labeled GTD historical fallback so the frontend remains usable.

## Run the legacy Streamlit version

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Place a GTD-compatible CSV at `data/globalterrorism.csv`. Required hotspot columns are `latitude`, `longitude`, `nkill`, `nwound`, `success`, `iyear`, `country_txt`, and `region_txt`.

Open **Hotspot Detection** first, adjust DBSCAN parameters, and then open **Forecasting**. Forecast downloads are available as CSV.

Open **Live Intelligence Feed** for GDELT-based public-source monitoring. Open **AI Situation Report** to select a country, review the risk breakdown, generate a brief, and export Markdown or PDF.

## Verify

```bash
python -m unittest discover -s tests -v
python -m compileall app.py pages utils
```

The system is an assisted analytical tool. Forecasts, live-feed classifications, and generated reports are estimates derived from historical data and public news metadata and should not be treated as autonomous operational recommendations.
