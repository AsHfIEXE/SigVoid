import sqlite3
from typing import Dict, Set, List
import time
from collections import defaultdict
import statistics

def oui_lookup(mac: str) -> str:
    try:
        conn = sqlite3.connect("database/oui.db")
        cursor = conn.cursor()
        oui = mac[:8].replace(":", "").upper()
        cursor.execute("SELECT vendor FROM oui WHERE oui = ?", (oui,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else "Unknown"
    except sqlite3.Error:
        return "Unknown"

def calculate_anomaly_score(device: Dict, total_devices: int) -> float:
    ssid_count = len(device["ssid_list"])
    timestamps = device["timestamps"]
    deauth_count = device.get("deauth_count", 0)
    rssi_list = device["rssi_list"]
    channel_counts = device["channel_counts"]
    
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
        score += rssi_weight * min(1.0, statistics.variance(rssi_list) / 100)
    
    # Channel diversity (10%)
    score += 0.1 * min(1.0, len(channel_counts) / 3.0)
    
    return min(1.0, score)

def calculate_persistence_score(device: Dict) -> float:
    timestamps = device["timestamps"]
    if len(timestamps) < 2:
        return 0.0
    time_span = timestamps[-1] - timestamps[0]
    return min(1.0, len(timestamps) / (time_span / 3600 + 1))

def calculate_pattern_score(device: Dict) -> float:
    ssid_list = sorted(list(device["ssid_list"]))
    if len(ssid_list) < 2:
        return 0.0
    # Simple entropy-like score for SSID sequence
    unique_pairs = len(set(zip(ssid_list[:-1], ssid_list[1:])))
    return min(1.0, unique_pairs / len(ssid_list))

def detect_evil_twin(devices: Dict, mac: str, ssid: str, bssid: str) -> bool:
    for other_mac, data in devices.items():
        if other_mac != mac and ssid in data["ssid_list"] and bssid not in data["bssid_list"]:
            return True
    return False

def cluster_ssids(devices: Dict) -> Dict[str, int]:
    ssid_counts = defaultdict(int)
    for device in devices.values():
        for ssid in device["ssid_list"]:
            ssid_counts[ssid] += 1
    return dict(ssid_counts)

def channel_analytics(devices: Dict) -> Dict[int, int]:
    channel_counts = defaultdict(int)
    for device in devices.values():
        for channel, count in device["channel_counts"].items():
            channel_counts[channel] += count
    return dict(channel_counts)

def summarize_devices(devices: Dict) -> Dict:
    return {
        mac: {
            "vendor": data["vendor"],
            "ssid_list": list(data["ssid_list"]),
            "rssi_list": data["rssi_list"],
            "timestamps": data["timestamps"],
            "anomaly_score": data["anomaly_score"],
            "persistence_score": data["persistence_score"],
            "pattern_score": data["pattern_score"],
            "deauth_count": data["deauth_count"],
            "channel_counts": data["channel_counts"]
        } for mac, data in devices.items()
    }