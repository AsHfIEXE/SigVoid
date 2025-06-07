import aiosqlite
import time
from collections import defaultdict, deque
import statistics
import json
from typing import Dict, Set, List

# Max history length for pattern analysis
MAX_SSID_HISTORY = 20

async def oui_lookup(mac: str) -> str:
    # Assuming oui.db is in the same directory as sigvoid.db or accessible
    # Note: For simplicity, I'm assuming oui.db is read-only and a separate connection.
    # If it's a very large DB, consider loading into memory or a more robust solution.
    OUI_DB_PATH = "backend/database/oui.db" # Make sure to put your oui.db here
    try:
        async with aiosqlite.connect(OUI_DB_PATH) as db:
            cursor = await db.cursor()
            oui = mac[:8].replace(":", "").upper()
            await cursor.execute("SELECT vendor FROM oui WHERE oui = ?", (oui,))
            result = await cursor.fetchone()
            return result[0] if result else "Unknown"
    except aiosqlite.Error:
        return "Unknown"

def calculate_anomaly_score(device: Dict, total_devices: int) -> float:
    ssid_count = len(json.loads(device.get("ssid_list", "[]")))
    timestamps = json.loads(device.get("timestamps", "[]"))
    deauth_count = device.get("deauth_count", 0)
    rssi_list = json.loads(device.get("rssi_list", "[]"))
    channel_counts = json.loads(device.get("channel_counts", "{}"))
    
    score = 0.0
    # Adaptive SSID weight (30-40% based on device density)
    ssid_weight = 0.3 + 0.1 * min(total_devices / 10, 1.0)
    score += ssid_weight * min(1.0, ssid_count / 5.0)
    
    # Probe frequency (20-30%)
    freq_weight = 0.2 + 0.1 * min(total_devices / 10, 1.0)
    if len(timestamps) > 1:
        frequency = len(timestamps) / (timestamps[-1] - timestamps[0] + 1)
        score += freq_weight * min(1.0, frequency * 10)
    
    # Deauth count (20%)
    score += 0.2 * min(1.0, deauth_count / 5.0)
    
    # RSSI variance (10-15%)
    rssi_weight = 0.1 + 0.05 * min(total_devices / 10, 1.0)
    if len(rssi_list) > 2:
        try: # Avoid variance calculation for lists with identical values
            score += rssi_weight * min(1.0, statistics.variance(rssi_list) / 100)
        except statistics.StatisticsError:
            pass # Variance is 0 for constant list, doesn't add to anomaly
    
    # Channel diversity (10%)
    score += 0.1 * min(1.0, len(channel_counts) / 3.0)
    
    return min(1.0, score)

def calculate_persistence_score(device: Dict) -> float:
    timestamps = json.loads(device.get("timestamps", "[]"))
    if len(timestamps) < 2:
        return 0.0
    time_span = timestamps[-1] - timestamps[0]
    # Normalize by minimum expected probes over time, assuming a steady presence
    # E.g., 10 probes per hour. max time_span is for normalization to 1.0
    return min(1.0, len(timestamps) / (time_span / 3600 + 1))

def calculate_pattern_score(device: Dict) -> float:
    ssid_history = deque(json.loads(device.get("ssid_history", "[]")))
    if len(ssid_history) < 2:
        return 0.0
    
    # Calculate unique sequential transitions (e.g., A->B, B->C)
    transitions = defaultdict(int)
    for i in range(len(ssid_history) - 1):
        pair = (ssid_history[i], ssid_history[i+1])
        transitions[pair] += 1
    
    total_transitions = sum(transitions.values())
    if total_transitions == 0:
        return 0.0
    
    # Calculate entropy-like score based on transition diversity
    # Higher diversity of transitions means less predictable patterns
    entropy = 0.0
    for count in transitions.values():
        probability = count / total_transitions
        entropy -= probability * (probability**0.5) # Softened log for better scaling
    
    # Normalize score to 0-1 range. Max entropy depends on num unique transitions
    # A simple normalization for now: ratio of unique transitions to total transitions
    score = len(transitions) / total_transitions
    
    return min(1.0, score * 2) # Multiply by 2 as 0.5 is max for random transitions

async def detect_evil_twin(db_conn: aiosqlite.Connection, mac: str, ssid: str, bssid: str) -> bool:
    # Check for other MACs beaconing the same SSID but with a different BSSID
    # This is a basic check. A full evil twin detection is complex.
    cursor = await db_conn.execute(
        "SELECT mac, ssid_list FROM devices WHERE mac != ?", (mac,)
    )
    async for row in cursor:
        other_mac = row['mac']
        other_ssids = json.loads(row['ssid_list'])
        if ssid in other_ssids:
            # More advanced check: if the other device is acting as an AP for this SSID
            # (which we don't track directly in current data, but could be added)
            # For now, just check if it's broadcasting the same SSID.
            return True
    return False

# This function is not used by the dashboard directly, but would be if
# you wanted to summarize specific aspects without fetching all device data.
# For now, the dashboard fetches all relevant device data from the DB itself.
# Retaining for conceptual completeness, but its role has changed with DB-centric approach.
async def summarize_devices_from_db() -> Dict:
    from backend.database.database import get_db_connection
    async with await get_db_connection() as db:
        cursor = await db.execute("SELECT * FROM devices")
        all_devices = await cursor.fetchall()
        summarized = {}
        for row in all_devices:
            summarized[row['mac']] = {
                "vendor": row['vendor'],
                "ssid_list": json.loads(row['ssid_list']),
                "rssi_list": json.loads(row['rssi_list']),
                "timestamps": json.loads(row['timestamps']),
                "anomaly_score": row['anomaly_score'],
                "persistence_score": row['persistence_score'],
                "pattern_score": row['pattern_score'],
                "deauth_count": row['deauth_count'],
                "channel_counts": json.loads(row['channel_counts']),
                "ssid_history": json.loads(row['ssid_history'])
            }
        return summarized