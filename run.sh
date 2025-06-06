#!/bin/bash

# Colors for Cyberacore aesthetic
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Config file
CONFIG_FILE="sigvoid.conf"
LOG_FILE="sigvoid.log"
SERVER_LOG="server.log"

# Default config values
DEFAULT_PORT="/dev/ttyUSB0"
DEFAULT_BAUD=115200
DEFAULT_SERVER_PORT=8000

# Load or create config
if [ -f "$CONFIG_FILE" ]; then
    source "$CONFIG_FILE"
else
    cat << EOF > "$CONFIG_FILE"
ESP_PORT="$DEFAULT_PORT"
ESP_BAUD=$DEFAULT_BAUD
SERVER_PORT=$DEFAULT_SERVER_PORT
VERBOSE=false
EOF
    source "$CONFIG_FILE"
fi

# Progress bar function
progress_bar() {
    local duration=$1
    local width=50
    local filled=0
    local empty=$((width - filled))
    for ((i=0; i<=duration; i++)); do
        filled=$((i * width / duration))
        empty=$((width - filled))
        printf "\r${CYAN}[%${filled}s%${empty}s] %d%%${NC}" "$(printf '#%.0s' $(seq 1 $filled))" "" $((i * 100 / duration))
        sleep 0.1
    done
    echo
}

# Log function
log() {
    local level=$1
    local msg=$2
    echo "$(date '+%Y-%m-%d %H:%M:%S') [$level] $msg" >> "$LOG_FILE"
    if [ "$VERBOSE" = true ] || [ "$level" != "DEBUG" ]; then
        case $level in
            ERROR) echo -e "${RED}[-] $msg${NC}" ;;
            WARN) echo -e "${YELLOW}[!] $msg${NC}" ;;
            INFO) echo -e "${GREEN}[+] $msg${NC}" ;;
            DEBUG) echo -e "${PURPLE}[*] $msg${NC}" ;;
        esac
    fi
}

# Dynamic ASCII banner
BANNERS=(
    "cat << 'EOF'
${GREEN}
███████╗██╗ ██████╗ ██╗   ██╗ ██████╗ ██╗██████╗ 
██╔════╝██║██╔════╝ ██║   ██║██╔═══██╗██║██╔══██╗
███████╗██║██║  ███╗██║   ██║██║   ██║██║██║  ██║
╚════██║██║██║   ██║╚██╗ ██╔╝██║   ██║██║██║  ██║
███████║██║╚██████╔╝ ╚████╔╝ ╚██████╔╝██║██████╔╝
╚══════╝╚═╝ ╚═════╝   ╚═══╝   ╚═════╝ ╚═╝╚═════╝ 
${CYAN}
  SigVoid - Cyberacore Wi-Fi Threat Monitor
  Made BY AsHfIEXE
${NC}
EOF"
    "cat << 'EOF'
${GREEN}
█───█ █───█ █───█ █───█ █───█ █───█ 
█───█ █───█ █───█ █───█ █───█ █───█ 
█─█─█ █─█─█ █─█─█ █─█─█ █─█─█ █─█─█ 
██─██ ██─██ ██─██ ██─██ ██─██ ██─██ 
█───█ █───█ █───█ █───█ █───█ █───█ 
${CYAN}
  SigVoid - Cyberacore Wi-Fi Threat Monitor
  Made BY AsHfIEXE
${NC}
EOF"
)
eval "${BANNERS[$RANDOM % ${#BANNERS[@]}]}"

# Help function
show_help() {
    echo -e "${CYAN}Usage: $0 [options]${NC}"
    echo -e "Launches SigVoid with diagnostics and dependency checks."
    echo -e "\nOptions:"
    echo -e "  --help        Display this help message and exit."
    echo -e "  --verbose     Enable verbose logging."
    echo -e "  --port <port> Override ESP8266 port (e.g., /dev/ttyUSB0)."
    echo -e "  --baud <rate> Override ESP8266 baud rate (e.g., 115200)."
    echo -e "  --server-port Override server port (e.g., 8000)."
    echo -e "\nExample:"
    echo -e "  ./run.sh --verbose --port /dev/ttyACM0 --baud 57600"
    exit 0
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --help) show_help ;;
        --verbose) VERBOSE=true; shift ;;
        --port) ESP_PORT="$2"; shift 2 ;;
        --baud) ESP_BAUD="$2"; shift 2 ;;
        --server-port) SERVER_PORT="$2"; shift 2 ;;
        *) echo -e "${RED}[-] Unknown option: $1${NC}"; show_help ;;
    esac
