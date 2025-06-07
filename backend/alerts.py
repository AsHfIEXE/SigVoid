# backend/alerts.py
import time
import aiohttp
import asyncio
import os
from typing import Dict

# Simple in-memory throttling for alerts
_alert_cooldown: Dict[str, float] = {} # {mac: last_alert_timestamp}
ALERT_COOLDOWN_SECONDS = 300 # 5 minutes

# --- NEW HELPER FUNCTIONS FOR BLOCKING I/O ---
def _blocking_write_alert_to_file(message: str):
    """Blocking helper function to write alert to file."""
    # Using 'a' for append mode. File is created if it doesn't exist.
    with open("alerts.log", "a") as f:
        f.write(message)

def _blocking_play_audio_alert():
    """Blocking helper function to play audio alert."""
    try:
        os.system("aplay alert.wav")
    except Exception as e:
        # This is a blocking function's error handling.
        # The main async loop is protected by run_in_executor.
        print(f"Error during audio playback (blocking call): {e}")

# ---------------------------------------------

async def send_alert(mac: str, device: Dict):
    # Check cooldown
    current_time = time.time()
    if mac in _alert_cooldown and (current_time - _alert_cooldown[mac] < ALERT_COOLDOWN_SECONDS):
        # print(f"Alert for {mac} throttled.") # Uncomment for debugging throttling
        return # Skip alert due to cooldown
    
    _alert_cooldown[mac] = current_time # Update last alert timestamp

    alert_message = (
        f"{time.ctime()}: Suspicious - MAC={mac}, Score={device['anomaly_score']:.2f}, "
        f"Persistence={device['persistence_score']:.2f}, Pattern={device['pattern_score']:.2f}, "
        f"Deauths={device['deauth_count']}, Vendor={device['vendor']}\n"
    )

    # File-based alert (run in executor to avoid blocking main loop)
    try:
        await asyncio.get_event_loop().run_in_executor(None, _blocking_write_alert_to_file, alert_message)
    except Exception as e:
        print(f"Error scheduling file alert: {e}")
    
    # Audio alert (run in executor to avoid blocking main loop)
    try:
        await asyncio.get_event_loop().run_in_executor(None, _blocking_play_audio_alert)
    except Exception as e:
        print(f"Error scheduling audio alert: {e}")
    
    # Optional Telegram alert (uncomment and configure if needed)
    """
    try:
        async with aiohttp.ClientSession() as session:
            await session.post(
                "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/sendMessage",
                json={"chat_id": "<YOUR_CHAT_ID>", "text": alert_message}
            )
    except Exception as e:
        print(f"Telegram alert failed: {e}")
    """