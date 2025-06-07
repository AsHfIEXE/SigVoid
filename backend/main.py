from fastapi import FastAPI, WebSocket, Request, HTTPException, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware # Needed for development if frontend served separately
import asyncio
import json
from collections import deque
from typing import Dict, Set
import re
import time

# Import updated modules
from backend.database.database import init_db, get_db_connection, get_setting, set_setting
from backend import serial_reader
from backend import analyzer
from backend import alerts
from backend import exporter
from backend import cleanup

app = FastAPI()
templates = Jinja2Templates(directory="frontend/templates")

# Allow CORS for development (adjust in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allows all origins during dev, change to specific origins in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global for diagnostics data and serial queue
diagnostics_data: Dict = {"free_heap": 0, "uptime": 0}
serial_data_queue: asyncio.Queue = asyncio.Queue()

@app.on_event("startup")
async def startup_event():
    await init_db()
    # Read initial ESP config from DB and set serial_reader's config
    esp_ap_ssid = await get_setting('esp_ap_ssid')
    esp_ap_password = await get_setting('esp_ap_password')
    # serial_reader expects these to be set before it tries to open port
    # The actual sending to ESP happens when requested by UI via /esp-config
    # We still need to pass port/baud from run.sh to serial_reader directly
    
    # Start the serial reading task in the background
    asyncio.create_task(serial_reader.read_serial_async_queue(serial_data_queue))

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/export/{format}")
async def export_logs(format: str, min_score: float = 0.0, mac_filter: str = "", ssid_filter: str = "", preset: str = "all"):
    if format not in ["csv", "json"]:
        raise HTTPException(status_code=400, detail="Invalid format")
    response = await exporter.export_data(format, min_score, mac_filter, ssid_filter, preset)
    return JSONResponse(content=response)

@app.post("/ban/{mac}")
async def ban_device(mac: str):
    response = await exporter.ban_device(mac)
    return JSONResponse(content=response)

@app.post("/cleanup")
async def cleanup_storage():
    response = await cleanup.cleanup_logs()
    await cleanup.prune_blacklist() # Also prune blacklist during general cleanup
    return JSONResponse(content=response)

@app.get("/diagnostics")
async def get_diagnostics():
    return JSONResponse(content=diagnostics_data)

@app.get("/esp-config")
async def get_esp_config():
    ssid = await get_setting('esp_ap_ssid')
    password = await get_setting('esp_ap_password')
    return JSONResponse(content={"ssid": ssid, "password": password})

