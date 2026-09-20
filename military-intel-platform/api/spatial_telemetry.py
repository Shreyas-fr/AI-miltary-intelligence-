import asyncio
import json
import logging
import math
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from pydantic import BaseModel
from typing import List, Dict, Optional, Set
import time
import uuid

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("spatial_engine")

app = FastAPI(title="Spatial Telemetry Engine")

# Connected WebSocket clients (Frontend Viewers)
active_connections: Set[WebSocket] = set()

# In-memory store of recent telemetry for new clients
latest_telemetry: Dict[str, dict] = {}

class CameraMetadata(BaseModel):
    K: List[List[float]]
    R: List[List[float]]
    t: List[float]
    camera_position_geo: Optional[List[float]] = None

class DetectionPayload(BaseModel):
    asset_id: str
    class_name: str
    confidence: float
    threat_level: float
    bbox_2d: List[float] # [x_min, y_min, x_max, y_max]
    camera_metadata: CameraMetadata

def pixel_to_world(u: float, v: float, K: np.ndarray, R: np.ndarray, t: np.ndarray, ground_altitude: float = 0.0) -> Optional[List[float]]:
    """
    Project 2D pixel to 3D world coordinate using Camera Intrinsics and Extrinsics.
    """
    try:
        # 1. Pixel to Normalized Device Coordinates
        pixel_homogenous = np.array([u, v, 1.0])
        K_inv = np.linalg.inv(K)
        ray_camera = K_inv @ pixel_homogenous
        
        # 2. Camera coordinate ray to World coordinate ray
        R_inv = np.linalg.inv(R)
        ray_world = R_inv @ ray_camera
        norm = np.linalg.norm(ray_world)
        if norm == 0:
            return None
        ray_world = ray_world / norm
        
        # 3. Ray-Plane Intersection (Ground Plane Z = ground_altitude)
        cam_x, cam_y, cam_z = t.flatten()
        dir_x, dir_y, dir_z = ray_world
        
        # If looking parallel to or away from ground
        if dir_z >= 0 and cam_z > ground_altitude: 
            return None
            
        if dir_z == 0:
            return None
            
        scale = (ground_altitude - cam_z) / dir_z
        
        intersect_x = cam_x + scale * dir_x
        intersect_y = cam_y + scale * dir_y
        intersect_z = ground_altitude
        
        return [intersect_x, intersect_y, intersect_z]
    except Exception as e:
        logger.error(f"Projection error: {e}")
        return None

@app.websocket("/ws/telemetry")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.add(websocket)
    logger.info(f"Client connected. Total clients: {len(active_connections)}")
    
    # Send current state
    for asset_id, data in latest_telemetry.items():
        try:
            await websocket.send_text(json.dumps(data))
        except Exception:
            pass

    try:
        while True:
            # Keep connection alive
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        active_connections.remove(websocket)
        logger.info(f"Client disconnected. Total clients: {len(active_connections)}")

async def broadcast_message(message: dict):
    if not active_connections:
        return
    
    msg_str = json.dumps(message)
    dead_connections = set()
    
    for connection in active_connections:
        try:
            await connection.send_text(msg_str)
        except Exception:
            dead_connections.add(connection)
            
    for dc in dead_connections:
        active_connections.remove(dc)

@app.post("/api/ingest")
async def ingest_detection(payload: DetectionPayload):
    """
    Ingest a 2D bounding box and output 3D telemetry to websockets.
    """
    x_min, y_min, x_max, y_max = payload.bbox_2d
    u = (x_min + x_max) / 2.0
    v = y_max # Bottom-center footprint for ground targets
    
    K = np.array(payload.camera_metadata.K)
    R = np.array(payload.camera_metadata.R)
    t = np.array(payload.camera_metadata.t).reshape(3, 1)
    
    world_pt = pixel_to_world(u, v, K, R, t)
    
    if world_pt is None:
        return {"status": "ignored", "reason": "ray did not intersect ground"}
        
    telemetry_msg = {
        "asset_id": payload.asset_id,
        "class_name": payload.class_name,
        "confidence": payload.confidence,
        "threat_level": payload.threat_level,
        "bbox_2d": payload.bbox_2d,
        "world_coords_3d": {
            "lon": world_pt[0],
            "lat": world_pt[1],
            "alt_m": world_pt[2]
        },
        "velocity_vector": [0, 0, 0], # Can be derived from Kalman filter across frames
        "timestamp": time.time()
    }
    
    latest_telemetry[payload.asset_id] = telemetry_msg
    await broadcast_message(telemetry_msg)
    
    return {"status": "success", "projected_point": world_pt}

# Background Mock Generator
async def generate_mock_telemetry():
    """
    Generates mock circular moving targets over Pune, India.
    (Approx: Lat 18.2602, Lon 73.1910)
    """
    center_lat = 18.2602
    center_lon = 73.1910
    
    assets = [
        {"id": "tgt-alpha-1", "class": "armored_vehicle", "radius": 0.005, "speed": 0.5, "angle": 0, "threat": 85},
        {"id": "tgt-bravo-2", "class": "infantry_squad", "radius": 0.002, "speed": -0.2, "angle": 1.5, "threat": 60},
        {"id": "tgt-charlie-3", "class": "mobile_artillery", "radius": 0.01, "speed": 0.3, "angle": 3.14, "threat": 95},
    ]
    
    while True:
        for a in assets:
            a["angle"] += a["speed"] * 0.1
            current_lat = center_lat + math.sin(a["angle"]) * a["radius"]
            current_lon = center_lon + math.cos(a["angle"]) * a["radius"]
            
            telemetry_msg = {
                "asset_id": a["id"],
                "class_name": a["class"],
                "confidence": round(0.85 + (math.sin(time.time()) * 0.1), 2),
                "threat_level": a["threat"],
                "bbox_2d": [100, 100, 150, 150], # Mocked
                "world_coords_3d": {
                    "lon": current_lon,
                    "lat": current_lat,
                    "alt_m": 0.0
                },
                "velocity_vector": [
                    math.cos(a["angle"]) * a["speed"] * 10,
                    math.sin(a["angle"]) * a["speed"] * 10,
                    0
                ],
                "timestamp": time.time()
            }
            
            latest_telemetry[a["id"]] = telemetry_msg
            await broadcast_message(telemetry_msg)
            
        await asyncio.sleep(0.1) # 10 FPS updates

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(generate_mock_telemetry())
    logger.info("Started mock telemetry generator in background.")
    # logger.info("Startup complete. (Mock telemetry deactivated for live data feed)")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
