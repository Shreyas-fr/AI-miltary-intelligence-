import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import os
from utils.hotspot_utils import build_yearly_series, forecast_hotspot

st.set_page_config(page_title="Hotspot Forecasting", page_icon="📈", layout="wide")


def load_css(file_name):
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


load_css("assets/style.css")

st.title("📈 Hotspot Threat Forecasting")
st.markdown(
    "##### SARIMA time-series forecasting per detected hotspot, "
    "validated on held-out years against a linear-regression baseline."
)

if "hotspot_summary" not in st.session_state or "hotspot_df" not in st.session_state:
    from utils.data_loader import query_data, load_combined
    from utils.hotspot_utils import compute_tsi, cluster_hotspots
    from database.intelligence_db import get_live_count

    with st.spinner("Computing default hotspots (visit Hotspot Detection to customize)..."):
        # Use combined data if live events are available in the DB
        if get_live_count() > 0:
            _df = load_combined()
            _df = _df.dropna(subset=["latitude", "longitude"])
            st.caption("📡 Forecasting includes live intelligence events from the database.")
        else:
            _df = query_data(
                "SELECT latitude, longitude, nkill, nwound, success, iyear, country_txt, region_txt "
                "FROM 'data/globalterrorism.csv' "
                "WHERE latitude IS NOT NULL AND longitude IS NOT NULL"
            )
        _df = compute_tsi(_df)
        df_clustered, hotspots = cluster_hotspots(_df, eps_km=100, min_samples=15)
        st.session_state["hotspot_df"] = df_clustered
        st.session_state["hotspot_summary"] = hotspots
else:
    hotspots = st.session_state["hotspot_summary"]
    df_clustered = st.session_state["hotspot_df"]

if hotspots.empty:
    st.warning("⚠️ No hotspots were found with the current clustering parameters. Go back and widen the radius.")
    st.stop()

# -----------------------------------------------
# Hotspot selector
# -----------------------------------------------
hotspot_options = {
    f"#{row.rank} — {row.countries} ({row.incidents} incidents, TSI {row.total_tsi:.0f})": row.cluster
    for row in hotspots.itertuples()
}
selected_label = st.sidebar.selectbox("Select Hotspot", list(hotspot_options.keys()))
selected_cluster = hotspot_options[selected_label]

value_col = st.sidebar.radio(
    "Forecast target", ["tsi", "count"],
    format_func=lambda x: "Annual Cumulative TSI" if x == "tsi" else "Attack Count",
)
test_years = st.sidebar.slider("Validation window (years held out)", 1, 5, 3)
forecast_years = st.sidebar.slider("Forecast horizon (years)", 1, 10, 5)

series = build_yearly_series(df_clustered, selected_cluster, value_col=value_col)

if len(series) < 8:
    st.warning(
        "⚠️ This hotspot doesn't have enough yearly history for reliable forecasting. "
        "Try a larger cluster radius on the Detection page."
    )
    st.stop()

with st.spinner("Fitting SARIMA model and validating against held-out years..."):
    try:
        result = forecast_hotspot(series, test_years=test_years, forecast_years=forecast_years)
    except ValueError as e:
        st.error(str(e))
        st.stop()

st.divider()

# -----------------------------------------------
# Validation metrics — SARIMA vs baseline
# -----------------------------------------------
st.subheader("Model Validation (held-out years)")
c1, c2 = st.columns(2)
with c1:
    st.markdown(f"**SARIMA{result['order']}**")
    st.metric("RMSE", f"{result['sarima_metrics']['RMSE']:.2f}")
    st.metric("MAE", f"{result['sarima_metrics']['MAE']:.2f}")
with c2:
    st.markdown("**Linear Regression (baseline)**")
    st.metric("RMSE", f"{result['lr_metrics']['RMSE']:.2f}")
    st.metric("MAE", f"{result['lr_metrics']['MAE']:.2f}")

better = "SARIMA" if result["sarima_metrics"]["RMSE"] < result["lr_metrics"]["RMSE"] else "Linear Regression"
st.success(f"✅ **{better}** performs better on held-out validation years for this hotspot.")

st.divider()

# -----------------------------------------------
# Forecast chart
# -----------------------------------------------
fig = go.Figure()

fig.add_trace(go.Scatter(
    x=result["train"].index, y=result["train"].values,
    mode="lines+markers", name="Historical (train)",
    line=dict(color="#00E5FF", width=2),
))
fig.add_trace(go.Scatter(
    x=result["test"].index, y=result["test"].values,
    mode="lines+markers", name="Historical (test)",
    line=dict(color="#00E5FF", width=2, dash="dot"),
))
fig.add_trace(go.Scatter(
    x=result["test"].index, y=result["sarima_test_pred"].values,
    mode="lines+markers", name="SARIMA validation",
    line=dict(color="#FFD166", width=2, dash="dash"),
))
fig.add_trace(go.Scatter(
    x=result["future_years"], y=result["future_forecast"].values,
    mode="lines+markers", name="SARIMA forecast",
    line=dict(color="#FF6B6B", width=2, dash="dash"),
))
fig.add_trace(go.Scatter(
    x=result["future_years"] + result["future_years"][::-1],
    y=list(result["future_conf_int"].iloc[:, 1]) + list(result["future_conf_int"].iloc[:, 0])[::-1],
    fill="toself", fillcolor="rgba(255,107,107,0.30)",
    line=dict(color="rgba(255,107,107,0)"), name="80% Confidence Interval",
))

if "future_conf_int_95" in result:
    fig.add_trace(go.Scatter(
        x=result["future_years"] + result["future_years"][::-1],
        y=list(result["future_conf_int_95"].iloc[:, 1]) + list(result["future_conf_int_95"].iloc[:, 0])[::-1],
        fill="toself", fillcolor="rgba(255,107,107,0.10)",
        line=dict(color="rgba(255,107,107,0)"), name="95% Confidence Interval",
    ))

fig.update_layout(
    title=f"Threat Forecast — {selected_label}",
    xaxis_title="Year",
    yaxis_title="Annual Cumulative TSI" if value_col == "tsi" else "Attack Count",
    template="plotly_dark",
    height=480,
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)
st.plotly_chart(fig, width="stretch")

st.divider()

st.subheader("Forecast Table")
forecast_table = pd.DataFrame({
    "Year": result["future_years"],
    "Forecast": result["future_forecast"].values.round(2),
    "Lower Bound": result["future_conf_int"].iloc[:, 0].values.round(2),
    "Upper Bound": result["future_conf_int"].iloc[:, 1].values.round(2),
})
st.dataframe(forecast_table, width="stretch")

csv = forecast_table.to_csv(index=False)
st.download_button("📥 Download Forecast", csv, file_name=f"{selected_label}_forecast.csv", mime="text/csv")
