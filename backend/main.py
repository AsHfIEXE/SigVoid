from fastapi import FastAPI, WebSocket, Request, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import asyncio
from typing import Dict, Set, List
import serial_reader
import analyzer
import alerts
import exporter
import cleanup
import diagnostics
import re

app = FastAPI()
templates = Jinja2Templates(directory="frontend/templates")
devices: Dict[str, Dict] = {}
diagnostics_data: Dict = {"free_heap": 0, "uptime": 0}

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/export/{format}")
async def export_logs(format: str, min_score: float = 0.0, mac_filter: str = "", ssid_filter: str = "", preset: str = "all"):
    if format not in ["csv", "json"]:
        raise HTTPException(status_code=400, detail="Invalid format")
    return await exporter.export_data(devices, format, min_score, mac_filter, ssid_filter, preset)

@app.get("/ban/{mac}")
async def ban_device(mac: str):
    return await exporter.ban_device(mac)

@app.get("/cleanup")
async def cleanup_storage():
    return await cleanup.cleanup_logs()

@app.get("/diagnostics")
async def get_diagnostics():
    return diagnostics_data

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    await websocket.send_json({
        "devices": analyzer.summarize_devices(devices),
        "diagnostics": diagnostics_data
    })
    while True:
        try:
            data = await asyncio.get_event_loop().run_in_executor(None, serial_reader.read_serial)
            if data:
                if data["type"] == "diagnostics":
                    diagnostics_data.update({"free_heap": data["free_heap"], "uptime": data["uptime"]})
                else:
                    mac, packet_type = data["mac"], data["type"]
                    timestamp = data["timestamp"] / 1000.0
                    if mac not in devices:
                        devices[mac] = {
                            "ssid_list": set(),
                            "rssi_list": [],
                            "timestamps": [],
                            "channels": [],
                            "bssid_list": set(),
                            "vendor": analyzer.oui_lookup(mac),
                            "anomaly_score": 0.0,
                            "persistence_score": 0.0,
                            "deauth_count": 0,
                            "channel_counts": {},
                            "pattern_score": 0.0
                        }
                    
                    if packet_type == "probe":
                        devices[mac]["ssid_list"].add(data["ssid"])
                        devices[mac]["rssi_list"].append(data["rssi"])
                        devices[mac]["timestamps"].append(timestamp)
                        devices[mac]["channels"].append(data["channel"])
                        devices[mac]["bssid_list"].add(data["bssid"])
                        devices[mac]["channel_counts"][data["channel"]] = devices[mac]["channel_counts"].get(data["channel"], 0) + 1
                        devices[mac]["anomaly_score"] = analyzer.calculate_anomaly_score(devices[mac], len(devices))
                        devices[mac]["persistence_score"] = analyzer.calculate_persistence_score(devices[mac])
                        devices[mac]["pattern_score"] = analyzer.calculate_pattern_score(devices[mac])
                        if analyzer.detect_evil_twin(devices, mac, data["ssid"], data["bssid"]):
                            devices[mac]["anomaly_score"] = min(1.0, devices[mac]["anomaly_score"] + 0.3)
                    
                    elif packet_type == "deauth":
                        devices[mac]["deauth_count"] += 1
                        devices[mac]["anomaly_score"] = analyzer.calculate_anomaly_score(devices[mac], len(devices))
                    
                    if devices[mac]["anomaly_score"] > 0.8 or devices[mac]["deauth_count"] > 5:
                        await alerts.send_alert(mac, devices[mac])
                    
                    await exporter.log_to_db(mac, devices[mac], data)
                
                await websocket.send_json({
                    "devices": analyzer.summarize_devices(devices),
                    "diagnostics": diagnostics_data
                })
        except Exception as e:
            print(f"Error: {e}")
        await asyncio.sleep(0.05)