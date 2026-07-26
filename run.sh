#!/bin/bash
# Local execution wrapper to fix PyArrow memory crashes on Apple Silicon (M-series Macs)
export ARROW_DEFAULT_MEMORY_POOL=system
streamlit run app.py
