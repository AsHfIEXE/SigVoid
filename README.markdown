# SigVoid

```
███████╗██╗ ██████╗ ██╗   ██╗ ██████╗ ██╗██████╗ 
██╔════╝██║██╔════╝ ██║   ██║██╔═══██╗██║██╔══██╗
███████╗██║██║  ███╗██║   ██║██║   ██║██║██║  ██║
╚════██║██║██║   ██║╚██╗ ██╔╝██║   ██║██║██║  ██║
███████║██║╚██████╔╝ ╚████╔╝ ╚██████╔╝██║██████╔╝
╚══════╝╚═╝ ╚═════╝   ╚═══╝   ╚═════╝ ╚═╝╚═════╝
   SigVoid - Cyberacore Wi-Fi Threat Monitor
```

**SigVoid**: A Cyberacore Wi-Fi threat monitor using a single ESP8266 to detect rogue APs, evil twins, and deauth attacks. Features a neon-green PWA dashboard with real-time analytics and auto-installs via `run.sh`.

[![MIT License](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![CI/CD](https://github.com/AsHfIEXE/SigVoid/workflows/SigVoid%20CI/badge.svg)](https://github.com/AsHfIEXE/SigVoid/actions)
[![GitHub Stars](https://img.shields.io/github/stars/AsHfIEXE/SigVoid?style=social)](https://github.com/AsHfIEXE/SigVoid/stargazers)
[![Python Version](https://img.shields.io/badge/Python-3.10-blue.svg)](https://www.python.org/downloads/release/python-3100/)
[![ESP8266](https://img.shields.io/badge/ESP8266-NodeMCU-orange.svg)](https://github.com/esp8266/Arduino)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115.0-teal.svg)](https://fastapi.tiangolo.com/)
[![TailwindCSS](https://img.shields.io/badge/TailwindCSS-3.4.2-blue.svg)](https://tailwindcss.com/)
[![Chart.js](https://img.shields.io/badge/Chart.js-4.4.0-blue.svg)](https://www.chartjs.org/)

## Overview

**SigVoid** is a lightweight, real-time Wi-Fi threat-hunting tool powered by a single ESP8266 microcontroller. It sniffs packets to identify rogue access points, evil twins, and deauthentication attacks, delivering insights through a neon-green, drag-and-drop Progressive Web App (PWA). With anomaly scoring, persistence tracking, and channel activity visualization, **SigVoid** exposes hidden threats in the Wi-Fi void. Its `run.sh` script automates setup, installing frameworks like FastAPI, TailwindCSS, and Chart.js, and supports offline environments. Perfect for pentesters, IoT enthusiasts, and network defenders.

## Features
- **Threat Detection**: Flags rogue APs, evil twins, and deauth attacks with anomaly scores (>0.8) and deauth counts (>5).
- **Cyberacore Dashboard**: Neon-green PWA with real-time charts (Chart.js), reactive UI (Alpine.js), and drag-and-drop widgets (Interact.js).
- **ESP8266 Insights**: Monitors RSSI, device persistence, and diagnostics (heap, uptime).
- **Auto-Setup**: `run.sh` installs dependencies, detects ESP8266 ports, and builds frontend assets.
- **Alerts**: Audio (`alert.wav`), logs (`alerts.log`), and visual (pulsing red) for high-risk devices.
- **Exports**: CSV/JSON reports for high-risk or recent devices.
- **Offline Mode**: Runs without internet if assets are pre-placed.

## Demo
![SigVoid Dashboard](https://placehold.co/800x400?text=SigVoid+Dashboard&font=Roboto) *(Placeholder: Neon-green UI with device table and charts)*

## Installation

### Prerequisites
- **Hardware**: ESP8266 (e.g., NodeMCU).
- **OS**: Linux (Ubuntu/Debian preferred; macOS/Windows with WSL2 supported).
- **Tools**: `sudo` privileges, internet (optional for offline).
- **Files**: `alert.wav` (root), `icon.png` (192x192, `frontend/static`).

### Quick Start
1. **Clone the Repo**:
   ```bash
   git clone https://github.com/AsHfIEXE/SigVoid.git
   cd SigVoid
   ```

2. **Flash ESP8266**:
   - Install [Arduino IDE](https://www.arduino.cc/en/software).
   - Add ESP8266 board: `http://arduino.esp8266.com/stable/package_esp8266com_index.json` (File > Preferences).
   - Open `esp8266/rogue_ap.ino`, select board (e.g., NodeMCU 1.0) and port (e.g., `/dev/ttyUSB0`).
   - Upload (baud 115200).
   - Verify Serial Monitor: `{"type":"diagnostics","source":"SigVoid","free_heap":XXXX,"uptime":XXXX}`.

3. **Run SigVoid**:
   ```bash
   chmod +x run.sh
   ./run.sh
   ```
   - **Offline**: Ensure `frontend/static/*.js`, `alert.wav`, and `icon.png` are present.
   - **Options**: `--verbose`, `--port /dev/ttyACM0`, `--baud 57600`, `--server-port 8080`.

4. **Access Dashboard**:
   - Open `http://localhost:8000`.
   - Install as a PWA via "Add to Home Screen."

### Manual Setup
If `run.sh` fails:
- **System Dependencies**:
  ```bash
  sudo apt update
  sudo apt install curl python3 python3-venv nodejs npm alsa-utils
  npm install -g tailwindcss
  ```
- **Python Dependencies**:
  ```bash
  python3 -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
  ```
- **Build TailwindCSS**:
  ```bash
  npx tailwindcss -i input.css -o frontend/static/styles.css --minify
  ```
- **Database**:
  ```bash
  sqlite3 database/oui.db < schema.sql
  ```
  Populate `oui` table with `oui.csv` (e.g., IEEE OUI database).

## Usage
1. **Launch**:
   ```bash
   ./run.sh
   ```
2. **Monitor Threats**:
   - Filter devices by MAC, SSID, or anomaly score in the dashboard.
   - Check red alerts for high-risk devices (deauths >5).
   - Listen for `alert.wav` or view `alerts.log`.
3. **Act**:
   - Ban rogue MACs (adds to `banned_macs.txt`).
   - Export high-risk devices as CSV/JSON.
4. **Customize**:
   - Drag widgets (saved in `localStorage`).
   - Toggle dark/light themes.
5. **Stop**:
   - Press `Ctrl+C`.

## Project Structure
```
SigVoid/
├── esp8266/
│   └── rogue_ap.ino
├── backend/
│   ├── main.py
│   └── *.py
├── frontend/
│   ├── static/
│   │   ├── dashboard.js
│   │   ├── styles.css
│   │   ├── *.js
│   │   ├── manifest.json
│   │   ├── sw.js
│   │   └── icon.png
│   └── templates/
│       └── index.html
├── database/
│   └── oui.db
├── alert.wav
├── input.css
├── requirements.txt
├── run.sh
├── sigvoid.conf
├── sigvoid.log
└── .github/workflows/ci.yml
```

## Contributing
- Fork and submit PRs with features or fixes.
- Report bugs via [Issues](https://github.com/AsHfIEXE/SigVoid/issues).
- Add tests in `tests/` or enhance the UI.
- Follow code style: `pylint` for Python, Prettier for JS/CSS.

## License
MIT License. See [LICENSE](LICENSE).

## Credits
- **AsHfIEXE**: Only done by ME
- **Community**: ESP8266, FastAPI, TailwindCSS, and Chart.js contributors.

---
*Hunt the void. Secure the signal. SigVoid stands watch.*
