from fastapi import FastAPI, WebSocket, Request, HTTPException, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles # NEW IMPORT
import asyncio
import json
from collections import deque
import os # NEW IMPORT (needed for os.path.join)
import time # Used for timestamp comparison in anomaly detection (though mostly handled by ESP's ms timestamp)

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

# NEW: Mount the static files directory
# This tells FastAPI to serve files from the "frontend/static" directory
# when requests come in for URLs starting with "/frontend/static"
current_dir = os.path.dirname(os.path.abspath(__file__))
static_files_disk_path = os.path.join(current_dir, "..", "frontend", "static")
app.mount("/frontend/static", StaticFiles(directory=static_files_disk_path), name="frontend_static")


# Global for diagnostics data and serial queue
diagnostics_data: Dict = {"free_heap": 0, "uptime": 0}
serial_data_queue: asyncio.Queue = asyncio.Queue()

@app.on_event("startup")
async def startup_event():
    await init_db()
    # Read initial ESP config from DB and set serial_reader's config
    # The actual sending to ESP happens when requested by UI via /esp-config endpoint
    # The serial_reader module needs its internal port config set, which run.sh handles.
    
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
            elif data["type"] == "info" or data["type"] == "error":
                # Handle ESP info/error messages, could log them or push to UI as toasts
                print(f"ESP Message: {data.get('message')}")
            else: # Packet data (probe or deauth)
                mac = data.get("mac")
                if not mac:
                    print(f"Received data without MAC: {data}")
                    continue

                packet_type = data["type"]
                timestamp_ms = data.get("timestamp")
                
                async with await get_db_connection() as db:
                    # Fetch existing device data from DB
                    cursor = await db.execute("SELECT * FROM devices WHERE mac = ?", (mac,))
                    row = await cursor.fetchone()
                    
                    device_data_db = {}
                    if row:
                        device_data_db = {k: row[k] for k in row.keys()}
                        # Deserialize JSON fields from DB
                        device_data_db['ssid_list'] = set(json.loads(device_data_db.get('ssid_list', '[]'))) # Convert to set
                        device_data_db['rssi_list'] = json.loads(device_data_db.get('rssi_list', '[]'))
                        device_data_db['timestamps'] = json.loads(device_data_db.get('timestamps', '[]'))
                        device_data_db['channel_counts'] = json.loads(device_data_db.get('channel_counts', '{}'))
                        device_data_db['ssid_history'] = deque(json.loads(device_data_db.get('ssid_history', '[]')), maxlen=analyzer.MAX_SSID_HISTORY) # Re-create deque
                    else:
                        # Initialize new device data
                        device_data_db = {
                            "vendor": await analyzer.oui_lookup(mac),
                            "ssid_list": set(),
                            "rssi_list": [],
                            "timestamps": [],
                            "deauth_count": 0,
                            "channel_counts": {},
                            "ssid_history": deque(maxlen=analyzer.MAX_SSID_HISTORY),
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
                            device_data_db["ssid_list"].add(ssid)
                            device_data_db["ssid_history"].append(ssid) # Add to history
                        if rssi is not None:
                            device_data_db["rssi_list"].append(rssi)
                        if timestamp_ms:
                            device_data_db["timestamps"].append(timestamp_ms)
                        if channel:
                            device_data_db["channel_counts"][str(channel)] = device_data_db["channel_counts"].get(str(channel), 0) + 1
                        
                        # Keep lists from growing indefinitely (e.g., last 500 points)
                        MAX_DATA_POINTS = 500
                        device_data_db["rssi_list"] = device_data_db["rssi_list"][-MAX_DATA_POINTS:]
                        device_data_db["timestamps"] = device_data_db["timestamps"][-MAX_DATA_POINTS:]

                        # Calculate scores based on updated data
                        # We need total_devices for adaptive anomaly scoring, so fetch dynamically
                        total_devices_cursor = await db.execute("SELECT COUNT(*) FROM devices")
                        total_devices = (await total_devices_cursor.fetchone())[0] # Get count of devices in DB
                        
                        device_data_db["anomaly_score"] = analyzer.calculate_anomaly_score(device_data_db, total_devices)
                        device_data_db["persistence_score"] = analyzer.calculate_persistence_score(device_data_db)
                        device_data_db["pattern_score"] = analyzer.calculate_pattern_score(device_data_db)

                        if await analyzer.detect_evil_twin(db, mac, ssid, bssid):
                            device_data_db["anomaly_score"] = min(1.0, device_data_db["anomaly_score"] + 0.3) # Boost score for evil twin
                    
                    elif packet_type == "deauth":
                        device_data_db["deauth_count"] = device_data_db.get("deauth_count", 0) + 1
                        total_devices_cursor = await db.execute("SELECT COUNT(*) FROM devices")
                        total_devices = (await total_devices_cursor.fetchone())[0]
                        device_data_db["anomaly_score"] = analyzer.calculate_anomaly_score(device_data_db, total_devices)
                    
                    # Check if MAC is banned and update anomaly score if needed
                    banned_macs = await exporter.get_banned_macs()
                    if mac in banned_macs:
                        device_data_db["anomaly_score"] = max(device_data_db["anomaly_score"], 0.95) # Flag banned as very high risk
                        # print(f"Banned MAC {mac} detected and score boosted!") # Debugging

                    # Update device state in DB
                    await exporter.upsert_device_state(mac, device_data_db)
                    
                    # Log raw packet to DB
                    await exporter.log_packet_to_db(mac, data, device_data_db) # Pass full packet data and current device summary

                    # Send alert if thresholds are met
                    if device_data_db["anomaly_score"] > 0.8 or device_data_db["deauth_count"] > 5:
                        await alerts.send_alert(mac, device_data_db)
                
                # Fetch all devices again to ensure all filters and updates are applied for UI
                # This is more robust than trying to update Alpine store piece by piece
                current_devices = await exporter.get_filtered_devices()
                
            # Send the updated state to the connected WebSocket client
            await websocket.send_json({
                "devices": current_devices,
                "diagnostics": diagnostics_data
            })
        except asyncio.CancelledError:
            print("WebSocket disconnected.")
            break # Exit loop if client disconnects
        except Exception as e:
            print(f"WebSocket processing error: {e}")
            await asyncio.sleep(1) # Prevent tight loop on error