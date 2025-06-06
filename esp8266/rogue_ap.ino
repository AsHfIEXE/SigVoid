#include <ESP8266WiFi.h>
#include "esp_wifi.h"

const char* apSSID = "FreeWiFi_Honeypot";
const char* apPassword = "";
const int ledPin = D4; // Onboard LED for alerts
uint8_t busyChannels[3] = {1, 6, 11}; // Dynamic channel selection
int channelProbes[13] = {0}; // Track probe counts per channel

void setup() {
  pinMode(ledPin, OUTPUT);
  digitalWrite(ledPin, HIGH); // LED off
  Serial.begin(115200);
  delay(500);

  // Initialize rogue AP
  WiFi.mode(WIFI_AP_STA);
  if (!WiFi.softAP(apSSID, apPassword)) {
    Serial.println("{\"error\":\"AP setup failed\"}");
    ESP.restart();
  }

  // Enable promiscuous mode
  wifi_set_opmode(STATION_MODE);
  wifi_set_promiscuous_rx_cb(promisc_cb);
  wifi_promiscuous_enable(1);

  // Initial diagnostics
  Serial.printf("{\"type\":\"diagnostics\",\"free_heap\":%u,\"uptime\":%lu}\n", ESP.getFreeHeap(), millis());
}

void promisc_cb(uint8_t *buf, uint16_t len) {
  if (len < 28) return;

  uint8_t frame_type = buf[0];
  uint8_t* src_mac = &buf[10];
  int rssi = buf[len-4];
  int channel = wifi_get_channel();
  unsigned long timestamp = millis();

  // Update channel probe count
  if (frame_type == 0x40 && channel >= 1 && channel <= 13) {
    channelProbes[channel-1]++;
  }

  if (frame_type == 0x40) { // Probe request
    char ssid[33] = {0};
    int ssid_len = buf[25];
    if (ssid_len > 0 && ssid_len <= 32) {
      memcpy(ssid, &buf[26], ssid_len);
    }
    uint8_t* bssid = &buf[16];
    Serial.printf("{\"type\":\"probe\",\"mac\":\"%02X:%02X:%02X:%02X:%02X:%02X\",\"bssid\":\"%02X:%02X:%02X:%02X:%02X:%02X\",\"ssid\":\"%s\",\"rssi\":%d,\"channel\":%d,\"timestamp\":%lu}\n",
                  src_mac[0], src_mac[1], src_mac[2], src_mac[3], src_mac[4], src_mac[5],
                  bssid[0], bssid[1], bssid[2], bssid[3], bssid[4], bssid[5], ssid, rssi, channel, timestamp);
  } else if (frame_type == 0x0C) { // Deauth frame
    digitalWrite(ledPin, LOW); // Blink LED
    delay(50);
    digitalWrite(ledPin, HIGH);
    Serial.printf("{\"type\":\"deauth\",\"mac\":\"%02X:%02X:%02X:%02X:%02X:%02X\",\"timestamp\":%lu}\n",
                  src_mac[0], src_mac[1], src_mac[2], src_mac[3], src_mac[4], src_mac[5], timestamp);
  }
}

void loop() {
  // Dynamic channel selection
  static unsigned long last_switch = 0;
  if (millis() - last_switch > 5000) { // Update channels every 5s
    update_busy_channels();
    last_switch = millis();
  }

  static int channel_idx = 0;
  wifi_set_channel(busyChannels[channel_idx]);
  channel_idx = (channel_idx + 1) % 3;
  delay(100);

  // Periodic diagnostics
  static unsigned long last_diag = 0;
  if (millis() - last_diag > 30000) { // Every 30s
    Serial.printf("{\"type\":\"diagnostics\",\"free_heap\":%u,\"uptime\":%lu}\n", ESP.getFreeHeap(), millis());
    last_diag = millis();
  }
}

void update_busy_channels() {
  // Sort channels by probe count
  int top_channels[13];
  for (int i = 0; i < 13; i++) top_channels[i] = i + 1;
  for (int i = 0; i < 12; i++) {
    for (int j = i + 1; j < 13; j++) {
      if (channelProbes[top_channels[i]-1] < channelProbes[top_channels[j]-1]) {
        int temp = top_channels[i];
        top_channels[i] = top_channels[j];
        top_channels[j] = temp;
      }
    }
  }
  for (int i = 0; i < 3; i++) busyChannels[i] = top_channels[i];
}