import cv2
import asyncio
import aiohttp
import threading
import queue
import atexit
import numpy as np
from scipy.spatial.transform import Rotation

INGEST_URL = "http://localhost:8000/api/ingest"

# 1. Camera Intrinsics (Calibrated values or sensor estimates)
fx, fy = 1200.0, 1200.0
cx, cy = 960.0, 540.0
K_MATRIX = [
    [fx, 0.0, cx],
    [0.0, fy, cy],
    [0.0, 0.0, 1.0]
]

def calculate_threat_score(class_name: str, confidence: float) -> float:
    base_threats = {
        "tank": 95.0,
        "military_truck": 75.0,
        "armored_vehicle": 85.0,
        "personnel": 40.0
    }
    base = base_threats.get(class_name.lower(), 50.0)
    return round(base * float(confidence), 1)

class AsyncTelemetryDispatcher:
    """
    Background worker that runs an asyncio event loop in a separate thread.
    This allows the synchronous main CV loop to offload network requests with zero latency.
    """
    def __init__(self, url=INGEST_URL, max_queue_size=100):
        self.url = url
        self.queue = queue.Queue(maxsize=max_queue_size)
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._start_loop, daemon=True)
        self.thread.start()
        atexit.register(self.stop)
        
    def _start_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._worker())
        
    async def _worker(self):
        # We reuse a single ClientSession for connection pooling and better performance
        async with aiohttp.ClientSession() as session:
            while True:
                try:
                    # Non-blocking get with a small timeout to allow clean shutdowns
                    payload = self.queue.get(timeout=0.1)
                    if payload is None: # Sentinel value to stop
                        break
                    
                    # Fire and forget concurrent request
                    asyncio.create_task(self._send_payload(session, payload))
                    self.queue.task_done()
                except queue.Empty:
                    continue
                except Exception as e:
                    print(f"Dispatcher error: {e}")
                    
    async def _send_payload(self, session, payload):
        try:
            async with session.post(self.url, json=payload, timeout=aiohttp.ClientTimeout(total=0.5)) as response:
                if response.status != 200:
                    pass # Optional: log failed ingestions
        except Exception:
            pass # Silently drop on network failure to avoid lagging the pipeline
            
    def stop(self):
        try:
            self.queue.put_nowait(None)
        except queue.Full:
            pass
        if self.thread.is_alive():
            self.thread.join(timeout=1.0)
            
    def dispatch(self, asset_id, class_name, conf, bbox, drone_telemetry):
        # Gimbal Attitude Mapping
        if "R" not in drone_telemetry and all(k in drone_telemetry for k in ("roll", "pitch", "yaw")):
            rot = Rotation.from_euler('zyx', [
                drone_telemetry["yaw"], 
                drone_telemetry["pitch"], 
                drone_telemetry["roll"]
            ], degrees=True)
            rotation_matrix = rot.as_matrix().tolist()
        else:
            rotation_matrix = drone_telemetry.get("R")

        payload = {
            "asset_id": str(asset_id),
            "class_name": str(class_name),
            "confidence": float(conf),
            "threat_level": calculate_threat_score(class_name, conf),
            "bbox_2d": [float(v) for v in bbox],
            "camera_metadata": {
                "K": K_MATRIX,
                "R": rotation_matrix,
                "t": drone_telemetry["t"],
                "camera_position_geo": [
                    drone_telemetry["lon"],
                    drone_telemetry["lat"],
                    drone_telemetry["alt"]
                ]
            }
        }
        
        # Zero-latency handoff to the background thread
        try:
            self.queue.put_nowait(payload)
        except queue.Full:
            pass # Drop frame if the network is so congested the queue is full

# Global singleton for easy drop-in replacement
dispatcher = AsyncTelemetryDispatcher()

def dispatch_detection(asset_id, class_name, conf, bbox, drone_telemetry):
    """
    Drop-in replacement for the synchronous dispatch_detection.
    It instantly hands off the detection to a background async worker.
    """
    dispatcher.dispatch(asset_id, class_name, conf, bbox, drone_telemetry)
