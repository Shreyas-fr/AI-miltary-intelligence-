# Predictive Tactical Intelligence & Spatial-Temporal Hotspot Forecasting Framework
### Implementation Plan — CAIR (DRDO Bengaluru) Submission

---

## 1. Problem Statement (Recap)

Given historical incident data (GTD), detect geographic threat hotspots
data-driven (not by political boundary), score them by casualty severity,
and forecast how each hotspot's threat level will evolve — to support a
human commander's resource-allocation decisions (Assisted Decision Support,
not autonomous action).

---

## 2. System Architecture — 5 Stages

```
Raw CSV (GTD)
     │
     ▼
[1] Data Ingestion Layer  ──  DuckDB SQL over CSV (no full load into RAM)
     │
     ▼
[2] Threat Severity Index (TSI)  ──  per-incident non-linear casualty score
     │
     ▼
[3] Spatial Clustering  ──  DBSCAN (haversine) → discovers hotspots
     │
     ▼
[4] Time-Series Forecasting  ──  SARIMA per hotspot, validated vs. baseline
     │
     ▼
[5] Decision Support UI  ──  Streamlit: map + ranked table + forecast chart
```

Each stage is a separate, testable unit — this matters for defending the
project, because you can explain and re-run any one stage in isolation.

---

## 3. Library Stack & Why Each One Is There

| Library | Role | Why this one, specifically |
|---|---|---|
| **DuckDB** | SQL queries directly over the CSV | Avoids loading the full multi-hundred-MB GTD file into pandas memory for every query — an engineering choice, not just a convenience |
| **pandas / numpy** | Dataframe manipulation, vectorized math | Standard; used for TSI computation and series reindexing |
| **scikit-learn** | `DBSCAN`, `LinearRegression`, `mean_squared_error`, `mean_absolute_error` | Industry-standard clustering + baseline model + validation metrics, all in one dependency |
| **statsmodels** | `SARIMAX` | The standard, peer-reviewed implementation of ARIMA/SARIMA in Python — gives you AIC, confidence intervals, and diagnostics for free, which a hand-rolled model wouldn't |
| **Plotly** | Forecast charts, bar/pie charts | Interactive, dark-theme-friendly, already used across your app |
| **PyDeck** | 3D hexbin map | GPU-accelerated geospatial rendering, handles hundreds of thousands of points without lag |
| **Streamlit** | UI framework + `session_state` | Lets you pass the DBSCAN output from the Detection page into the Forecasting page without recomputation |

Nothing here needs classified data, a GPU, or a dependency you can't `pip install` today.

---

## 4. Mathematical Foundations

### 4.1 Threat Severity Index (TSI)