done

# Initialize log
echo -e "=== SigVoid Run Log ===" > "$LOG_FILE"
log INFO "Starting SigVoid at $(date)"

# System diagnostics
log INFO "Running system diagnostics"
echo -e "${YELLOW}[*] System Diagnostics:${NC}"
# Fix CPU usage parsing for cross-platform compatibility
CPU_USAGE=$(top -bn1 | grep -E "Cpu(s)|%Cpu" | head -n 1 | awk '{for(i=1;i<=NF;i++) if($i ~ /^[0-9]/) {print $i; exit}}' | sed 's/[^0-9.]//g')
echo -e "  CPU Usage: ${CPU_USAGE:-N/A}%"
echo -e "  Memory Free: $(free -h | grep Mem | awk '{print $4}')"
echo -e "  Disk Free: $(df -h . | tail -n 1 | awk '{print $4}')"
# Enhanced network check with fallback
NETWORK_STATUS=$(ping -c 1 8.8.8.8 >/dev/null 2>&1 && echo 'Online' || echo 'Offline')
if [ "$NETWORK_STATUS" = "Offline" ]; then
    log WARN "Network is offline"
    echo -e "  Network: Offline"
    echo -e "${YELLOW}[!] Network offline. Proceed without asset downloads? (y/n):${NC}"
    read -n 1 choice
    echo
    if [ "$choice" != "y" ]; then
        log ERROR "User aborted due to offline network"
        echo -e "${RED}[-] Exiting. Check network and retry.${NC}"
        exit 1
    fi
else
    log INFO "Network is online"
    echo -e "  Network: Online"
fi

# Install system dependencies
log INFO "Checking system dependencies"
echo -e "${YELLOW}[*] Installing system dependencies...${NC}"
sudo apt update -qq && sudo apt install -y curl python3 python3-venv nodejs npm alsa-utils >/dev/null 2>&1 &
progress_bar 10
if [ $? -eq 0 ]; then
    log INFO "System dependencies installed"
    echo -e "${GREEN}[+] System dependencies installed.${NC}"
else
    log ERROR "Failed to install system dependencies"
    echo -e "${RED}[-] Failed to install system dependencies. Check sudo privileges.${NC}"
    exit 1
fi
npm install -g tailwindcss >/dev/null 2>&1 || { log ERROR "Failed to install TailwindCSS"; echo -e "${RED}[-] Failed to install TailwindCSS.${NC}"; exit 1; }

# Setup virtual environment
log INFO "Setting up virtual environment"
echo -e "${YELLOW}[*] Setting up virtual environment...${NC}"
if [ -d "venv" ]; then
    source venv/bin/activate
    log INFO "Virtual environment activated"
    echo -e "${GREEN}[+] Virtual environment activated.${NC}"
else
    python3 -m venv venv
    source venv/bin/activate
    log INFO "Virtual environment created and activated"
    echo -e "${GREEN}[+] Virtual environment created and activated.${NC}"
fi

# Install Python dependencies
log INFO "Checking Python dependencies"
echo -e "${YELLOW}[*] Checking Python dependencies...${NC}"
pip install --quiet fastapi uvicorn pyserial aiohttp pandas &
progress_bar 5
if [ $? -eq 0 ]; then
    log INFO "Python dependencies installed"
    echo -e "${GREEN}[+] Python dependencies installed.${NC}"
else
    log ERROR "Failed to install Python dependencies"
    echo -e "${RED}[-] Failed to install Python dependencies. Check pip and internet connection.${NC}"
    exit 1
fi

# Auto-detect ESP8266 port
log INFO "Detecting ESP8266 port"
echo -e "${YELLOW}[*] Detecting ESP8266 port...${NC}"
if [ -z "$ESP_PORT" ] || [ ! -e "$ESP_PORT" ]; then
    for p in /dev/ttyUSB* /dev/ttyACM*; do
        if [ -e "$p" ]; then
            ESP_PORT="$p"
            break
        fi
    done
fi

