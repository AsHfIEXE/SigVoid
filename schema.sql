```
   CREATE TABLE oui (oui TEXT PRIMARY KEY, vendor TEXT);
   CREATE TABLE logs (timestamp DATETIME, mac TEXT, ssid TEXT, rssi INTEGER, anomaly_score REAL, persistence_score REAL, pattern_score REAL, deauth_count INTEGER, channel INTEGER);
   ```