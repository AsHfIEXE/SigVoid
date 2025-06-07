# backend/database/database.py
import aiosqlite
import os

DATABASE_PATH = "backend/database/sigvoid.db"

async def get_db_connection():
    # Ensure the directory exists
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    db = await aiosqlite.connect(DATABASE_PATH)
    db.row_factory = aiosqlite.Row # Access columns by name
    return db

async def init_db():
    async with await get_db_connection() as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS devices (
                mac TEXT PRIMARY KEY,
                vendor TEXT,
                ssid_list TEXT, -- JSON string of SSIDs (set)
                rssi_list TEXT, -- JSON string of RSSIs (list)
                timestamps TEXT, -- JSON string of timestamps (list)
                anomaly_score REAL,
                persistence_score REAL,
                pattern_score REAL,
                deauth_count INTEGER,
                channel_counts TEXT, -- JSON string of channel counts (dict)
                ssid_history TEXT -- JSON string of ordered SSID history (deque)
            );
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL,
                mac TEXT,
                ssid TEXT,
                rssi INTEGER,
                anomaly_score REAL,
                persistence_score REAL,
                pattern_score REAL,
                deauth_count INTEGER,
                channel INTEGER
            );
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS banned_macs (
                mac TEXT PRIMARY KEY,
                banned_at REAL
            );
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );
        """)
        # Initialize default settings if not present
        await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('esp_ap_ssid', 'FreeWiFi_Honeypot');")
        await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('esp_ap_password', '');")
        await db.commit()

async def get_setting(key: str) -> str:
    async with await get_db_connection() as db:
        cursor = await db.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = await cursor.fetchone()
        return row['value'] if row else None

async def set_setting(key: str, value: str):
    async with await get_db_connection() as db:
        await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?);", (key, value))
        await db.commit()