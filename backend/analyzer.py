# backend/analyzer.py
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
    OUI_DB_PATH = "backend/database/oui.db" # Make sure to put your oui.db here
    try:
        async with aiosqlite.connect(OUI_DB_PATH) as db:
            db.row_factory = aiosqlite.Row # Ensure row_factory for consistency
            cursor = await db.cursor()
            oui = mac[:8].replace(":", "").upper()
            await cursor.execute("SELECT vendor FROM oui WHERE oui = ?", (oui,))
            result = await cursor.fetchone()
            return result['vendor'] if result else "Unknown"
    except aiosqlite.Error as e:
        print(f"OUI lookup DB error: {e}")
        return "Unknown"
    except Exception as e:
        print(f"Unexpected error in OUI lookup: {e}")
        return "Unknown"

def calculate_anomaly_score(device: Dict, total_devices: int) -> float:
    # Safely load JSON fields, providing defaults for calculation
    ssid_list = json.loads(device.get("ssid_list", "[]"))
    timestamps = json.loads(device.get("timestamps", "[]"))
    rssi_list = json.loads(device.get("rssi_list", "[]"))
    channel_counts = json.loads(device.get("channel_counts", "{}"))
    deauth_count = device.get("deauth_count", 0)
    
    score = 0.0
    
    # Adaptive SSID weight (30-40% based on device density)
    # More unique SSIDs -> higher anomaly
    ssid_weight = 0.3 + 0.1 * min(total_devices / 10, 1.0)
    score += ssid_weight * min(1.0, len(ssid_list) / 5.0) # Scale by 5 unique SSIDs

    # Probe frequency (20-30%)
    # More frequent probes -> higher anomaly
    freq_weight = 0.2 + 0.1 * min(total_devices / 10, 1.0)
    if len(timestamps) > 1:
        time_span = timestamps[-1] - timestamps[0] # Time in milliseconds
        if time_span > 0:
            frequency_per_sec = len(timestamps) / (time_span / 1000.0)
            score += freq_weight * min(1.0, frequency_per_sec / 2.0) # Scale by 2 probes/sec
    
    # Deauth count (20%)
    # More deauths -> higher anomaly
    score += 0.2 * min(1.0, deauth_count / 5.0) # Scale by 5 deauths

    # RSSI variance (10-15%)
    # High RSSI variance (device moving erratically/flickering signals) -> higher anomaly
    rssi_weight = 0.1 + 0.05 * min(total_devices / 10, 1.0)
    if len(rssi_list) > 2:
        try:
            # Normalize variance by a typical range (e.g., 100 is large variance for RSSI)
            score += rssi_weight * min(1.0, statistics.variance(rssi_list) / 100.0)
        except statistics.StatisticsError:
            pass # Variance is 0 for lists with identical values, doesn't add to anomaly score
    
    # Channel diversity (10%)
    # Probing many channels -> higher anomaly
    score += 0.1 * min(1.0, len(channel_counts) / 3.0) # Scale by 3 channels

    return min(1.0, score) # Cap score at 1.0

def calculate_persistence_score(device: Dict) -> float:
    timestamps = json.loads(device.get("timestamps", "[]"))
    if len(timestamps) < 2:
        return 0.0
    
    time_span_ms = timestamps[-1] - timestamps[0]
    time_span_seconds = time_span_ms / 1000.0
    
    # Persistence = (Number of unique probes) / (Total time span in hours + 1)
    # Score is 0-1, 1.0 being highly persistent over a long period.
    # Example: if device is seen 100 times over 1 hour, persistence is higher than 100 times over 10 hours.
    # Here, we use total distinct probes within the MAX_DATA_POINTS window for simplicity,
    # normalized against a typical 1-hour presence to reach 1.0.
    
    # Using total number of probes recorded for simplicity and recency within the window
    return min(1.0, len(timestamps) / (time_span_seconds / 3600.0 + 0.1)) # Add 0.1 to avoid division by zero

def calculate_pattern_score(device: Dict) -> float:
    # ssid_history is stored as a list in DB, representing the deque
    ssid_history = json.loads(device.get("ssid_history", "[]"))
    if len(ssid_history) < 2:
        return 0.0
    
    # Detect sequential patterns or lack thereof
    # Using a simple measure of "randomness" or "diversity" of sequential SSIDs
    
    transitions = defaultdict(int)
    for i in range(len(ssid_history) - 1):
        pair = (ssid_history[i], ssid_history[i+1])
        transitions[pair] += 1
    
    total_transitions = sum(transitions.values())
    if total_transitions == 0:
        return 0.0
    
    # A higher pattern score implies less predictable or more "random" transitions
    # (e.g., rapid switching between many different SSIDs, or cycling through a set)
    # Normalized by the maximum possible unique transitions for the history length
    
    num_unique_transitions = len(transitions)
    
    # Maximum possible unique transitions for a given history length: length - 1
    max_possible_transitions = len(ssid_history) - 1
    
    if max_possible_transitions == 0:
        return 0.0

    score = num_unique_transitions / max_possible_transitions
    
    return min(1.0, score) # Cap score at 1.0


async def detect_evil_twin(db_conn: aiosqlite.Connection, mac: str, ssid: str, bssid: str) -> bool:
    """
    Detects potential evil twin by checking if another device is broadcasting the same SSID
    but with a different BSSID (acting as a rogue AP or another client probing the same SSID).
    This is a simplified check.
    """
    if not ssid: return False # Cannot detect evil twin without an SSID
    if not mac: return False # Cannot detect evil twin without a MAC address
    if not bssid: return False # Cannot detect evil twin without a BSSID
    cursor = await db_conn.execute(
        """
        SELECT mac, ssid_list, timestamps -- For recent activity
        FROM devices 
        WHERE mac != ?
        """, (mac,)
    )
    
    async for row in cursor:
        other_mac = row['mac']
        other_ssids = json.loads(row['ssid_list'])
        
        # Consider a device as an "evil twin" candidate if it's broadcasting the same SSID
        # (even if we don't have explicit AP data, if it's just in its probed SSID list)
        if ssid in other_ssids:
            # To be more specific about a *rogue AP* (Evil Twin), we'd need data like:
            # - Is `other_mac` also sending beacons for `ssid`?
            # - Is `bssid` (from the probe) consistent with a known good AP, or is `other_mac` a new/rogue AP?
            
            # Simplified "evil twin" check: if another device also has this SSID in its list
            # and is actively probing or deauthing. This is a very loose interpretation.
            # To tighten, you need AP detection firmware-side.
            
            # Check for recent activity from the "other" device to confirm it's active
            other_timestamps = json.loads(row['timestamps'])
            if other_timestamps and (time.time() * 1000 - other_timestamps[-1] < 300000): # Seen in last 5 mins
                return True # Potentially an evil twin candidate (or another active device probing the same network)
    
    return False