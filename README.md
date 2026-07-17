# Predictive Tactical Intelligence & Hotspot Forecasting

This project now uses a **React frontend** and a **FastAPI backend** for GTD-based military intelligence analysis.

## Architecture

- `backend/main.py` exposes REST endpoints for health checks, dataset summary, and hotspot detection.
- `frontend/` contains a Vite + React app that consumes the FastAPI API.
- `utils/hotspot_utils.py` contains TSI scoring, hotspot clustering, and forecasting logic.

## Run

### 1) Start backend (FastAPI)

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --reload
```

### 2) Start frontend (React)

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at `http://localhost:5173` and expects backend at `http://127.0.0.1:8000`.
You can override this with `VITE_API_BASE_URL`.

## API Endpoints

- `GET /api/health`
- `GET /api/summary`
- `GET /api/hotspots?eps_km=100&min_samples=15`

## Verify

```bash
python -m unittest discover -s tests -v
python -m compileall backend utils
cd frontend && npm run build
```

Place a GTD-compatible CSV at `data/globalterrorism.csv`.
