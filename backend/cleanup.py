# backend/cleanup.py
import time
from typing import Dict
from backend.database.database import get_db_connection
import json

async def cleanup_logs(max_age_hours: int = 24) -> Dict:
    try:
        cutoff_timestamp = time.time() - max_age_hours * 3600
        
        async with await get_db_connection() as db:
            # 1. Clean up individual log entries
            cursor_logs = await db.execute("DELETE FROM logs WHERE timestamp < ?", (cutoff_timestamp,))
            deleted_logs = cursor_logs.rowcount

            # 2. Clean up inactive devices from the 'devices' table
            #    A device is "inactive" if its latest timestamp is older than the cutoff.
            #    We need to deserialize the timestamps JSON string to check the last one.
            #    This is not easily done directly in SQL without JSON functions.
            #    A more robust solution would be to add a 'last_seen' REAL column to the devices table.
            
            # For now, let's fetch devices and filter in Python, then delete.
            # This is less efficient for very large tables but safe and correct.
            devices_to_delete = []
            cursor_devices = await db.execute("SELECT mac, timestamps FROM devices")
            async for row in cursor_devices:
                timestamps_str = row['timestamps']
                if timestamps_str:
                    timestamps = json.loads(timestamps_str)
                    if timestamps and (timestamps[-1] / 1000.0 < cutoff_timestamp): # Convert ms to s
                        devices_to_delete.append(row['mac'])
            
            deleted_devices = 0
            if devices_to_delete:
                placeholders = ','.join('?' for _ in devices_to_delete)
                delete_query = f"DELETE FROM devices WHERE mac IN ({placeholders})"
                delete_cursor = await db.execute(delete_query, devices_to_delete)
                deleted_devices = delete_cursor.rowcount

            await db.commit()
        return {"status": f"Deleted {deleted_logs} old log entries and {deleted_devices} inactive devices."}
    except Exception as e:
        return {"error": f"Cleanup failed: {e}"}

async def prune_blacklist(max_age_days: int = 7) -> Dict:
    try:
        cutoff_timestamp = time.time() - max_age_days * 86400
        async with await get_db_connection() as db:
            cursor = await db.execute("DELETE FROM banned_macs WHERE banned_at < ?", (cutoff_timestamp,))
            deleted = cursor.rowcount
            await db.commit()
        return {"status": f"Pruned {deleted} old entries from blacklist."}
    except Exception as e:
        return {"error": f"Blacklist prune failed: {e}"}