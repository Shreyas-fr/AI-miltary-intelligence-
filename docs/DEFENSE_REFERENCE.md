# 🛡️ Defense Reference Guide

This document is your cheat sheet for defending the platform during a review or live demo. Memorize the honest caveats—they build credibility.

---

## 1. Machine Learning Metrics
**Claim:** Random Forest Classifier Accuracy is **79.9%**.
*   **Source:** Trained on real, historical GTD data targeting attack success/weapon type.
*   **The Defense:** "We achieved ~80% accuracy. We ran 5 out of 5 standard sanity checks (Precision, Recall, F1, Confusion Matrix, Cross-Validation). It's a robust baseline, but we are fully transparent that predicting human behavior isn't perfect, hence the ~20% error rate."

## 2. SARIMA Forecasting (MAPE)
**Claim:** SARIMA Backtest MAPE (Mean Absolute Percentage Error) varies by hotspot: **India (13%), Iraq (37%), Pakistan (47%)**.
*   **Source:** Time-series validation holding out the last 3-5 years of data.
*   **The Defense:** "Our models perform exceptionally well in stable conflict zones like India (13% error). However, you'll notice higher errors in Iraq and Pakistan. **Honest Caveat:** The model missed the massive, unprecedented spike in Iraq around 2014-2017 (the rise of ISIS). SARIMA relies on historical seasonality; it cannot predict black-swan geopolitical regime changes. We show this backtest precisely so commanders know when to trust the model and when to rely on human intelligence."

## 3. Threat Severity Index (TSI) Formula
**Claim:** The TSI quantifies the severity of an incident or region.
*   **Source:** Custom mathematical formula built into the platform's core (`tests/test_core_math.py`).
*   **Formula:** $TSI\_raw = 0.50 \cdot \ln(1 + nkill) + 0.30 \cdot \ln(1 + nwound) + 0.15 \cdot success + 0.05 \cdot claimed$
*   **The Defense:** "We don't just count incidents; 100 broken windows is not the same as 1 bombing. We use a non-linear logarithmic scale for casualties to prevent a single massive event (like 9/11) from blowing out the scale, while still heavily weighting fatalities (50%) and injuries (30%)."
*   **Annual Cumulative TSI vs. 0-100 Score:** "Cumulative TSI is the raw mathematical sum of all incident severities in a year. The 0-100 'Threat Score' you see on the dashboard is that raw data *clamped and normalized* against global maximums so it's readable for an analyst."

## 4. Group Networks Thresholds
**Claim:** Similarity Threshold is **0.85**, Noise Filter is **100 incidents**.
*   **Source:** Default parameters in `utils/network_utils.py`.
*   **The Defense:** "To build the perpetrator network graph, we calculate the cosine similarity of tactical footprints (weapons, targets, regions). We set a strict **0.85 threshold** to ensure we only draw edges between groups with highly identical tactics. We also filter out any group with fewer than **100 historical incidents** to eliminate statistical noise from one-off actors."

## 5. Known Limitations (Be Upfront!)
If asked about limitations, proactively list these to show you understand the data boundaries:
1.  **Data Cutoff (2017):** The core GTD dataset ends in 2017. The platform is built to ingest newer data, but the current static historical layer stops there.
2.  **Live Feed Unreliability:** The live GDELT/OSINT feed is subject to API rate limits and external uptime. It is a supplementary feed, not the core analytical engine.
3.  **Mobile Map WebGL Downsampling:** The 3D PyDeck map is incredibly heavy on GPU memory. On mobile devices, we explicitly downsample the data to a 10,000-point 2D scatter map (`scatter_mapbox`) to prevent mobile browser crashes. It's a deliberate performance fallback.