# Retry logic with interactive prompt
if [ -z "$ESP_PORT" ] || [ ! -e "$ESP_PORT" ]; then
    log WARN "No ESP8266 port found, retrying"
    echo -e "${YELLOW}[*] No ESP8266 port found. Retrying in 5 seconds...${NC}"
    sleep 5
    for p in /dev/ttyUSB* /dev/ttyACM*; do
        if [ -e "$p" ]; then
            ESP_PORT="$p"
            break
        fi
    done
    if [ -z "$ESP_PORT" ] || [ ! -e "$ESP_PORT" ]; then
        log ERROR "No ESP8266 port found"
        echo -e "${RED}[-] No ESP8266 port found. Available ports:${NC}"
        ls /dev/tty* 2>/dev/null || echo "None"
        read -p "Enter port (e.g., /dev/ttyUSB0) or press Enter to exit: " user_port
        if [ -n "$user_port" ] && [ -e "$user_port" ]; then
            ESP_PORT="$user_port"
        else
            log ERROR "User aborted or invalid port"
            echo -e "${RED}[-] Exiting. Connect ESP8266 and retry.${NC}"
            exit 1
        fi
    fi
fi
log INFO "ESP8266 detected at $ESP_PORT"
echo -e "${GREEN}[+] ESP8266 detected at $ESP_PORT.${NC}"

# Validate ESP8266 firmware
log INFO "Validating ESP8266 firmware"
echo -e "${YELLOW}[*] Validating ESP8266 firmware...${NC}"
for baud in $ESP_BAUD 57600 9600; do
    stty -F "$ESP_PORT" $baud >/dev/null 2>&1
    timeout 3 cat "$ESP_PORT" | grep -q '{"type":"diagnostics"' && break
done
if [ $? -eq 0 ]; then
    log INFO "ESP8266 firmware validated"
    echo -e "${GREEN}[+] ESP8266 firmware validated.${NC}"
else
    log WARN "ESP8266 firmware not responding"
    echo -e "${YELLOW}[!] Warning: ESP8266 not responding. Flash rogue_ap.ino and retry.${NC}"
fi

# Check audio alert
log INFO "Checking audio alert"
echo -e "${YELLOW}[*] Checking audio alert...${NC}"
if [ ! -f "alert.wav" ]; then
    log WARN "alert.wav not found"
    if [ "$NETWORK_STATUS" = "Online" ]; then
        echo -e "${YELLOW}[!] Warning: alert.wav not found. Download? (y/n):${NC}"
        read -n 1 choice
        echo
        if [ "$choice" = "y" ]; then
            curl -s -o alert.wav https://freesound.org/data/previews/254/254774_4590445-lq.wav
            if [ $? -eq 0 ]; then
                log INFO "alert.wav downloaded"
                echo -e "${GREEN}[+] alert.wav downloaded.${NC}"
            else
                log WARN "Failed to download alert.wav"
                echo -e "${YELLOW}[!] Failed to download alert.wav. Audio alerts disabled.${NC}"
            fi
        else
            log WARN "Audio alerts disabled"
            echo -e "${YELLOW}[!] Audio alerts disabled.${NC}"
        fi
    else
        log WARN "Audio alerts disabled due to offline network"
        echo -e "${YELLOW}[!] Audio alerts disabled due to offline network.${NC}"
    fi
else
    log INFO "Audio alert file found"
    echo -e "${GREEN}[+] Audio alert file found.${NC}"
fi

# Check PWA icon
log INFO "Checking PWA icon"
echo -e "${YELLOW}[*] Checking PWA icon...${NC}"
if [ ! -f "frontend/static/icon.png" ]; then
    log WARN "icon.png not found"
    echo -e "${YELLOW}[!] Warning: icon.png not found. PWA icon missing.${NC}"
else
    log INFO "PWA icon found"
    echo -e "${GREEN}[+] PWA icon found.${NC}"
fi

