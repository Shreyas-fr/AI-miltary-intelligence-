# pyrefly: ignore [missing-import]
import streamlit as st
import zmq
import json
import time
import pandas as pd
import plotly.express as px

# Set page configuration
st.set_page_config(
    page_title="SIGINT RF Spectrum Analysis",
    page_icon="📡",
    layout="wide"
)

# ----------------- Honesty Banner (Non-Negotiable Requirement) -----------------
st.warning(
    "⚠️ **SIMULATED SIGNAL** — No SDR hardware detected. This demonstrates the software pipeline "
    "architecture with synthetic FFT data, not live RF capture."
)

st.title("📡 SIGINT RF Spectrum Analyzer")
st.write(
    "This module simulates the signal acquisition pipeline. It models an analog frequency downconverter "
    "translating a high-frequency C/Ku-band signal down to the intermediate frequency (IF) of the SDR's receiver."
)

# ----------------- Sidebar Controls -----------------
st.sidebar.header("Tuning Parameters")

# Target RF Frequency: 15 GHz band
rf_freq_mhz = st.sidebar.slider(
    "Target RF Frequency (MHz)",
    min_value=14850.0,
    max_value=15150.0,
    value=15000.0,
    step=1.0,
    help="Target frequency band (15 GHz center)."
)

# Gain Settings
rf_gain = st.sidebar.slider(
    "SDR RF Gain (dB)",
    min_value=0,
    max_value=50,
    value=30,
    step=1
)

# Bandwidth Settings
bandwidth_mhz = st.sidebar.selectbox(
    "Acquisition Bandwidth",
    options=[1.0, 2.0, 5.0],
    index=1,
    format_func=lambda x: f"{x} MHz"
)

# Downconversion details
lo_freq_mhz = 14850.0 # LO of the hardware mixer
if_freq_mhz = rf_freq_mhz - lo_freq_mhz

st.sidebar.markdown("---")
st.sidebar.subheader("Frequency Translation Math")
st.sidebar.markdown(f"**Target RF:** `{rf_freq_mhz:.1f} MHz`")
st.sidebar.markdown(f"**LO Mixer Offset:** `-{lo_freq_mhz:.1f} MHz`")
st.sidebar.markdown(f"**SDR IF Tuning:** `{if_freq_mhz:.1f} MHz` (VHF Range)")

# ----------------- Connection Settings -----------------
st.subheader("Receiver Stream Status")

# Manage start/stop of reading
if 'stream_active' not in st.session_state:
    st.session_state.stream_active = False

col1, col2 = st.columns([1, 4])

with col1:
    if st.button("Start Signal Acquisition", disabled=st.session_state.stream_active):
        st.session_state.stream_active = True
        st.rerun()

with col2:
    if st.button("Stop Acquisition", disabled=not st.session_state.stream_active):
        st.session_state.stream_active = False
        st.rerun()

# ----------------- Live Plotting & Connection -----------------
if st.session_state.stream_active:
    st.info("🔄 Connecting to `tcp://127.0.0.1:5555` ZMQ publisher...")
    
    # Init ZMQ subscriber
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    socket.connect("tcp://127.0.0.1:5555")
    socket.setsockopt_string(zmq.SUBSCRIBE, "")
    
    plot_placeholder = st.empty()
    metrics_placeholder = st.empty()
    
    try:
        # Loop for real-time updates inside Streamlit
        # We run a loop of 150 iterations (to prevent infinite loops freezing the tab permanently)
        for i in range(150):
            try:
                # Non-blocking read (CRITICAL to avoid freezing Streamlit UI)
                message = socket.recv_string(flags=zmq.NOBLOCK)
                payload = json.loads(message)
                
                # Verify payload match
                fft_data = payload.get("data", [])
                freq_mhz = payload.get("rf_frequency_mhz", 15000.0)
                if_mhz = payload.get("if_frequency_mhz", 150.0)
                bw_mhz = payload.get("sample_rate_mhz", 2.0)
                
                # Calculate frequency axis bins centered at target IF frequency
                bins = len(fft_data)
                freq_axis = [if_mhz - (bw_mhz / 2.0) + (bw_mhz * j / bins) for j in range(bins)]
                
                df = pd.DataFrame({
                    "IF Frequency (MHz)": freq_axis,
                    "Amplitude (dBm)": fft_data
                })
                
                # Render Metrics
                with metrics_placeholder.container():
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Physical Tuning (IF)", f"{if_mhz:.3f} MHz")
                    m2.metric("Target RF Frequency", f"{freq_mhz / 1e3:.4f} GHz")
                    m3.metric("Signal Peak", f"{max(fft_data):.1f} dBm")
                
                # Render Plotly Chart
                fig = px.line(
                    df, 
                    x="IF Frequency (MHz)", 
                    y="Amplitude (dBm)",
                    title="Intermediate Frequency Spectrum (SDR Tuner Output)"
                )
                fig.update_layout(
                    yaxis=dict(range=[-100, 0]),
                    template="plotly_dark",
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)"
                )
                fig.update_traces(line_color="#00f0ff", line_width=1.5)
                
                plot_placeholder.plotly_chart(fig, use_container_width=True)
                
            except zmq.Again:
                # No data ready on this loop tick, continue
                pass
            
            # Short sleep to pace updates
            time.sleep(0.1)
            
    except Exception as e:
        st.error(f"Error during signal acquisition: {e}")
    finally:
        socket.close()
        context.destroy()
        
    st.success("Signal stream disconnected cleanly.")
else:
    st.write("Acquisition stream is offline. Click 'Start Signal Acquisition' to connect.")
