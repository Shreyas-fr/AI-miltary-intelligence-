import { useEffect, useState, useRef } from 'react';
import { Activity, Power, Radio, Settings2, Terminal as TerminalIcon, FileImage } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, ResponsiveContainer } from 'recharts';
import './index.css';

const API_URL = 'http://localhost:8001';
const WS_URL = 'ws://localhost:8001/ws/fft';

interface SDRState {
  center_freq_hz: number;
  sample_rate_hz: number;
  gain_db: number;
  is_running: boolean;
}

function App() {
  const [state, setState] = useState<SDRState>({
    center_freq_hz: 137912500,
    sample_rate_hz: 1200000,
    gain_db: 34,
    is_running: false,
  });
  
  const [fftData, setFftData] = useState<any[]>([]);
  const [telemetryLogs, setTelemetryLogs] = useState<string[]>([]);
  const [decodedImageUrl, setDecodedImageUrl] = useState<string | null>(null);
  
  const wsRef = useRef<WebSocket | null>(null);
  const terminalEndRef = useRef<HTMLDivElement | null>(null);

  // Fetch initial state
  useEffect(() => {
    fetch(`${API_URL}/api/state`)
      .then(res => res.json())
      .then(data => setState(data))
      .catch(err => console.error("Failed to fetch state", err));
  }, []);

  // WebSocket connection
  useEffect(() => {
    wsRef.current = new WebSocket(WS_URL);
    
    wsRef.current.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      
      switch (msg.type) {
        case 'fft':
          if (msg.data && msg.data.length > 0) {
            const formattedData = msg.data.map((val: number, index: number) => ({
              bin: index,
              magnitude: val
            }));
            setFftData(formattedData);
          }
          break;
        case 'text':
          setTelemetryLogs(prev => [...prev, msg.message]);
          break;
        case 'image':
          setDecodedImageUrl(msg.url);
          break;
        case 'clear':
          setFftData([]);
          setTelemetryLogs([]);
          setDecodedImageUrl(null);
          break;
        default:
          break;
      }
    };

    return () => {
      wsRef.current?.close();
    };
  }, []);

  // Scroll to bottom of terminal log when new log arrives
  useEffect(() => {
    if (terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [telemetryLogs]);

  const handleUpdateState = (field: keyof SDRState, value: number) => {
    const newState = { ...state, [field]: value };
    setState(newState);
    
    fetch(`${API_URL}/api/state`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newState)
    });
  };

  const togglePower = () => {
    const endpoint = state.is_running ? '/api/stop' : '/api/start';
    fetch(`${API_URL}${endpoint}`, { method: 'POST' })
      .then(() => {
        setState(prev => {
          const nextRunning = !prev.is_running;
          if (!nextRunning) {
            // Clearing states manually on stop
            setFftData([]);
            setTelemetryLogs([]);
            setDecodedImageUrl(null);
          }
          return { ...prev, is_running: nextRunning };
        });
      });
  };

  return (
    <div className="dashboard-container">
      
      {/* Sidebar Controls */}
      <div className="panel" style={{ gridColumn: '1 / 2' }}>
        <h2 className="title-glow">
          <Settings2 size={22} color="var(--primary)" />
          SDR Settings
        </h2>
        
        <div className="status-badge" style={{ alignSelf: 'flex-start' }}>
          <div className={`status-indicator ${state.is_running ? 'active' : ''}`}></div>
          {state.is_running ? 'SYSTEM DECODING' : 'SYSTEM STANDBY'}
        </div>

        <div className="control-group" style={{ marginTop: '16px' }}>
          <label>Target Frequency (Hz)</label>
          <input 
            type="number" 
            className="control-input"
            value={state.center_freq_hz}
            onChange={(e) => handleUpdateState('center_freq_hz', Number(e.target.value))}
          />
        </div>

        <div className="control-group">
          <label>SDR Bandwidth (Hz)</label>
          <input 
            type="number" 
            className="control-input"
            value={state.sample_rate_hz}
            onChange={(e) => handleUpdateState('sample_rate_hz', Number(e.target.value))}
          />
        </div>

        <div className="control-group">
          <label>Gain Control</label>
          <input 
            type="range" 
            min="0" 
            max="50"
            value={state.gain_db}
            onChange={(e) => handleUpdateState('gain_db', Number(e.target.value))}
          />
          <span style={{ fontFamily: 'monospace', color: 'var(--primary)', fontSize: '0.9rem' }}>
            {state.gain_db} dB
          </span>
        </div>

        <button 
          className={state.is_running ? 'btn-danger' : 'btn-primary'}
          onClick={togglePower}
          style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', marginTop: 'auto' }}
        >
          <Power size={18} />
          {state.is_running ? 'Stop Receiver' : 'Start Receiver'}
        </button>
      </div>

      {/* Main Spectrum Display */}
      <div className="panel" style={{ gridColumn: '2 / 3' }}>
        <div className="header-bar">
          <h2 className="title-glow">
            <Radio size={22} color="var(--primary)" />
            IF Spectrum Analyzer
          </h2>
          <Activity color={state.is_running ? 'var(--primary)' : '#444'} />
        </div>
        
        <div className="stats-row">
          <div className="stat-card">
            <span className="stat-label">Frequency (IF)</span>
            <span className="stat-value">{(state.center_freq_hz / 1e6).toFixed(4)} MHz</span>
          </div>
          <div className="stat-card">
            <span className="stat-label">Acquisition Band</span>
            <span className="stat-value">{(state.sample_rate_hz / 1e3).toFixed(1)} kHz</span>
          </div>
          <div className="stat-card">
            <span className="stat-label">Signal Peak</span>
            <span className="stat-value">
              {fftData.length > 0 
                ? `${Math.round(Math.max(...fftData.map(d => d.magnitude)))} dBm`
                : 'N/A'}
            </span>
          </div>
        </div>

        <div className="plot-container">
          {state.is_running ? (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={fftData} margin={{ top: 10, right: 20, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="bin" stroke="#444" tick={false} />
                <YAxis domain={[-100, -10]} stroke="#444" />
                <Line 
                  type="monotone" 
                  dataKey="magnitude" 
                  stroke="var(--primary)" 
                  strokeWidth={1.5}
                  dot={false}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div style={{ 
              position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, 
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: '#444', fontFamily: 'monospace', fontSize: '1rem',
              flexDirection: 'column', gap: '12px'
            }}>
              <Radio size={40} opacity={0.15} />
              AWAITING CARRIER SIGNAL
            </div>
          )}
        </div>
      </div>

      {/* Decoded Payloads Panel */}
      <div className="panel" style={{ gridColumn: '3 / 4' }}>
        <div className="header-bar">
          <h2 className="title-glow">
            <TerminalIcon size={22} color="var(--primary)" />
            Signal Decoder
          </h2>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: '14px' }}>
          {/* Text/Telemetry Stream */}
          <div style={{ display: 'flex', flexDirection: 'column', flexGrow: 1, overflow: 'hidden' }}>
            <label style={{ fontSize: '0.8rem', color: '#888', textTransform: 'uppercase', marginBottom: '6px' }}>
              Decoded ASCII Data
            </label>
            <div className="terminal-container">
              {state.is_running ? (
                telemetryLogs.map((log, index) => (
                  <div key={index} className="terminal-line">
                    &gt; {log}
                  </div>
                ))
              ) : (
                <div style={{ color: '#444', fontStyle: 'italic' }}>Waiting for frames...</div>
              )}
              <div ref={terminalEndRef} />
            </div>
          </div>

          {/* Image Decoder */}
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <label style={{ fontSize: '0.8rem', color: '#888', textTransform: 'uppercase', marginBottom: '6px' }}>
              Decoded Telemetry Imagery (APT)
            </label>
            <div className="image-decode-container">
              {state.is_running && decodedImageUrl ? (
                <>
                  <img src={decodedImageUrl} alt="Satellite Decode" />
                  <div className="image-scanline-overlay"></div>
                </>
              ) : (
                <div style={{ 
                  display: 'flex', flexDirection: 'column', alignItems: 'center', 
                  gap: '8px', color: '#444', fontSize: '0.9rem', fontFamily: 'monospace' 
                }}>
                  <FileImage size={32} opacity={0.2} />
                  {state.is_running ? 'RECONSTRUCTING IMAGE MATRIX...' : 'DECODER IDLE'}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
      
    </div>
  );
}

export default App;
