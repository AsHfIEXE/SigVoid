import time
from typing import Dict
from backend.database.database import get_db_connection

async def cleanup_logs(max_age_hours: int = 24) -> Dict:
    try:
        cutoff = time.time() - max_age_hours * 3600
        async with await get_db_connection() as db:
            cursor = await db.execute("DELETE FROM logs WHERE timestamp < ?", (cutoff,))
            deleted_logs = cursor.rowcount
            await db.execute("DELETE FROM devices WHERE substr(timestamps, 2, instr(timestamps, ',') - 2) < ?", (cutoff,))
            deleted_devices = cursor.rowcount # This heuristic needs refinement for devices
            await db.commit()
        return {"status": f"Deleted {deleted_logs} old log entries and {deleted_devices} inactive devices."}
    except Exception as e:
        return {"error": f"Cleanup failed: {e}"}

async def prune_blacklist(max_age_days: int = 7) -> Dict:
    try:
        cutoff = time.time() - max_age_days * 86400
        async with await get_db_connection() as db:
            cursor = await db.execute("DELETE FROM banned_macs WHERE banned_at < ?", (cutoff,))
            deleted = cursor.rowcount
            await db.commit()
        return {"status": f"Pruned {deleted} old entries from blacklist."}
    except Exception as e:
        return {"error": f"Blacklist prune failed: {e}"}