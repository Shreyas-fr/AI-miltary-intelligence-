import os

# We check if gnuradio is installed in the current environment
GNU_RADIO_AVAILABLE = False
try:
    from gnuradio import gr, blocks, fft, filter as gr_filter
    from gnuradio.filter import firdes
    import osmosdr
    from gnuradio import zeromq
    from gnuradio import analog
    GNU_RADIO_AVAILABLE = True
except ImportError:
    pass

if GNU_RADIO_AVAILABLE:
    class SDRReceiver(gr.top_block):
        def __init__(self, rf_freq_hz=15000e6, sample_rate_hz=2e6, gain_db=30):
            super(SDRReceiver, self).__init__("SDR Receiver with HW Downconverter")
            
            self.rf_freq_hz = rf_freq_hz
            self.sample_rate_hz = sample_rate_hz
            self.gain_db = gain_db
            
            # Local Oscillator frequency of the physical downconverter hardware
            # 14.85 GHz downconverts 15.00 GHz RF down to 150 MHz IF
            self.lo_freq_hz = 14850e6 
            self.if_freq_hz = self.rf_freq_hz - self.lo_freq_hz
            
            # 1. Osmocom Source (Supports HackRF, RTL-SDR, USRP, etc.)
            self.src = osmosdr.source(args="numchan=1")
            self.src.set_sample_rate(self.sample_rate_hz)
            self.src.set_center_freq(self.if_freq_hz, 0)
            self.src.set_gain(self.gain_db, 0)
            
            # 2. FFT Processing Chain (for spectrum analyzer WebSockets)
            # Size of the FFT bins we transmit to the UI
            self.fft_size = 256
            self.s2v = blocks.stream_to_vector(gr.sizeof_gr_complex, self.fft_size)
            self.fft_block = fft.fft_vcc(
                self.fft_size,
                True, # Forward FFT
                firdes.window(firdes.WIN_BLACKMAN_HARRIS, self.fft_size, 1),
                True # Shift zero frequency to center
            )
            self.v2s = blocks.vector_to_stream(gr.sizeof_gr_complex, self.fft_size)
            self.complex_to_mag = blocks.complex_to_mag(1)
            # Convert to dB: 10 * log10(val)
            self.nlog10 = blocks.nlog10_ff(10, self.fft_size, -20)
            
            # FFT data streaming over ZMQ (Local port 5555)
            self.fft_pub = zeromq.pub_sink(gr.sizeof_float, 1, "tcp://127.0.0.1:5555", 100, False, -1)
            
            # Connect the FFT DSP pipeline
            self.connect(self.src, self.s2v, self.fft_block, self.v2s, self.complex_to_mag, self.nlog10, self.fft_pub)
            
            # 3. Demodulator & Decoder pipeline (e.g. FM / QPSK for telemetry data)
            # Low pass filter to clean up the bandwidth (100kHz passband)
            self.lp_filter = gr_filter.fir_filter_ccf(
                1,
                firdes.low_pass(
                    1,
                    self.sample_rate_hz,
                    100e3, # Cutoff freq
                    20e3,  # Transition width
                    firdes.WIN_HAMMING,
                    6.76
                )
            )
            
            # Demodulate FM (e.g. NOAA weather satellites use FM modulated audio subcarrier)
            self.demod = analog.quadrature_demod_cf(1.0)
            
            # Demodulated output streamed over ZMQ (Local port 5556)
            self.data_pub = zeromq.pub_sink(gr.sizeof_float, 1, "tcp://127.0.0.1:5556", 100, False, -1)
            
            # Connect the Demodulation pipeline
            self.connect(self.src, self.lp_filter, self.demod, self.data_pub)

        def set_rf_freq(self, rf_freq_hz):
            self.rf_freq_hz = rf_freq_hz
            self.if_freq_hz = self.rf_freq_hz - self.lo_freq_hz
            # Tell the physical SDR hardware to tune to the intermediate frequency
            self.src.set_center_freq(self.if_freq_hz, 0)
            print(f"[GNU Radio] Tuning SDR to IF: {self.if_freq_hz / 1e6} MHz (RF: {self.rf_freq_hz / 1e6} MHz)")
            
        def set_gain(self, gain_db):
            self.gain_db = gain_db
            self.src.set_gain(self.gain_db, 0)
            print(f"[GNU Radio] Set SDR Gain: {self.gain_db} dB")
            
        def set_sample_rate(self, sample_rate_hz):
            self.sample_rate_hz = sample_rate_hz
            self.src.set_sample_rate(self.sample_rate_hz)
            print(f"[GNU Radio] Set SDR Sample Rate: {self.sample_rate_hz / 1e6} MHz")
else:
    # Fallback mock implementation if GNU Radio is not installed on this machine
    class SDRReceiver:
        def __init__(self, rf_freq_hz=15000e6, sample_rate_hz=2e6, gain_db=30):
            print("[WARN] GNU Radio not found. Initializing Simulation Mode.")
            self.rf_freq_hz = rf_freq_hz
            self.sample_rate_hz = sample_rate_hz
            self.gain_db = gain_db
            self.lo_freq_hz = 14850e6
            self.if_freq_hz = self.rf_freq_hz - self.lo_freq_hz

        def start(self):
            print("[Simulation] SDR Receiver thread started.")

        def stop(self):
            print("[Simulation] SDR Receiver thread stopped.")

        def wait(self):
            pass

        def set_rf_freq(self, rf_freq_hz):
            self.rf_freq_hz = rf_freq_hz
            self.if_freq_hz = self.rf_freq_hz - self.lo_freq_hz
            print(f"[Simulation] Tuned to IF: {self.if_freq_hz / 1e6} MHz (RF: {self.rf_freq_hz / 1e6} MHz)")

        def set_gain(self, gain_db):
            self.gain_db = gain_db
            print(f"[Simulation] Set Gain: {self.gain_db} dB")
            
        def set_sample_rate(self, sample_rate_hz):
            self.sample_rate_hz = sample_rate_hz
            print(f"[Simulation] Set Sample Rate: {self.sample_rate_hz / 1e6} MHz")
