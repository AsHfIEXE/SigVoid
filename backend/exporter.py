import csv
import json
import asyncio
from typing import Dict, List
import time
import re
from backend.database.database import get_db_connection

async def upsert_device_state(mac: str, device_data: Dict):
    """
    Updates or inserts a device's state in the 'devices' table.
    Expects device_data to be ready for JSON serialization for list/dict fields.
    """
    async with await get_db_connection() as db:
        await db.execute("""
            INSERT OR REPLACE INTO devices (
                mac, vendor, ssid_list, rssi_list, timestamps,
                anomaly_score, persistence_score, pattern_score,
                deauth_count, channel_counts, ssid_history
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            mac,
            device_data.get("vendor"),
            json.dumps(list(device_data.get("ssid_list", []))), # Convert set to list
            json.dumps(device_data.get("rssi_list", [])),
            json.dumps(device_data.get("timestamps", [])),
            device_data.get("anomaly_score", 0.0),
            device_data.get("persistence_score", 0.0),
            device_data.get("pattern_score", 0.0),
            device_data.get("deauth_count", 0),
            json.dumps(device_data.get("channel_counts", {})),
            json.dumps(list(device_data.get("ssid_history", []))) # Convert deque to list
        ))
        await db.commit()

async def log_packet_to_db(mac: str, packet_data: Dict, device_summary: Dict):
    """Logs individual packet data to the 'logs' table."""
    async with await get_db_connection() as db:
        await db.execute(
            "INSERT INTO logs (timestamp, mac, ssid, rssi, anomaly_score, persistence_score, pattern_score, deauth_count, channel) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (packet_data.get("timestamp", time.time()) / 1000.0,
             mac,
             packet_data.get("ssid", ""),
             packet_data.get("rssi", 0),
             device_summary.get("anomaly_score", 0.0),
             device_summary.get("persistence_score", 0.0),
             device_summary.get("pattern_score", 0.0),
             device_summary.get("deauth_count", 0),
             packet_data.get("channel", 0))
        )
        await db.commit()

async def get_filtered_devices(min_score: float = 0.0, mac_filter: str = "", ssid_filter: str = "", preset: str = "all") -> Dict:
    query = "SELECT * FROM devices WHERE 1=1"
    params = []

    if preset == "high_risk":
        query += " AND (anomaly_score > 0.8 OR deauth_count > 5)"
    elif preset == "recent":
        cutoff = time.time() - 3600 # Last hour
        # This is a bit tricky with JSON string in DB. A LIKE query might be too broad.
        # For accurate recent check, consider last timestamp in timestamps list or a separate 'last_seen' column.
        # For now, we'll do a lenient check based on string.
        # Better: add a 'last_seen' column to devices table for efficient filtering.
        pass # Will filter in Python for now if 'recent' preset selected

    if min_score > 0:
        query += " AND anomaly_score >= ?"
        params.append(min_score)

    async with await get_db_connection() as db:
        cursor = await db.execute(query, params)
        all_devices_rows = await cursor.fetchall()
        
        filtered_devices = {}
        mac_regex = re.compile(mac_filter, re.IGNORECASE) if mac_filter else None
        ssid_regex = re.compile(ssid_filter, re.IGNORECASE) if ssid_filter else None
        
        for row in all_devices_rows:
            device_data = {k: row[k] for k in row.keys()} # Convert Row object to dict
            
            # Deserialize JSON fields
            device_data['ssid_list'] = json.loads(device_data['ssid_list'])
            device_data['rssi_list'] = json.loads(device_data['rssi_list'])
            device_data['timestamps'] = json.loads(device_data['timestamps'])
            device_data['channel_counts'] = json.loads(device_data['channel_counts'])
            device_data['ssid_history'] = json.loads(device_data['ssid_history']) # This will be a list now
            
            # Apply Python-side filters (especially for regex and 'recent' preset)
            if mac_regex and not mac_regex.search(device_data['mac']):
                continue
            if ssid_regex and not any(ssid_regex.search(ssid) for ssid in device_data['ssid_list']):
                continue
            if preset == "recent":
                cutoff = time.time() - 3600
                if not any(ts / 1000.0 >= cutoff for ts in device_data['timestamps']): # timestamps are in ms from ESP
                    continue

            filtered_devices[device_data['mac']] = device_data
            
    return filtered_devices

async def export_data(format: str, min_score: float = 0.0, mac_filter: str = "", ssid_filter: str = "", preset: str = "all") -> Dict:
    filtered_devices = await get_filtered_devices(min_score, mac_filter, ssid_filter, preset)
    
    if format == "csv":
        # Blocking file write, run in executor
        await asyncio.get_event_loop().run_in_executor(None, lambda: _export_csv(filtered_devices))
        return {"status": "Exported to export.csv"}
    elif format == "json":
        # Blocking file write, run in executor
        await asyncio.get_event_loop().run_in_executor(None, lambda: _export_json(filtered_devices))
        return {"status": "Exported to export.json"}
    return {"error": "Invalid format"}

def _export_csv(devices_data: Dict):
    with open("export.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["MAC", "Vendor", "SSIDs", "Anomaly Score", "Persistence Score", "Pattern Score", "Deauth Count", "Channels"])
        for mac, data in devices_data.items():
            writer.writerow([mac, data["vendor"], ",".join(data["ssid_list"]), 
                            f"{data['anomaly_score']:.2f}", f"{data['persistence_score']:.2f}", 
                            f"{data['pattern_score']:.2f}", data["deauth_count"], 
                            ",".join(map(str, data["channel_counts"].keys()))])

def _export_json(devices_data: Dict):
    with open("export.json", "w") as f:
        json.dump(devices_data, f, indent=2)

async def ban_device(mac: str) -> Dict:
    async with await get_db_connection() as db:
        await db.execute("INSERT OR REPLACE INTO banned_macs (mac, banned_at) VALUES (?, ?)", (mac, time.time()))
        await db.commit()
    return {"status": f"MAC {mac} added to ban list"}

async def get_banned_macs() -> List[str]:
    async with await get_db_connection() as db:
        cursor = await db.execute("SELECT mac FROM banned_macs")
        rows = await cursor.fetchall()
        return [row['mac'] for row in rows]