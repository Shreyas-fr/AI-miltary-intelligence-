#!/bin/bash
# Start FastAPI in the background
cd api && uvicorn main:app --host 0.0.0.0 --port 8000 &
# Start Streamlit in the foreground
cd ../dashboard && streamlit run app.py --server.port $PORT --server.address 0.0.0.0
