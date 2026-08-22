import zmq
import time
import numpy as np
import json
import sys

def main():
    print("[SIGINT Simulator] Initializing synthetic ZMQ transmitter...")
    context = zmq.Context()
    socket = context.socket(zmq.PUB)
    
    try:
        socket.bind("tcp://127.0.0.1:5555")
        print("[SIGINT Simulator] Socket bound to tcp://127.0.0.1:5555. Publishing synthetic spectrum.")
    except Exception as e:
        print(f"[SIGINT Simulator] Failed to bind to port 5555: {e}")
        sys.exit(1)

    # State variables (mock values that can be updated or read)
    lo_freq_hz = 14850e6  # 14.85 GHz Downconverter LO
    rf_freq_hz = 15000e6  # 15.00 GHz default RF target
    sample_rate_hz = 2000000 # 2 MHz Default
    
    print("[SIGINT Simulator] Running frequency translation calculations:")
    print(f"  Target RF Frequency: {rf_freq_hz / 1e6} MHz")
    print(f"  Hardware LO Offset:  {lo_freq_hz / 1e6} MHz")
    print(f"  SDR Intermediate Freq: {(rf_freq_hz - lo_freq_hz) / 1e6} MHz")
    
    num_bins = 256
    
    try:
        while True:
            # Calculate dynamic IF based on simulated target frequency
            if_freq_hz = rf_freq_hz - lo_freq_hz # 150 MHz
            
            # Generate simulated noise floor
            fft_data = np.random.normal(loc=-85, scale=3, size=num_bins)
            
            # Create a signal peak (simulating the downconverted carrier)
            center_bin = num_bins // 2
            # Add a sine wander to make the carrier signal look "live"
            peak_offset = int(np.sin(time.time() * 1.5) * 15)
            peak_idx = center_bin + peak_offset
            
            if 0 <= peak_idx < num_bins:
                fft_data[peak_idx] = -35 + np.random.normal(0, 1) # Signal peak
                # Smear the peak to adjacent bins for realism
                if peak_idx > 0: fft_data[peak_idx-1] = -48 + np.random.normal(0, 1.5)
                if peak_idx < num_bins-1: fft_data[peak_idx+1] = -48 + np.random.normal(0, 1.5)
            
            # Construct JSON payload
            payload = {
                "type": "fft",
                "rf_frequency_mhz": rf_freq_hz / 1e6,
                "if_frequency_mhz": if_freq_hz / 1e6,
                "sample_rate_mhz": sample_rate_hz / 1e6,
                "data": fft_data.tolist()
            }
            
            # Publish payload as JSON string
            socket.send_string(json.dumps(payload))
            
            # Run at ~10 Hz update rate
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\n[SIGINT Simulator] Shutting down socket.")
    finally:
        socket.close()
        context.destroy()
        print("[SIGINT Simulator] Context terminated.")

if __name__ == "__main__":
    main()
