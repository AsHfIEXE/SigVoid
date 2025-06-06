import sqlite3
import time

def oui_lookup(mac):
    conn = sqlite3.connect('database/oui.db')
    cursor = conn.cursor()
    oui = mac[:8].replace(':', '').upper()
    cursor.execute('SELECT vendor FROM oui WHERE oui = ?', (oui,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 'Unknown'

def calculate_anomaly_score(device):
    # Score based on SSID count and frequency of probes
    ssid_count = len(device['ssid_list'])
    timestamps = device['timestamps']
    if len(timestamps) < 2:
        return min(1.0, ssid_count / 5.0)
    frequency = len(timestamps) / (timestamps[-1] - timestamps[0] + 1)
    return min(1.0, (ssid_count / 5.0) + (frequency * 10))

def send_alert(mac, device):
    # Offline: Log to file
    with open('alerts.log', 'a') as f:
        f.write(f"{time.ctime()}: Suspicious device - MAC={mac}, Score={device['anomaly_score']:.2f}, Vendor={device['vendor']}\n")
    
    # Optional: Telegram alert (requires internet)
    # import requests
    # requests.post('https://api.telegram.org/bot<YOUR_BOT_TOKEN>/sendMessage', 
    #               data={'chat_id': '<YOUR_CHAT_ID>', 'text': f'Suspicious: {mac}'})