# Check frontend assets in parallel
log INFO "Checking frontend assets"
echo -e "${YELLOW}[*] Checking frontend assets...${NC}"
ASSETS=(
    "chart.min.js:https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.min.js"
    "alpine.min.js:https://cdn.jsdelivr.net/npm/alpinejs@3.14.1/dist/cdn.min.js"
    "socket.io.min.js:https://cdn.jsdelivr.net/npm/socket.io-client@4.7.5/dist/socket.io.min.js"
    "interact.min.js:https://cdn.jsdelivr.net/npm/interactjs@1.10.11/dist/interact.min.js"
)
pids=()
if [ "$NETWORK_STATUS" = "Online" ]; then
    for asset in "${ASSETS[@]}"; do
        IFS=':' read -r file url <<< "$asset"
        if [ ! -f "frontend/static/$file" ]; then
            log DEBUG "Downloading $file"
            echo -e "${YELLOW}[*] Downloading $file...${NC}"
            curl -s -o "frontend/static/$file" "$url" &
            pids+=($!)
        else
            log INFO "$file found"
            echo -e "${GREEN}[+] $file found.${NC}"
        fi
    done
    for pid in "${pids[@]}"; do
        wait $pid
        if [ $? -eq 0 ]; then
            log INFO "Asset download completed"
        else
            log WARN "Failed to download an asset"
            echo -e "${YELLOW}[!] Failed to download an asset. PWA functionality may be limited.${NC}"
        fi
    done
else
    log WARN "Skipping asset downloads due to offline network"
    echo -e "${YELLOW}[!] Skipping asset downloads due to offline network.${NC}"
    for asset in "${ASSETS[@]}"; do
        IFS=':' read -r file url <<< "$asset"
        if [ ! -f "frontend/static/$file" ]; then
            log ERROR "$file missing and cannot download offline"
            echo -e "${RED}[-] $file missing. PWA functionality disabled. Download manually or connect to network.${NC}"
            exit 1
        fi
    done
fi

# Check TailwindCSS build
log INFO "Checking TailwindCSS build"
echo -e "${YELLOW}[*] Checking TailwindCSS build...${NC}"
if [ ! -f "frontend/static/styles.css" ]; then
    log INFO "Building TailwindCSS"
    echo -e "${YELLOW}[*] Building TailwindCSS...${NC}"
    npx tailwindcss -i input.css -o frontend/static/styles.css --minify &
    progress_bar 3
    if [ $? -eq 0 ]; then
        log INFO "TailwindCSS built successfully"
        echo -e "${GREEN}[+] TailwindCSS built successfully.${NC}"
    else
        log ERROR "Failed to build TailwindCSS"
        echo -e "${RED}[-] Failed to build TailwindCSS. Install Node.js and run 'npm install tailwindcss'.${NC}"
        exit 1
    fi
else
    log INFO "TailwindCSS styles found"
    echo -e "${GREEN}[+] TailwindCSS styles found.${NC}"
fi

# Rotate logs
log INFO "Rotating logs"
if [ -f "$SERVER_LOG" ]; then
    mv "$SERVER_LOG" "${SERVER_LOG}.$(date +%F_%T)"
    log INFO "Server log rotated"
fi
if [ -f "alerts.log" ] && [ $(stat -c %s alerts.log) -gt 1048576 ]; then
    mv alerts.log "alerts.log.$(date +%F_%T)"
    log INFO "Alerts log rotated"
fi

# Start FastAPI server
log INFO "Starting SigVoid server"
echo -e "${YELLOW}[*] Starting SigVoid server...${NC}"
timeout 10s uvicorn backend.main:app --host 0.0.0.0 --port "$SERVER_PORT" > "$SERVER_LOG" 2>&1 &
SERVER_PID=$!
sleep 2
if ps -p $SERVER_PID > /dev/null; then
    log INFO "SigVoid running at http://localhost:$SERVER_PORT"
    echo -e "${GREEN}[+] SigVoid running at http://localhost:$SERVER_PORT${NC}"
    echo -e "${CYAN}[i] Press Ctrl+C to stop the server gracefully.${NC}"
else
    log ERROR "Failed to start server"
    echo -e "${RED}[-] Failed to start server. Check $SERVER_LOG for details:${NC}"
    cat "$SERVER_LOG"
    exit 1
fi

# Trap Ctrl+C for graceful shutdown
trap 'log INFO "Stopping server"; echo -e "${YELLOW}[*] Stopping server...${NC}"; kill $SERVER_PID; wait $SERVER_PID 2>/dev/null; echo -e "${GREEN}[+] Server stopped.${NC}"; exit 0' INT

# Keep script running
wait