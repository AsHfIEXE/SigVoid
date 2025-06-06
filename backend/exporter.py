import sqlite3
import csv
import json
import asyncio
from typing import Dict
import time
import re

async def log_to_db(mac: str, device: Dict, data: Dict):
    try:
        conn = sqlite3.connect("database/oui.db")
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO logs (timestamp, mac, ssid, rssi, anomaly_score, persistence_score, pattern_score, deauth_count, channel) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (data.get("timestamp", time.time()) / 1000.0, mac, data.get("ssid", ""), data.get("rssi", 0), 
             device["anomaly_score"], device["persistence_score"], device["pattern_score"], device["deauth_count"], data.get("channel", 0))
        )
        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        print(f"DB error: {e}")

async def export_data(devices: Dict, format: str, min_score: float = 0.0, mac_filter: str = "", ssid_filter: str = "", preset: str = "all") -> Dict:
    filtered = devices.copy()
    
    # Apply filters
    if mac_filter:
        mac_regex = re.compile(mac_filter, re.IGNORECASE)
        filtered = {mac: data for mac, data in filtered.items() if mac_regex.search(mac)}
    
    if ssid_filter:
        ssid_regex = re.compile(ssid_filter, re.IGNORECASE)
        filtered = {mac: data for mac, data in filtered.items() if any(ssid_regex.search(ssid) for ssid in data["ssid_list"])}
    
    if min_score > 0:
        filtered = {mac: data for mac, data in filtered.items() if data["anomaly_score"] >= min_score}
    
    if preset == "high_risk":
        filtered = {mac: data for mac, data in filtered.items() if data["anomaly_score"] > 0.8 or data["deauth_count"] > 5}
    elif preset == "recent":
        cutoff = time.time() - 3600  # Last hour
        filtered = {mac: data for mac, data in filtered.items() if any(ts >= cutoff for ts in data["timestamps"])}
    
    if format == "csv":
        with open("export.csv", "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["MAC", "Vendor", "SSIDs", "Anomaly Score", "Persistence Score", "Pattern Score", "Deauth Count", "Channels"])
            for mac, data in filtered.items():
                writer.writerow([mac, data["vendor"], ",".join(data["ssid_list"]), 
                                f"{data['anomaly_score']:.2f}", f"{data['persistence_score']:.2f}", 
                                f"{data['pattern_score']:.2f}", data["deauth_count"], 
                                ",".join(map(str, data["channel_counts"].keys()))])
        return {"status": "Exported to export.csv"}
    elif format == "json":
        with open("export.json", "w") as f:
            json.dump(filtered, f, indent=2)
        return {"status": "Exported to export.json"}
    return {"error": "Invalid format"}

async def ban_device(mac: str) -> Dict:
    with open("banned_macs.txt", "a") as f:
        f.write(f"{mac}\n")
    return {"status": f"MAC {mac} added to ban list"}