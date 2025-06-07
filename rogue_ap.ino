// rogue_ap.ino
#include <ESP8266WiFi.h>
#include <EEPROM.h>
#include "esp_wifi.h"

// EEPROM addresses for settings
#define SSID_ADDR 0
#define PASS_ADDR 33 // Max SSID length 32 + 1 for null terminator
// Max password length 64 + 1 for null terminator. EEPROM.begin(128) should be enough.
// SETTINGS_FLAG_ADDR is implicitly handled by checking if SSID[0] is 0xFF

const int ledPin = D4; // Onboard LED for alerts (usually GPIO2 on NodeMCU)
uint8_t busyChannels[3] = {1, 6, 11}; // Dynamic channel selection
int channelProbes[13] = {0}; // Track probe counts per channel

// Use non-const char arrays so they can be modified
char apSSID[33] = "SigVoid_Honeypot"; // Default SSID
char apPassword[65] = "";            // Default Password (empty for open)

void setup() {
  pinMode(ledPin, OUTPUT);
  digitalWrite(ledPin, HIGH); // LED off (HIGH is off for onboard LED on NodeMCU)
  Serial.begin(115200);
  delay(500);

  // Initialize EEPROM with enough space for SSID and Password
  // SSID (33 bytes) + PASS (65 bytes) = 98 bytes. Let's use 128 bytes for margin.
  EEPROM.begin(128); 

  // Load settings from EEPROM
  loadSettings();

  // Initialize rogue AP
  WiFi.mode(WIFI_AP_STA);
  // Ensure softAP starts with current loaded settings
  if (!WiFi.softAP(apSSID, apPassword)) {
    Serial.println("{\"type\":\"error\",\"message\":\"AP setup failed, restarting ESP\"}");
    delay(100);
    ESP.restart(); // Restart if AP setup fails
  } else {
    Serial.printf("{\"type\":\"info\",\"message\":\"AP '%s' started on %s\"}\n", apSSID, WiFi.softAPIP().toString().c_str());
  }

  // Enable promiscuous mode
  wifi_set_opmode(STATION_MODE); // Ensure station mode is also active
  wifi_set_promiscuous_rx_cb(promisc_cb);
  wifi_promiscuous_enable(1);

  // Initial diagnostics
  Serial.printf("{\"type\":\"diagnostics\",\"free_heap\":%u,\"uptime\":%lu}\n", ESP.getFreeHeap(), millis());
}

void promisc_cb(uint8_t *buf, uint16_t len) {
  if (len < 28) return; // Minimum length for basic frame info + RSSI

  uint8_t frame_type = buf[0];
  uint8_t* src_mac = &buf[10]; // Source MAC is at byte 10 for most frames
  int rssi = buf[len-4];       // RSSI is typically 4 bytes from end
  int channel = wifi_get_channel();
  unsigned long timestamp = millis();

  // Update channel probe count for management frames (type 0)
  if ((frame_type & 0xF0) == 0x40 && channel >= 1 && channel <= 13) { // Probe request (0x40)
    channelProbes[channel-1]++;
  }

  if ((frame_type & 0xF0) == 0x40) { // Probe request (0x40 for type 0, subtype 4)
    char ssid[33] = {0}; // Max 32 chars + null terminator
    int ssid_len = buf[25]; // SSID length field is at byte 25
    if (ssid_len > 0 && ssid_len <= 32) {
      memcpy(ssid, &buf[26], ssid_len); // SSID data starts at byte 26
    }
    ssid[ssid_len] = '\0'; // Null-terminate string
    
    uint8_t* bssid = &buf[16]; // BSSID for probe requests is usually at byte 16 (TA)
    Serial.printf("{\"type\":\"probe\",\"mac\":\"%02X:%02X:%02X:%02X:%02X:%02X\",\"bssid\":\"%02X:%02X:%02X:%02X:%02X:%02X\",\"ssid\":\"%s\",\"rssi\":%d,\"channel\":%d,\"timestamp\":%lu}\n",
                  src_mac[0], src_mac[1], src_mac[2], src_mac[3], src_mac[4], src_mac[5],
                  bssid[0], bssid[1], bssid[2], bssid[3], bssid[4], bssid[5], ssid, rssi, channel, timestamp);
  } else if ((frame_type & 0xFC) == 0xA0) { // Deauth/Disassoc frame (Type 0, Subtype 0xA or 0xC)
    digitalWrite(ledPin, LOW); // Blink LED (LOW is ON for NodeMCU onboard LED)
    delay(50);
    digitalWrite(ledPin, HIGH); // LED off
    Serial.printf("{\"type\":\"deauth\",\"mac\":\"%02X:%02X:%02X:%02X:%02X:%02X\",\"timestamp\":%lu}\n",
                  src_mac[0], src_mac[1], src_mac[2], src_mac[3], src_mac[4], src_mac[5], timestamp);
  }
}

