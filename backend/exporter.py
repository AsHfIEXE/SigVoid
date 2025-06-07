# backend/exporter.py
import csv
import json
import asyncio
from typing import Dict, List
import time
import re
from backend.database.database import get_db_connection

# Helper function to run blocking file I/O in an executor
def _blocking_file_write(file_path: str, content, mode: str = 'w', is_json: bool = False):
    """Writes content to a file. Can handle JSON dumping."""
    with open(file_path, mode, newline='' if mode == 'w' and file_path.endswith('.csv') else '') as f:
        if is_json:
            json.dump(content, f, indent=2)
        else:
            f.write(content)

async def upsert_device_state(mac: str, device_data: Dict):
    """
    Updates or inserts a device's state in the 'devices' table.
    Expects device_data to be ready for JSON serialization for list/dict/set fields.
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
            json.dumps(list(device_data.get("ssid_list", []))), # Convert set to list for JSON
            json.dumps(device_data.get("rssi_list", [])),
            json.dumps(device_data.get("timestamps", [])),
            device_data.get("anomaly_score", 0.0),
            device_data.get("persistence_score", 0.0),
            device_data.get("pattern_score", 0.0),
            device_data.get("deauth_count", 0),
            json.dumps(device_data.get("channel_counts", {})),
            json.dumps(list(device_data.get("ssid_history", []))) # Convert deque to list for JSON
        ))
        await db.commit()

async def log_packet_to_db(mac: str, packet_data: Dict, device_summary: Dict):
    """Logs individual packet data to the 'logs' table."""
    async with await get_db_connection() as db:
        await db.execute(
            "INSERT INTO logs (timestamp, mac, ssid, rssi, anomaly_score, persistence_score, pattern_score, deauth_count, channel) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (packet_data.get("timestamp", time.time()) / 1000.0, # Timestamps from ESP are in ms
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

    # Apply database-level filters first for efficiency
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
            device_data['ssid_list'] = json.loads(device_data.get('ssid_list', '[]'))
            device_data['rssi_list'] = json.loads(device_data.get('rssi_list', '[]'))
            device_data['timestamps'] = json.loads(device_data.get('timestamps', '[]'))
            device_data['channel_counts'] = json.loads(device_data.get('channel_counts', '{}'))
            device_data['ssid_history'] = json.loads(device_data.get('ssid_history', '[]'))
            
            # Apply Python-side filters (especially for regex and 'recent' preset)
            if mac_regex and not mac_regex.search(device_data['mac']):
                continue
            if ssid_regex and not any(ssid_regex.search(ssid) for ssid in device_data['ssid_list']):
                continue
            
            if preset == "recent":
                # Convert ESP's milliseconds timestamp to seconds for cutoff comparison
                cutoff_time_s = time.time() - 3600 # Last hour
                # Check if *any* timestamp in the list is newer than cutoff
                if not any(ts_ms / 1000.0 >= cutoff_time_s for ts_ms in device_data['timestamps']):
                    continue
            elif preset == "high_risk":
                # This filter is already handled by `anomaly_score > 0.8 OR deauth_count > 5`
                # which can be added directly to the SQL query for more efficiency.
                # Adding it here to ensure it's always applied if preset is used.
                if not (device_data['anomaly_score'] > 0.8 or device_data['deauth_count'] > 5):
                    continue

            filtered_devices[device_data['mac']] = device_data
            
    return filtered_devices

async def export_data(format: str, min_score: float = 0.0, mac_filter: str = "", ssid_filter: str = "", preset: str = "all") -> Dict:
    filtered_devices = await get_filtered_devices(min_score, mac_filter, ssid_filter, preset)
    
    if format == "csv":
        csv_file_path = "export.csv"
        # Blocking file write, run in executor
        await asyncio.get_event_loop().run_in_executor(
            None, 
            lambda: _export_csv_blocking(csv_file_path, filtered_devices)
        )
        return {"status": f"Exported high-risk devices to {csv_file_path}"}
    elif format == "json":
        json_file_path = "export.json"
        # Blocking file write, run in executor
        await asyncio.get_event_loop().run_in_executor(
            None, 
            lambda: _export_json_blocking(json_file_path, filtered_devices)
        )
        return {"status": f"Exported all devices to {json_file_path}"}
    return {"error": "Invalid format"}

def _export_csv_blocking(file_path: str, devices_data: Dict):
    """Blocking CSV export function."""
    with open(file_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["MAC", "Vendor", "SSIDs", "Anomaly Score", "Persistence Score", "Pattern Score", "Deauth Count", "Channels"])
        for mac, data in devices_data.items():
            writer.writerow([
                mac,
                data["vendor"],
                ", ".join(data["ssid_list"]), # Use ", " for readability in CSV
                f"{data['anomaly_score']:.2f}",
                f"{data['persistence_score']:.2f}",
                f"{data['pattern_score']:.2f}",
                data["deauth_count"],
                ", ".join(map(str, data["channel_counts"].keys()))
            ])

def _export_json_blocking(file_path: str, devices_data: Dict):
    """Blocking JSON export function."""
    with open(file_path, "w") as f:
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