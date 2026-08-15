# 🎤 Live Demo Script: AI Military Intelligence Platform

This script provides a structured, high-impact path through the platform. It focuses on narrative flow, moving from high-level global overviews down to specific, actionable intelligence.

---

## Step 1: The Global Overview 
**Page:** `10_🏠_Home.py` -> `20_🌍_Global_Threat_Map.py`

### What to do:
1. Start on the **Home** page. Briefly gesture to the high-level KPIs and the clean dark-mode UI.
2. Quickly click over to the **Global Threat Map**. 
3. Switch the "View Mode" in the sidebar to **Both (Hexbin + DBSCAN)**.
4. Pan the 3D map around the Middle East or South Asia.

### What to say:
> "Welcome to the AI Military Intelligence Platform. We start at the macro level: the Global Threat Map. What you're seeing isn't just plotted points—it's a live WebGL rendering of historical incident density. The glowing hexbins show raw volume, but the teal polygons are where our spatial algorithms have automatically identified contiguous threat 'hotspots' using DBSCAN clustering."

### The "Wow" Moment:
Holding `Shift` and dragging the mouse to tilt the 3D map, showing the extruded hexbins.

---

## Step 2: AI Narrative Intelligence & Threat Scoring
**Page:** `23_🧠_Threat_Level_&_AI_Intelligence.py`

### What to do:
1. Navigate to **Threat Level & AI Intelligence**.
2. Select **Syria** or **Iraq** from the country dropdown.
3. Show the **Threat Score Breakdown** gauge (the 0-100 score).
4. Scroll down (or switch to the AI tab) to show the generated Gemini narrative report.

### What to say:
> "Raw data is useless without context. Here, we analyze a specific sovereign nation. Our Threat Score isn't arbitrary; it's a normalized 0-100 index combining historical volume, cluster density, and recent activity. More importantly, we pipe this quantitative data directly into a large language model to generate an immediate, qualitative intelligence brief—synthesizing years of data into a readable situation report in seconds."

### The "Wow" Moment:
The instant generation of the AI narrative report based on the specific country selected, demonstrating GenAI integration.

---

## Step 3: Predictive Analytics & Forecasting
**Page:** `31_📈_Forecasting.py`

### What to do:
1. Navigate to **Forecasting**.
2. Select a high-activity hotspot (e.g., `Hotspot 0` or a Middle East cluster).
3. Point out the **SARIMA Backtest** chart showing the "Predicted" vs "Actual" lines overlapping.

### What to say:
> "Looking backward is easy; the goal is to look forward. We use SARIMA time-series models to forecast future attack volumes. Before we trust the forecast, we force the model to backtest against data it hasn't seen. As you can see by the overlap, the model accurately anticipates seasonal spikes. We then project this out for the next 3-5 years to inform long-term resource deployment."

### The "Wow" Moment:
Showing the backtest chart. It proves the platform doesn't just guess—it validates its own accuracy before making future predictions.

---

## Step 4: Tactical Action (Mission Planning)
**Page:** `42_🎖️_Mission_Planning.py`

### What to do:
1. Navigate to **Mission Planning**.
2. Set the latitude/longitude to a known conflict zone (e.g., Baghdad: `33.31`, `44.36`).
3. Set the Mission Radius to `100km`.
4. Scroll down to show the **Recommended Resource Allocations**.
5. **(New Feature)** Click the **Download Mission Brief (PDF)** button and open the resulting PDF on screen.

### What to say:
> "Finally, we move from the strategic to the tactical. An operator drops a pin on their exact mission center. The platform instantly scans the radius, assesses the localized threat severity, and generates concrete tactical recommendations—like deploying MedEvac or securing convoy routes based on the dominant attack types in that exact 100km circle. With one click, this entire intelligence package is exported to a PDF brief, ready to be handed to a field commander."

### The "Wow" Moment:
Opening the cleanly formatted PDF export, proving the platform generates offline-ready, actionable deliverables. 

---

## Closing
> "From global clustering to AI narratives, predictive forecasting, and tactical PDF briefs—this is a complete, end-to-end intelligence pipeline."