```
TSI = (w_k · nkill + w_w · nwound) ^ 0.85 · S
```
- `w_k = 3.0`, `w_w = 1.0` — fatalities weighted 3× injuries (standard severity weighting in casualty-based risk models)
- `S` = 1.0 if the attack succeeded, 0.4 if it failed (a failed attack still signals hostile capability/intent, so it isn't scored zero)
- **Exponent 0.85 (why non-linear):** a raw linear sum lets one mass-casualty event outweigh 50 smaller recurring attacks in the same area. Compressing with a sub-linear power keeps hotspot ranking sensitive to *persistence and frequency* of threat, which is what actually matters for "should we watch this region," not just "did one bad thing happen here once."

### 4.2 DBSCAN with Haversine Distance

DBSCAN groups points where at least `min_samples` other points lie within
radius `eps` (a **core point**); points reachable from a core point form a
cluster; everything else is **noise** (`cluster = -1`).

Critically, distance is NOT computed as `sqrt((lat1-lat2)² + (lon1-lon2)²)`
— that treats the Earth as flat and is wrong at scale (1° of longitude is
~111 km at the equator but ~0 km at the poles). Instead we use the
**haversine formula** (great-circle distance on a sphere):

```
a = sin²(Δφ/2) + cos(φ1)·cos(φ2)·sin²(Δλ/2)
d = 2r · atan2(√a, √(1−a))
```
where `φ` = latitude, `λ` = longitude (radians), `r` = Earth's radius (6371 km).

`eps_km` (a UI slider) is converted to radians (`eps_km / r`) because
sklearn's haversine metric expects radian input.

### 4.3 SARIMA Forecasting

SARIMA(p,d,q) models a time series as:

```
φ(L)(1−L)^d y_t = θ(L) ε_t
```
- `φ(L)` — autoregressive terms (past values predict current value)
- `(1−L)^d` — differencing of order `d` (removes trend, makes series stationary)
- `θ(L)` — moving-average terms (past forecast errors predict current value)
- `ε_t` — white noise residual

**Order selection:** rather than guessing `(p,d,q)`, the code fits 6
candidate orders and keeps the one with the lowest **AIC**
(Akaike Information Criterion):

```
AIC = 2k − 2·ln(L̂)
```
where `k` = number of parameters, `L̂` = maximized likelihood. Lower AIC
means a better fit-to-complexity tradeoff — this is the standard,
defensible way to pick a model order instead of eyeballing it.

**Confidence intervals** come directly from the state-space model's
estimated forecast variance at each step — not manually computed, which
is more statistically sound.

### 4.4 Baseline Model — Linear Regression

```
y_t = β₀ + β₁·t + ε
```
fit by ordinary least squares. This exists purely as a **sanity check**:
if SARIMA can't beat a straight line, SARIMA isn't earning its complexity.
The app reports both and states explicitly which one wins on held-out
years — this comparison is itself the strongest "ML rigor" signal in
the whole project, because it shows model evaluation, not just model use.

### 4.5 Validation Metrics

```
RMSE = √( (1/n) Σ (y_i − ŷ_i)² )      — penalizes large errors more
MAE  = (1/n) Σ |y_i − ŷ_i|            — average absolute error, more interpretable
```
Both are computed on **held-out years never seen during training**
(default: last 3 years), not on training data — this is the difference
between "the model fits the past" and "the model can predict the future,"
and evaluators will specifically check you did this correctly.

---

## 5. Data Flow Between Pages

```
Hotspot Detection page
   → runs DBSCAN + TSI
   → writes df_clustered, hotspot_summary to st.session_state
   → user navigates to Forecasting page
Hotspot Forecasting page
   → reads from st.session_state (no recomputation)
   → user selects a hotspot from the ranked list
   → builds yearly series → SARIMA fit → validate → forecast
```

---

## 6. Timeline vs. 30 August Deadline (6 weeks)

| Week | Task |
|---|---|
| 1 | ✅ TSI scoring + DBSCAN clustering (done) |
| 2 | ✅ SARIMA forecasting + validation layer (done) |
| 3 | Test on full dataset, tune `eps_km`/`min_samples` defaults, handle edge cases (sparse hotspots) |
| 4 | Report writing — math derivations, methodology chapter |
| 5 | Slide deck + demo rehearsal, screenshot/record walkthroughs |
| 6 | Buffer — fix whatever breaks in rehearsal, polish UI/CSS |

---

## 7. What You Can Say in the Viva When Asked "Why This Model?"

- **"Why DBSCAN and not K-Means?"** — K-Means needs you to pre-specify the number of clusters and assumes round, evenly-sized clusters. Threat hotspots are irregular and unknown in number — DBSCAN discovers both cluster count and shape from the data, and naturally separates noise (isolated incidents) from real hotspots.
- **"Why SARIMA and not a neural net (LSTM)?"** — With only ~40 years of yearly data per hotspot, a deep model would overfit badly. SARIMA is the statistically appropriate choice for short, low-frequency time series, and it's interpretable — you can show the fitted order and explain what each term means, which an LSTM's weights don't give you.
- **"How do you know your model isn't just memorizing history?"** — held-out validation years + RMSE/MAE reported explicitly, and compared against a baseline it has to beat.
