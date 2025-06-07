

# 🛡️ SigVoid: Real-Time Wi-Fi Threat Monitoring System



```
███████╗██╗ ██████╗ ██╗   ██╗ ██████╗ ██╗██████╗ 
██╔════╝██║██╔════╝ ██║   ██║██╔═══██╗██║██╔══██╗
███████╗██║██║  ███╗██║   ██║██║   ██║██║██║  ██║
╚════██║██║██║   ██║╚██╗ ██╔╝██║   ██║██║██║  ██║
███████║██║╚██████╔╝ ╚████╔╝ ╚██████╔╝██║██████╔╝
╚══════╝╚═╝ ╚═════╝   ╚═══╝   ╚═════╝ ╚═╝╚═════╝
   SigVoid - Cyberacore Wi-Fi Threat Monitor
```


![Python Version](https://img.shields.io/badge/Python-3.9%2B-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688?logo=fastapi&logoColor=white)
![ESP8266](https://img.shields.io/badge/ESP8266-Arduino-blueviolet?logo=arduino&logoColor=white)
![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-3.x-38B2AC?logo=tailwind-css&logoColor=white)
![License](https://img.shields.io/github/license/AsHfIEXE/SigVoid?color=neon_green)
[![Chart.js](https://img.shields.io/badge/Chart.js-4.4.0-blue.svg)](https://www.chartjs.org/)
[![Python Version](https://img.shields.io/badge/Python-3.10-blue.svg)](https://www.python.org/downloads/release/python-3100/)
[![GitHub Stars](https://img.shields.io/github/stars/AsHfIEXE/SigVoid?style=social)](https://github.com/AsHfIEXE/SigVoid/stargazers)


SigVoid is a powerful, multi-layered Wi-Fi threat monitoring platform designed for offensive security researchers, blue teamers, and network forensics. It integrates an ESP8266-based hardware sensor, a high-performance Python backend, persistent data storage, and a sleek, reactive web frontend to identify, analyze, and respond to various wireless threats, including rogue access points, probe floods, and evil twin attacks.

---

## ✨ Key Features

*   **Comprehensive Threat Detection:** Identifies abnormal Wi-Fi device behavior, including high anomaly scores, persistent probing, unusual patterns, and excessive deauthentication events.
*   **Real-time Insights:** A live, interactive dashboard provides instant visibility into detected devices and network diagnostics.
*   **Dynamic Honeypot AP:** Configure an enticing rogue access point (SSID & password) directly from the dashboard to attract and analyze target devices.
*   **Intelligent Alerting:** Receive immediate audio and file-based alerts for critical threats, with smart throttling to prevent spam.
*   **Customizable & Sleek UI:** A modern, minimal web interface with drag-and-drop widgets, dark/light themes, and real-time data visualizations.
*   **Actionable Data Management:** Export filtered threat intelligence to CSV/JSON, ban malicious MAC addresses, and perform automated log/blacklist cleanup.
*   **PWA Support:** Installable as a Progressive Web App for a native application feel.

---

## ⚙️ Architecture Overview

SigVoid is built as a modular system, with distinct layers communicating to provide a seamless threat monitoring experience.

### 1. 📡 Hardware Layer – ESP8266 Firmware (`rogue_ap.ino`)

*   **Promiscuous Sniffing:** Operates in promiscuous mode to capture all nearby Wi-Fi frames (802.11 management frames, specifically probe requests and deauthentication frames).
*   **Deauth & Probe Monitoring:** Efficiently parses captured packets to extract critical information like MAC addresses, SSIDs, RSSI, channels, and timestamps, essential for threat detection.
*   **Honeypot AP:** Hosts a configurable rogue Access Point to bait devices into sending probe requests, enhancing detection capabilities.
*   **Dynamic Channel Hopping:** Optimizes sniffing by dynamically switching between the top 3 most active Wi-Fi channels based on observed probe request density.
*   **EEPROM Storage:** Persists the honeypot AP's SSID and password in EEPROM, ensuring configuration is retained across device reboots.
*   **Diagnostics:** Continuously reports ESP8266's free heap memory and uptime statistics to the backend.
*   **JSON Serial Protocol:** Utilizes a custom, bi-directional JSON-over-serial protocol for efficient and structured communication with the backend.

### 2. 🐍 Backend Layer – FastAPI & Python Modules

*   **High-Performance API:** Built with **FastAPI** to provide a fast and asynchronous (non-blocking) API for all operations.
*   **Real-time Communication:** Employs **WebSockets (Socket.IO)** to push live device data and diagnostics updates to the frontend dashboard.
*   **Serial Integration:** Manages a robust, asynchronous, and **thread-safe serial communication** link with the ESP8266 using **`pyserial`** and **`asyncio.run_in_executor()`** to prevent blocking the main event loop.
*   **Anomaly Engine:**
    *   **OUI Lookup:** Resolves MAC addresses to vendor names using an **SQLite OUI database**.
    *   **Anomaly Scoring:** Calculates a real-time anomaly score for each device based on:
        *   The **diversity of probed SSIDs**.
        *   **RSSI variance** (indicating erratic movement or signal instability).
        *   **Probe request frequency**.
        *   **Channel hop behavior**.
        *   **Deauthentication event counts**.
    *   **Persistence Scoring:** Quantifies how consistently a device is present in the environment.
    *   **Pattern Scoring:** Analyzes the sequential patterns of probed SSIDs, designed to detect unusual or randomized probing behaviors.
    *   **Evil Twin Detection (Simplified):** Flags potential evil twin scenarios by identifying devices probing the same SSID with conflicting BSSIDs, or simply multiple devices associated with the same SSID appearing suspiciously. *Note: This is a simplified detection based on available probe data; dedicated beacon analysis firmware-side would enhance this.*
*   **Alerting System:** Triggers **audio alerts (`aplay`)** and writes detailed logs to `alerts.log` when suspicious activity exceeds thresholds. Alerts are intelligently throttled per MAC address.
*   **Database Handlers:** Manages all data interactions with the **SQLite** database using **`aiosqlite`** for asynchronous operations:
    *   `devices` table: Stores the latest analyzed state of all observed MAC addresses.
    *   `logs` table: Archives raw Wi-Fi event data for forensic review.
    *   `banned_macs` table: Maintains a persistent blacklist of identified threats.
    *   `settings` table: Stores configurable application settings, including ESP AP credentials.
*   **Export System:** Provides API endpoints for exporting device data to CSV (`export.csv`) or JSON (`export.json`), with options for high-risk or recently active devices.

### 3. 🗄️ Data Layer – SQLite Database (`backend/database/sigvoid.db`)

*   **Role:** Stores all critical application data persistently, ensuring state is maintained across server restarts.
*   **Technology:** **SQLite** – A lightweight, file-based relational database system, ideal for embedded applications and smaller-scale deployments.
*   **Access:** Managed asynchronously using **`aiosqlite`**, which provides non-blocking access from the FastAPI application.
*   **Key Tables:**
    *   **`devices`:** Stores the latest analyzed state for each unique MAC address observed (vendor, SSID list, RSSI history, timestamps, all anomaly scores, deauth counts, channel activity, SSID history for pattern analysis).
    *   **`logs`:** A historical record of individual probe requests and deauthentication events.
    *   **`banned_macs`:** A blacklist of MAC addresses deemed hostile, along with the timestamp they were banned.
    *   **`settings`:** Stores configurable application settings, such as the ESP8266's honeypot AP SSID and password.
*   **Module:** `backend/database/database.py` handles database connection, schema initialization, and basic setting management.

### 4. 🖥️ Frontend Layer – PWA + Web Dashboard

*   **Modern Design:** Built with **Tailwind CSS** for a sleek, minimal, and highly customizable user interface, supporting seamless dark/light theme switching.
*   **Reactive UI:** Utilizes **Alpine.js** for lightweight, declarative UI elements, handling dynamic data display, filtering, tab management, and interactive components.
*   **Dynamic Visualizations:** Leverages **Chart.js** to render real-time graphs and charts for signal strength trends, SSID distribution, device persistence timelines, and channel activity. Chart elements dynamically adapt to the selected theme.
*   **Customizable Layout:** Implements **Interact.js** for intuitive drag-and-drop functionality, allowing users to rearrange dashboard widgets, with layout preferences saved locally.
*   **Real-time Updates:** The **Socket.IO client** maintains a live connection to the FastAPI backend, ensuring the dashboard reflects threats and diagnostics in real-time.
*   **Progressive Web App (PWA):** Provides an installable, app-like experience with offline capabilities and push notification support via a **Service Worker (`sw.js`)** and **Web App Manifest (`manifest.json`)**.

### 5. 🚀 DevOps Layer – `run.sh`

*   **One-Command Launch:** A comprehensive Bash script designed for Linux systems that automates the entire setup, dependency installation, and application launch with a single command.
*   **Automated Setup:** Handles:
    *   Installation of system-level packages (`curl`, `python3-venv`, `nodejs`, `npm`, `alsa-utils`).
    *   Creation and activation of a Python virtual environment.
    *   Installation of all Python dependencies (`fastapi`, `uvicorn`, `pyserial`, `aiosqlite`, etc.).
    *   Global installation of `tailwindcss` for CSS compilation.
    *   Downloading and parsing of the **OUI (vendor) database** on first run.
    *   Downloading of frontend JavaScript libraries and PWA assets from CDNs.
    *   Downloading of `alert.wav` for audio notifications.
*   **Hardware Integration:** Includes intelligent auto-detection of the **ESP8266 serial port** with robust retry mechanisms and interactive prompts.
*   **Build Automation:** Compiles `input.css` into the optimized `styles.css` using `npx tailwindcss`.
*   **Logging & Diagnostics:** Provides colorful, verbose console output with ASCII banners, progress bars, and writes detailed logs for both the setup process and the FastAPI server.
*   **Graceful Shutdown:** Ensures the FastAPI server is cleanly terminated upon `Ctrl+C`.

---

## 🔁 Workflow Summary

```
[ESP8266 Sensor]
      ↓ (Serial JSON)
[FastAPI Backend] ↔ [SQLite Database]
      ↓ ↑ (WebSockets / HTTP)
[Web Dashboard (PWA)]
```

---

## 🛠️ Suggested Enhancements

While SigVoid is a robust system, here are some ideas for future development:

### 🔧 Backend Ideas

*   **Rate-limiting API Endpoints:** Implement rate-limiting (e.g., using `slowapi`) for certain endpoints like `/ban` or `/export` to prevent abuse or overload.
*   **Authentication & Authorization:** Add JWT-based authentication for admin access or finer-grained control over dashboard features.
*   **External Alert Integrations:** Beyond Telegram, consider integrations with Discord, Slack, or email services for remote notifications.
*   **Device Blacklisting Rules:** Allow more complex blacklist rules (e.g., MACs that have been deauthing for more than X seconds).

### 🧠 Detection Engine

*   **Machine Learning-Based Classifier:** Train an ML model (e.g., using scikit-learn) on historical device activity to identify new, sophisticated anomaly types.
*   **Beacon Frame Analysis:** Enhance the ESP firmware to capture and analyze Beacon frames, allowing for more robust detection of actual rogue APs and evil twins (identifying AP BSSIDs and their SSIDs).
*   **Client Association Tracking:** Track when devices successfully associate with the honeypot AP for deeper behavioral analysis.

### 📉 Frontend Tweaks

*   **Historical View Toggles:** Add options to view device data or chart trends over specific historical periods (e.g., last hour, last day).
*   **Auto-Refresh Control:** Implement a toggle to pause/resume real-time updates for forensic deep dives or performance optimization.
*   **Interactive Chart Filtering:** Allow clicking on chart elements (e.g., a specific SSID in the pie chart) to filter the devices table.

### 🧪 Test/Simulation

*   **Mock Serial Input:** Develop a `mock_serial.py` module to simulate ESP8266 input during development and testing, allowing the backend and frontend to run without physical hardware.
*   **Automated Testing:** Implement unit and integration tests for backend logic and API endpoints.

---

## 🚀 Getting Started

Follow these steps to set up and run your SigVoid dashboard.

### Prerequisites

Before you begin, ensure you have the following installed on your **Linux-based system (e.g., Ubuntu/Debian)**:

*   **Git:** For cloning the repository.
*   **Arduino IDE:** For flashing the ESP8266 firmware.
*   **`python3` and `npm`:** While `run.sh` installs many dependencies, these base tools are typically needed.
*   **An ESP8266 development board:** (e.g., NodeMCU ESP-12E)

### 1. Clone the Repository

```bash
git clone https://github.com/AsHfIEXE/SigVoid.git
cd SigVoid
```

### 2. Flash the ESP8266 Firmware

The ESP8266 acts as the Wi-Fi packet sniffing sensor.

1.  **Open `rogue_ap.ino`** in the Arduino IDE.
2.  **Install ESP8266 Board Package:**
    *   Go to `File > Preferences > Additional Board Manager URLs` and add: `http://arduino.esp8266.com/stable/package_esp8266com_index.json`
    *   Go to `Tools > Board > Boards Manager...`, search for `esp8266`, and install the `ESP8266 by ESP8266 Community` package.
3.  **Install Libraries:** Go to `Sketch > Include Library > Manage Libraries...`, search for `EEPROM`, and install the `EEPROM` library.
4.  **Select Board and Port:**
    *   Go to `Tools > Board`, select your ESP8266 board (e.g., `NodeMCU 1.0 (ESP-12E Module)`).
    *   Go to `Tools > Port` and select the serial port connected to your ESP8266.
5.  **Upload:** Click the `Upload` button (right arrow icon) to compile and flash the firmware to your ESP8266.
    *   After flashing, the ESP's EEPROM will be initialized with default AP settings (`SigVoid_Honeypot` with no password). You can change these via the dashboard's settings tab later.

### 3. Run the SigVoid Dashboard

The `run.sh` script automates the entire backend and frontend setup.

1.  **Make the script executable:**
    ```bash
    chmod +x run.sh
    ```
2.  **Execute the script:**
    ```bash
    ./run.sh
    ```
    *   **Follow the prompts:** The script will check system diagnostics, install Python and Node.js dependencies, set up a virtual environment, download necessary frontend assets, compile Tailwind CSS, and attempt to auto-detect your ESP8266 serial port.
    *   If the ESP8266 is not found automatically, it will prompt you to enter the correct serial port (e.g., `/dev/ttyUSB0`, `/dev/ttyACM0`). Ensure the ESP8266 is connected via USB and powered on.
    *   The script will also download and parse the OUI database for vendor lookups (requires internet connection on first run).
3.  **Access the Dashboard:** Once the script finishes, it will launch the FastAPI server. Open your web browser and navigate to:
    ```
    http://localhost:8000
    ```
    (Or the port specified in `sigvoid.conf` or via the `--server-port` argument)

---

## 💻 Usage

The SigVoid dashboard provides a real-time, interactive overview of your Wi-Fi environment.

### Dashboard Overview

*   **Devices Table:** Displays MAC addresses, vendors, SSIDs, RSSI, and calculated anomaly scores (Anomaly, Persistence, Pattern) for detected devices. High-risk devices are highlighted.
*   **ESP8266 Diagnostics:** Monitor your ESP's free heap memory and uptime.
*   **Charts:** Visualize Wi-Fi data trends:
    *   **Signal Strength:** RSSI changes over time for individual devices.
    *   **SSID Distribution:** Breakdown of most frequently probed SSIDs.
    *   **Persistence Timeline:** How long devices are observed.
    *   **Channel Activity:** Probe counts across different Wi-Fi channels.
*   **Filters:** Use the filter panel at the top to narrow down device listings by MAC address (regex), SSID (regex), or minimum anomaly score.
*   **Widget Management:** Drag and drop widgets to rearrange your dashboard layout. The layout is saved to your local storage.
*   **Device Details Modal:** Click "Details" next to any device for a comprehensive view of its collected data.

### Settings Tab

Navigate to the "Settings" tab via the sidebar:

*   **ESP8266 AP Settings:** Change the SSID and password of the Wi-Fi honeypot access point running on your ESP8266. These changes are saved to the ESP's EEPROM and become persistent across ESP reboots.

### Actions

*   **Export Data:** Use the floating buttons at the bottom-right to export data:
    *   **High-Risk CSV:** Exports devices with high anomaly scores or deauth counts.
    *   **Recent JSON:** Exports devices seen in the last hour.
    *   **Cleanup Logs:** Prunes old log entries and inactive devices from the database.
*   **Ban Device:** Click "Ban" next to a device in the table to add its MAC address to a blacklist. Banned devices will automatically show a very high anomaly score.

---

## ⚙️ Configuration

The `sigvoid.conf` file (located in the project root) allows you to customize core settings:

```ini
# sigvoid.conf
ESP_PORT="/dev/ttyUSB0"  # Serial port connected to your ESP8266
ESP_BAUD=115200          # Baud rate for serial communication with ESP8266
SERVER_PORT=8000         # Port for the FastAPI web server
VERBOSE=false            # Set to true for more detailed script output
```

You can also override `ESP_PORT`, `ESP_BAUD`, and `SERVER_PORT` directly when running `run.sh`:

```bash
./run.sh --port /dev/ttyACM0 --baud 57600 --server-port 5000 --verbose
```

---

## 📂 Project Structure

```
SigVoid/
├── backend/
│   ├── database/
│   │   ├── database.py       # Manages SQLite DB connection and schema
│   │   └── oui.db            # OUI database for vendor lookups (generated on first run)
│   ├── alerts.py             # Handles alert generation (file logging, audio)
│   ├── analyzer.py           # Core logic for anomaly detection and scoring
│   ├── cleanup.py            # Database cleanup and blacklist pruning
│   ├── exporter.py           # Data export (CSV/JSON) and ban list management
│   ├── main.py               # FastAPI application entry point, WebSockets, API endpoints
│   ├── serial_reader.py      # Handles serial communication with ESP8266
│   └── __init__.py           # Makes 'backend' a Python package
├── frontend/
│   ├── static/
│   │   ├── alpine.min.js     # Alpine.js library
│   │   ├── chart.min.js      # Chart.js library for visualizations
│   │   ├── dashboard.js      # Frontend logic, WebSocket handling, Chart updates, D&D
│   │   ├── input.css         # TailwindCSS input file with custom styles and variables
│   │   ├── interact.min.js   # Interact.js library for drag-and-drop
│   │   ├── manifest.json     # Web App Manifest for PWA support
│   │   ├── socket.io.min.js  # Socket.IO client library
│   │   ├── styles.css        # COMPILED TailwindCSS output (DO NOT EDIT DIRECTLY)
│   │   └── sw.js             # Service Worker for PWA caching and notifications
│   └── templates/
│       └── index.html        # Main dashboard HTML template
├── .github/                  # GitHub Actions workflows
│   └── workflows/
│       └── ci.yml            # Example CI workflow
├── alert.wav                 # Audio file for alerts
├── alerts.log                # Log file for suspicious device alerts
├── README.markdown           # This README file
├── rogue_ap.ino              # ESP8266 Arduino firmware sketch
├── run.sh                    # Main setup, installation, and launch script
├── schema.sql                # SQL schema definition (for reference)
├── server.log                # FastAPI server logs
├── sigvoid.conf              # Configuration file for `run.sh`
└── sigvoid.log               # Log file for `run.sh` execution
```

---

## 🤝 Contributing

Contributions are welcome! If you have suggestions for improvements, new features, or bug fixes, feel free to open an issue or submit a pull request.

---

## 📄 License

This project is licensed under the MIT License - see the `LICENSE` file (if you create one, otherwise add the MIT license text directly here) for details.

---

## 🙏 Credits

Made with passion by AsHfIEXE.