void loop() {
  handleSerialCommands();

  // Dynamic channel selection
  static unsigned long last_channel_switch = 0;
  if (millis() - last_channel_switch > 5000) { // Update channels every 5s
    update_busy_channels();
    last_channel_switch = millis();
  }

  static int channel_idx = 0;
  // Make sure to only set channels from 1 to 13
  uint8_t target_channel = busyChannels[channel_idx];
  if (target_channel < 1 || target_channel > 13) {
      target_channel = 1; // Fallback to channel 1 if invalid
  }
  wifi_set_channel(target_channel);
  channel_idx = (channel_idx + 1) % 3; // Cycle through top 3 busy channels
  delay(100);

  // Periodic diagnostics
  static unsigned long last_diag = 0;
  if (millis() - last_diag > 30000) { // Every 30s
    Serial.printf("{\"type\":\"diagnostics\",\"free_heap\":%u,\"uptime\":%lu}\n", ESP.getFreeHeap(), millis());
    last_diag = millis();
  }
}

void update_busy_channels() {
  // Reset counts after a period (e.g., every minute) to avoid stale data
  static unsigned long last_reset = 0;
  if (millis() - last_reset > 60000) { // Reset counts every 60s
    for (int i = 0; i < 13; i++) {
      channelProbes[i] = 0;
    }
    last_reset = millis();
  }

  // Sort channels by probe count (bubble sort for simplicity, 13 elements is small)
  int temp_channels[13];
  for (int i = 0; i < 13; i++) temp_channels[i] = i + 1; // 1-13
  
  for (int i = 0; i < 12; i++) {
    for (int j = i + 1; j < 13; j++) {
      if (channelProbes[temp_channels[i]-1] < channelProbes[temp_channels[j]-1]) {
        int temp = temp_channels[i];
        temp_channels[i] = temp_channels[j];
        temp_channels[j] = temp;
      }
    }
  }
  // Assign top 3 busiest channels
  for (int i = 0; i < 3; i++) {
      busyChannels[i] = temp_channels[i];
      if (busyChannels[i] == 0) busyChannels[i] = 1; // Fallback for uninitialized/zero counts
  }
}

void handleSerialCommands() {
  if (Serial.available()) {
    String command = Serial.readStringUntil('\n');
    command.trim(); // Remove leading/trailing whitespace

    if (command.startsWith("SET_AP_SSID:")) {
      String newSSID = command.substring(12); // "SET_AP_SSID:".length()
      if (newSSID.length() <= 32) {
        newSSID.toCharArray(apSSID, sizeof(apSSID));
        saveSettings();
        applyAPSettings(); // Apply new settings immediately
        Serial.printf("{\"type\":\"info\",\"message\":\"AP SSID set to '%s'\"}\n", apSSID);
      } else {
        Serial.println("{\"type\":\"error\",\"message\":\"SSID too long (max 32 chars)\"}");
      }
    } else if (command.startsWith("SET_AP_PASS:")) {
      String newPass = command.substring(12); // "SET_AP_PASS:".length()
      if (newPass.length() <= 64) {
        newPass.toCharArray(apPassword, sizeof(apPassword));
        saveSettings();
        applyAPSettings(); // Apply new settings immediately
        Serial.printf("{\"type\":\"info\",\"message\":\"AP password updated\"}\n");
      } else {
        Serial.println("{\"type\":\"error\",\"message\":\"Password too long (max 64 chars)\"}");
      }
    } else {
      // Echo unrecognized command for debugging
      Serial.printf("{\"type\":\"info\",\"message\":\"Unrecognized command: %s\"}\n", command.c_str());
    }
  }
}

void loadSettings() {
  char temp_ssid_char;
  EEPROM.get(SSID_ADDR, temp_ssid_char); // Read first char of SSID to check if EEPROM is initialized

  if (temp_ssid_char == 0xFF) { // If EEPROM is erased (all FF), use defaults
    Serial.println("{\"type\":\"info\",\"message\":\"No saved AP settings found, using defaults.\"}");
    // Defaults are already set at global variable declaration
    saveSettings(); // Save defaults so they exist in EEPROM
  } else {
    EEPROM.get(SSID_ADDR, apSSID);
    EEPROM.get(PASS_ADDR, apPassword);
    // Ensure null termination in case of partial writes/reads
    apSSID[sizeof(apSSID) - 1] = '\0';
    apPassword[sizeof(apPassword) - 1] = '\0';
    Serial.println("{\"type\":\"info\",\"message\":\"Loaded AP settings from EEPROM.\"}");
  }
}

void saveSettings() {
  EEPROM.put(SSID_ADDR, apSSID);
  EEPROM.put(PASS_ADDR, apPassword);
  EEPROM.commit(); // Commit changes to EEPROM
  Serial.println("{\"type\":\"info\",\"message\":\"AP settings saved to EEPROM.\"}");
}

void applyAPSettings() {
  // Re-initialize SoftAP with new settings
  WiFi.softAPdisconnect(true); // Disconnect existing AP
  delay(100);
  if (!WiFi.softAP(apSSID, apPassword)) {
    Serial.println("{\"type\":\"error\",\"message\":\"Failed to re-apply AP settings, restarting ESP\"}");
    delay(100);
    ESP.restart();
  }
}