import sqlite3
import os
import time
from typing import Dict

async def cleanup_logs(max_age_hours: int = 24) -> Dict:
    try:
        cutoff = time.time() - max_age_hours * 3600
        conn = sqlite3.connect("database/oui.db")
        cursor = conn.cursor()
        cursor.execute("DELETE FROM logs WHERE timestamp < ?", (cutoff,))
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        return {"status": f"Deleted {deleted} old log entries"}
    except sqlite3.Error as e:
        return {"error": f"Cleanup failed: {e}"}

async def prune_blacklist(max_age_days: int = 7) -> Dict:
    try:
        cutoff = time.time() - max_age_days * 86400
        with open("banned_macs.txt", "r") as f:
            lines = [(line.strip(), cutoff) for line in f if line.strip()]
        with open("banned_macs.txt", "w") as f:
            for mac, _ in lines:
                f.write(f"{mac}\n")
        return {"status": f"Pruned blacklist"}
    except Exception as e:
        return {"error": f"Blacklist prune failed: {e}"}