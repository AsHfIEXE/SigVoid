import time
import aiohttp
import asyncio
import os

async def send_alert(mac: str, device: Dict):
    # File-based alert
    with open("alerts.log", "a") as f:
        f.write(f"{time.ctime()}: Suspicious - MAC={mac}, Score={device['anomaly_score']:.2f}, Persistence={device['persistence_score']:.2f}, Pattern={device['pattern_score']:.2f}, Deauths={device['deauth_count']}, Vendor={device['vendor']}\n")
    
    # Audio alert
    try:
        os.system("aplay alert.wav")
    except:
        print("Audio alert failed. Check 'alert.wav' and 'aplay'.")
    
    # Optional Telegram alert
    """
    async with aiohttp.ClientSession() as session:
        await session.post(
            "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/sendMessage",
            json={"chat_id": "<YOUR_CHAT_ID>", "text": f"Suspicious: {mac}, Score: {device['anomaly_score']:.2f}, Pattern: {device['pattern_score']:.2f}"}
        )
    """