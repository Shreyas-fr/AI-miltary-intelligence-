from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import asyncio
import numpy as np
import json
import os
import struct

# Import GNU Radio receiver wrapper
from sdr_receiver import SDRReceiver, GNU_RADIO_AVAILABLE

# Try importing ZMQ for IPC with GNU Radio sockets
ZMQ_AVAILABLE = False
try:
    import zmq
    ZMQ_AVAILABLE = True
except ImportError:
    pass

app = FastAPI()

# Allow CORS for the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files to serve the decoded image
static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# State tracking
sdr_state = {
    "center_freq_hz": 15000e6,    # User inputs RF frequency: 15 GHz (15000 MHz)
    "sample_rate_hz": 2000000,    # 2 MHz
    "gain_db": 30,
    "is_running": False
}

active_receiver = None

@app.get("/api/state")
def get_state():
    return sdr_state

@app.post("/api/state")
def update_state(new_state: dict):
    global sdr_state, active_receiver
    sdr_state.update(new_state)
    
    if active_receiver is not None:
        if "center_freq_hz" in new_state:
            active_receiver.set_rf_freq(new_state["center_freq_hz"])
        if "gain_db" in new_state:
            active_receiver.set_gain(new_state["gain_db"])
        if "sample_rate_hz" in new_state:
            active_receiver.set_sample_rate(new_state["sample_rate_hz"])
            
    return sdr_state

@app.post("/api/start")
def start_sdr():
    global sdr_state, active_receiver
    if active_receiver is None:
        active_receiver = SDRReceiver(
            rf_freq_hz=sdr_state["center_freq_hz"],
            sample_rate_hz=sdr_state["sample_rate_hz"],
            gain_db=sdr_state["gain_db"]
        )
        if GNU_RADIO_AVAILABLE:
            print("[API] Starting GNU Radio top_block...")
            active_receiver.start()
        else:
            print("[API] Starting Simulation...")
            active_receiver.start() # Runs simulator logging
            
    sdr_state["is_running"] = True
    return {"status": "started", "mode": "GNU Radio" if GNU_RADIO_AVAILABLE else "Simulation"}

@app.post("/api/stop")
def stop_sdr():
    global sdr_state, active_receiver
    if active_receiver is not None:
        if GNU_RADIO_AVAILABLE:
            print("[API] Stopping GNU Radio top_block...")
            active_receiver.stop()
            active_receiver.wait()
        else:
            active_receiver.stop()
        active_receiver = None
        
    sdr_state["is_running"] = False
    return {"status": "stopped"}

@app.websocket("/ws/fft")
async def fft_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    # Initialize ZMQ Subscriber sockets if GNU Radio and ZMQ are available
    zmq_context = None
    fft_sub = None
    data_sub = None
    
    if GNU_RADIO_AVAILABLE and ZMQ_AVAILABLE:
        try:
            zmq_context = zmq.Context()
            
            # FFT data receiver (Port 5555)
            fft_sub = zmq_context.socket(zmq.SUB)
            fft_sub.connect("tcp://127.0.0.1:5555")
            fft_sub.setsockopt_string(zmq.SUBSCRIBE, "")
            
            # Demodulated payload receiver (Port 5556)
            data_sub = zmq_context.socket(zmq.SUB)
            data_sub.connect("tcp://127.0.0.1:5556")
            data_sub.setsockopt_string(zmq.SUBSCRIBE, "")
            
            print("[WebSocket] ZMQ Subscribers connected successfully to GNU Radio.")
        except Exception as e:
            print(f"[WebSocket] Failed to initialize ZMQ sockets: {e}")
            fft_sub = None
            data_sub = None

    try:
        frame_counter = 0
        start_time = asyncio.get_event_loop().time()
        
        telemetry_logs = [
            "[System] Frequency Translation: 15.0 GHz RF downconverted to 150.0 MHz IF.",
            "[System] Lock acquired on 150 MHz IF band.",
            "[Decoder] Searching for carrier synchronization...",
            "[Decoder] Symbol recovery locked. Rescuing lines...",
            "[Decoder] Telemetry frame #002 decoded. Frame health: OK.",
            "[Decoder] Downlink speed: 1.2 kbps | BER: 1.2e-5",
            "[Decoder] Composing high-frequency telemetry imagery..."
        ]
        
        while True:
            if sdr_state["is_running"]:
                
                # ----------------- Mode A: Real GNU Radio stream via ZMQ -----------------
                if fft_sub is not None:
                    # 1. Check for FFT Data
                    try:
                        fft_bytes = fft_sub.recv(flags=zmq.NOBLOCK)
                        num_floats = len(fft_bytes) // 4
                        fft_floats = struct.unpack(f"{num_floats}f", fft_bytes)
                        await websocket.send_text(json.dumps({
                            "type": "fft",
                            "data": list(fft_floats)
                        }))
                    except zmq.Again:
                        pass # No new FFT packet this tick
                    
                    # 2. Check for Demodulated Payload Data (simplified log parser)
                    try:
                        data_bytes = data_sub.recv(flags=zmq.NOBLOCK)
                        # Here we would decode the custom telemetry payload.
                        # For now, we print telemetry logs to indicate connection.
                        if frame_counter % 30 == 0:
                            await websocket.send_text(json.dumps({
                                "type": "text",
                                "message": f"[Live Hardware] Signal lock active. Recv payload packet: {len(data_bytes)} bytes."
                            }))
                    except zmq.Again:
                        pass
                
                # ----------------- Mode B: Simulation Fallback -----------------
                else:
                    # 1. FFT Simulation
                    num_bins = 256
                    fft_data = np.random.normal(loc=-80, scale=4, size=num_bins)
                    center_bin = num_bins // 2
                    # Create a peak at 150 MHz IF (offset based on UI sweep)
                    peak_idx = center_bin + int(np.sin(asyncio.get_event_loop().time() * 1.5) * 15)
                    if 0 <= peak_idx < num_bins:
                        fft_data[peak_idx] = -32
                        if peak_idx > 0: fft_data[peak_idx-1] = -42
                        if peak_idx < num_bins-1: fft_data[peak_idx+1] = -42

                    await websocket.send_text(json.dumps({
                        "type": "fft",
                        "data": fft_data.tolist()
                    }))
                    
                    # 2. Telemetry Text Log Simulation
                    if frame_counter % 30 == 0:
                        log_idx = (frame_counter // 30) % len(telemetry_logs)
                        await websocket.send_text(json.dumps({
                            "type": "text",
                            "message": telemetry_logs[log_idx]
                        }))
                
                # ----------------- Reconstructed Image Trigger -----------------
                # Simulates that the complete weather map has finished download
                running_duration = asyncio.get_event_loop().time() - start_time
                if running_duration > 15:
                    await websocket.send_text(json.dumps({
                        "type": "image",
                        "url": f"http://localhost:8001/static/decoded_image.jpg"
                    }))
                
                frame_counter += 1
            else:
                # Reset states when inactive
                start_time = asyncio.get_event_loop().time()
                frame_counter = 0
                await websocket.send_text(json.dumps({
                    "type": "clear"
                }))
                
            await asyncio.sleep(0.1) # 10 FPS
    except Exception as e:
        print(f"WebSocket closed: {e}")
    finally:
        # Clean up sockets on connection close
        if fft_sub: fft_sub.close()
        if data_sub: data_sub.close()
        if zmq_context: zmq_context.destroy()