@app.post("/esp-config")
async def update_esp_config(ssid: str = Form(...), password: str = Form(...)):
    await set_setting('esp_ap_ssid', ssid)
    await set_setting('esp_ap_password', password)
    
    # Send commands to ESP8266 via serial
    ssid_sent = await serial_reader.send_command(f"SET_AP_SSID:{ssid}")
    pass_sent = await serial_reader.send_command(f"SET_AP_PASS:{password}")

    if ssid_sent and pass_sent:
        return JSONResponse(content={"status": "ESP config updated and sent to device."})
    else:
        raise HTTPException(status_code=500, detail="Failed to send config to ESP8266. Check serial connection.")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    # Send initial state
    current_devices = await exporter.get_filtered_devices() # Fetch all current devices from DB
    await websocket.send_json({
        "devices": current_devices,
        "diagnostics": diagnostics_data
    })

    while True:
        try:
            # Get data from the queue (non-blocking)
            data = await serial_data_queue.get() 
            
            if data["type"] == "diagnostics":
                diagnostics_data.update({
                    "free_heap": data.get("free_heap", 0),
                    "uptime": data.get("uptime", 0) / 1000.0 # Convert to seconds
                })
            else:
                mac = data.get("mac")
                if not mac:
                    print(f"Received data without MAC: {data}")
                    continue

                packet_type = data["type"]
                timestamp_ms = data.get("timestamp")
                current_time_s = timestamp_ms / 1000.0 if timestamp_ms else time.time()

                async with await get_db_connection() as db:
                    # Fetch existing device data
                    cursor = await db.execute("SELECT * FROM devices WHERE mac = ?", (mac,))
                    row = await cursor.fetchone()
                    
                    device_data = {}
                    if row:
                        device_data = {k: row[k] for k in row.keys()}
                        # Deserialize JSON fields from DB
                        device_data['ssid_list'] = set(json.loads(device_data['ssid_list']))
                        device_data['rssi_list'] = json.loads(device_data['rssi_list'])
                        device_data['timestamps'] = json.loads(device_data['timestamps'])
                        device_data['channel_counts'] = json.loads(device_data['channel_counts'])
                        device_data['ssid_history'] = deque(json.loads(device_data['ssid_history']), maxlen=analyzer.MAX_SSID_HISTORY)
                    else:
                        device_data = {
                            "vendor": await analyzer.oui_lookup(mac),
                            "ssid_list": set(),
                            "rssi_list": [],
                            "timestamps": [],
                            "deauth_count": 0,
                            "channel_counts": {},
                            "ssid_history": deque(maxlen=analyzer.MAX_SSID_HISTORY), # Store history for pattern score
                            "anomaly_score": 0.0,
                            "persistence_score": 0.0,
                            "pattern_score": 0.0,
                        }
                    
                    if packet_type == "probe":
                        ssid = data.get("ssid")
                        rssi = data.get("rssi")
                        channel = data.get("channel")
                        bssid = data.get("bssid")

                        if ssid:
                            device_data["ssid_list"].add(ssid)
                            device_data["ssid_history"].append(ssid) # Add to history
                        if rssi:
                            device_data["rssi_list"].append(rssi)
                        if timestamp_ms:
                            device_data["timestamps"].append(timestamp_ms)
                        if channel:
                            device_data["channel_counts"][str(channel)] = device_data["channel_counts"].get(str(channel), 0) + 1
                        
                        # Keep lists from growing indefinitely (optional, for long-running systems)
                        MAX_DATA_POINTS = 500
                        device_data["rssi_list"] = device_data["rssi_list"][-MAX_DATA_POINTS:]
                        device_data["timestamps"] = device_data["timestamps"][-MAX_DATA_POINTS:]

                        # Calculate scores based on updated data
                        total_devices = (await db.execute("SELECT COUNT(*) FROM devices")).fetchone()[0] + 1 # +1 for current device if new
                        device_data["anomaly_score"] = analyzer.calculate_anomaly_score(device_data, total_devices)
                        device_data["persistence_score"] = analyzer.calculate_persistence_score(device_data)
                        device_data["pattern_score"] = analyzer.calculate_pattern_score(device_data)

                        if await analyzer.detect_evil_twin(db, mac, ssid, bssid):
                            device_data["anomaly_score"] = min(1.0, device_data["anomaly_score"] + 0.3)
                    
                    elif packet_type == "deauth":
                        device_data["deauth_count"] = device_data.get("deauth_count", 0) + 1
                        total_devices = (await db.execute("SELECT COUNT(*) FROM devices")).fetchone()[0] + 1
                        device_data["anomaly_score"] = analyzer.calculate_anomaly_score(device_data, total_devices)
                    
                    # Update device state in DB
                    await exporter.upsert_device_state(mac, device_data)
                    # Log raw packet to DB (optional, depending on desired log granularity)
                    await exporter.log_packet_to_db(mac, data, device_data)
                    
                    banned_macs = await exporter.get_banned_macs()
                    if mac in banned_macs:
                        device_data["anomaly_score"] = max(device_data["anomaly_score"], 0.95) # Flag banned as high risk
                        print(f"Banned MAC {mac} detected!")

                    if device_data["anomaly_score"] > 0.8 or device_data["deauth_count"] > 5:
                        await alerts.send_alert(mac, device_data)
                
                # Fetch all devices again to ensure all filters and updates are applied for UI
                # In a high-traffic app, you might only send updates for changed devices.
                # For this dashboard, re-fetching all allows filters to work correctly live.
                current_devices = await exporter.get_filtered_devices()
                
            await websocket.send_json({
                "devices": current_devices,
                "diagnostics": diagnostics_data
            })
        except asyncio.CancelledError:
            print("WebSocket disconnected.")
            break
        except Exception as e:
            print(f"WebSocket error: {e}")
            await asyncio.sleep(1) # Prevent tight loop on error